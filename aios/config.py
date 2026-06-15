"""
AIOS configuration.
All settings come from environment variables / .env file.
The supported runtime path uses PostgreSQL for app state and Foundry IQ for retrieval.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- Azure OpenAI ---
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_DEPLOYMENT_PRIMARY: str = "gpt-5.4"
    AZURE_OPENAI_DEPLOYMENT_FALLBACK: str = "gpt-5.4-mini"
    AZURE_OPENAI_DEPLOYMENT_UTILITY: str = "gpt-5.4-mini"
    AZURE_OPENAI_DEPLOYMENT_CRITIC: str = "gpt-4.1"
    AZURE_OPENAI_DEPLOYMENT_EMBEDDING: str = "text-embedding-3-small"
    AZURE_OPENAI_API_VERSION: str = "2024-12-01-preview"
    AZURE_OPENAI_MAX_CONCURRENT_REQUESTS: int = 4
    AZURE_OPENAI_FALLBACK_COOLDOWN_SECONDS: int = 8

    # --- Web Search ---
    WEB_SEARCH_PROVIDER: str = "auto"
    TAVILY_API_KEY: str = ""
    TAVILY_SEARCH_ENDPOINT: str = "https://api.tavily.com/search"
    BING_SEARCH_API_KEY: str = ""
    BING_SEARCH_ENDPOINT: str = "https://api.bing.microsoft.com/v7.0/search"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/aios"

    # --- Knowledge Base ---
    KB_PROVIDER: str = "foundry_iq"
    KNOWLEDGE_DIR: str = "knowledge"
    FOUNDRY_IQ_ENDPOINT: str = ""
    FOUNDRY_IQ_KEY: str = ""
    FOUNDRY_IQ_API_VERSION: str = "2024-07-01"
    FOUNDRY_IQ_INDEX_NAME: str = ""

    # --- Integration Mode ---
    REQUIRE_LIVE_MODELS: bool = True
    REQUIRE_LIVE_WEB_SEARCH: bool = False
    ENABLE_SEED_SAMPLE_DATA: bool = False

    # --- Auth / JWT ---
    JWT_SECRET_KEY: str = "change-this-to-a-strong-random-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60

    # --- Teams ---
    TEAMS_WEBHOOK_URL: str = ""
    TEAMS_BOT_APP_ID: str = ""
    TEAMS_BOT_APP_SECRET: str = ""

    # --- Application ---
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"
    ALLOWED_ORIGIN: str = "http://localhost:8000"

    # --- Token Budgets (per-agent) ---
    TOKEN_BUDGET_PRIMARY: int = 8000
    TOKEN_BUDGET_UTILITY: int = 4000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    """Singleton settings instance — cached after first load."""
    return Settings()


settings = get_settings()
