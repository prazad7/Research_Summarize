import { useState } from "react";
import { getStoredApiKey, setStoredApiKey } from "../api/client";

/**
 * Small, unobtrusive settings control for the shared API key.
 * Only relevant once the backend is deployed with APP_API_KEY set; in pure
 * local dev (no key configured server-side) this can be left empty.
 */
export default function ApiKeyGate() {
  const [open, setOpen] = useState(false);
  const [key, setKey] = useState(getStoredApiKey());
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setStoredApiKey(key.trim());
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <div className="api-key-gate">
      <button className="link-button" onClick={() => setOpen((v) => !v)}>
        {open ? "Hide" : "API key"}
      </button>
      {open && (
        <div className="api-key-panel">
          <label htmlFor="api-key-input">Access key (only needed if the server requires one)</label>
          <div className="api-key-row">
            <input
              id="api-key-input"
              type="password"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="Paste your access key"
            />
            <button onClick={handleSave}>{saved ? "Saved" : "Save"}</button>
          </div>
        </div>
      )}
    </div>
  );
}
