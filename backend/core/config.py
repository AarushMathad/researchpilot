from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Required
    gemini_api_key: str

    # Model
    gemini_model: str = "gemini-2.5-flash-lite"
    gemini_temperature: float = 0.1

    # Search
    semantic_scholar_api_key: str = ""
    max_papers_per_query: int = 5
    max_search_queries: int = 3

    # Pipeline
    top_k_papers: int = 8
    summarizer_batch_size: int = 3
    reflection_threshold: float = 0.65
    min_corpus_size: int = 4

    # Ranking weights
    rank_weight_semantic: float = 0.40
    rank_weight_citation: float = 0.30
    rank_weight_recency: float = 0.20
    rank_weight_venue: float = 0.10

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"

    # Database
    database_url: str = "sqlite+aiosqlite:///./research_pilot.db"

    # SSE
    sse_queue_ttl_seconds: int = 600

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "Settings":
        total = (
            self.rank_weight_semantic
            + self.rank_weight_citation
            + self.rank_weight_recency
            + self.rank_weight_venue
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Ranking weights must sum to 1.0, got {total:.4f}. "
                "Check RANK_WEIGHT_* in your .env file."
            )
        return self

    @field_validator("reflection_threshold")
    @classmethod
    def threshold_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("REFLECTION_THRESHOLD must be between 0.0 and 1.0")
        return v


def load_venue_tiers() -> dict[str, float]:
    """Load venue_tiers.json and return a flat {venue_name: score} dict."""
    path = Path(__file__).parent.parent.parent / "venue_tiers.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    tiers: dict[str, float] = {}
    for name in data.get("tier_1", []):
        tiers[name.lower()] = 1.0
    for name in data.get("tier_2", []):
        tiers[name.lower()] = 0.8
    for name in data.get("proceedings", []):
        tiers[name.lower()] = 0.6
    return tiers


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_venue_tiers() -> dict[str, float]:
    return load_venue_tiers()
