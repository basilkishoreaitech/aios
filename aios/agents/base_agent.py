import time
import logging
from datetime import datetime, timezone
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings
from models.database import AgentTrace
from services.model_router import ModelRouter
from services.token_budget import TokenBudgetTracker

logger = logging.getLogger("aios.agents")

class BaseAgent:
    """Base SRE Agent providing unified lifecycle hooks, DB tracing, timing, and token budgeting."""
    
    def __init__(
        self,
        agent_name: str,
        config: Settings,
        model_router: ModelRouter,
        token_tracker: TokenBudgetTracker
    ):
        self.agent_name = agent_name
        self.config = config
        self.model_router = model_router
        self.token_tracker = token_tracker

    async def execute(self, session: AsyncSession, incident_id: str, *args, **kwargs) -> Any:
        """Wrapper method that sets up tracing, measures timing, checks budgets, and handles failures."""
        logger.info(f"🚀 Starting agent '{self.agent_name}' for incident {incident_id}")
        
        # Create trace record in running state
        args_str = ", ".join([str(a)[:200] for a in args])
        kwargs_str = ", ".join([f"{k}={str(v)[:200]}" for k, v in kwargs.items()])
        extra = f" | {kwargs_str}" if kwargs_str else ""
        extra = f"{args_str}{extra}" if args_str else extra.lstrip(" | ")
        input_sum = f"incident_id={incident_id}" + (f" | {extra}" if extra else "")
        input_sum = input_sum[:2000]
        
        trace = AgentTrace(
            incident_id=incident_id,
            agent_name=self.agent_name,
            status="running",
            started_at=datetime.now(timezone.utc),
            input_summary=input_sum
        )
        session.add(trace)
        await session.commit()
        
        start_time = time.perf_counter()
        
        try:
            # Run the actual agent logic
            result = await self._run(session, incident_id, *args, **kwargs)
            
            # Measure duration
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            
            # Get model usage details from model_router
            model_used = self.model_router.last_model_used
            tokens_used = self.model_router.last_tokens_used
            
            # Consume token budget
            self.token_tracker.consume(self.agent_name, tokens_used)
            
            # Update trace status
            trace.status = "completed"
            trace.duration_ms = duration_ms
            trace.model_used = model_used
            trace.tokens_used = tokens_used
            trace.output_summary = str(result)[:2000] # truncate summary for DB storage
            
            await session.commit()
            logger.info(f"✅ Agent '{self.agent_name}' completed in {duration_ms}ms using {tokens_used} tokens.")
            return result
            
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"❌ Agent '{self.agent_name}' failed: {e}", exc_info=True)
            
            # Update trace with failure info
            trace.status = "failed"
            trace.duration_ms = duration_ms
            trace.error_message = str(e)
            
            await session.commit()
            raise e

    async def _run(self, session: AsyncSession, incident_id: str, *args, **kwargs) -> Any:
        """The actual logic of the agent. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _run")
