from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.core.config import get_settings
from backend.core.state import Paper, ResearchState

logger = logging.getLogger(__name__)

_SS_BASE = "https://api.semanticscholar.org/graph/v1"
_ARXIV_BASE = "http://export.arxiv.org/api/query"

_SS_FIELDS = "paperId,externalIds,title,abstract,authors,year,venue,citationCount,openAccessPdf"


def _make_headers() -> dict[str, str]:
    settings = get_settings()
    h: dict[str, str] = {}
    if settings.semantic_scholar_api_key:
        h["x-api-key"] = settings.semantic_scholar_api_key
    return h


# --- Semantic Scholar ---

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _ss_search(client: httpx.AsyncClient, query: str, limit: int) -> list[dict[str, Any]]:
    resp = await client.get(
        f"{_SS_BASE}/paper/search",
        params={"query": query, "limit": limit, "fields": _SS_FIELDS},
        headers=_make_headers(),
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _ss_paper_by_arxiv(client: httpx.AsyncClient, arxiv_id: str) -> dict[str, Any] | None:
    """Fetch citation count for an arXiv paper via Semantic Scholar."""
    try:
        resp = await client.get(
            f"{_SS_BASE}/paper/arXiv:{arxiv_id}",
            params={"fields": "citationCount"},
            headers=_make_headers(),
            timeout=10.0,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _parse_ss_paper(raw: dict[str, Any]) -> Paper:
    ext = raw.get("externalIds") or {}
    oa = raw.get("openAccessPdf") or {}
    authors = [a.get("name", "") for a in (raw.get("authors") or [])]
    return Paper(
        paper_id=raw.get("paperId", ""),
        arxiv_id=ext.get("ArXiv", ""),
        doi=ext.get("DOI", ""),
        title=raw.get("title", ""),
        abstract=raw.get("abstract", "") or "",
        authors=authors,
        year=raw.get("year") or 0,
        venue=raw.get("venue", "") or "",
        citation_count=raw.get("citationCount") or 0,
        open_access_pdf=oa.get("url", "") if oa else "",
        score=0.0,
    )


# --- arXiv ---

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _arxiv_search(client: httpx.AsyncClient, query: str, limit: int) -> list[Paper]:
    resp = await client.get(
        _ARXIV_BASE,
        params={"search_query": f"all:{query}", "max_results": limit, "sortBy": "relevance"},
        timeout=15.0,
    )
    resp.raise_for_status()
    return _parse_arxiv_feed(resp.text)


def _parse_arxiv_feed(xml: str) -> list[Paper]:
    papers: list[Paper] = []
    entries = re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL)
    for entry in entries:
        def _tag(name: str) -> str:
            m = re.search(rf"<{name}[^>]*>(.*?)</{name}>", entry, re.DOTALL)
            return m.group(1).strip() if m else ""

        arxiv_url = _tag("id")
        arxiv_id = arxiv_url.split("/abs/")[-1].strip() if "/abs/" in arxiv_url else ""
        authors = re.findall(r"<name>(.*?)</name>", entry)
        year_m = re.search(r"<published>(\d{4})", entry)
        year = int(year_m.group(1)) if year_m else 0
        papers.append(Paper(
            paper_id="",           # will be assigned after dedup
            arxiv_id=arxiv_id,
            doi="",
            title=_tag("title").replace("\n", " "),
            abstract=_tag("summary").replace("\n", " "),
            authors=authors,
            year=year,
            venue="arXiv",
            citation_count=0,      # enriched later
            open_access_pdf=f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else "",
            score=0.0,
        ))
    return papers


# --- Deduplication ---

def _normalise_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def _deduplicate(papers: list[Paper]) -> list[Paper]:
    """Priority: DOI → arXiv ID → normalised title. Keep first seen (SS results first)."""
    seen_doi: set[str] = set()
    seen_arxiv: set[str] = set()
    seen_title: set[str] = set()
    result: list[Paper] = []

    for p in papers:
        if p["doi"] and p["doi"] in seen_doi:
            continue
        if p["arxiv_id"] and p["arxiv_id"] in seen_arxiv:
            continue
        norm = _normalise_title(p["title"])
        if norm and norm in seen_title:
            continue

        if p["doi"]:
            seen_doi.add(p["doi"])
        if p["arxiv_id"]:
            seen_arxiv.add(p["arxiv_id"])
        if norm:
            seen_title.add(norm)
        result.append(p)

    return result


# --- Enrichment: arXiv citation count via Semantic Scholar ---

async def _enrich_arxiv_citations(client: httpx.AsyncClient, papers: list[Paper]) -> list[Paper]:
    arxiv_papers = [p for p in papers if p["arxiv_id"] and p["citation_count"] == 0]
    if not arxiv_papers:
        return papers

    tasks = [_ss_paper_by_arxiv(client, p["arxiv_id"]) for p in arxiv_papers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    enriched_map: dict[str, int] = {}
    for paper, result in zip(arxiv_papers, results):
        if isinstance(result, dict) and result:
            enriched_map[paper["arxiv_id"]] = result.get("citationCount") or 0

    updated: list[Paper] = []
    for p in papers:
        if p["arxiv_id"] in enriched_map:
            p = dict(p)  # type: ignore[assignment]
            p["citation_count"] = enriched_map[p["arxiv_id"]]  # type: ignore[index]
        updated.append(p)  # type: ignore[arg-type]

    return updated


# --- Agent entry point ---

async def search_agent(state: ResearchState) -> dict:
    settings = get_settings()
    queries = state["search_queries"][: settings.max_search_queries]
    limit = settings.max_papers_per_query

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Run all queries against both sources concurrently
        ss_tasks = [_ss_search(client, q, limit) for q in queries]
        arxiv_tasks = [_arxiv_search(client, q, limit) for q in queries]

        all_results = await asyncio.gather(*ss_tasks, *arxiv_tasks, return_exceptions=True)

        ss_results = all_results[: len(queries)]
        arxiv_results = all_results[len(queries):]

        papers: list[Paper] = []
        errors: list[str] = list(state["errors"])

        for i, res in enumerate(ss_results):
            if isinstance(res, Exception):
                errors.append(f"[search] Semantic Scholar query {i} failed: {res}")
                logger.warning("SS query %d failed: %s", i, res)
            else:
                papers.extend([_parse_ss_paper(r) for r in res if r.get("title")])

        for i, res in enumerate(arxiv_results):
            if isinstance(res, Exception):
                errors.append(f"[search] arXiv query {i} failed: {res}")
                logger.warning("arXiv query %d failed: %s", i, res)
            else:
                papers.extend(res)

        # Deduplicate (SS first = priority)
        papers = _deduplicate(papers)

        # Assign paper_id for arXiv-only papers (no SS ID)
        for idx, p in enumerate(papers):
            if not p["paper_id"]:
                papers[idx] = {**p, "paper_id": f"arxiv_{p['arxiv_id'] or idx}"}  # type: ignore[misc]

        # Enrich arXiv citation counts
        papers = await _enrich_arxiv_citations(client, papers)

    logger.info("Search complete: %d papers after dedup", len(papers))

    return {
        "raw_papers": papers,
        "errors": errors,
        "current_agent": "ranker",
    }
