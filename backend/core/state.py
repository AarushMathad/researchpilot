from __future__ import annotations

from typing import TypedDict


class Paper(TypedDict):
    paper_id: str           # Semantic Scholar ID (canonical)
    arxiv_id: str           # arXiv ID if available, else ""
    doi: str                # DOI if available, else ""
    title: str
    abstract: str
    authors: list[str]
    year: int
    venue: str
    citation_count: int
    open_access_pdf: str    # URL if available, else ""
    score: float            # computed by Ranker


class PaperSummary(TypedDict):
    paper_id: str
    title: str
    main_contribution: str
    methodology: str
    key_findings: str
    limitations: str
    relevance_to_query: str


class GapItem(TypedDict):
    title: str
    description: str
    evidence: str           # which papers support this gap claim
    suggested_direction: str


class EvaluationResult(TypedDict):
    relevance: float        # LLM-as-judge (self-reported)
    coverage: float         # deterministic
    paper_quality: float    # deterministic
    gap_quality: float      # LLM-as-judge (self-reported)
    coherence: float        # LLM-as-judge (self-reported)
    overall: float          # mean of above
    note: str               # reminds reader these are self-reported where applicable


class ResearchState(TypedDict):
    session_id: str
    query: str

    # Planner outputs
    subtopics: list[str]
    search_queries: list[str]
    key_concepts: list[str]

    # Search output
    raw_papers: list[Paper]

    # Ranker output
    ranked_papers: list[Paper]
    corpus_warning: bool    # True if len(raw_papers) < min_corpus_size

    # Summariser output
    summaries: list[PaperSummary]

    # Gaps output
    research_gaps: list[GapItem]

    # Writer output
    final_review: str

    # Pipeline bookkeeping
    status: str             # pending | running | complete | error
    current_agent: str
    errors: list[str]       # non-fatal warnings + fatal error (last item)
