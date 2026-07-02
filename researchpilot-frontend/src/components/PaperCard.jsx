import "./PaperCard.css";

export default function PaperCard({ paper, summary }) {
  const authors = paper.authors?.slice(0, 3).join(", ") || "Unknown authors";
  const moreAuthors = paper.authors?.length > 3 ? ` +${paper.authors.length - 3}` : "";

  return (
    <div className="paper-card fade-in">
      <div className="paper-card-header">
        <h3 className="paper-card-title">{paper.title}</h3>
        <div className="paper-card-score" title="Ranking score">
          {paper.score?.toFixed(2)}
        </div>
      </div>

      <div className="paper-card-meta">
        <span>{authors}{moreAuthors}</span>
        <span className="paper-card-dot">·</span>
        <span>{paper.year || "n.d."}</span>
        {paper.venue && (
          <>
            <span className="paper-card-dot">·</span>
            <span className="paper-card-venue">{paper.venue}</span>
          </>
        )}
        {paper.citation_count > 0 && (
          <>
            <span className="paper-card-dot">·</span>
            <span>{paper.citation_count} citations</span>
          </>
        )}
      </div>

      {summary && (
        <div className="paper-card-summary">
          <SummaryRow label="Contribution" text={summary.main_contribution} />
          <SummaryRow label="Method" text={summary.methodology} />
          <SummaryRow label="Findings" text={summary.key_findings} />
          {summary.limitations && (
            <SummaryRow label="Limitations" text={summary.limitations} muted />
          )}
        </div>
      )}

      {(paper.open_access_pdf || paper.doi) && (
        <div className="paper-card-links">
          {paper.open_access_pdf && (
            <a href={paper.open_access_pdf} target="_blank" rel="noreferrer">
              PDF ↗
            </a>
          )}
          {paper.doi && (
            <a href={`https://doi.org/${paper.doi}`} target="_blank" rel="noreferrer">
              DOI ↗
            </a>
          )}
        </div>
      )}
    </div>
  );
}

function SummaryRow({ label, text, muted }) {
  if (!text) return null;
  return (
    <div className="paper-summary-row">
      <span className="paper-summary-label">{label}</span>
      <p className={`paper-summary-text ${muted ? "paper-summary-text--muted" : ""}`}>
        {text}
      </p>
    </div>
  );
}
