import { FormEvent, useEffect, useRef, useState } from "react";
import { getChatMessages, sendChatMessage } from "../api/client";
import { ApiError, ChatMessage } from "../types";

interface Props {
  jobId: string;
}

export default function ChatPanel({ jobId }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoadingHistory(true);
    getChatMessages(jobId)
      .then((history) => {
        if (!cancelled) setMessages(history);
      })
      .catch(() => {
        // A history load failure shouldn't block starting a fresh
        // conversation -- just start with an empty thread.
      })
      .finally(() => {
        if (!cancelled) setIsLoadingHistory(false);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages, isSending]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text || isSending) return;

    setError(null);
    setIsSending(true);
    setDraft("");
    // Optimistic: show the question immediately, replace once the real
    // (persisted) message + reply come back.
    const optimisticId = `pending-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { id: optimisticId, role: "user", content: text, created_at: new Date().toISOString() },
    ]);

    try {
      const reply = await sendChatMessage(jobId, text);
      setMessages((prev) => [...prev, reply]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't send that. Please try again.");
      // Keep the optimistic question visible but drop the failed send from
      // the draft-loss state -- the user can just retype and resend.
    } finally {
      setIsSending(false);
    }
  };

  return (
    <section className="chat-panel">
      <h2>Ask about this content</h2>
      <p className="chat-hint muted">
        Continue the conversation -- questions are answered using only what was uploaded above.
      </p>

      <div className="chat-messages" ref={listRef}>
        {isLoadingHistory ? (
          <p className="muted chat-empty">Loading conversation...</p>
        ) : messages.length === 0 ? (
          <p className="muted chat-empty">No questions yet -- ask something about this content.</p>
        ) : (
          messages.map((m) => (
            <div key={m.id} className={`chat-bubble chat-bubble-${m.role}`}>
              {m.content}
            </div>
          ))
        )}
        {isSending && (
          <div className="chat-bubble chat-bubble-assistant chat-bubble-pending">Thinking...</div>
        )}
      </div>

      {error && <p className="error-banner chat-error">{error}</p>}

      <form onSubmit={handleSubmit} className="chat-form">
        <input
          type="text"
          placeholder="Ask a question about this content..."
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={isSending}
          aria-label="Ask a question about this content"
        />
        <button type="submit" disabled={isSending || !draft.trim()}>
          Send
        </button>
      </form>
    </section>
  );
}
