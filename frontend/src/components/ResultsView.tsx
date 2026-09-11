import { useState } from "react";
import { JobResult } from "../types";

interface Props {
  result: JobResult;
  onReset: () => void;
}

export default function ResultsView({ result, onReset }: Props) {
  const [showTranscript, setShowTranscript] = useState(false);

  return (
    <div className="results-view">
      {result.content_title && <p className="results-eyebrow">{result.content_title}</p>}
      <h1 className="results-headline">{result.headline}</h1>

      <section>
        <h2>Key takeaways</h2>
        <ul className="takeaways-list">
          {result.key_takeaways.map((point, i) => (
            <li key={i}>{point}</li>
          ))}
        </ul>
      </section>

      {result.entities.length > 0 && (
        <section>
          <h2>Notable entities & topics</h2>
          <div className="entity-chips">
            {result.entities.map((entity, i) => (
              <span key={i} className="entity-chip">
                {entity}
              </span>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2>Sources</h2>
        {result.sources.length > 0 ? (
          <ul className="sources-list">
            {result.sources.map((source, i) => (
              <li key={i}>
                {source.url ? (
                  <a href={source.url} target="_blank" rel="noreferrer">
                    {source.title}
                  </a>
                ) : (
                  <span className="source-title-unlinked">{source.title}</span>
                )}
                <p className="source-note">{source.note}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No external sources were needed to verify this content.</p>
        )}
      </section>

      {result.verification_notes && (
        <section className="verification-note">
          <strong>Note:</strong> {result.verification_notes}
        </section>
      )}

      {result.raw_transcript && (
        <section>
          <button className="link-button" onClick={() => setShowTranscript((v) => !v)}>
            {showTranscript ? "Hide raw transcript" : "Show raw transcript"}
          </button>
          {showTranscript && <pre className="raw-transcript">{result.raw_transcript}</pre>}
        </section>
      )}

      <button className="secondary-button" onClick={onReset}>
        Summarize something else
      </button>
    </div>
  );
}
