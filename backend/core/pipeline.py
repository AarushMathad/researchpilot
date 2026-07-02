from __future__ import annotations

import logging
from typing import AsyncIterator

from langgraph.graph import END, StateGraph

from backend.agents.gaps import gaps_agent
from backend.agents.planner import planner_agent
from backend.agents.ranker import ranker_agent
from backend.agents.search import search_agent
from backend.agents.summariser import summariser_agent
from backend.agents.writer import writer_agent
from backend.core.state import ResearchState

logger = logging.getLogger(__name__)


def _build_graph() -> StateGraph:
    graph = StateGraph(ResearchState)

    graph.add_node("planner", planner_agent)
    graph.add_node("search", search_agent)
    graph.add_node("ranker", ranker_agent)
    graph.add_node("summariser", summariser_agent)
    graph.add_node("gaps", gaps_agent)
    graph.add_node("writer", writer_agent)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "search")
    graph.add_edge("search", "ranker")
    graph.add_edge("ranker", "summariser")
    graph.add_edge("summariser", "gaps")
    graph.add_edge("gaps", "writer")
    graph.add_edge("writer", END)

    return graph


_compiled = _build_graph().compile()

# Node order mirrors the graph edges — used to name SSE step events
PIPELINE_STEPS = ["planner", "search", "ranker", "summariser", "gaps", "writer"]


async def run_pipeline(initial_state: ResearchState) -> AsyncIterator[tuple[str, ResearchState]]:
    """
    Yields (node_name, full_state_after_node) for each completed node.

    Uses stream_mode='values' so LangGraph returns the complete merged state
    after each node — no manual accumulation needed.
    """
    async for state in _compiled.astream(initial_state, stream_mode="values"):
        current = state.get("current_agent", "unknown")
        yield current, state
