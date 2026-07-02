from __future__ import annotations

import logging

from langchain_google_genai import ChatGoogleGenerativeAI

from backend.core.config import get_settings
from backend.core.state import ResearchState

logger = logging.getLogger(__name__)

_SYSTEM = """You are an academic writer producing a formal literature review.
Write in clear, precise, third-person academic prose. Use Markdown headings and paragraphs.
Do not use bullet points for the main body — prose only. Bullet points are acceptable only
in the Research Gaps section."""

_WRITER_PROMPT = """Write a comprehensive literature review based on the following research materials.

## Query
{query}

## Subtopics to cover
{subtopics}

## Key Concepts
{concepts}

## Paper Summaries
{summaries_block}

## Research Gaps
{gaps_block}

---

Structure the review as follows:
1. **Introduction** — frame the research area and why it matters
2. **{subtopic_sections}** — one section per subtopic, citing relevant papers by title and year
3. **Research Gaps and Future Directions** — synthesise the identified gaps; list each with its suggested direction
4. **Conclusion** — summarise the state of the field

Use in-text citations in the format (Author et al., Year) where authors are available.
Write at least 600 words. Be specific, not generic."""


def _format_summaries(state: ResearchState) -> str:
    parts = []
    for s in state["summaries"]:
        # Find the matching paper for author/year info
        paper = next(
            (p for p in state["ranked_papers"] if p["paper_id"] == s["paper_id"]),
            None,
        )
        if paper:
            authors = paper["authors"]
            first_author = authors[0].split()[-1] if authors else "Unknown"
            cite = f"{first_author} et al., {paper['year']}" if len(authors) > 1 else f"{first_author}, {paper['year']}"
        else:
            cite = "Unknown"

        parts.append(
            f"**{s['title']}** ({cite})\n"
            f"Contribution: {s['main_contribution']}\n"
            f"Methodology: {s['methodology']}\n"
            f"Findings: {s['key_findings']}\n"
            f"Limitations: {s['limitations']}"
        )
    return "\n\n".join(parts)


def _format_gaps(state: ResearchState) -> str:
    return "\n\n".join(
        f"Gap: {g['title']}\n"
        f"Description: {g['description']}\n"
        f"Evidence: {g['evidence']}\n"
        f"Direction: {g['suggested_direction']}"
        for g in state["research_gaps"]
    )


async def writer_agent(state: ResearchState) -> dict:
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        temperature=settings.gemini_temperature,
        google_api_key=settings.gemini_api_key,
    )

    subtopic_sections = " / ".join(state["subtopics"]) if state["subtopics"] else "Thematic Sections"
    concepts = ", ".join(state["key_concepts"])

    prompt = _WRITER_PROMPT.format(
        query=state["query"],
        subtopics="\n".join(f"- {s}" for s in state["subtopics"]),
        concepts=concepts,
        summaries_block=_format_summaries(state),
        gaps_block=_format_gaps(state),
        subtopic_sections=subtopic_sections,
    )

    errors = list(state["errors"])
    try:
        response = await llm.ainvoke([("system", _SYSTEM), ("human", prompt)])
        review = response.content
    except Exception as e:
        errors.append(f"[writer] Fatal: failed to generate review: {e}")
        logger.error("Writer failed: %s", e)
        review = ""

    logger.info("Writer complete: %d chars", len(review))

    return {
        "final_review": review,
        "errors": errors,
        "current_agent": "complete",
        "status": "complete" if review else "error",
    }
