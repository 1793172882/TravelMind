from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def ensure_application_tables() -> None:
    """Create additive application tables without owning schema migrations."""
    import app.infrastructure.models  # noqa: F401

    Base.metadata.create_all(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("trips")}
    with engine.begin() as connection:
        if "owner_id" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE trips ADD COLUMN owner_id VARCHAR(200) NOT NULL "
                    "DEFAULT 'anonymous' COMMENT '逻辑用户标识' AFTER id"
                )
            )
        if "thread_id" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE trips ADD COLUMN thread_id VARCHAR(200) NULL "
                    "COMMENT '创建行程的 Agent 会话' AFTER owner_id"
                )
            )
