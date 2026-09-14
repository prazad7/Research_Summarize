import { ApiError, ChatMessage, JobCreateResponse, JobStatusResponse } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_KEY_STORAGE_KEY = "research_summarize_api_key";

export function getStoredApiKey(): string {
  return localStorage.getItem(API_KEY_STORAGE_KEY) ?? "";
}

export function setStoredApiKey(key: string): void {
  localStorage.setItem(API_KEY_STORAGE_KEY, key);
}

function authHeaders(): HeadersInit {
  const key = getStoredApiKey();
  return key ? { "X-API-Key": key } : {};
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body.detail ?? `Request failed (${response.status}).`;
  } catch {
    return `Request failed (${response.status}).`;
  }
}

export async function submitUrl(url: string): Promise<JobCreateResponse> {
  const formData = new FormData();
  formData.append("url", url);

  const response = await fetch(`${API_BASE_URL}/api/jobs`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return response.json();
}

export async function submitFile(file: File): Promise<JobCreateResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/jobs`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return response.json();
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`, {
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return response.json();
}

export async function getChatMessages(jobId: string): Promise<ChatMessage[]> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/messages`, {
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return response.json();
}

export async function sendChatMessage(jobId: string, message: string): Promise<ChatMessage> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/messages`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return response.json();
}
