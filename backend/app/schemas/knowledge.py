"""Knowledge-base (RAG) schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeDocumentIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    source: str = Field(default="", max_length=200)
    content: str = Field(min_length=1)


class KnowledgeIngestRequest(BaseModel):
    documents: list[KnowledgeDocumentIn] = Field(min_length=1, max_length=50)


class KnowledgeDocOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    source: str
    chunk_count: int
    content: str
    created_at: datetime


class KnowledgeIngestOut(BaseModel):
    queued: bool = Field(description="True when the ingestion task was queued with Celery")
    documents: int
    task_id: str | None = None
    detail: str | None = Field(
        default=None, description="Set when ingestion fell back to synchronous processing"
    )


class KnowledgeStatsOut(BaseModel):
    documents: int
    indexed_chunks: int


class KnowledgeDocumentUpdate(BaseModel):
    """Partial document update (admin). Re-chunking + re-indexing follows."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    source: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, min_length=1)
