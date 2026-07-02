import "./PipelineStepper.css";

const LABELS = {
  planner: "Planner",
  search: "Search",
  ranker: "Ranker",
  summariser: "Summariser",
  gaps: "Gaps",
  writer: "Writer",
};

export default function PipelineStepper({ steps, order }) {
  return (
    <div className="stepper" role="list" aria-label="Research pipeline progress">
      {order.map((key, idx) => {
        const status = steps[key];
        const isLast = idx === order.length - 1;
        return (
          <div className="stepper-item" key={key} role="listitem">
            <div className="stepper-node-wrap">
              <div className={`stepper-node stepper-node--${status}`}>
                {status === "done" ? (
                  <CheckIcon />
                ) : status === "active" ? (
                  <span className="stepper-pulse-dot" />
                ) : (
                  <span className="stepper-index">{idx + 1}</span>
                )}
              </div>
              <span className={`stepper-label stepper-label--${status}`}>
                {LABELS[key]}
              </span>
            </div>
            {!isLast && (
              <div className="stepper-line-track">
                <div
                  className={`stepper-line-fill ${
                    status === "done" ? "stepper-line-fill--full" : ""
                  }`}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function CheckIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M3 8.5L6.2 11.7L13 4.5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
