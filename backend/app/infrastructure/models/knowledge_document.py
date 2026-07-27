"""SQLAlchemy mapping for RAG knowledge document metadata."""

from datetime import datetime

from sqlalchemy import DateTime, FetchedValue, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class KnowledgeDocument(Base):
    """Describe one user-owned source whose chunks live in Chroma."""

    __tablename__ = "knowledge_documents"
    __table_args__ = {"comment": "RAG知识文档元数据"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="文档UUID")
    owner_id: Mapped[str] = mapped_column(
        String(200), nullable=False, index=True, comment="逻辑用户标识"
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False, comment="原始文件名")
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="知识标题")
    source: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="来源")
    city: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="城市过滤")
    category: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="知识分类"
    )
    content_type: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="上传内容类型"
    )
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, comment="Chunk数量")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'ready'"), comment="索引状态"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=FetchedValue(),
        comment="更新时间",
    )
