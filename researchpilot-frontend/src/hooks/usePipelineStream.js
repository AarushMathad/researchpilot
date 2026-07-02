import { useEffect, useRef, useState } from "react";
import { streamSession } from "../lib/api";

const PIPELINE_ORDER = ["planner", "search", "ranker", "summariser", "gaps", "writer"];

/**
 * Subscribes to a session's SSE stream and tracks pipeline progress.
 * Returns: { steps, warnings, errors, isComplete, isError }
 *
 * steps: { [agentName]: "pending" | "active" | "done" }
 */
export function usePipelineStream(sessionId, { onComplete } = {}) {
  const [steps, setSteps] = useState(() => initSteps());
  const [warnings, setWarnings] = useState([]);
  const [errors, setErrors] = useState([]);
  const [isComplete, setIsComplete] = useState(false);
  const [isError, setIsError] = useState(false);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  useEffect(() => {
    if (!sessionId) return;

    setSteps(initSteps());
    setWarnings([]);
    setErrors([]);
    setIsComplete(false);
    setIsError(false);

    const cleanup = streamSession(
      sessionId,
      (event) => {
        switch (event.type) {
          case "pipeline_start": {
            setSteps((prev) => ({ ...prev, planner: "active" }));
            break;
          }
          case "step_complete": {
            const node = event.data.node;
            setSteps((prev) => markComplete(prev, node));
            if (event.data.errors?.length) {
              setErrors(event.data.errors);
            }
            break;
          }
          case "warning": {
            setWarnings((prev) => [...prev, event.data.message]);
            break;
          }
          case "complete": {
            setSteps((prev) => {
              const next = { ...prev };
              for (const k of PIPELINE_ORDER) next[k] = "done";
              return next;
            });
            setIsComplete(true);
            onCompleteRef.current?.();
            break;
          }
          case "error": {
            setIsError(true);
            setErrors((prev) => [...prev, event.data.message]);
            break;
          }
          default:
            break;
        }
      },
      () => {
        // SSE connection error — if not already complete, surface a generic error
      }
    );

    return cleanup;
  }, [sessionId]);

  return { steps, warnings, errors, isComplete, isError, pipelineOrder: PIPELINE_ORDER };
}

function initSteps() {
  const s = {};
  for (const k of PIPELINE_ORDER) s[k] = "pending";
  return s;
}

function markComplete(prev, completedNode) {
  const next = { ...prev };
  const idx = PIPELINE_ORDER.indexOf(completedNode);
  if (idx === -1) return next;

  // Mark this node and all before it as done
  for (let i = 0; i <= idx; i++) {
    next[PIPELINE_ORDER[i]] = "done";
  }
  // Mark the next node as active
  if (idx + 1 < PIPELINE_ORDER.length) {
    next[PIPELINE_ORDER[idx + 1]] = "active";
  }
  return next;
}
