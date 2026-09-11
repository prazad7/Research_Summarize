import { useEffect, useRef, useState } from "react";
import { getJobStatus, submitFile, submitUrl } from "./api/client";
import ApiKeyGate from "./components/ApiKeyGate";
import InputPanel from "./components/InputPanel";
import ProgressView from "./components/ProgressView";
import ResultsView from "./components/ResultsView";
import { ApiError, JobStatusResponse } from "./types";

const POLL_INTERVAL_MS = 2500;
const TERMINAL_STATUSES = new Set(["completed", "failed"]);

type View = "input" | "processing" | "results" | "error";

export default function App() {
  const [view, setView] = useState<View>("input");
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // Presentational only (drives the "Xs elapsed" readout) -- not read by any
  // request/poll logic.
  const [processingStartedAt, setProcessingStartedAt] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => stopPolling, []);

  const startPolling = (jobId: string) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const status = await getJobStatus(jobId);
        setJob(status);
        if (TERMINAL_STATUSES.has(status.status)) {
          stopPolling();
          setView(status.status === "completed" ? "results" : "error");
        }
      } catch (err) {
        stopPolling();
        setSubmitError(err instanceof ApiError ? err.message : "Lost connection to the server.");
        setView("error");
      }
    }, POLL_INTERVAL_MS);
  };

  const handleSubmitUrl = async (url: string) => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const created = await submitUrl(url);
      setJob({
        job_id: created.job_id,
        status: created.status,
        stage_message: "Queued...",
        content_type: created.content_type,
        source_reference: url,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        result: null,
        error_message: null,
      });
      setProcessingStartedAt(Date.now());
      setView("processing");
      startPolling(created.job_id);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmitFile = async (file: File) => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const created = await submitFile(file);
      setJob({
        job_id: created.job_id,
        status: created.status,
        stage_message: "Queued...",
        content_type: created.content_type,
        source_reference: file.name,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        result: null,
        error_message: null,
      });
      setProcessingStartedAt(Date.now());
      setView("processing");
      startPolling(created.job_id);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    stopPolling();
    setJob(null);
    setSubmitError(null);
    setView("input");
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-titles">
          <h1>
            <span className="app-header-mark" aria-hidden="true">
              R
            </span>
            Research &amp; Summarize
          </h1>
        </div>
        <ApiKeyGate />
      </header>

      <p className="app-intro">
        Drop a file or paste a link — <strong>we'll extract it, research it, and hand you back a
        clear summary.</strong>
      </p>

      <main className="app-main">
        {view === "input" && (
          <>
            <InputPanel
              disabled={isSubmitting}
              onSubmitUrl={handleSubmitUrl}
              onSubmitFile={handleSubmitFile}
            />
            {submitError && <p className="error-banner">{submitError}</p>}
          </>
        )}

        {view === "processing" && job && (
          <ProgressView
            status={job.status}
            stageMessage={job.stage_message}
            startedAt={processingStartedAt}
          />
        )}

        {view === "results" && job?.result && (
          <ResultsView result={job.result} onReset={handleReset} />
        )}

        {view === "error" && (
          <div className="error-view">
            <h2>We couldn't finish that one</h2>
            <p>{job?.error_message ?? submitError ?? "Something went wrong. Please try again."}</p>
            <button className="secondary-button" onClick={handleReset}>
              Try something else
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
