from __future__ import annotations

import json
import logging
import re

from langchain_google_genai import ChatGoogleGenerativeAI

from backend.core.config import get_settings
from backend.core.state import ResearchState

logger = logging.getLogger(__name__)

_SYSTEM = """You are an academic research planning assistant.
Always respond with valid JSON only — no markdown fences, no preamble."""

_PLAN_PROMPT = """Decompose the following research query into a structured research plan.

Query: {query}

Work through this in three stages inside a single JSON response:

1. Draft a plan
2. Critique it: are subtopics specific enough? are search queries varied and concise?
   are key concepts technically precise?
3. Produce a final improved version based on your critique

Return a single JSON object with these keys:
  subtopics: list of 3-5 specific subtopics (strings) — final version
  search_queries: list of {n_queries} distinct search queries (strings, 3-6 words each,
    no boolean operators, no quotes) — final version
  key_concepts: list of 5-10 key technical terms central to this query — final version
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


async def planner_agent(state: ResearchState) -> dict:
    settings = get_settings()
    llm = _make_llm()
    query = state["query"]
    errors = list(state["errors"])

    response = await llm.ainvoke([
        ("system", _SYSTEM),
        ("human", _PLAN_PROMPT.format(query=query, n_queries=settings.max_search_queries)),
    ])

    try:
        plan = json.loads(_clean_json(response.content))
    except json.JSONDecodeError as e:
        errors.append(f"[planner] Failed to parse plan JSON: {e}")
        logger.error("Planner JSON parse failed: %s", e)
        return {
            "subtopics": [query],
            "search_queries": [query],
            "key_concepts": [],
            "errors": errors,
            "current_agent": "search",
        }

    logger.info(
        "Planner complete: %d subtopics, %d queries. Critique: %s",
        len(plan.get("subtopics", [])),
        len(plan.get("search_queries", [])),
        plan.get("critique", "none"),
    )

    return {
        "subtopics": plan.get("subtopics", []),
        "search_queries": plan.get("search_queries", []),
        "key_concepts": plan.get("key_concepts", []),
        "errors": errors,
        "current_agent": "search",
    }
