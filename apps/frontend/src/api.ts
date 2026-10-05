/** The browser calls only this API. MCP servers stay on the Compose network. */

export type ApiError = { code: string; message: string; retryable?: boolean };

export type RepositorySummary = {
  repository_id: string;
  url: string;
  owner: string;
  name: string;
  ref: string | null;
  resolved_commit: string;
  status: string;
};

export type Overview = RepositorySummary & {
  languages: string[];
  dependencies: { name: string; version: string; source: string }[];
  frameworks: string[];
  services: string[];
  analysis_status: string;
  analyzer_version: string;
  analysis_commit: string;
};

export type JobRow = { id: string; kind: string; status: string; error_code: string | null };

export type Evidence = {
  file: string;
  start_line: number;
  end_line: number;
  tool: string;
  mcp_server: string;
};

export type ChatMessage = { role: string; text: string; evidence?: Evidence[] };

export type Investigation = {
  session_id: string;
  repository_id: string;
  messages: ChatMessage[];
  job: { id: string; status: string; error_code: string | null } | null;
};

export type TraceRow = {
  server: string;
  tool: string;
  status: string;
  duration_ms: number;
  arguments: Record<string, string>;
};

export type PromptSpec = {
  name: string;
  server: string;
  arguments: { name: string; required: boolean }[];
};

export type FileWindow = {
  path: string;
  start_line: number;
  end_line: number;
  content: string;
  truncated: boolean;
  total_lines: number;
};

export type SymbolMatch = { name: string; path: string; line: number; snippet: string };

export type GraphNode = { id: string; kind: string; name: string; path: string; line: number };
export type GraphEdge = {
  source: string;
  target: string;
  path?: string;
  target_path?: string;
  kind?: string;
  line?: number;
};

export function apiBase(): string {
  const host = window.location.hostname;
  if (host === "localhost" || host === "127.0.0.1") {
    return "http://localhost:8004";
  }
  return "http://api:8004";
}

export function asError(error: unknown): ApiError {
  if (error && typeof error === "object" && "code" in error && "message" in error) {
    return error as ApiError;
  }
  return { code: "INTERNAL_ERROR", message: "The request failed." };
}

let token = "";
let onUnauthorized: (code: string) => void = () => undefined;

export function hasToken(): boolean {
  return token.length > 0;
}

export function setToken(value: string): void {
  token = value.trim();
}

export function clearToken(): void {
  token = "";
}

export function setUnauthorizedHandler(handler: (code: string) => void): void {
  onUnauthorized = handler;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(`${apiBase()}${path}`, { ...init, headers });
  const body = await response.json();
  if (response.status === 401) {
    const code = body.error?.code || "UNAUTHORIZED";
    clearToken();
    onUnauthorized(code);
  }
  if (!response.ok) {
    throw (body.error || { code: "INTERNAL_ERROR", message: response.statusText }) as ApiError;
  }
  return body as T;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function idempotencyKey(): string {
  const random = globalThis.crypto?.randomUUID;
  if (random) {
    return random.call(globalThis.crypto);
  }
  return `import-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export async function importRepository(url: string, ref: string): Promise<{ repository_id: string; job_id: string }> {
  return request("/repositories", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey() },
    body: JSON.stringify({ url, ref: ref || null }),
  });
}

export async function waitUntilReady(repositoryId: string, jobId: string): Promise<void> {
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    const status = await request<{ status: string; job: JobRow | null }>(`/repositories/${repositoryId}/status`);
    if (status.job && status.job.id === jobId && status.job.status === "failed") {
      throw { code: status.job.error_code || "CLONE_FAILED", message: "Import failed." } as ApiError;
    }
    if (status.status === "ready") {
      return;
    }
    await sleep(400);
  }
  throw { code: "TOOL_TIMEOUT", message: "Import did not finish." } as ApiError;
}

export async function startInvestigation(
  repositoryId: string,
  input: { question?: string; prompt?: string; arguments?: Record<string, string> },
): Promise<{ session_id: string; job_id: string }> {
  return request(`/investigations`, {
    method: "POST",
    body: JSON.stringify({ repository_id: repositoryId, ...input }),
  });
}

export async function sendMessage(
  sessionId: string,
  input: { question?: string; prompt?: string; arguments?: Record<string, string> },
): Promise<{ session_id: string; job_id: string }> {
  return request(`/investigations/${sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function waitForInvestigation(sessionId: string): Promise<Investigation> {
  const deadline = Date.now() + 120000;
  while (Date.now() < deadline) {
    const session = await request<Investigation>(`/investigations/${sessionId}`);
    const status = session.job?.status;
    if (status === "succeeded" || status === "failed") {
      return session;
    }
    await sleep(400);
  }
  throw { code: "TOOL_TIMEOUT", message: "The investigation did not finish." } as ApiError;
}
