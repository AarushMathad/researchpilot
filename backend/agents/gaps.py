from __future__ import annotations

import json
import logging
import re

from langchain_google_genai import ChatGoogleGenerativeAI

from backend.core.config import get_settings
from backend.core.state import GapItem, PaperSummary, ResearchState

logger = logging.getLogger(__name__)

_SYSTEM = """You are a research analyst identifying gaps in academic literature.
Always respond with valid JSON only — no markdown fences, no preamble."""

_GAPS_PROMPT = """You have been given summaries of the top academic papers on this topic:

Query: {query}
Key concepts: {concepts}

Paper summaries:
{summaries_block}

Work through this in three stages inside a single JSON response:

1. Draft 3-5 research gaps
2. Critique them: are they specific and concrete? is each one grounded in the papers above?
   does each suggested direction give a researcher a real starting point?
3. Produce a final improved set based on your critique

Return a single JSON object with these keys:
  gaps: array of gap objects, each with:
    title: short name for this gap (5-10 words)
    description: what is missing or underexplored (2-3 sentences)
    evidence: which papers (by title) support this gap claim
    suggested_direction: one concrete way a researcher could address this gap
  critique: one sentence describing what you improved (for logging)"""


def _make_llm() -> ChatGoogleGenerativeAI:
    s = get_settings()
    return ChatGoogleGenerativeAI(
        model=s.gemini_model,
        temperature=s.gemini_temperature,
        google_api_key=s.gemini_api_key,
    )


def _clean_json(raw: str) -> str:
    return re.sub(r"```(?:json)?|```", "", raw).strip()


def _format_summaries(summaries: list[PaperSummary]) -> str:
    parts = []
    for s in summaries:
        parts.append(
            f"Title: {s['title']}\n"
            f"  Contribution: {s['main_contribution']}\n"
            f"  Methodology: {s['methodology']}\n"
            f"  Findings: {s['key_findings']}\n"
            f"  Limitations: {s['limitations']}"
        )
    return "\n\n".join(parts)


async def gaps_agent(state: ResearchState) -> dict:
    llm = _make_llm()
    errors = list(state["errors"])

    response = await llm.ainvoke([
        ("system", _SYSTEM),
        ("human", _GAPS_PROMPT.format(
            query=state["query"],
            concepts=", ".join(state["key_concepts"]),
            summaries_block=_format_summaries(state["summaries"]),
        )),
    ])

    try:
        result = json.loads(_clean_json(response.content))
    except json.JSONDecodeError as e:
        errors.append(f"[gaps] Failed to parse gaps JSON: {e}")
        logger.error("Gaps JSON parse failed: %s", e)
        return {
            "research_gaps": [],
            "errors": errors,
            "current_agent": "writer",
        }

    gaps_data = result.get("gaps", result if isinstance(result, list) else [])

    gaps: list[GapItem] = [
        GapItem(
            title=item.get("title", ""),
            description=item.get("description", ""),
            evidence=item.get("evidence", ""),
            suggested_direction=item.get("suggested_direction", ""),
        )
        for item in gaps_data
    ]

    logger.info(
        "Gaps agent: %d gaps identified. Critique: %s",
        len(gaps),
        result.get("critique", "none"),
    )

    return {
        "research_gaps": gaps,
        "errors": errors,
        "current_agent": "writer",
    }
