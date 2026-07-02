import "./EvaluationPanel.css";

const DIMENSIONS = [
  { key: "relevance", label: "Relevance", selfReported: true },
  { key: "coverage", label: "Coverage", selfReported: false },
  { key: "paper_quality", label: "Paper quality", selfReported: false },
  { key: "gap_quality", label: "Gap quality", selfReported: true },
  { key: "coherence", label: "Coherence", selfReported: true },
];

export default function EvaluationPanel({ evaluation }) {
  if (!evaluation) return null;

  return (
    <div className="eval-panel fade-in">
      <div className="eval-panel-header">
        <h3 className="eval-panel-title">Quality evaluation</h3>
        <div className="eval-overall">
          <span className="eval-overall-value">{(evaluation.overall * 100).toFixed(0)}</span>
          <span className="eval-overall-unit">/ 100</span>
        </div>
      </div>

      <div className="eval-grid">
        {DIMENSIONS.map((d) => (
          <div className="eval-dim" key={d.key}>
            <div className="eval-dim-header">
              <span className="eval-dim-label">{d.label}</span>
              {d.selfReported && (
                <span className="eval-dim-tag" title="Scored by the same model that generated this review">
                  self-reported
                </span>
              )}
            </div>
            <div className="eval-bar-track">
              <div
                className="eval-bar-fill"
                style={{ width: `${(evaluation[d.key] ?? 0) * 100}%` }}
              />
            </div>
            <span className="eval-dim-value">{(evaluation[d.key] ?? 0).toFixed(2)}</span>
          </div>
        ))}
      </div>

      {evaluation.note && <p className="eval-note">{evaluation.note}</p>}
    </div>
  );
}
