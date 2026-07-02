import "./Sidebar.css";

export default function Sidebar({ sessions, activeId, onSelect, onNew, onDelete, loading }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <span className="sidebar-logo-mark" />
          <span className="sidebar-logo-text">ResearchPilot</span>
        </div>
        <button className="sidebar-new-btn" onClick={onNew}>
          <PlusIcon />
          New research
        </button>
      </div>

      <div className="sidebar-list">
        {loading && <div className="sidebar-empty">Loading sessions…</div>}

        {!loading && sessions.length === 0 && (
          <div className="sidebar-empty">
            No research sessions yet. Start one above.
          </div>
        )}

        {sessions.map((s) => (
          <div
            key={s.id}
            className={`sidebar-item ${s.id === activeId ? "sidebar-item--active" : ""}`}
            onClick={() => onSelect(s.id)}
          >
            <div className="sidebar-item-main">
              <p className="sidebar-item-query">{s.query}</p>
              <div className="sidebar-item-meta">
                <StatusDot status={s.status} />
                <span className="sidebar-item-status">{statusLabel(s.status)}</span>
                {s.corpus_warning && (
                  <span className="sidebar-item-warn" title="Few papers found">
                    ⚠
                  </span>
                )}
              </div>
            </div>
            <button
              className="sidebar-item-delete"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(s.id);
              }}
              aria-label="Delete session"
              title="Delete session"
            >
              <TrashIcon />
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}

function statusLabel(status) {
  switch (status) {
    case "complete":
      return "Complete";
    case "running":
      return "Running";
    case "error":
      return "Error";
    case "pending":
      return "Queued";
    default:
      return status;
  }
}

function StatusDot({ status }) {
  return <span className={`status-dot status-dot--${status}`} />;
}

function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M8 2V14M2 8H14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M2 4H14M5.5 4V2.5C5.5 2.22386 5.72386 2 6 2H10C10.2761 2 10.5 2.22386 10.5 2.5V4M6.5 7.5V11.5M9.5 7.5V11.5M3.5 4L4 13C4 13.5523 4.44772 14 5 14H11C11.5523 14 12 13.5523 12 13L12.5 4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
