"""Knowledge-base (RAG) management endpoints."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_agent, require_admin
from app.core.config import get_settings
from app.models import KnowledgeDocument, User
from app.schemas.knowledge import (
    KnowledgeDocOut,
    KnowledgeDocumentUpdate,
    KnowledgeIngestOut,
    KnowledgeIngestRequest,
    KnowledgeStatsOut,
)
from app.services.rag import knowledge_index
from app.utils.text import chunk_text

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# backend/app/api/v1/knowledge.py → parents[2] == backend/app
SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "knowledge_seed.json"


@router.get("/documents", response_model=list[KnowledgeDocOut])
def documents(
    _viewer: User = Depends(require_agent),
    db: Session = Depends(get_db),
) -> list[KnowledgeDocument]:
    """List ingested knowledge documents incl. content (agent/admin)."""
    return db.query(KnowledgeDocument).order_by(KnowledgeDocument.id.desc()).all()


@router.get("/stats", response_model=KnowledgeStatsOut)
def stats(
    _viewer: User = Depends(require_agent),
    db: Session = Depends(get_db),
) -> KnowledgeStatsOut:
    """PostgreSQL document count + ChromaDB indexed chunk count."""
    total = db.query(KnowledgeDocument).count()
    return KnowledgeStatsOut(documents=total, indexed_chunks=knowledge_index.count())


@router.patch(
    "/documents/{document_id}",
    response_model=KnowledgeDocOut,
    dependencies=[Depends(require_admin)],
)
def update_document(
    document_id: int,
    payload: KnowledgeDocumentUpdate,
    db: Session = Depends(get_db),
) -> KnowledgeDocument:
    """Update a document (admin). Vector chunks are rebuilt asynchronously."""
    obj = db.get(KnowledgeDocument, document_id)
    if obj is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="No fields to update")

    obj.title = (changes.get("title") or obj.title)[:200]
    if changes.get("source") is not None:
        obj.source = changes["source"]
    obj.content = changes.get("content") or obj.content
    obj.chunk_count = len(
        chunk_text(obj.content, get_settings().RAG_CHUNK_SIZE, get_settings().RAG_CHUNK_OVERLAP)
    )
    db.commit()
    db.refresh(obj)

    try:
        from app.tasks.tasks import reindex_knowledge_document

        reindex_knowledge_document.delay(obj.id)
    except Exception:  # noqa: BLE001 - broker down: rebuild vectors synchronously
        knowledge_index.index_chunks(
            obj.id,
            obj.title,
            obj.source,
            chunk_text(
                obj.content, get_settings().RAG_CHUNK_SIZE, get_settings().RAG_CHUNK_OVERLAP
            ),
        )
    return obj


def _dispatch_ingest(documents: list[dict]) -> KnowledgeIngestOut:
    """Prefer Celery; fall back to synchronous processing if the broker is down."""
    try:
        from app.tasks.tasks import ingest_knowledge

        async_result = ingest_knowledge.delay(documents)
        return KnowledgeIngestOut(
            queued=True,
            documents=len(documents),
            task_id=getattr(async_result, "id", None),
        )
    except Exception as exc:  # noqa: BLE001
        from app.tasks.tasks import _ingest_documents_impl

        result = _ingest_documents_impl(documents)
        return KnowledgeIngestOut(
            queued=False,
            documents=int(result.get("ingested", 0)),
            detail=f"Broker unavailable; processed synchronously ({exc.__class__.__name__})",
        )


@router.post(
    "/ingest",
    response_model=KnowledgeIngestOut,
    dependencies=[Depends(require_admin)],
)
def ingest(payload: KnowledgeIngestRequest) -> KnowledgeIngestOut:
    """Ingest documents into PostgreSQL + ChromaDB (admin role required)."""
    return _dispatch_ingest([doc.model_dump() for doc in payload.documents])


@router.post(
    "/ingest-default",
    response_model=KnowledgeIngestOut,
    dependencies=[Depends(require_admin)],
)
def ingest_default() -> KnowledgeIngestOut:
    """Ingest the bundled starter knowledge base (admin)."""
    if not SEED_PATH.exists():
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bundled knowledge seed file is missing",
        )
    documents = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return _dispatch_ingest(documents)


@router.delete(
    "/documents/{document_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_document(document_id: int) -> Response:
    """Delete a document's chunks from ChromaDB and its metadata row (admin)."""
    try:
        from app.tasks.tasks import delete_knowledge_document

        delete_knowledge_document.delay(document_id)
    except Exception:  # noqa: BLE001 - broker down: delete synchronously
        from app.db.session import SessionLocal
        from app.services.rag import knowledge_index

        db_local = SessionLocal()
        try:
            obj = db_local.get(KnowledgeDocument, document_id)
            if obj is not None:
                knowledge_index.delete_document(document_id)
                db_local.delete(obj)
                db_local.commit()
        finally:
            db_local.close()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
