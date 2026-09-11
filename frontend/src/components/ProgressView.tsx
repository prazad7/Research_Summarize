import { useEffect, useState } from "react";
import { JobStatus } from "../types";

interface Props {
  status: JobStatus;
  stageMessage: string;
  /** When this job started processing (ms epoch) -- purely for the elapsed-time display. */
  startedAt: number;
}

const STAGES: { key: JobStatus; label: string }[] = [
  { key: "extracting", label: "Extracting" },
  { key: "analyzing", label: "Analyzing" },
  { key: "researching", label: "Researching" },
  { key: "summarizing", label: "Summarizing" },
];

function stageIndex(status: JobStatus): number {
  if (status === "pending") return -1;
  if (status === "completed") return STAGES.length;
  return STAGES.findIndex((s) => s.key === status);
}

const CheckIcon = () => (
  <svg width="12" height="12" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <path
      d="M3.5 8.5L6.5 11.5L12.5 4.5"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export default function ProgressView({ status, stageMessage, startedAt }: Props) {
  const currentIndex = stageIndex(status);
  const [elapsedSeconds, setElapsedSeconds] = useState(() =>
    Math.max(0, Math.round((Date.now() - startedAt) / 1000))
  );

  // Client-side ticking clock only -- purely presentational (so the user
  // can see something is actively happening), independent of the actual
  // job-status polling in App.tsx.
  useEffect(() => {
    const tick = () => setElapsedSeconds(Math.max(0, Math.round((Date.now() - startedAt) / 1000)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);

  return (
    <div className="progress-view">
      <div className="spinner" aria-hidden="true" />
      <p className="progress-message">{stageMessage}</p>
      <p className="progress-elapsed">{elapsedSeconds}s elapsed</p>
      <ol className="progress-steps">
        {STAGES.map((stage, i) => {
          const state = i < currentIndex ? "done" : i === currentIndex ? "active" : "upcoming";
          return (
            <li key={stage.key} className={`progress-step progress-step-${state}`}>
              <span className="progress-step-dot">
                {state === "done" ? <CheckIcon /> : i + 1}
              </span>
              {stage.label}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
