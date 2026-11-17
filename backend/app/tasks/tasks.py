"""Celery tasks: alert classification, knowledge ingestion, summarisation."""
from __future__ import annotations

import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _ingest_documents_impl(documents: list[dict]) -> dict:
    """Shared ingestion logic (also called synchronously by the seed script)."""
    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.models import KnowledgeDocument
    from app.services.rag import knowledge_index
    from app.utils.text import chunk_text

    settings = get_settings()
    db = SessionLocal()
    try:
        ingested = 0
        for document in documents:
            chunks = chunk_text(
                document["content"], settings.RAG_CHUNK_SIZE, settings.RAG_CHUNK_OVERLAP
            )
            obj = KnowledgeDocument(
                title=document["title"][:200],
                source=(document.get("source") or "")[:200],
                content=document["content"],
                chunk_count=len(chunks),
            )
            db.add(obj)
            db.flush()  # assigns obj.id before the vector write
            knowledge_index.index_chunks(obj.id, obj.title, obj.source, chunks)
            ingested += 1
        db.commit()
        logger.info("Ingested %s knowledge document(s)", ingested)
        return {"ingested": ingested}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(
    name="tasks.ingest_knowledge", bind=True, max_retries=3, default_retry_delay=10
)
def ingest_knowledge(self, documents: list[dict]) -> dict:
    """Chunk + embed documents into ChromaDB and persist metadata rows."""
    try:
        return _ingest_documents_impl(documents)
    except Exception as exc:
        logger.exception("Knowledge ingestion failed")
        raise self.retry(exc=exc)


@celery_app.task(
    name="tasks.classify_and_alert", bind=True, max_retries=2, default_retry_delay=5
)
def classify_and_alert(self, message_id: int, session_id: str, text: str) -> dict:
    """Zero-shot classification of one user message; creates an Alert row."""
    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.models import Alert
    from app.services.classifier import zero_shot_classifier
    from app.utils.text import heuristic_classify

    db = SessionLocal()
    try:
        try:
            result = zero_shot_classifier.classify(text)
        except Exception:  # noqa: BLE001 - degrade to heuristics, never lose alerts
            logger.exception("Zero-shot classifier unavailable; using heuristics")
            result = heuristic_classify(text)

        alert = Alert(
            session_id=session_id,
            message_id=message_id,
            category=result["category"],
            severity=result["severity"],
            confidence=result["confidence"],
            scores=result.get("scores", {}),
            summary=text[:500],
            provider=result.get("provider", "zero-shot"),
        )
        db.add(alert)
        db.commit()
        logger.info(
            "Alert #%s created (category=%s severity=%s)",
            alert.id,
            alert.category,
            alert.severity,
        )
        return {
            "alert_id": alert.id,
            "category": alert.category,
            "severity": alert.severity,
            "confidence": alert.confidence,
            "high_severity": alert.severity >= get_settings().ALERT_HIGH_SEVERITY,
        }
    except Exception as exc:
        db.rollback()
        logger.exception("classify_and_alert failed")
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    name="tasks.delete_knowledge_document",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
)
def delete_knowledge_document(self, document_id: int) -> dict:
    """Remove a document's chunks from ChromaDB and its metadata row."""
    from app.db.session import SessionLocal
    from app.models import KnowledgeDocument
    from app.services.rag import knowledge_index

    db = SessionLocal()
    try:
        obj = db.get(KnowledgeDocument, document_id)
        if obj is None:
            return {"deleted": False}
        knowledge_index.delete_document(document_id)
        db.delete(obj)
        db.commit()
        return {"deleted": True}
    except Exception as exc:
        db.rollback()
        logger.exception("delete_knowledge_document failed")
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(name="tasks.summarize_session")
def summarize_session(session_id: str) -> dict:
    """Produce a short CRM-style summary of a conversation."""
    from app.db.session import SessionLocal
    from app.models import Message
    from app.services.llm import llm_engine

    db = SessionLocal()
    try:
        rows = (
            db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.id.asc())
            .all()
        )
        if not rows:
            return {"summary": ""}
        transcript = "\n".join(f"{row.role.upper()}: {row.content}" for row in rows)
        summary = llm_engine.generate(
            [
                {
                    "role": "system",
                    "content": "You summarise customer support conversations concisely.",
                },
                {
                    "role": "user",
                    "content": (
                        "Summarise the following conversation in at most 3 sentences:\n\n"
                        f"{transcript}"
                    ),
                },
            ],
            max_new_tokens=120,
        )
        return {"summary": summary}
    except Exception:  # noqa: BLE001
        logger.exception("summarize_session failed")
        return {"summary": ""}
    finally:
        db.close()


@celery_app.task(
    name="tasks.reindex_knowledge_document",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
)
def reindex_knowledge_document(self, document_id: int) -> dict:
    """Rebuild a document's vector chunks from its current stored content."""
    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.models import KnowledgeDocument
    from app.services.rag import knowledge_index
    from app.utils.text import chunk_text

    db = SessionLocal()
    try:
        obj = db.get(KnowledgeDocument, document_id)
        if obj is None:
            return {"reindexed": False}
        chunks = chunk_text(
            obj.content, get_settings().RAG_CHUNK_SIZE, get_settings().RAG_CHUNK_OVERLAP
        )
        knowledge_index.index_chunks(obj.id, obj.title, obj.source, chunks)
        logger.info("Reindexed document %s (%s chunks)", document_id, len(chunks))
        return {"reindexed": True, "chunk_count": len(chunks)}
    except Exception as exc:
        logger.exception("reindex_knowledge_document failed")
        raise self.retry(exc=exc)
    finally:
        db.close()
