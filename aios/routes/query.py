import json
import logging
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi import File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from auth.dependencies import get_current_user
from models.database import User
from models.query import QueryRequest, QueryResponse
from services.query_service import QueryService

logger = logging.getLogger("aios.routes.query")
router = APIRouter()

@router.post("/query", response_model=QueryResponse)
async def interactive_query(
    request: Request,
    payload: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Perform natural language search across incidents, runbooks, and Bing Web Search."""
    logger.info(f"Operator '{current_user.username}' submitted interactive query: '{payload.question}'")
    
    # Instantiate query service dynamically using lifespan cached singletons
    query_service = QueryService(
        embedding_service=request.app.state.embedding_service,
        web_search_service=request.app.state.web_search_service,
        model_router=request.app.state.model_router
    )
    
    try:
        response = await query_service.run_query(db, payload)
        return response
    except Exception as e:
        logger.error(f"Error handling query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while triaging query: {str(e)}"
        )


@router.post("/query/evidence", response_model=QueryResponse)
async def interactive_query_with_evidence(
    request: Request,
    question: str = Form(...),
    filters: str = Form(default="{}"),
    screenshot: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Perform natural language search with optional screenshot evidence."""
    logger.info("Operator '%s' submitted evidence-backed query: '%s'", current_user.username, question)

    query_service = QueryService(
        embedding_service=request.app.state.embedding_service,
        web_search_service=request.app.state.web_search_service,
        model_router=request.app.state.model_router
    )

    try:
        parsed_filters = json.loads(filters) if filters else {}
        evidence_payload = None
        if screenshot is not None:
            evidence_payload = {
                "filename": screenshot.filename or "screenshot",
                "content_type": screenshot.content_type or "application/octet-stream",
                "bytes": await screenshot.read()
            }

        payload = QueryRequest(question=question, filters=parsed_filters)
        return await query_service.run_query(db, payload, image_evidence=evidence_payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid filters payload: {exc}") from exc
    except Exception as e:
        logger.error(f"Error handling evidence query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while triaging query: {str(e)}"
        )
