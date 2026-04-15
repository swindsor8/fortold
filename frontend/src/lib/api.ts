const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

// ─── Response types ──────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserResponse {
  id: string;
  email: string;
  created_at: string;
}

export interface ProjectResponse {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectListItem {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  dataset_count: number;
  run_count: number;
}

export interface ColumnInfo {
  name: string;
  dtype: string;
  null_pct: number;
  n_unique: number;
  sample_values: unknown[];
}

export interface DatasetUploadResponse {
  dataset_id: string;
  dataset_version_id: string;
  name: string;
  row_count: number;
  column_schema: ColumnInfo[];
  file_size_bytes: number;
}

export interface DatasetVersionResponse {
  id: string;
  dataset_id: string;
  version_number: number;
  row_count: number | null;
  column_schema: ColumnInfo[];
  goal: string;
  uploaded_at: string;
}

export interface PlanResponse {
  id: string;
  user_id: string;
  dataset_version_id: string;
  status: string;
  plan_json: Record<string, unknown>;
  llm_model: string;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface ExperimentResultResponse {
  id: string;
  run_id: string;
  model_name: string;
  split: string;
  metrics: Record<string, number>;
  feature_importances: Record<string, number> | null;
  created_at: string;
}

export interface RunResponse {
  id: string;
  user_id: string;
  plan_id: string;
  status: string;
  rq_job_id: string | null;
  metrics: Record<string, unknown> | null;
  model_artifacts_path: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  experiment_results: ExperimentResultResponse[];
}

// ─── Base request helper ─────────────────────────────────────────────────────

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // Only set JSON content-type if body is not FormData
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...headers, ...(options.headers as Record<string, string> | undefined) },
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      detail = err.detail ?? detail;
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ─── Auth ────────────────────────────────────────────────────────────────────

export const auth = {
  register: (email: string, password: string) =>
    request<UserResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<UserResponse>("/auth/me"),
};

// ─── Projects ────────────────────────────────────────────────────────────────

export const projects = {
  list: () => request<ProjectListItem[]>("/projects/"),

  create: (name: string, description?: string) =>
    request<ProjectResponse>("/projects/", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    }),

  get: (id: string) => request<ProjectResponse>(`/projects/${id}`),

  update: (id: string, data: { name?: string; description?: string }) =>
    request<ProjectResponse>(`/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  delete: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
};

// ─── Datasets ────────────────────────────────────────────────────────────────

export const datasets = {
  upload: (projectId: string, name: string, goal: string, file: File) => {
    const form = new FormData();
    form.append("project_id", projectId);
    form.append("name", name);
    form.append("goal", goal);
    form.append("file", file);
    return request<DatasetUploadResponse>("/datasets/upload", { method: "POST", body: form });
  },

  list: (projectId: string) =>
    request<DatasetVersionResponse[]>(`/datasets/?project_id=${projectId}`),

  getVersion: (versionId: string) =>
    request<DatasetVersionResponse>(`/datasets/${versionId}`),
};

// ─── Plans ───────────────────────────────────────────────────────────────────

export const plans = {
  generate: (datasetVersionId: string) =>
    request<PlanResponse>("/plans/generate", {
      method: "POST",
      body: JSON.stringify({ dataset_version_id: datasetVersionId }),
    }),

  list: (datasetVersionId: string) =>
    request<PlanResponse[]>(`/plans/?dataset_version_id=${datasetVersionId}`),

  get: (id: string) => request<PlanResponse>(`/plans/${id}`),

  review: (id: string, action: "approve" | "reject", reason?: string) =>
    request<PlanResponse>(`/plans/${id}/review`, {
      method: "POST",
      body: JSON.stringify({ action, reason }),
    }),
};

// ─── Runs ─────────────────────────────────────────────────────────────────────

export const runs = {
  create: (planId: string) =>
    request<RunResponse>("/runs/", {
      method: "POST",
      body: JSON.stringify({ plan_id: planId }),
    }),

  list: (planId: string) => request<RunResponse[]>(`/runs/?plan_id=${planId}`),

  get: (id: string) => request<RunResponse>(`/runs/${id}`),
};
