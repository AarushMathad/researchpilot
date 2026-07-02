import "./GapCard.css";

export default function GapCard({ gap, index }) {
  return (
    <div className="gap-card fade-in">
      <div className="gap-card-header">
        <span className="gap-card-index">{String(index + 1).padStart(2, "0")}</span>
        <h3 className="gap-card-title">{gap.title}</h3>
      </div>
      <p className="gap-card-description">{gap.description}</p>
      {gap.evidence && (
        <div className="gap-card-row">
          <span className="gap-card-label">Evidence</span>
          <p className="gap-card-text">{gap.evidence}</p>
        </div>
      )}
      {gap.suggested_direction && (
        <div className="gap-card-row gap-card-row--direction">
          <span className="gap-card-label">Direction</span>
          <p className="gap-card-text">{gap.suggested_direction}</p>
        </div>
      )}
    </div>
  );
}
