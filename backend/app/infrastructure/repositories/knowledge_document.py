"""Database operations for RAG knowledge document metadata."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models.knowledge_document import KnowledgeDocument


class KnowledgeDocumentRepository:
    """Query document metadata without owning transaction boundaries."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, document: KnowledgeDocument) -> None:
        self.session.add(document)

    def get_by_id(self, document_id: str, owner_id: str) -> KnowledgeDocument | None:
        return self.session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.owner_id == owner_id,
            )
        )

    def list_all(self, owner_id: str) -> Sequence[KnowledgeDocument]:
        return self.session.scalars(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.owner_id == owner_id)
            .order_by(KnowledgeDocument.created_at.desc())
        ).all()

    def delete(self, document: KnowledgeDocument) -> None:
        self.session.delete(document)
