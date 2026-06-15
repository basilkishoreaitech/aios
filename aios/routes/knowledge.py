import json
import logging
from pathlib import Path
from fastapi import APIRouter, Request, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database import get_db
from auth.dependencies import require_permission
from models.database import User, KBDocument

logger = logging.getLogger("aios.routes.knowledge")
router = APIRouter()

class ManualKnowledgeIngestRequest(BaseModel):
    id: str
    title: str
    category: str  # runbook, postmortem, architecture
    content: str
    tags: list[str] = []

@router.post("/knowledge/ingest")
async def manual_ingest(
    payload: ManualKnowledgeIngestRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage:knowledge"))
):
    """Manually ingest a new runbook or postmortem document into the KB (RBAC restricted)."""
    logger.info(f"User '{current_user.username}' is manually ingesting KB document: '{payload.id}'")
    
    # Check if document already exists
    stmt = select(KBDocument).where(KBDocument.id == payload.id)
    res = await db.execute(stmt)
    existing = res.scalars().first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Knowledge Base document with ID '{payload.id}' already exists."
        )
        
    if payload.category not in ["runbook", "postmortem", "architecture"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category must be one of: 'runbook', 'postmortem', or 'architecture'."
        )

    # 1. Compute embedding
    embedding_service = request.app.state.embedding_service
    content_text = f"{payload.title} {payload.content} {' '.join(payload.tags)}"
    
    try:
        logger.info(f"Generating embedding vector for manual doc: {payload.id}")
        embedding = await embedding_service.embed(content_text)
        
        # 2. Insert into DB
        db_doc = KBDocument(
            id=payload.id,
            title=payload.title,
            category=payload.category,
            content=payload.content,
            tags=payload.tags,
            embedding=embedding,
            source_file=f"manual/{payload.id}.json"
        )
        db.add(db_doc)
        
        # 3. Write to local disk to keep files in sync (zero-drift)
        category_dir_name = f"{payload.category}s" if payload.category in ["runbook", "postmortem"] else "architecture_docs"
        local_path = Path(embedding_service.config.KNOWLEDGE_DIR) / category_dir_name / f"{payload.id}.json"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(local_path, "w", encoding="utf-8") as f:
            json.dump({
                "id": payload.id,
                "title": payload.title,
                "category": payload.category,
                "content": payload.content,
                "tags": payload.tags
            }, f, indent=2)
            
        logger.info(f"Manual KB doc written to disk: {local_path}")
        await db.commit()

        # 4. Sync to Azure AI Search so chatbot can find it immediately
        try:
            await embedding_service.adapter.add_document(db, {
                "id": payload.id,
                "title": payload.title,
                "content": payload.content,
                "category": payload.category,
                "tags": payload.tags,
                "source_file": f"manual/{payload.id}.json"
            }, embedding)
            logger.info(f"Document '{payload.id}' synced to Azure AI Search index.")
        except Exception as sync_err:
            logger.warning(f"Azure AI Search sync failed for '{payload.id}' (doc saved to DB/disk): {sync_err}")
        
        return {
            "message": f"Document {payload.id} successfully added to KB.",
            "id": payload.id,
            "category": payload.category,
            "synced_file": str(local_path.relative_to(embedding_service.config.KNOWLEDGE_DIR))
        }
    except Exception as e:
        logger.error(f"Failed manual knowledge ingestion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion process aborted: {str(e)}"
        )
