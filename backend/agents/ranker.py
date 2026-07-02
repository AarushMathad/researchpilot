from __future__ import annotations

import logging
import math
from datetime import datetime
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from backend.core.config import get_settings, get_venue_tiers
from backend.core.state import Paper, ResearchState

logger = logging.getLogger(__name__)

CURRENT_YEAR = datetime.now().year
RECENCY_BASE_YEAR = 2010


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    settings = get_settings()
    return SentenceTransformer(settings.embedding_model)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _semantic_scores(query: str, papers: list[Paper]) -> list[float]:
    model = _get_model()
    texts = [f"{p['title']} {p['abstract']}" for p in papers]
    embeddings = model.encode([query] + texts, show_progress_bar=False)
    query_emb = embeddings[0].tolist()
    return [_cosine(query_emb, e.tolist()) for e in embeddings[1:]]


def _citation_score(papers: list[Paper]) -> list[float]:
    """Log-normalised against the max citation count in the set."""
    counts = [p["citation_count"] for p in papers]
    max_count = max(counts) if any(c > 0 for c in counts) else 1
    scores: list[float] = []
    for c in counts:
        if c == 0:
            scores.append(0.0)
        else:
            scores.append(math.log1p(c) / math.log1p(max_count))
    return scores


def _recency_score(year: int) -> float:
    if year <= 0:
        return 0.0
    clamped = max(RECENCY_BASE_YEAR, min(year, CURRENT_YEAR))
    span = CURRENT_YEAR - RECENCY_BASE_YEAR or 1
    return (clamped - RECENCY_BASE_YEAR) / span


def _venue_score(venue: str) -> float:
    tiers = get_venue_tiers()
    key = venue.lower().strip()
    # Try exact match, then substring match
    if key in tiers:
        return tiers[key]
    for tier_name, score in tiers.items():
        if tier_name in key or key in tier_name:
            return score
    return 0.3  # unknown venue


def rank_papers(query: str, papers: list[Paper]) -> list[Paper]:
    if not papers:
        return []

    settings = get_settings()
    w_sem = settings.rank_weight_semantic
    w_cit = settings.rank_weight_citation
    w_rec = settings.rank_weight_recency
    w_ven = settings.rank_weight_venue

    semantic = _semantic_scores(query, papers)
    citation = _citation_score(papers)

    scored: list[Paper] = []
    for i, p in enumerate(papers):
        score = (
            w_sem * semantic[i]
            + w_cit * citation[i]
            + w_rec * _recency_score(p["year"])
            + w_ven * _venue_score(p["venue"])
        )
        scored.append({**p, "score": round(score, 4)})  # type: ignore[misc]

    return sorted(scored, key=lambda x: x["score"], reverse=True)


async def ranker_agent(state: ResearchState) -> dict:
    settings = get_settings()
    papers = state["raw_papers"]
    errors = list(state["errors"])
    corpus_warning = False

    if len(papers) < settings.min_corpus_size:
        msg = (
            f"Only {len(papers)} paper(s) found — fewer than the minimum of "
            f"{settings.min_corpus_size}. The review may be shallow. "
            "Consider broadening your query or lowering MIN_CORPUS_SIZE."
        )
        errors.append(f"[corpus_warning] {msg}")
        corpus_warning = True
        logger.warning(msg)

    ranked = rank_papers(state["query"], papers)
    top_k = ranked[: settings.top_k_papers]

    logger.info("Ranker: %d → top %d papers selected", len(papers), len(top_k))

    return {
        "ranked_papers": top_k,
        "corpus_warning": corpus_warning,
        "errors": errors,
        "current_agent": "summariser",
    }
