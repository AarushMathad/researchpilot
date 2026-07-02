import { useState } from "react";
import "./QueryInput.css";

const EXAMPLES = [
  "Retrieval-augmented generation for long-document question answering",
  "Self-supervised learning methods for medical image segmentation",
  "Energy-efficient inference for large language models on edge devices",
];

export default function QueryInput({ onSubmit, submitting }) {
  const [value, setValue] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || submitting) return;
    onSubmit(trimmed);
  };

  return (
    <div className="query-screen">
      <div className="query-screen-inner fade-in">
        <div className="query-mark" aria-hidden="true" />
        <h1 className="query-title">What should ResearchPilot look into?</h1>
        <p className="query-subtitle">
          Give it a topic. It plans search queries, retrieves and ranks papers from Semantic
          Scholar and arXiv, summarises each one, identifies gaps in the literature, and writes
          a full review.
        </p>

        <form className="query-form" onSubmit={handleSubmit}>
          <textarea
            className="query-textarea"
            placeholder="e.g. transformer architectures for long-context NLP"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            rows={3}
            disabled={submitting}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                handleSubmit(e);
              }
            }}
          />
          <button className="query-submit" type="submit" disabled={!value.trim() || submitting}>
            {submitting ? "Starting…" : "Start research"}
            {!submitting && <ArrowIcon />}
          </button>
        </form>

        <div className="query-examples">
          <span className="query-examples-label">Try one of these</span>
          <div className="query-examples-list">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                className="query-example-chip"
                onClick={() => setValue(ex)}
                disabled={submitting}
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ArrowIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M3 8H13M13 8L9 4M13 8L9 12"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
