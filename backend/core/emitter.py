from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field

from backend.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class _SessionQueue:
    events: list[dict] = field(default_factory=list)
    listeners: list[asyncio.Queue] = field(default_factory=list)
    completed_at: float | None = None   # epoch seconds when session reached terminal state


class ProgressEmitter:
    """Singleton. Manages per-session SSE event queues with replay and TTL cleanup."""

    def __init__(self) -> None:
        self._sessions: dict[str, _SessionQueue] = defaultdict(_SessionQueue)
        self._lock = asyncio.Lock()

    async def emit(self, session_id: str, event_type: str, data: dict) -> None:
        event = {"type": event_type, "data": data, "ts": time.time()}
        async with self._lock:
            sq = self._sessions[session_id]
            sq.events.append(event)
            for q in sq.listeners:
                await q.put(event)

        if event_type in ("complete", "error"):
            await self._mark_complete(session_id)

    async def _mark_complete(self, session_id: str) -> None:
        async with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].completed_at = time.time()
        asyncio.create_task(self._schedule_cleanup(session_id))

    async def _schedule_cleanup(self, session_id: str) -> None:
        ttl = get_settings().sse_queue_ttl_seconds
        await asyncio.sleep(ttl)
        async with self._lock:
            self._sessions.pop(session_id, None)
        logger.debug("SSE queue cleaned up for session %s", session_id)

    async def subscribe(self, session_id: str) -> asyncio.AsyncGenerator[str, None]:
        """Async generator yielding SSE-formatted strings. Replays history on connect."""
        q: asyncio.Queue = asyncio.Queue()

        async with self._lock:
            sq = self._sessions[session_id]
            # Replay history
            history = list(sq.events)
            sq.listeners.append(q)

        try:
            # Send all past events immediately
            for event in history:
                yield _format_sse(event)

            # If already completed, we're done
            if history and history[-1]["type"] in ("complete", "error"):
                return

            # Stream future events
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield _format_sse(event)
                    if event["type"] in ("complete", "error"):
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            async with self._lock:
                sq = self._sessions.get(session_id)
                if sq and q in sq.listeners:
                    sq.listeners.remove(q)


def _format_sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


# Module-level singleton
emitter = ProgressEmitter()
