from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend.core.config import get_settings


class Base(DeclarativeBase):
    pass


class ResearchSession(Base):
    __tablename__ = "research_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | running | complete | error
    current_agent: Mapped[str] = mapped_column(String(50), default="")
    errors: Mapped[str] = mapped_column(Text, default="[]")          # JSON list of error strings
    corpus_warning: Mapped[bool] = mapped_column(default=False)       # True if < min_corpus_size papers found

    # Pipeline outputs (stored as JSON strings)
    subtopics: Mapped[str] = mapped_column(Text, default="[]")
    search_queries: Mapped[str] = mapped_column(Text, default="[]")
    key_concepts: Mapped[str] = mapped_column(Text, default="[]")
    ranked_papers: Mapped[str] = mapped_column(Text, default="[]")
    summaries: Mapped[str] = mapped_column(Text, default="[]")
    research_gaps: Mapped[str] = mapped_column(Text, default="[]")
    final_review: Mapped[str] = mapped_column(Text, default="")

    # Evaluation (stored as JSON, null until evaluated)
    evaluation: Mapped[str | None] = mapped_column(Text, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def set_json(self, field: str, value: Any) -> None:
        setattr(self, field, json.dumps(value))

    def get_json(self, field: str) -> Any:
        raw = getattr(self, field)
        if raw is None:
            return None
        return json.loads(raw)


# --- Engine & session factory ---

def _make_engine():
    settings = get_settings()
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_async_engine(settings.database_url, connect_args=connect_args, echo=False)


engine = _make_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
