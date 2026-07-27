"""Persist travel knowledge chunks in Chroma and retrieve them by user scope."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from app.config import settings
from app.rag.loaders import KnowledgeChunk


@dataclass(frozen=True, slots=True)
class KnowledgeHit:
    """One retrieved chunk with enough metadata for a verifiable citation."""

    text: str
    document_id: str
    title: str
    source: str
    filename: str
    city: str | None
    category: str | None
    page: int | None
    distance: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "document_id": self.document_id,
            "title": self.title,
            "source": self.source,
            "filename": self.filename,
            "city": self.city,
            "category": self.category,
            "page": self.page,
            "distance": self.distance,
        }


class ChromaKnowledgeStore:
    """Store embeddings in one local Chroma collection."""

    def __init__(
        self,
        persist_dir: Path,
        collection_name: str,
        embeddings: Embeddings,
    ) -> None:
        persist_dir.mkdir(parents=True, exist_ok=True)
        self.embeddings = embeddings
        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.collection = self.client.get_or_create_collection(collection_name)

    def add_document(
        self,
        *,
        document_id: str,
        owner_id: str,
        title: str,
        filename: str,
        source: str | None,
        city: str | None,
        category: str | None,
        chunks: list[KnowledgeChunk],
    ) -> None:
        """Embed and add all chunks of one document."""
        documents = [chunk.text for chunk in chunks]
        vectors = self.embeddings.embed_documents(documents)
        metadatas = [
            {
                "document_id": document_id,
                "owner_id": owner_id,
                "title": title,
                "filename": filename,
                "source": source or filename,
                "city": city or "",
                "category": category or "",
                "page": chunk.page or 0,
                "chunk_index": chunk.index,
            }
            for chunk in chunks
        ]
        self.collection.add(
            ids=[f"{document_id}:{chunk.index}" for chunk in chunks],
            documents=documents,
            embeddings=vectors,
            metadatas=metadatas,
        )

    def search(
        self,
        *,
        query: str,
        owner_id: str,
        city: str | None = None,
        category: str | None = None,
        top_k: int = 4,
    ) -> list[KnowledgeHit]:
        """Return the nearest chunks visible to one logical user."""
        filters = [{"owner_id": {"$eq": owner_id}}]
        if city:
            filters.append({"city": {"$eq": city}})
        if category:
            filters.append({"category": {"$eq": category}})
        where: dict[str, Any] = filters[0] if len(filters) == 1 else {"$and": filters}
        result = self.collection.query(
            query_embeddings=[self.embeddings.embed_query(query)],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        hits: list[KnowledgeHit] = []
        for index, text in enumerate(documents):
            metadata = metadatas[index] or {}
            page = int(metadata.get("page") or 0) or None
            hits.append(
                KnowledgeHit(
                    text=text,
                    document_id=str(metadata.get("document_id", "")),
                    title=str(metadata.get("title", "")),
                    source=str(metadata.get("source", "")),
                    filename=str(metadata.get("filename", "")),
                    city=str(metadata.get("city") or "") or None,
                    category=str(metadata.get("category") or "") or None,
                    page=page,
                    distance=float(distances[index]) if index < len(distances) else None,
                )
            )
        return hits

    def delete_document(self, document_id: str, owner_id: str) -> None:
        """Delete all vector chunks belonging to one user's document."""
        self.collection.delete(
            where={
                "$and": [
                    {"document_id": {"$eq": document_id}},
                    {"owner_id": {"$eq": owner_id}},
                ]
            }
        )


def build_knowledge_store() -> ChromaKnowledgeStore:
    """Build the configured Chroma store with the existing DashScope credential."""
    api_key = settings.dashscope_api_key or settings.model_api_key
    if api_key is None:
        raise RuntimeError("缺少 DASHSCOPE_API_KEY，无法使用 RAG 向量检索")
    embeddings = OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=api_key,
        base_url=settings.model_base_url,
        check_embedding_ctx_length=False,
    )
    return ChromaKnowledgeStore(
        settings.chroma_persist_dir,
        settings.chroma_collection,
        embeddings,
    )
