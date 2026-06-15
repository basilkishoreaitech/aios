import logging
import asyncio
import random
from openai import AsyncAzureOpenAI
from openai import RateLimitError, APITimeoutError, APIConnectionError, OpenAIError
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Type, Union
from config import Settings

logger = logging.getLogger(__name__)


def _is_live_model_configuration(config: Settings) -> bool:
    return bool(config.AZURE_OPENAI_API_KEY and config.AZURE_OPENAI_ENDPOINT)

class ModelRouter:
    """Routing mechanism to manage model selections, usage statistics, and failover/fallbacks."""
    
    def __init__(self, config: Settings):
        self.config = config
        
        if _is_live_model_configuration(config):
            self.client = AsyncAzureOpenAI(
                api_key=config.AZURE_OPENAI_API_KEY,
                azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
                api_version=config.AZURE_OPENAI_API_VERSION
            )
            self.enabled = True
        else:
            raise ValueError("Azure OpenAI configuration is incomplete. Set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT.")
            
        self.models = {
            "primary": config.AZURE_OPENAI_DEPLOYMENT_PRIMARY,
            "fallback": config.AZURE_OPENAI_DEPLOYMENT_FALLBACK,
            "utility": config.AZURE_OPENAI_DEPLOYMENT_UTILITY,
            "critic": config.AZURE_OPENAI_DEPLOYMENT_CRITIC,
        }
        
        # Track statistics
        self.last_model_used: str = ""
        self.last_tokens_used: int = 0
        self.total_tokens_used: int = 0
        self._semaphore = asyncio.Semaphore(max(1, config.AZURE_OPENAI_MAX_CONCURRENT_REQUESTS))
        self._cooldowns: Dict[str, float] = {}

    async def _wait_for_cooldown(self, model_name: str) -> None:
        cooldown_until = self._cooldowns.get(model_name, 0.0)
        remaining = cooldown_until - asyncio.get_running_loop().time()
        if remaining > 0:
            logger.info("Model %s cooling down for %.2fs before next call.", model_name, remaining)
            await asyncio.sleep(remaining)

    def _get_retry_after_seconds(self, error: RateLimitError) -> Optional[float]:
        response = getattr(error, "response", None)
        headers = getattr(response, "headers", None)
        if not isinstance(headers, dict):
            return None

        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        if retry_after is None:
            return None

        try:
            return max(1.0, min(60.0, float(retry_after)))
        except (TypeError, ValueError):
            return None

    def _set_cooldown(self, model_name: str, wait_seconds: float) -> None:
        loop_time = asyncio.get_running_loop().time()
        self._cooldowns[model_name] = max(self._cooldowns.get(model_name, 0.0), loop_time + wait_seconds)

    async def call_with_fallback(
        self,
        messages: List[Dict[str, Any]],
        response_format: Optional[Type[BaseModel]] = None,
        preferred: str = "primary",
        fallback: str = "fallback"
    ) -> Union[BaseModel, str]:
        """Calls the preferred deployment with automatic fallback if rate limited or timed out."""
        
        if not self.enabled:
            raise ValueError("ModelRouter is not initialized with a live Azure OpenAI client.")

        # Try the preferred model first, then the fallback model
        for model_key in [preferred, fallback]:
            last_exc = None
            last_wait = 0.0
            for attempt in range(3):  # up to 3 retries with backoff
              try:
                model_name = self.models.get(model_key, self.models["fallback"])
                await self._wait_for_cooldown(model_name)
                logger.info(f"Attempting LLM call using model key: {model_key} (Deployment: {model_name}), attempt {attempt+1}")

                async with self._semaphore:
                    if response_format:
                        response = await self.client.beta.chat.completions.parse(
                            model=model_name,
                            messages=messages,
                            response_format=response_format,
                            timeout=60.0
                        )
                        parsed_result = response.choices[0].message.parsed
                        self.last_model_used = model_name
                        self.last_tokens_used = response.usage.total_tokens if response.usage else 0
                        self.total_tokens_used += self.last_tokens_used
                        return parsed_result
                    else:
                        response = await self.client.chat.completions.create(
                            model=model_name,
                            messages=messages,
                            timeout=60.0
                        )
                        content = response.choices[0].message.content or ""
                        self.last_model_used = model_name
                        self.last_tokens_used = response.usage.total_tokens if response.usage else 0
                        self.total_tokens_used += self.last_tokens_used
                        return content

              except RateLimitError as e:
                wait = self._get_retry_after_seconds(e) or min(30.0, (2 ** attempt) + random.uniform(0.25, 0.75))
                last_wait = wait
                self._set_cooldown(model_name, wait)
                logger.warning(f"Rate limited on {model_key} attempt {attempt+1}. Waiting {wait}s before retry.")
                last_exc = e
                if attempt < 2:
                    await asyncio.sleep(wait)
                    continue
                break  # exhausted retries → fall through to next model_key
              except (APITimeoutError, APIConnectionError) as e:
                logger.warning(f"Deployment {model_key} failed due to timeout/connection: {e}. Trying next fallback...")
                last_exc = e
                break
              except OpenAIError as e:
                logger.error(f"OpenAI API Error under model key {model_key}: {e}")
                last_exc = e
                break
              except Exception as e:
                logger.error(f"Unexpected error in ModelRouter call for model key {model_key}: {e}")
                last_exc = e
                break

            # Wait before switching to the next model key to let rate limits settle
            if model_key != fallback and isinstance(last_exc, RateLimitError):
                switch_wait = max(float(self.config.AZURE_OPENAI_FALLBACK_COOLDOWN_SECONDS), last_wait)
                logger.info("Waiting %.2fs before trying fallback model due to rate limiting.", switch_wait)
                await asyncio.sleep(switch_wait)

            if model_key == fallback and last_exc is not None:
                raise last_exc
