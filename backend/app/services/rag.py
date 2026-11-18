"""RAG index: Ollama embeddings + PostgreSQL storage (no separate vector DB).

Document chunks and their embedding vectors live in the ``knowledge_chunks``
table (vectors stored as JSONB); the vectors themselves are produced by the
local Ollama server (``hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0``). Similarity
is plain in-process cosine maths — plenty fast for a support knowledge base and
completely dependency-free.

All writes are performed by the Celery worker (single-writer pattern); the API
process only reads and deletes.
"""
from __future__ import annotations

import hashlib
import logging
import math
import threading

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.cache import redis_cache
from app.services.ollama_client import get_ollama_client

logger = logging.getLogger(__name__)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed one or more texts with the Ollama embedding model."""
    if not texts:
        return []
    settings = get_settings()
    response = get_ollama_client().embed(model=settings.EMBEDDING_MODEL_NAME, input=texts)
    try:
        embeddings = list(response["embeddings"])  # dict or ollama response model
    except (KeyError, TypeError, AttributeError) as exc:
        raise RuntimeError("Ollama embed response did not contain 'embeddings'") from exc
    if len(embeddings) != len(texts):
        raise RuntimeError(
            f"Ollama returned {len(embeddings)} embeddings for {len(texts)} input(s)"
        )
    return embeddings


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Plain-python cosine similarity (no numpy dependency)."""
    if not a or not b:
        return 0.0
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / math.sqrt(na * nb)


class KnowledgeIndex:
    """Thread-safe lazy singleton around the PostgreSQL-backed vector index."""

    _instance: "KnowledgeIndex | None" = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "KnowledgeIndex":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def is_available(self) -> bool:
        """Health-check helper: is the chunk table reachable?"""
        try:
            self._count_rows()
            return True
        except Exception:  # noqa: BLE001
            return False

    def count(self) -> int:
        try:
            return self._count_rows()
        except Exception:  # noqa: BLE001
            return 0

    def index_chunks(
        self,
        document_id: int,
        title: str,
        source: str,
        chunks: list[str],
        db: Session | None = None,
    ) -> int:
        """(Re-)index the chunks of one document; returns the number indexed.

        Pass ``db`` to join the caller's transaction — ingestion writes the
        ``knowledge_documents`` row and its chunks atomically that way (and the
        FK on ``document_id`` is satisfied because the parent row lives in the
        same transaction). Without ``db``, a dedicated session is opened and
        committed here.
        """
        if not chunks:
            return 0
        embeddings = embed_texts(chunks)
        from app.models import KnowledgeChunk

        owns_session = db is None
        if owns_session:
            from app.db.session import SessionLocal

            db = SessionLocal()
        try:
            removed = (
                db.query(KnowledgeChunk)
                .filter(KnowledgeChunk.document_id == document_id)
                .delete(synchronize_session=False)
            )
            if removed:
                logger.info(
                    "Replaced %s existing chunk(s) for document %s", removed, document_id
                )
            for i, (content, embedding) in enumerate(zip(chunks, embeddings)):
                db.add(
                    KnowledgeChunk(
                        document_id=document_id,
                        chunk_index=i,
                        content=content,
                        title=title,
                        source=source,
                        embedding=embedding,
                    )
                )
            if owns_session:
                db.commit()
            else:
                db.flush()  # visible to the caller's transaction; they commit
        except Exception:
            if owns_session:
                db.rollback()
            raise
        finally:
            if owns_session:
                db.close()
        return len(chunks)

    def query(self, query_text: str, top_k: int | None = None) -> list[dict]:
        """Semantic search with a short-lived Redis cache."""
        settings = get_settings()
        cache_key = "rag:" + hashlib.sha1(query_text.encode("utf-8")).hexdigest()
        cached = redis_cache.get_json(cache_key)
        if cached is not None:
            return cached

        try:
            query_vector = embed_texts([query_text])[0]
        except Exception:  # noqa: BLE001
            logger.exception("Ollama embedding unavailable during query")
            return []

        from app.models import KnowledgeChunk

        rows: list[KnowledgeChunk] = []
        try:
            from app.db.session import SessionLocal

            db = SessionLocal()
            try:
                rows = db.query(KnowledgeChunk).all()
            finally:
                db.close()
        except Exception:  # noqa: BLE001
            logger.exception("PostgreSQL unavailable during vector query")
            return []

        if not rows:
            return []

        # Cosine distance (1 − similarity), same semantics ChromaDB used.
        scored: list[tuple[float, KnowledgeChunk]] = []
        for row in rows:
            similarity = cosine_similarity(query_vector, list(row.embedding or []))
            scored.append((1.0 - similarity, row))
        scored.sort(key=lambda item: item[0])

        k = min(top_k or settings.RAG_TOP_K, len(scored))
        hits: list[dict] = []
        for distance, row in scored[:k]:
            if distance <= settings.RAG_MAX_DISTANCE:
                hits.append(
                    {
                        "document_id": row.document_id,
                        "title": row.title,
                        "source": row.source,
                        "chunk_index": row.chunk_index,
                        "text": row.content,
                        "distance": float(distance),
                    }
                )
        redis_cache.set_json(cache_key, hits)
        return hits

    def delete_document(self, document_id: int, db: Session | None = None) -> int:
        """Remove every chunk belonging to a document; returns the count removed.

        Pass ``db`` to join the caller's transaction (chunks and the document
        row are deleted atomically). Without ``db``, a dedicated session is
        opened and committed here; failures are logged and swallowed.
        """
        from app.models import KnowledgeChunk

        owns_session = db is None
        if owns_session:
            from app.db.session import SessionLocal

            db = SessionLocal()
        try:
            removed = (
                db.query(KnowledgeChunk)
                .filter(KnowledgeChunk.document_id == document_id)
                .delete(synchronize_session=False)
            )
            if owns_session:
                db.commit()
            else:
                db.flush()  # visible to the caller's transaction; they commit
            return int(removed or 0)
        except Exception:  # noqa: BLE001
            if owns_session:
                db.rollback()
                logger.exception("Failed to delete chunks for document %s", document_id)
                return 0
            raise
        finally:
            if owns_session:
                db.close()

    @staticmethod
    def _count_rows() -> int:
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            result = db.execute(text("SELECT COUNT(*) FROM knowledge_chunks"))
            return int(result.scalar_one())
        finally:
            db.close()


knowledge_index = KnowledgeIndex()