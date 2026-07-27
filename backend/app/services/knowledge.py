"""Application service coordinating MySQL metadata and Chroma vectors."""

from collections.abc import Sequence
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.infrastructure.models.knowledge_document import KnowledgeDocument
from app.infrastructure.repositories.knowledge_document import KnowledgeDocumentRepository
from app.rag.loaders import extract_sections, split_sections
from app.rag.vector_store import ChromaKnowledgeStore, KnowledgeHit


class KnowledgeService:
    """Own RAG ingestion, retrieval and deletion use cases."""

    def __init__(
        self,
        session: Session,
        store: ChromaKnowledgeStore,
        *,
        owner_id: str,
    ) -> None:
        self.session = session
        self.store = store
        self.owner_id = owner_id
        self.repository = KnowledgeDocumentRepository(session)

    def create_document(
        self,
        *,
        filename: str,
        content_type: str,
        content: bytes,
        title: str | None = None,
        source: str | None = None,
        city: str | None = None,
        category: str | None = None,
    ) -> KnowledgeDocument:
        """Parse, chunk, embed and persist one user-owned document."""
        if not content:
            raise ValueError("上传文件不能为空")
        if len(content) > settings.rag_max_file_bytes:
            raise ValueError(
                f"文件不能超过 {settings.rag_max_file_bytes // 1024 // 1024} MB"
            )
        chunks = split_sections(
            extract_sections(filename, content),
            chunk_size=settings.rag_chunk_size,
            overlap=settings.rag_chunk_overlap,
        )
        if not chunks:
            raise ValueError("文件中没有可索引的文本")
        document_id = str(uuid4())
        clean_title = (title or filename).strip()
        if not clean_title:
            raise ValueError("知识标题不能为空")
        self.store.add_document(
            document_id=document_id,
            owner_id=self.owner_id,
            title=clean_title,
            filename=filename,
            source=source,
            city=city,
            category=category,
            chunks=chunks,
        )
        document = KnowledgeDocument(
            id=document_id,
            owner_id=self.owner_id,
            filename=filename,
            title=clean_title,
            source=source,
            city=city,
            category=category,
            content_type=content_type or "application/octet-stream",
            chunk_count=len(chunks),
            status="ready",
        )
        self.repository.add(document)
        try:
            self.session.commit()
            self.session.refresh(document)
        except SQLAlchemyError:
            self.session.rollback()
            self.store.delete_document(document_id, self.owner_id)
            raise
        return document

    def list_documents(self) -> Sequence[KnowledgeDocument]:
        return self.repository.list_all(self.owner_id)

    def search(
        self,
        *,
        query: str,
        city: str | None = None,
        category: str | None = None,
        top_k: int | None = None,
    ) -> list[KnowledgeHit]:
        return self.store.search(
            query=query,
            owner_id=self.owner_id,
            city=city,
            category=category,
            top_k=top_k or settings.rag_top_k,
        )

    def delete_document(self, document_id: str) -> bool:
        document = self.repository.get_by_id(document_id, self.owner_id)
        if document is None:
            return False
        self.store.delete_document(document_id, self.owner_id)
        self.repository.delete(document)
        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return True
