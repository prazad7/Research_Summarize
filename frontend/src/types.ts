export type JobStatus =
  | "pending"
  | "extracting"
  | "analyzing"
  | "researching"
  | "summarizing"
  | "completed"
  | "failed";

export type ContentType =
  | "website"
  | "youtube"
  | "pdf"
  | "docx"
  | "xlsx"
  | "csv"
  | "pptx"
  | "audio"
  | "video";

export interface SourceItem {
  title: string;
  url: string | null;
  note: string;
}

export interface JobResult {
  headline: string;
  key_takeaways: string[];
  entities: string[];
  sources: SourceItem[];
  verification_notes: string | null;
  content_title: string | null;
  raw_transcript: string | null;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  stage_message: string;
  content_type: ContentType;
  source_reference: string;
  created_at: string;
  updated_at: string;
  result: JobResult | null;
  error_message: string | null;
}

export interface JobCreateResponse {
  job_id: string;
  status: JobStatus;
  content_type: ContentType;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  created_at: string;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}
