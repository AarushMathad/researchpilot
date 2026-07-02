const BASE = "/api";

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function startResearch(query) {
  const res = await fetch(`${BASE}/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  return handle(res);
}

export async function getSession(sessionId) {
  const res = await fetch(`${BASE}/research/${sessionId}`);
  return handle(res);
}

export async function listSessions() {
  const res = await fetch(`${BASE}/sessions`);
  return handle(res);
}

export async function deleteSession(sessionId) {
  const res = await fetch(`${BASE}/research/${sessionId}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) {
    throw new Error(res.statusText);
  }
}

export async function getEvaluation(sessionId) {
  const res = await fetch(`${BASE}/research/${sessionId}/evaluate`);
  return handle(res);
}

/**
 * Opens an SSE connection to the pipeline stream.
 * Calls onEvent(eventObj) for each event, onError on failure.
 * Returns a cleanup function to close the connection.
 */
export function streamSession(sessionId, onEvent, onError) {
  const source = new EventSource(`${BASE}/research/${sessionId}/stream`);

  source.onmessage = (e) => {
    try {
      const parsed = JSON.parse(e.data);
      onEvent(parsed);
    } catch (err) {
      console.error("Failed to parse SSE event", err);
    }
  };

  source.onerror = (e) => {
    onError?.(e);
  };

  return () => source.close();
}
