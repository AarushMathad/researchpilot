from __future__ import annotations

import asyncio
import json
import logging
import re

from langchain_google_genai import ChatGoogleGenerativeAI

from backend.core.config import get_settings
from backend.core.state import Paper, PaperSummary, ResearchState

logger = logging.getLogger(__name__)

_SYSTEM = """You are a research assistant producing structured summaries of academic papers.
Always respond with valid JSON only — no markdown fences, no preamble."""

_BATCH_PROMPT = """Summarise each of the following {n} academic papers as a JSON array.
Each element must have exactly these keys:
  paper_id, main_contribution, methodology, key_findings, limitations, relevance_to_query

Query context: {query}

Papers:
{papers_block}

Return ONLY a JSON array with {n} objects, one per paper, in the same order."""


def _make_llm() -> ChatGoogleGenerativeAI:
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        temperature=settings.gemini_temperature,
        google_api_key=settings.gemini_api_key,
    )


def _format_paper(p: Paper, idx: int) -> str:
    authors = ", ".join(p["authors"][:3]) + (" et al." if len(p["authors"]) > 3 else "")
    return (
        f"[{idx}] paper_id: {p['paper_id']}\n"
        f"Title: {p['title']}\n"
        f"Authors: {authors} ({p['year']})\n"
        f"Venue: {p['venue']}\n"
        f"Abstract: {p['abstract'][:800]}"
    )


def _parse_summaries(raw: str, batch: list[Paper]) -> list[PaperSummary]:
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        items = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning("JSON parse failed for batch: %s", e)
        return []

    summaries: list[PaperSummary] = []
    for item, paper in zip(items, batch):
        summaries.append(PaperSummary(
            paper_id=item.get("paper_id", paper["paper_id"]),
            title=paper["title"],
            main_contribution=item.get("main_contribution", ""),
            methodology=item.get("methodology", ""),
            key_findings=item.get("key_findings", ""),
            limitations=item.get("limitations", ""),
            relevance_to_query=item.get("relevance_to_query", ""),
        ))
    return summaries


async def _summarise_batch(
    llm: ChatGoogleGenerativeAI,
    batch: list[Paper],
    query: str,
    semaphore: asyncio.Semaphore,
) -> list[PaperSummary]:
    papers_block = "\n\n".join(_format_paper(p, i + 1) for i, p in enumerate(batch))
    prompt = _BATCH_PROMPT.format(n=len(batch), query=query, papers_block=papers_block)

    async with semaphore:
        try:
            response = await llm.ainvoke([
                ("system", _SYSTEM),
                ("human", prompt),
            ])
            return _parse_summaries(response.content, batch)
        except Exception as e:
            logger.error("Summariser batch failed: %s", e)
            return []


async def summariser_agent(state: ResearchState) -> dict:
    settings = get_settings()
    papers = state["ranked_papers"]
    query = state["query"]
    batch_size = settings.summarizer_batch_size

    llm = _make_llm()
    semaphore = asyncio.Semaphore(2)  # max 2 concurrent batch calls

    batches = [papers[i: i + batch_size] for i in range(0, len(papers), batch_size)]
    tasks = [_summarise_batch(llm, batch, query, semaphore) for batch in batches]
    results = await asyncio.gather(*tasks)

    summaries: list[PaperSummary] = []
    for batch_summaries in results:
        summaries.extend(batch_summaries)

    errors = list(state["errors"])
    if len(summaries) < len(papers):
        errors.append(
            f"[summariser] {len(papers) - len(summaries)} paper(s) failed to summarise "
            "and were skipped."
        )

    logger.info("Summariser: %d/%d papers summarised", len(summaries), len(papers))

    return {
        "summaries": summaries,
        "errors": errors,
        "current_agent": "gaps",
    }
