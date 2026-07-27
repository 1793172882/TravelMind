"""Harness tool exposing user-scoped Chroma retrieval to the Agent."""

import asyncio

from pydantic import BaseModel, Field

from app.harness.runtime_context import require_agent_context
from app.rag.vector_store import ChromaKnowledgeStore


class KnowledgeSearchArgs(BaseModel):
    """Parameters the model may use to narrow a knowledge search."""

    query: str = Field(min_length=2, max_length=500)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    top_k: int = Field(default=4, ge=1, le=8)


async def search_knowledge(
    store: ChromaKnowledgeStore,
    *,
    query: str,
    city: str | None,
    category: str | None,
    top_k: int,
) -> list[dict]:
    """Retrieve evidence without blocking the Agent event loop."""
    owner_id = require_agent_context().user_id
    hits = await asyncio.to_thread(
        store.search,
        query=query,
        owner_id=owner_id,
        city=city,
        category=category,
        top_k=top_k,
    )
    return [hit.as_dict() for hit in hits]
