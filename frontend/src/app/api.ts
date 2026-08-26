export type DocumentState =
  | "uploaded"
  | "parsing"
  | "analyzing"
  | "review_required"
  | "completed"
  | "partial"
  | "failed"
  | "ocr_required";

export interface User {
  id: string;
  email: string;
}

export interface Project {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentRecord {
  id: string;
  project_id: string;
  original_name: string;
  media_type: string;
  checksum_sha256: string;
  state: DocumentState;
  error_code: string | null;
  error_message: string | null;
  block_count: number;
  created_at: string;
  updated_at: string;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
}

interface ApiErrorBody {
  detail?: string | { code?: string; message?: string };
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code?: string,
    message = "요청을 처리하지 못했습니다.",
  ) {
    super(message);
  }
}

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api").replace(
  /\/$/,
  "",
);
let accessToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(`${apiBase}${path}`, { ...init, headers });
  if (response.status === 401) unauthorizedHandler?.();
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    const detail = body.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.message ?? "요청을 처리하지 못했습니다.";
    throw new ApiError(response.status, typeof detail === "object" ? detail.code : undefined, message);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  register(email: string, password: string): Promise<User> {
    return request<User>("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  },
  login(email: string, password: string): Promise<TokenResponse> {
    const body = new URLSearchParams({ username: email, password });
    return request<TokenResponse>("/auth/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
  },
  me(): Promise<User> {
    return request<User>("/auth/me");
  },
  listProjects(): Promise<Project[]> {
    return request<Project[]>("/projects");
  },
  createProject(name: string): Promise<Project> {
    return request<Project>("/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
  },
  deleteProject(projectId: string): Promise<void> {
    return request<void>(`/projects/${projectId}`, { method: "DELETE" });
  },
  listDocuments(projectId: string): Promise<DocumentRecord[]> {
    return request<DocumentRecord[]>(`/projects/${projectId}/documents`);
  },
  uploadDocument(projectId: string, file: File): Promise<DocumentRecord> {
    const body = new FormData();
    body.append("file", file);
    return request<DocumentRecord>(`/projects/${projectId}/documents`, {
      method: "POST",
      body,
    });
  },
  startProcessing(projectId: string, documentId: string): Promise<DocumentRecord> {
    return request<DocumentRecord>(
      `/projects/${projectId}/documents/${documentId}/process`,
      { method: "POST" },
    );
  },
};
