"""Pydantic schemas for the RAG knowledge API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    title: str
    source: str | None
    city: str | None
    category: str | None
    content_type: str
    chunk_count: int
    status: str
    created_at: datetime
    updated_at: datetime


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    top_k: int = Field(default=4, ge=1, le=8)


class KnowledgeSearchResult(BaseModel):
    text: str
    document_id: str
    title: str
    source: str
    filename: str
    city: str | None
    category: str | None
    page: int | None
    distance: float | None
