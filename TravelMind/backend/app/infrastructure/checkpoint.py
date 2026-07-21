"""LangGraph checkpoint persistence compatible with the project's MySQL."""

from langgraph.checkpoint.mysql.aio import AIOMySQLSaver


class TravelMindMySQLSaver(AIOMySQLSaver):
    """Support MySQL 8.0.12, which cannot assign defaults to JSON columns."""

    MIGRATIONS = [
        migration.replace(
            "metadata JSON NOT NULL DEFAULT ('{}'),",
            "metadata JSON NOT NULL,",
        )
        for migration in AIOMySQLSaver.MIGRATIONS
    ]
