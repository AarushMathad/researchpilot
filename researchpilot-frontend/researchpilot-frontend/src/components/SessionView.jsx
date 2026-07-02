import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import PipelineStepper from "./PipelineStepper";
import PaperCard from "./PaperCard";
import GapCard from "./GapCard";
import EvaluationPanel from "./EvaluationPanel";
import { usePipelineStream } from "../hooks/usePipelineStream";
import { getEvaluation } from "../lib/api";
import "./SessionView.css";

const TABS = [
  { key: "review", label: "Review" },
  { key: "papers", label: "Papers" },
  { key: "gaps", label: "Gaps" },
  { key: "evaluation", label: "Evaluation" },
];

export default function SessionView({ session, onRefresh }) {
  const [activeTab, setActiveTab] = useState("review");
  const [evaluation, setEvaluation] = useState(session.evaluation || null);

  const isRunning = session.status === "running" || session.status === "pending";

  const { steps, warnings, errors, isComplete, pipelineOrder } = usePipelineStream(
    isRunning ? session.id : null,
    { onComplete: onRefresh }
  );

  // If session already complete on load, show full stepper as done
  const displaySteps = isRunning
    ? steps
    : Object.fromEntries(pipelineOrder.map((k) => [k, "done"]));

  useEffect(() => {
    setEvaluation(session.evaluation || null);
  }, [session.id, session.evaluation]);

  useEffect(() => {
    if (!evaluation && session.status === "complete") {
      getEvaluation(session.id)
        .then(setEvaluation)
        .catch(() => {});
    }
  }, [session.id, session.status, evaluation]);

  const showResults = session.status === "complete" || (!isRunning && session.final_review);
  const allErrors = [...new Set([...(session.errors || []), ...errors])];
  const allWarnings = [...new Set(warnings)];

  return (
    <div className="session-view">
      <div className="session-header fade-in">
        <p className="session-eyebrow">Research query</p>
        <h1 className="session-query">{session.query}</h1>
      </div>

      <div className="session-pipeline fade-in">
        <PipelineStepper steps={displaySteps} order={pipelineOrder} />
        {isRunning && <p className="session-pipeline-status">Running pipeline…</p>}
        {session.status === "error" && (
          <p className="session-pipeline-status session-pipeline-status--error">
            Pipeline encountered an error
          </p>
        )}
      </div>

      {allWarnings.length > 0 && (
        <div className="session-banner session-banner--warn fade-in">
          {allWarnings.map((w, i) => (
            <p key={i}>{w}</p>
          ))}
        </div>
      )}

      {session.corpus_warning && allWarnings.length === 0 && (
        <div className="session-banner session-banner--warn fade-in">
          <p>
            Few papers were found for this query. The review below may be based on a small
            corpus — consider trying a broader query.
          </p>
        </div>
      )}

      {allErrors.length > 0 && session.status === "error" && (
        <div className="session-banner session-banner--error fade-in">
          {allErrors.map((e, i) => (
            <p key={i}>{e}</p>
          ))}
        </div>
      )}

      {showResults && (
        <div className="session-results fade-in">
          <div className="session-tabs">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                className={`session-tab ${activeTab === tab.key ? "session-tab--active" : ""}`}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label}
                {tab.key === "papers" && session.ranked_papers?.length > 0 && (
                  <span className="session-tab-count">{session.ranked_papers.length}</span>
                )}
                {tab.key === "gaps" && session.research_gaps?.length > 0 && (
                  <span className="session-tab-count">{session.research_gaps.length}</span>
                )}
              </button>
            ))}
          </div>

          <div className="session-tab-content">
            {activeTab === "review" && (
              <div className="review-content">
                {session.final_review ? (
                  <ReactMarkdown>{session.final_review}</ReactMarkdown>
                ) : (
                  <EmptyState text="No review was generated for this session." />
                )}
              </div>
            )}

            {activeTab === "papers" && (
              <div className="session-card-list">
                {session.ranked_papers?.length > 0 ? (
                  session.ranked_papers.map((paper) => {
                    const summary = session.summaries?.find(
                      (s) => s.paper_id === paper.paper_id
                    );
                    return <PaperCard key={paper.paper_id} paper={paper} summary={summary} />;
                  })
                ) : (
                  <EmptyState text="No papers were retrieved for this session." />
                )}
              </div>
            )}

            {activeTab === "gaps" && (
              <div className="session-card-list">
                {session.research_gaps?.length > 0 ? (
                  session.research_gaps.map((gap, i) => (
                    <GapCard key={i} gap={gap} index={i} />
                  ))
                ) : (
                  <EmptyState text="No research gaps were identified for this session." />
                )}
              </div>
            )}

            {activeTab === "evaluation" && (
              <div className="session-card-list">
                {evaluation ? (
                  <EvaluationPanel evaluation={evaluation} />
                ) : (
                  <EmptyState text="Evaluation runs automatically after the pipeline completes. Check back shortly." />
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function EmptyState({ text }) {
  return <div className="session-empty">{text}</div>;
}
