import { useState, useEffect, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import QueryInput from "./components/QueryInput";
import SessionView from "./components/SessionView";
import { startResearch, getSession, listSessions, deleteSession } from "./lib/api";
import "./App.css";

export default function App() {
  const [sessions, setSessions] = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [activeId, setActiveId] = useState(null);
  const [activeSession, setActiveSession] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [loadError, setLoadError] = useState(null);

  const refreshSessions = useCallback(async () => {
    try {
      const data = await listSessions();
      setSessions(data);
      setLoadError(null);
    } catch (e) {
      setLoadError(
        "Couldn't reach the ResearchPilot backend. Make sure the server is running at " +
          "localhost:8000 (python main.py)."
      );
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  const refreshActiveSession = useCallback(async () => {
    if (!activeId) return;
    try {
      const data = await getSession(activeId);
      setActiveSession(data);
      // Also refresh the sidebar so status/paper count stay in sync
      refreshSessions();
    } catch {
      /* session may have been deleted */
    }
  }, [activeId, refreshSessions]);

  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    if (activeId) {
      refreshActiveSession();
    } else {
      setActiveSession(null);
    }
  }, [activeId, refreshActiveSession]);

  const handleSubmit = async (query) => {
    setSubmitting(true);
    try {
      const { session_id } = await startResearch(query);
      await refreshSessions();
      setActiveId(session_id);
    } catch (e) {
      setLoadError(e.message || "Failed to start research session.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleNew = () => {
    setActiveId(null);
  };

  const handleDelete = async (id) => {
    try {
      await deleteSession(id);
      if (id === activeId) {
        setActiveId(null);
      }
      refreshSessions();
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="app">
      <Sidebar
        sessions={sessions}
        activeId={activeId}
        onSelect={setActiveId}
        onNew={handleNew}
        onDelete={handleDelete}
        loading={sessionsLoading}
      />

      <main className="app-main">
        {loadError && (
          <div className="app-error-banner">
            <p>{loadError}</p>
          </div>
        )}

        {!activeSession ? (
          <QueryInput onSubmit={handleSubmit} submitting={submitting} />
        ) : (
          <SessionView session={activeSession} onRefresh={refreshActiveSession} />
        )}
      </main>
    </div>
  );
}
