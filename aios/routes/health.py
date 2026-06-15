import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database import get_db
from config import settings

logger = logging.getLogger("aios.routes.health")
router = APIRouter()

@router.get("/health")
async def liveness_check():
    """Liveness probe. Return HTTP 200 immediately to verify application process is running."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }

@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness probe. Check database connectivity and credentials configurations."""
    checks = {
        "database": False,
        "openai_api": False,
        "embedding_model": False,
        "foundry_iq": False,
        "bing_search": False,
    }
    required_checks = ["database", "openai_api", "embedding_model", "foundry_iq"]
    optional_checks = []
    
    # 1. Check database connection
    try:
        await db.execute(select(1))
        checks["database"] = True
    except Exception as e:
        logger.error(f"Readiness DB probe failed: {e}")
        
    # 2. Check OpenAI model availability configurations
    if settings.AZURE_OPENAI_API_KEY and settings.AZURE_OPENAI_ENDPOINT:
        checks["openai_api"] = True
        checks["embedding_model"] = True

    # 3. Check Azure AI Search / Foundry IQ configuration
    if settings.FOUNDRY_IQ_ENDPOINT and settings.FOUNDRY_IQ_KEY and settings.FOUNDRY_IQ_INDEX_NAME:
        checks["foundry_iq"] = True
            
    # 4. Check external web search configuration. Preserve the existing check name for compatibility.
    if settings.TAVILY_API_KEY or settings.BING_SEARCH_API_KEY:
        checks["bing_search"] = True
    elif settings.REQUIRE_LIVE_WEB_SEARCH:
        required_checks.append("bing_search")
    # else: key absent and not required — leave bing_search=False (accurate status; no LLM fallback note below)

    all_ready = all(checks[name] for name in required_checks)
    status_code = status.HTTP_200_OK if all_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    
    # Return details
    return {
        "ready": all_ready,
        "checks": checks,
        "required_checks": required_checks,
        "optional_checks": optional_checks,
    }
