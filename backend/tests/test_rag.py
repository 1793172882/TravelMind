"""Tests for document ingestion, Chroma isolation and Harness retrieval."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings
from pydantic import SecretStr
import pytest

from app.agent.runtime import build_default_registry
from app.agent.state import AgentContext
from app.api.dependencies import get_knowledge_service
from app.config import settings
from app.harness.runtime_context import current_agent_context
from app.main import app
from app.rag.loaders import KnowledgeChunk, SourceSection, extract_sections, split_sections
from app.rag.vector_store import ChromaKnowledgeStore
from app.rag.vector_store import build_knowledge_store
from app.services.knowledge import KnowledgeService


class KeywordEmbeddings(Embeddings):
    """Small deterministic embedding used to exercise a real local Chroma."""

    @staticmethod
    def _embed(text: str) -> list[float]:
        return [
            float(text.count("故宫")),
            float(text.count("西湖")),
            float(text.count("行李")),
            0.01,
        ]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def test_text_loader_and_overlap_split() -> None:
    sections = extract_sections("guide.md", "# 西湖攻略\n建议清晨游览。".encode())
    chunks = split_sections(
        [SourceSection(text="甲" * 150)],
        chunk_size=100,
        overlap=20,
    )

    assert sections[0].text.startswith("# 西湖攻略")
    assert len(chunks) == 2
    assert chunks[0].text[-20:] == chunks[1].text[:20]


def test_dashscope_embeddings_receive_text_instead_of_token_ids(monkeypatch) -> None:
    embedding_factory = Mock(return_value=KeywordEmbeddings())
    store_factory = Mock(return_value=Mock())
    monkeypatch.setattr(settings, "dashscope_api_key", SecretStr("test-key"))
    monkeypatch.setattr("app.rag.vector_store.OpenAIEmbeddings", embedding_factory)
    monkeypatch.setattr("app.rag.vector_store.ChromaKnowledgeStore", store_factory)

    build_knowledge_store()

    assert embedding_factory.call_args.kwargs["check_embedding_ctx_length"] is False


def test_chroma_search_is_user_scoped_and_deletable(tmp_path) -> None:
    store = ChromaKnowledgeStore(tmp_path / "chroma", "travelmind_test", KeywordEmbeddings())
    store.add_document(
        document_id="doc-1",
        owner_id="web:1",
        title="故宫参观说明",
        filename="palace.md",
        source="官方说明",
        city="北京",
        category="景区政策",
        chunks=[KnowledgeChunk("故宫需要提前预约。", 0)],
    )
    store.add_document(
        document_id="doc-2",
        owner_id="web:2",
        title="私有资料",
        filename="private.md",
        source=None,
        city="北京",
        category="景区政策",
        chunks=[KnowledgeChunk("故宫内部私有行程。", 0)],
    )

    hits = store.search(query="故宫", owner_id="web:1", city="北京")

    assert [hit.document_id for hit in hits] == ["doc-1"]
    assert hits[0].source == "官方说明"
    store.delete_document("doc-1", "web:1")
    assert store.search(query="故宫", owner_id="web:1") == []


def test_knowledge_service_coordinates_vector_and_mysql(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rag_chunk_size", 100)
    monkeypatch.setattr(settings, "rag_chunk_overlap", 20)
    session = Mock()
    store = Mock()

    document = KnowledgeService(session, store, owner_id="web:7").create_document(
        filename="hangzhou.md",
        content_type="text/markdown",
        content="西湖建议清晨游览。".encode(),
        title="杭州攻略",
        source="个人整理",
        city="杭州",
        category="攻略",
    )

    assert document.owner_id == "web:7"
    assert document.chunk_count == 1
    store.add_document.assert_called_once()
    session.add.assert_called_once_with(document)
    session.commit.assert_called_once()


@pytest.mark.anyio
async def test_knowledge_tool_is_read_only_and_uses_agent_identity() -> None:
    store = Mock()
    store.search.return_value = []
    registry = build_default_registry(knowledge_store=store)
    tool = registry.get("knowledge.search")
    token = current_agent_context.set(AgentContext("web:9", "web:9:rag"))
    try:
        result = await registry.invoke(
            "knowledge.search",
            {"query": "北京带老人参观注意事项", "top_k": 3},
        )
    finally:
        current_agent_context.reset(token)

    assert tool.risk_level.value == "read"
    assert result == []
    store.search.assert_called_once_with(
        query="北京带老人参观注意事项",
        owner_id="web:9",
        city=None,
        category=None,
        top_k=3,
    )


def test_knowledge_upload_api_uses_service() -> None:
    now = datetime(2026, 7, 27, 10)
    service = Mock(spec=KnowledgeService)
    service.create_document.return_value = SimpleNamespace(
        id="doc-api",
        filename="guide.md",
        title="杭州攻略",
        source="个人整理",
        city="杭州",
        category="攻略",
        content_type="text/markdown",
        chunk_count=1,
        status="ready",
        created_at=now,
        updated_at=now,
    )
    app.dependency_overrides[get_knowledge_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/knowledge/documents",
            files={"file": ("guide.md", "西湖建议清晨游览。", "text/markdown")},
            data={"title": "杭州攻略", "city": "杭州", "category": "攻略"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["id"] == "doc-api"
    service.create_document.assert_called_once()
