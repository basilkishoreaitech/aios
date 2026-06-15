"""
AIOS — FastAPI Application Entry Point.
Lifespan: init DB → seed knowledge base → seed users → start.
Routes: auth, ingest, query, incidents, approve, retrospective, postmortem, topology, teams, health, knowledge.
"""

import logging
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure CWD is the directory containing main.py so relative paths work
_HERE = Path(__file__).parent.resolve()
os.chdir(_HERE)

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from config import settings
from database import init_db, async_session

# Rate limiter — keyed by IP address
limiter = Limiter(key_func=get_remote_address)
from models.database import User
from auth.rbac import SEED_USERS, hash_password
from sqlalchemy import select

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("aios")


async def seed_users():
    """Create default platform users if they don't exist (idempotent)."""
    async with async_session() as session:
        for user_data in SEED_USERS:
            result = await session.execute(
                select(User).where(User.username == user_data["username"])
            )
            if result.scalar_one_or_none() is None:
                user = User(
                    username=user_data["username"],
                    hashed_password=hash_password(user_data["password"]),
                    role=user_data["role"],
                    display_name=user_data["display_name"],
                )
                session.add(user)
                logger.info(f"  Seeded user: {user_data['username']} ({user_data['role']})")
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup & shutdown lifecycle."""
    logger.info("🚀 AIOS starting up...")

    # Ensure DB tables exist — no seeding, no file scanning.
    # Use `python seed.py` manually to (re)seed users / KB / topology when needed.
    from database import init_db
    try:
        await init_db()
    except Exception as exc:
        logger.warning(
            "⚠️  Database unavailable at startup (%s). "
            "DB-dependent features will return errors until PostgreSQL is reachable.",
            exc,
        )

    # Initialize and cache services/orchestrator in app.state
    from services.model_router import ModelRouter
    from services.embedding_service import EmbeddingService
    from services.web_search_service import WebSearchService
    from orchestrator.pipeline import IncidentPipeline

    app.state.model_router = ModelRouter(settings)
    app.state.embedding_service = EmbeddingService(settings)
    app.state.web_search_service = WebSearchService(settings)
    app.state.pipeline = IncidentPipeline(
        config=settings,
        model_router=app.state.model_router,
        embedding_service=app.state.embedding_service,
        web_search_service=app.state.web_search_service
    )

    logger.info("✅ AIOS started — all systems ready")
    yield
    logger.info("🛑 AIOS shutting down")


app = FastAPI(
    title="AIOS — Agentic Incident Operating System",
    description="AI Decision Intelligence for High-Stakes Operations",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "development" else [settings.ALLOWED_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Check server logs.",
        },
    )


# --- Register Routes ---
from routes.auth import router as auth_router
from routes.ingest import router as ingest_router
from routes.query import router as query_router
from routes.incidents import router as incidents_router
from routes.approve import router as approve_router
from routes.retrospective import router as retrospective_router
from routes.postmortem import router as postmortem_router
from routes.topology import router as topology_router
from routes.teams import router as teams_router
from routes.health import router as health_router
from routes.knowledge import router as knowledge_router

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(ingest_router, prefix="/api", tags=["ingest"])
app.include_router(query_router, prefix="/api", tags=["query"])
app.include_router(incidents_router, prefix="/api", tags=["incidents"])
app.include_router(approve_router, prefix="/api", tags=["actions"])
app.include_router(retrospective_router, prefix="/api", tags=["retrospective"])
app.include_router(postmortem_router, prefix="/api", tags=["postmortem"])
app.include_router(topology_router, prefix="/api", tags=["topology"])
app.include_router(teams_router, prefix="/api", tags=["teams"])
app.include_router(health_router, tags=["health"])
app.include_router(knowledge_router, prefix="/api", tags=["knowledge"])

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """Serve the Reasoning Canvas SPA."""
    return FileResponse("static/index.html")
