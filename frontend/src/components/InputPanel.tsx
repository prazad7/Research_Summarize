import { DragEvent, FormEvent, useRef, useState } from "react";

interface Props {
  disabled: boolean;
  onSubmitUrl: (url: string) => void;
  onSubmitFile: (file: File) => void;
}

const ACCEPTED_EXTENSIONS =
  ".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.mp3,.wav,.m4a,.aac,.ogg,.flac,.mp4,.mov,.avi,.mkv,.webm";

export default function InputPanel({ disabled, onSubmitUrl, onSubmitFile }: Props) {
  const [url, setUrl] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUrlSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (url.trim()) onSubmitUrl(url.trim());
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onSubmitFile(file);
    e.target.value = "";
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) onSubmitFile(file);
  };

  return (
    <div className="input-panel">
      <form onSubmit={handleUrlSubmit} className="url-form">
        <input
          type="text"
          placeholder="Paste a website or YouTube link..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={disabled}
          aria-label="URL to summarize"
        />
        <button type="submit" disabled={disabled || !url.trim()}>
          Summarize link
        </button>
      </form>

      <div className="divider">
        <span>or</span>
      </div>

      <div
        className={`dropzone ${isDragging ? "dropzone-active" : ""} ${disabled ? "dropzone-disabled" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={disabled ? undefined : handleDrop}
        onClick={() => !disabled && fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
      >
        <div className="dropzone-icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path
              d="M12 16V4M12 4L7 9M12 4L17 9"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M4 16V18.5C4 19.8807 5.11929 21 6.5 21H17.5C18.8807 21 20 19.8807 20 18.5V16"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <p>Drop a file here, or click to choose one</p>
        <p className="dropzone-hint">PDF, Word, Excel, PowerPoint, audio, or video</p>
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS}
          onChange={handleFileChange}
          disabled={disabled}
          hidden
        />
      </div>
    </div>
  );
}
