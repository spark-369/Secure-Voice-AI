"""Knowledge-base documents ingested into the RAG index."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class KnowledgeDocument(TimestampMixin, Base):
    """A source document chunked and embedded into the RAG index."""

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<KnowledgeDocument id={self.id} title={self.title!r}>"


class KnowledgeChunk(Base):
    """One embedded chunk of a knowledge document (vector stored as JSONB).

    Embeddings are produced by the local Ollama embedding model and searched
    with in-process cosine similarity — no separate vector database needed.
    """

    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    source: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    embedding: Mapped[list[float]] = mapped_column(JSONB, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<KnowledgeChunk id={self.id} document_id={self.document_id}>"
