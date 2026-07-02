"""
Tests for config layer and database layer.
Run with: pytest
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_ranking_weights_must_sum_to_one(monkeypatch):
    """Settings should reject weights that don't sum to 1.0."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("RANK_WEIGHT_SEMANTIC", "0.50")
    monkeypatch.setenv("RANK_WEIGHT_CITATION", "0.50")
    monkeypatch.setenv("RANK_WEIGHT_RECENCY", "0.50")
    monkeypatch.setenv("RANK_WEIGHT_VENUE", "0.10")

    from backend.core.config import Settings
    with pytest.raises(ValidationError, match="sum to 1.0"):
        Settings()


def test_ranking_weights_valid(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("RANK_WEIGHT_SEMANTIC", "0.40")
    monkeypatch.setenv("RANK_WEIGHT_CITATION", "0.30")
    monkeypatch.setenv("RANK_WEIGHT_RECENCY", "0.20")
    monkeypatch.setenv("RANK_WEIGHT_VENUE", "0.10")

    from backend.core.config import Settings
    s = Settings()
    assert abs(s.rank_weight_semantic + s.rank_weight_citation +
               s.rank_weight_recency + s.rank_weight_venue - 1.0) < 1e-6


def test_reflection_threshold_out_of_range(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("REFLECTION_THRESHOLD", "1.5")

    from backend.core.config import Settings
    with pytest.raises(ValidationError, match="between 0.0 and 1.0"):
        Settings()


@pytest.mark.asyncio
async def test_db_init_creates_table(monkeypatch, tmp_path):
    """init_db() should create the research_sessions table without error."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

    # Reset cached settings and engine
    from backend.core import config as cfg
    cfg.get_settings.cache_clear()

    import importlib
    import backend.core.database as db_module
    importlib.reload(db_module)

    await db_module.init_db()

    # Verify table exists by running a query
    from sqlalchemy.future import select
    async with db_module.AsyncSessionLocal() as session:
        result = await session.execute(select(db_module.ResearchSession))
        assert result.scalars().all() == []
