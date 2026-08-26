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

export type RequirementCategory =
  | "eligibility" | "exclusion" | "schedule" | "budget" | "submission"
  | "technical_goal" | "quantitative_target" | "evaluation" | "other";
export type ReviewState = "pending" | "confirmed" | "rejected" | "edited";
export type Importance = "required" | "high" | "medium" | "low";
export type ComplianceStatus = "not_started" | "in_progress" | "complete" | "not_applicable";
export type AiProvider = "openai" | "fake" | "local";

export interface AnalysisSettings {
  ai_provider: AiProvider;
  openai_model: string;
  openai_api_key_set: boolean;
  local_base_url: string;
  local_model: string;
  updated_at: string;
}

export interface AnalysisSettingsPatch {
  ai_provider?: AiProvider;
  openai_api_key?: string;
  openai_model?: string;
  local_base_url?: string;
  local_model?: string;
}

export interface SourceLocator {
  format: "pdf" | "hwpx";
  page?: number;
  section?: string;
  paragraph?: number;
  table?: number;
  row?: number;
  column?: number;
}

export interface RequirementEvidence {
  id: string;
  block_id: string;
  quote: string;
  verified: boolean;
  locator: SourceLocator;
}

export interface RequirementRecord {
  id: string;
  project_id: string;
  document_id: string;
  text: string;
  category: RequirementCategory;
  mandatory: boolean;
  confidence: string;
  review_state: ReviewState;
  evidence: RequirementEvidence[];
  created_at: string;
  updated_at: string;
}

export interface RequirementPatch {
  updated_at: string;
  text?: string;
  review_state?: ReviewState;
  confirm_unverified?: boolean;
}

export interface ComplianceRecord {
  id: string;
  requirement_id: string;
  requirement_text: string;
  category: RequirementCategory;
  mandatory: boolean;
  evidence_quote: string;
  source_location: string;
  importance: Importance;
  proposal_section: string;
  owner_note: string;
  status: ComplianceStatus;
  created_at: string;
  updated_at: string;
}

export interface CompliancePatch {
  updated_at: string;
  importance?: Importance;
  proposal_section?: string;
  owner_note?: string;
  status?: ComplianceStatus;
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

async function download(path: string): Promise<Blob> {
  const headers = new Headers();
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(`${apiBase}${path}`, { headers });
  if (response.status === 401) unauthorizedHandler?.();
  if (!response.ok) throw new ApiError(response.status);
  return response.blob();
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
  deleteDocument(projectId: string, documentId: string): Promise<void> {
    return request<void>(`/projects/${projectId}/documents/${documentId}`, {
      method: "DELETE",
    });
  },
  listRequirements(projectId: string, filters: { category?: RequirementCategory; review_state?: ReviewState } = {}): Promise<RequirementRecord[]> {
    const params = new URLSearchParams();
    if (filters.category) params.set("category", filters.category);
    if (filters.review_state) params.set("review_state", filters.review_state);
    const query = params.size ? `?${params.toString()}` : "";
    return request<RequirementRecord[]>(`/projects/${projectId}/requirements${query}`);
  },
  patchRequirement(projectId: string, requirementId: string, payload: RequirementPatch): Promise<RequirementRecord> {
    return request<RequirementRecord>(`/projects/${projectId}/requirements/${requirementId}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
  },
  listCompliance(projectId: string): Promise<ComplianceRecord[]> {
    return request<ComplianceRecord[]>(`/projects/${projectId}/compliance`);
  },
  patchCompliance(projectId: string, itemId: string, payload: CompliancePatch): Promise<ComplianceRecord> {
    return request<ComplianceRecord>(`/projects/${projectId}/compliance/${itemId}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
  },
  downloadCompliance(projectId: string): Promise<Blob> {
    return download(`/projects/${projectId}/compliance.xlsx`);
  },
  getAnalysisSettings(): Promise<AnalysisSettings> {
    return request<AnalysisSettings>("/settings/analysis");
  },
  patchAnalysisSettings(payload: AnalysisSettingsPatch): Promise<AnalysisSettings> {
    return request<AnalysisSettings>("/settings/analysis", {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
  },
};
