from __future__ import annotations

import json
import logging
import math
import re

from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.core.config import get_settings
from backend.core.database import ResearchSession
from backend.core.state import EvaluationResult

logger = logging.getLogger(__name__)

_SYSTEM = "You are an evaluation assistant. Always respond with valid JSON only — no markdown, no preamble."

_RELEVANCE_PROMPT = """Query: {query}

Literature review:
{review}

Score from 0.0 to 1.0: does the review directly address the query? 
Consider: correct domain, specific enough, does not drift into unrelated areas.

Return JSON: {{"score": float, "reason": "one sentence"}}"""

_GAP_QUALITY_PROMPT = """Query: {query}

Research gaps identified:
{gaps}

Score from 0.0 to 1.0: are the gaps specific, evidence-grounded, and actionable?
Penalise generic "more research is needed" statements.

Return JSON: {{"score": float, "reason": "one sentence"}}"""

_COHERENCE_PROMPT = """Literature review:
{review}

Score from 0.0 to 1.0: is the review well-structured, uses academic prose, 
properly introduces and concludes, and cites papers consistently?

Return JSON: {{"score": float, "reason": "one sentence"}}"""


def _make_llm() -> ChatGoogleGenerativeAI:
    s = get_settings()
    return ChatGoogleGenerativeAI(
        model=s.gemini_model,
        temperature=0.0,       # deterministic for evaluation
        google_api_key=s.gemini_api_key,
    )


def _clean(raw: str) -> str:
    return re.sub(r"```(?:json)?|```", "", raw).strip()


async def _llm_score(llm: ChatGoogleGenerativeAI, prompt: str) -> float:
    try:
        resp = await llm.ainvoke([("system", _SYSTEM), ("human", prompt)])
        data = json.loads(_clean(resp.content))
        return max(0.0, min(1.0, float(data.get("score", 0.5))))
    except Exception as e:
        logger.warning("LLM eval failed: %s", e)
        return 0.5


# --- Deterministic metrics ---

def _coverage_score(subtopics: list[str], review: str) -> float:
    """Fraction of planned subtopics that appear in the final review."""
    if not subtopics:
        return 1.0
    review_lower = review.lower()
    hits = sum(
        1 for s in subtopics
        if any(word in review_lower for word in s.lower().split() if len(word) > 4)
    )
    return hits / len(subtopics)


def _paper_quality_score(papers: list[dict]) -> float:
    """
    60% log-normalised citation quality (cited papers only) +
    20% citation coverage (fraction of papers with any citations) +
    20% recency bonus (fraction of papers from last 5 years)
    """
    if not papers:
        return 0.0

    from datetime import datetime
    current_year = datetime.now().year

    cited = [p for p in papers if p.get("citation_count", 0) > 0]
    max_cit = max((p["citation_count"] for p in cited), default=1)

    cit_quality = (
        sum(math.log1p(p["citation_count"]) / math.log1p(max_cit) for p in cited) / len(papers)
        if cited else 0.0
    )
    cit_coverage = len(cited) / len(papers)
    recency = sum(
        1 for p in papers if (p.get("year") or 0) >= current_year - 5
    ) / len(papers)

    return 0.60 * cit_quality + 0.20 * cit_coverage + 0.20 * recency


# --- Main evaluation function ---

async def run_evaluation(session_id: str, db: AsyncSession) -> dict:
    result = await db.execute(
        select(ResearchSession).where(ResearchSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise ValueError(f"Session {session_id} not found")

    # Return cached result if already evaluated
    cached = session.get_json("evaluation")
    if cached:
        return cached

    review = session.final_review or ""
    subtopics = session.get_json("subtopics") or []
    gaps = session.get_json("research_gaps") or []
    papers = session.get_json("ranked_papers") or []
    query = session.query

    llm = _make_llm()

    # LLM-as-judge scores (self-reported — same model that generated the output)
    relevance, gap_quality, coherence = 0.5, 0.5, 0.5
    if review:
        gaps_text = "\n".join(
            f"- {g.get('title', '')}: {g.get('description', '')}" for g in gaps
        )
        relevance, gap_quality, coherence = [
            await _llm_score(llm, p) for p in [
                _RELEVANCE_PROMPT.format(query=query, review=review[:3000]),
                _GAP_QUALITY_PROMPT.format(query=query, gaps=gaps_text),
                _COHERENCE_PROMPT.format(review=review[:3000]),
            ]
        ]

    # Deterministic scores
    coverage = _coverage_score(subtopics, review)
    paper_quality = _paper_quality_score(papers)

    overall = round((relevance + coverage + paper_quality + gap_quality + coherence) / 5, 3)

    evaluation = EvaluationResult(
        relevance=round(relevance, 3),
        coverage=round(coverage, 3),
        paper_quality=round(paper_quality, 3),
        gap_quality=round(gap_quality, 3),
        coherence=round(coherence, 3),
        overall=overall,
        note=(
            "relevance, gap_quality, and coherence are self-reported — scored by the same "
            "model that generated this review. coverage and paper_quality are deterministic."
        ),
    )

    # Cache in DB
    session.set_json("evaluation", dict(evaluation))
    await db.commit()

    return dict(evaluation)
