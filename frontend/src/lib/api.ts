/** Typed API client. Tokens are injected from localStorage; every call throws
 *  on non-2xx so React Query surfaces errors in the UI. */

const BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function getToken(): string | null {
  return localStorage.getItem("fl_token");
}
export function setToken(t: string) {
  localStorage.setItem("fl_token", t);
}
export function clearToken() {
  localStorage.removeItem("fl_token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    if (res.status === 401) clearToken();
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body == null ? undefined : JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

/* ------------------------------------------------------------- types */
export interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  organization_id: number | null;
  organization_name?: string | null;
  title: string;
  is_active: boolean;
  last_login?: string | null;
  created_at: string;
}
export interface Me {
  user: User;
  permissions: string[];
  role_label: string;
  feature_flags: Record<string, boolean>;
}
export interface Organization {
  id: number;
  name: string;
  slug: string;
  industry: string;
  country: string;
  description: string;
  status: string;
  compliance_level: string;
  data_guardian_enabled: boolean;
  created_at: string;
  node_count: number;
  dataset_count: number;
  user_count: number;
}
export interface Node {
  id: number;
  organization_id: number;
  organization_name?: string | null;
  name: string;
  endpoint: string;
  status: string;
  device_type: string;
  cpu_cores: number;
  gpu_name: string;
  ram_gb: number;
  bandwidth_mbps: number;
  latency_ms: number;
  last_heartbeat?: string | null;
  mTLS_verified: boolean;
  trust_score: number;
  created_at: string;
}
export interface Dataset {
  id: number;
  organization_id: number;
  organization_name?: string | null;
  name: string;
  description: string;
  data_type: string;
  feature_count: number;
  sample_count: number;
  positive_ratio: number;
  noise: number;
  privacy_controls: Record<string, unknown>;
  status: string;
  created_at: string;
}
export interface TrainingJob {
  id: number;
  name: string;
  description: string;
  status: string;
  algorithm: string;
  model_architecture: string;
  total_rounds: number;
  current_round: number;
  client_fraction: number;
  learning_rate: number;
  local_epochs: number;
  secure_aggregation: boolean;
  privacy_budget_per_round: number;
  metrics_json: Record<string, unknown>;
  created_by: number;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}
export interface Round {
  id: number;
  round_number: number;
  status: string;
  participated_count: number;
  avg_loss?: number | null;
  accuracy?: number | null;
  precision?: number | null;
  recall?: number | null;
  f1?: number | null;
  communication_bytes: number;
  aggregation_time_ms: number;
  privacy_budget_used: number;
  started_at?: string | null;
  finished_at?: string | null;
}
export interface ModelVersion {
  id: number;
  job_id: number;
  job_name?: string | null;
  version: number;
  status: string;
  accuracy?: number | null;
  loss?: number | null;
  precision?: number | null;
  recall?: number | null;
  f1?: number | null;
  metrics_json: Record<string, unknown>;
  parent_version?: number | null;
  approval_notes: string;
  created_at: string;
}
export interface Provider {
  id: number;
  name: string;
  provider_type: string;
  base_url: string;
  key_mask: string;
  models: string[];
  temperature_default: number;
  status: string;
  latency_ms: number;
  created_at: string;
}
export interface InferenceResult {
  version_id: number;
  version: number;
  model_name: string;
  prediction: number;
  probability: number;
  confidence: number;
  explanation?: Record<string, unknown> | null;
}

/* ------------------------------------------------------------- auth */
export const authApi = {
  login: (email: string, password: string) =>
    api.post<{ access_token: string; refresh_token: string; user: User }>("/auth/login", { email, password }),
  register: (body: Record<string, unknown>) => api.post("/auth/register", body),
  me: () => api.get<Me>("/auth/me"),
};

/* ------------------------------------------------------------- modules */
export const orgApi = {
  list: (q = "") => api.get<Organization[]>(`/organizations${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  stats: () => api.get<Record<string, unknown>>("/organizations/stats"),
  create: (body: Record<string, unknown>) => api.post<Organization>("/organizations", body),
  update: (id: number, body: Record<string, unknown>) => api.put<Organization>(`/organizations/${id}`, body),
  remove: (id: number) => api.del(`/organizations/${id}`),
};

export const nodeApi = {
  list: () => api.get<Node[]>("/nodes"),
  health: () => api.get<Record<string, unknown>>("/nodes/health"),
  create: (body: Record<string, unknown>) => api.post<Node>("/nodes", body),
  update: (id: number, body: Record<string, unknown>) => api.put<Node>(`/nodes/${id}`, body),
  remove: (id: number) => api.del(`/nodes/${id}`),
  events: (id: number) => api.get<Record<string, unknown>[]>(`/nodes/${id}/events`),
  handshake: (id: number) => api.get<Record<string, unknown>>(`/nodes/${id}/handshake`),
};

export const datasetApi = {
  list: () => api.get<Dataset[]>("/datasets"),
  summary: () => api.get<Record<string, unknown>>("/datasets/summary"),
  schema: (features: number) => api.get<{ feature_names: string[] }>(`/datasets/schema/${features}`),
  create: (body: Record<string, unknown>) => api.post<Dataset>("/datasets", body),
  remove: (id: number) => api.del(`/datasets/${id}`),
};

export const trainingApi = {
  list: () => api.get<TrainingJob[]>("/training"),
  stats: () => api.get<Record<string, unknown>>("/training/stats"),
  get: (id: number) => api.get<TrainingJob>(`/training/${id}`),
  rounds: (id: number) => api.get<Round[]>(`/training/${id}/rounds`),
  create: (body: Record<string, unknown>) => api.post<TrainingJob>("/training", body),
  action: (id: number, action: string, notes = "") =>
    api.post<TrainingJob>(`/training/${id}/action`, { action, notes }),
  remove: (id: number) => api.del(`/training/${id}`),
};

export const coordinatorApi = {
  overview: () => api.get<Record<string, unknown>>("/coordinator/overview"),
  approvals: () => api.get<TrainingJob[]>("/coordinator/approvals"),
  approve: (id: number, action: string, notes = "") =>
    api.post<TrainingJob>(`/coordinator/approvals/${id}`, { action, notes }),
  aggregationDemo: (body: Record<string, unknown>) =>
    api.post<Record<string, unknown>>("/coordinator/secure-aggregation/demo", body),
  aggregationLogs: () => api.get<Record<string, unknown>[]>("/coordinator/aggregation-logs"),
};

export const modelApi = {
  list: (jobId?: number) => api.get<ModelVersion[]>(`/models${jobId ? `?job_id=${jobId}` : ""}`),
  stats: () => api.get<Record<string, unknown>>("/models/stats"),
  get: (id: number) => api.get<ModelVersion>(`/models/${id}`),
  approve: (id: number, notes: string) => api.post<ModelVersion>(`/models/${id}/approve`, { notes }),
  deploy: (id: number, notes: string) => api.post<ModelVersion>(`/models/${id}/deploy`, { notes }),
  rollback: (id: number, notes: string) => api.post<ModelVersion>(`/models/${id}/rollback`, { notes }),
  archive: (id: number) => api.post<ModelVersion>(`/models/${id}/archive`, {}),
  infer: (features: number[], version_id?: number) =>
    api.post<InferenceResult>("/models/infer", { features, version_id }),
};

export const evalApi = {
  summary: () => api.get<Record<string, unknown>>("/evaluation"),
  compare: (ids: number[]) => api.get<Record<string, unknown>>(`/evaluation/compare?version_ids=${ids.join(",")}`),
  confusion: (versionId: number) => api.get<Record<string, unknown>>(`/evaluation/confusion/${versionId}`),
};

export const xaiApi = {
  explain: (versionId: number, sampleIndex: number) =>
    api.get<Record<string, unknown>>(`/xai/explain?version_id=${versionId}&sample_index=${sampleIndex}`),
  importance: (versionId: number) => api.get<Record<string, unknown>>(`/xai/importance?version_id=${versionId}`),
  fairness: (versionId: number, feature = "feature_0") =>
    api.get<Record<string, unknown>>(`/xai/fairness?version_id=${versionId}&sensitive_feature=${feature}`),
  compare: (ids: number[]) => api.get<Record<string, unknown>>(`/xai/compare?version_ids=${ids.join(",")}`),
  biasReport: () => api.get<Record<string, unknown>>("/xai/bias-report"),
};

export const monitorApi = {
  overview: () => api.get<Record<string, unknown>>("/monitor/overview"),
  timeline: () => api.get<Record<string, unknown>>("/monitor/timeline"),
};

export const analyticsApi = {
  overview: () => api.get<Record<string, unknown>>("/analytics/overview"),
  privacy: () => api.get<Record<string, unknown>>("/analytics/privacy"),
};

export const reportApi = {
  types: () => api.get<string[]>("/reports/types"),
  generate: (type: string) => api.get<{ ok: boolean; data: Record<string, unknown> }>(`/reports/generate?report_type=${type}`),
};

export const auditApi = {
  logs: (params = "") => api.get<Record<string, unknown>>(`/audit/logs${params}`),
  verify: () => api.get<{ ok: boolean; message: string }>("/audit/verify"),
  summary: () => api.get<Record<string, unknown>>("/audit/summary"),
};

export const assistantApi = {
  ask: (content: string, providerId?: number) =>
    api.post<Record<string, unknown>>("/assistant/ask", {
      provider_id: providerId ?? 0,
      messages: [{ role: "user", content }],
    }),
};

export const aiApi = {
  specs: () => api.get<Record<string, unknown>[]>("/ai/specs"),
  providers: () => api.get<Provider[]>("/ai/providers"),
  availableProviders: () => api.get<Provider[]>("/ai/providers/available"),
  createProvider: (body: Record<string, unknown>) => api.post<Provider>("/ai/providers", body),
  updateProvider: (id: number, body: Record<string, unknown>) => api.put<Provider>(`/ai/providers/${id}`, body),
  testProvider: (id: number) => api.post<{ ok: boolean; message: string; latency_ms: number }>(`/ai/providers/${id}/test`),
  removeProvider: (id: number) => api.del(`/ai/providers/${id}`),
  chat: (providerId: number, messages: { role: string; content: string }[], model = "", temperature?: number) =>
    api.post<Record<string, unknown>>("/ai/chat", { provider_id: providerId, messages, model, temperature }),
  prompts: () => api.get<Record<string, unknown>[]>("/ai/prompts"),
  createPrompt: (body: Record<string, unknown>) => api.post("/ai/prompts", body),
  removePrompt: (id: number) => api.del(`/ai/prompts/${id}`),
  inferenceLogs: () => api.get<Record<string, unknown>[]>("/ai/inference-logs"),
};

export const adminApi = {
  users: () => api.get<User[]>("/admin/users"),
  createUser: (body: Record<string, unknown>) => api.post("/admin/users", body),
  updateUser: (id: number, body: Record<string, unknown>) => api.put(`/admin/users/${id}`, body),
  removeUser: (id: number) => api.del(`/admin/users/${id}`),
  roles: () => api.get<{ role: string; label: string }[]>("/admin/roles"),
  flags: () => api.get<Record<string, unknown>[]>("/admin/feature-flags"),
  updateFlag: (key: string, enabled: boolean) =>
    api.put(`/admin/feature-flags/${key}`, { enabled }),
  settings: () => api.get<{ key: string; value: string }[]>("/admin/settings"),
  updateSetting: (key: string, value: string) => api.put(`/admin/settings/${key}`, { value }),
  system: () => api.get<Record<string, unknown>>("/admin/system"),
};

export const settingsApi = {
  profile: () => api.get<User>("/settings/profile"),
  updateProfile: (body: Record<string, unknown>) => api.put<User>("/settings/profile", body),
  changePassword: (current: string, next: string) =>
    api.post("/settings/change-password", { current_password: current, new_password: next }),
};

export const labApi = {
  list: () => api.get<Record<string, unknown>[]>("/lab/experiments"),
  create: (body: Record<string, unknown>) => api.post<Record<string, unknown>>("/lab/experiments", body),
  get: (id: number) => api.get<Record<string, unknown>>(`/lab/experiments/${id}`),
  benchmark: (distribution: string, clients: number, rounds: number) =>
    api.get<Record<string, unknown>>(
      `/lab/benchmark?distribution=${distribution}&clients=${clients}&rounds=${rounds}`
    ),
};

export const dashboardApi = {
  get: () => api.get<Record<string, unknown>>("/dashboard"),
};
