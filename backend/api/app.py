from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.core.config import get_settings
from backend.core.database import ResearchSession, get_db, init_db
from backend.core.emitter import emitter
from backend.core.pipeline import PIPELINE_STEPS, run_pipeline
from backend.core.state import ResearchState
from backend.evaluation.evaluator import run_evaluation

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialised")
    yield


app = FastAPI(title="ResearchPilot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request / response models ---

class StartResearchRequest(BaseModel):
    query: str


class SessionSummary(BaseModel):
    id: str
    query: str
    status: str
    current_agent: str
    corpus_warning: bool
    paper_count: int
    created_at: str
    completed_at: str | None


# --- Pipeline background task ---

async def _run_pipeline_task(session_id: str, query: str) -> None:
    """Runs the full pipeline, writes state to DB after each node, triggers eval on completion."""
    from backend.core.database import AsyncSessionLocal

    initial_state = ResearchState(
        session_id=session_id,
        query=query,
        subtopics=[],
        search_queries=[],
        key_concepts=[],
        raw_papers=[],
        ranked_papers=[],
        corpus_warning=False,
        summaries=[],
        research_gaps=[],
        final_review="",
        status="running",
        current_agent="planner",
        errors=[],
    )

    await emitter.emit(session_id, "pipeline_start", {"session_id": session_id, "query": query})

    try:
        async for node_name, state in run_pipeline(initial_state):
            # Persist after each node
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(ResearchSession).where(ResearchSession.id == session_id)
                )
                session = result.scalar_one_or_none()
                if session:
                    session.current_agent = node_name
                    session.status = state.get("status", "running")
                    session.corpus_warning = state.get("corpus_warning", False)
                    session.set_json("errors", state.get("errors", []))
                    session.set_json("subtopics", state.get("subtopics", []))
                    session.set_json("search_queries", state.get("search_queries", []))
                    session.set_json("key_concepts", state.get("key_concepts", []))
                    session.set_json("ranked_papers", state.get("ranked_papers", []))
                    session.set_json("summaries", state.get("summaries", []))
                    session.set_json("research_gaps", state.get("research_gaps", []))
                    session.final_review = state.get("final_review", "")
                    if state.get("status") in ("complete", "error"):
                        session.completed_at = datetime.utcnow()
                    await db.commit()

            # Emit SSE step event
            await emitter.emit(session_id, "step_complete", {
                "node": node_name,
                "status": state.get("status", "running"),
                "corpus_warning": state.get("corpus_warning", False),
                "errors": state.get("errors", []),
            })

            # Emit corpus warning SSE if flagged
            if state.get("corpus_warning") and node_name == "ranker":
                await emitter.emit(session_id, "warning", {
                    "code": "corpus_too_small",
                    "message": (
                        f"Only {len(state.get('raw_papers', []))} paper(s) found. "
                        "The review may be shallow. Consider broadening your query."
                    ),
                })

        # DB commit is done inside the loop above; now emit complete
        await emitter.emit(session_id, "complete", {"session_id": session_id})

        # Auto-trigger evaluation (fire-and-forget, non-blocking)
        #asyncio.create_task(_auto_evaluate(session_id))

    except Exception as e:
        logger.exception("Pipeline failed for session %s: %s", session_id, e)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ResearchSession).where(ResearchSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            if session:
                session.status = "error"
                errors = session.get_json("errors") or []
                errors.append(f"[pipeline] Fatal: {e}")
                session.set_json("errors", errors)
                session.completed_at = datetime.utcnow()
                await db.commit()
        await emitter.emit(session_id, "error", {"message": str(e)})


async def _auto_evaluate(session_id: str) -> None:
    """Run evaluation automatically after completion. Results cached in DB."""
    from backend.core.database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as db:
            await run_evaluation(session_id, db)
        logger.info("Auto-evaluation complete for session %s", session_id)
    except Exception as e:
        logger.warning("Auto-evaluation failed for session %s: %s", session_id, e)


# --- Endpoints ---

@app.post("/api/research", status_code=202)
async def start_research(
    body: StartResearchRequest,
    db: AsyncSession = Depends(get_db),
):
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query must not be empty.")

    session_id = str(uuid.uuid4())
    session = ResearchSession(id=session_id, query=query, status="pending")
    db.add(session)
    await db.commit()

    # Launch pipeline as a background task — return session_id immediately
    asyncio.create_task(_run_pipeline_task(session_id, query))

    return {"session_id": session_id}


@app.get("/api/research/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ResearchSession).where(ResearchSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    return {
        "id": session.id,
        "query": session.query,
        "status": session.status,
        "current_agent": session.current_agent,
        "corpus_warning": session.corpus_warning,
        "errors": session.get_json("errors"),
        "subtopics": session.get_json("subtopics"),
        "search_queries": session.get_json("search_queries"),
        "key_concepts": session.get_json("key_concepts"),
        "ranked_papers": session.get_json("ranked_papers"),
        "summaries": session.get_json("summaries"),
        "research_gaps": session.get_json("research_gaps"),
        "final_review": session.final_review,
        "evaluation": session.get_json("evaluation"),
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
    }


@app.get("/api/research/{session_id}/stream")
async def stream_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ResearchSession).where(ResearchSession.id == session_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found.")

    return StreamingResponse(
        emitter.subscribe(session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/research/{session_id}/papers")
async def get_papers(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ResearchSession).where(ResearchSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"papers": session.get_json("ranked_papers")}


@app.get("/api/research/{session_id}/report")
async def get_report(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ResearchSession).where(ResearchSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {
        "final_review": session.final_review,
        "research_gaps": session.get_json("research_gaps"),
    }


@app.get("/api/research/{session_id}/evaluate")
async def get_evaluation(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ResearchSession).where(ResearchSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Return cached result if already run
    cached = session.get_json("evaluation")
    if cached:
        return cached

    # Otherwise run now (idempotent — also runs automatically post-completion)
    evaluation = await run_evaluation(session_id, db)
    return evaluation


@app.get("/api/sessions")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ResearchSession).order_by(ResearchSession.created_at.desc()).limit(50)
    )
    sessions = result.scalars().all()
    return [
        SessionSummary(
            id=s.id,
            query=s.query,
            status=s.status,
            current_agent=s.current_agent,
            corpus_warning=s.corpus_warning,
            paper_count=len(s.get_json("ranked_papers") or []),
            created_at=s.created_at.isoformat() if s.created_at else "",
            completed_at=s.completed_at.isoformat() if s.completed_at else None,
        )
        for s in sessions
    ]


@app.delete("/api/research/{session_id}", status_code=204)
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ResearchSession).where(ResearchSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    await db.delete(session)
    await db.commit()
