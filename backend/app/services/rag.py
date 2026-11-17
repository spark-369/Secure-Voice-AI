"""RAG index: python-embedded ChromaDB with persistent storage.

All writes are performed by the Celery worker (single-writer pattern to avoid
SQLite contention); the API process only reads and deletes.
"""
from __future__ import annotations

import hashlib
import logging
import threading

from app.core.config import get_settings
from app.services.cache import redis_cache

logger = logging.getLogger(__name__)


class KnowledgeIndex:
    """Thread-safe lazy singleton around the ChromaDB persistent collection."""

    _instance: "KnowledgeIndex | None" = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "KnowledgeIndex":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._collection = None
                    instance._collection_lock = threading.Lock()
                    cls._instance = instance
        return cls._instance

    def _get_collection(self):
        if self._collection is None:
            with self._collection_lock:
                if self._collection is None:
                    import chromadb

                    settings = get_settings()
                    client = chromadb.PersistentClient(
                        path=settings.CHROMA_PERSIST_DIR,
                        settings=chromadb.config.Settings(
                            anonymized_telemetry=False, allow_reset=True
                        ),
                    )
                    self._collection = client.get_or_create_collection(
                        name=settings.RAG_COLLECTION,
                        metadata={"hnsw:space": "cosine"},
                    )
                    logger.info(
                        "ChromaDB collection %r ready (%s chunks)",
                        settings.RAG_COLLECTION,
                        self._collection.count(),
                    )
        return self._collection

    def is_available(self) -> bool:
        """Health-check helper: can the index be opened and counted?"""
        try:
            self._get_collection().count()
            return True
        except Exception:  # noqa: BLE001
            return False

    def count(self) -> int:
        try:
            return int(self._get_collection().count())
        except Exception:  # noqa: BLE001
            return 0

    def index_chunks(
        self, document_id: int, title: str, source: str, chunks: list[str]
    ) -> int:
        """(Re-)index the chunks of one document; returns the number indexed."""
        if not chunks:
            return 0
        collection = self._get_collection()
        self._delete_document_chunks(collection, document_id)
        ids = [f"doc-{document_id}-chunk-{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "document_id": document_id,
                "title": title,
                "source": source,
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]
        collection.add(ids=ids, documents=chunks, metadatas=metadatas)
        return len(chunks)

    def query(self, query_text: str, top_k: int | None = None) -> list[dict]:
        """Semantic search with a short-lived Redis cache."""
        settings = get_settings()
        cache_key = "rag:" + hashlib.sha1(query_text.encode("utf-8")).hexdigest()
        cached = redis_cache.get_json(cache_key)
        if cached is not None:
            return cached

        try:
            collection = self._get_collection()
        except Exception:  # noqa: BLE001
            logger.exception("ChromaDB unavailable during query")
            return []

        total = collection.count()
        if total == 0:
            return []

        k = min(top_k or settings.RAG_TOP_K, total)
        result = collection.query(
            query_texts=[query_text],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[dict] = []
        for doc, meta, distance in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            if float(distance) <= settings.RAG_MAX_DISTANCE:
                hits.append(
                    {
                        "document_id": int(meta.get("document_id", 0)),
                        "title": meta.get("title", ""),
                        "source": meta.get("source", ""),
                        "chunk_index": int(meta.get("chunk_index", 0)),
                        "text": doc,
                        "distance": float(distance),
                    }
                )
        redis_cache.set_json(cache_key, hits)
        return hits

    def delete_document(self, document_id: int) -> int:
        """Remove every chunk belonging to a document; returns the count removed."""
        collection = self._get_collection()
        return self._delete_document_chunks(collection, document_id)

    @staticmethod
    def _delete_document_chunks(collection, document_id: int) -> int:
        try:
            existing = collection.get(where={"document_id": document_id})
            ids = existing.get("ids") or []
            if ids:
                collection.delete(ids=ids)
            return len(ids)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to delete chunks for document %s", document_id)
            return 0


knowledge_index = KnowledgeIndex()
