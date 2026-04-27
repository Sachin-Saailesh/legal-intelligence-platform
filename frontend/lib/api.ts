const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<{ data: T; error: null } | { data: null; error: { code: string; message: string } }> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const json = await res.json();
  return json;
}

export const api = {
  dashboard: {
    stats: () => request<DashboardStats>("/api/dashboard/stats"),
  },

  matters: {
    list: () => request<Matter[]>("/api/matters"),
    get: (id: string) => request<Matter>(`/api/matters/${id}`),
    create: (body: { title: string; matter_type: string; jurisdiction?: string; practice_area?: string; industry?: string }) =>
      request<Matter>("/api/matters", { method: "POST", body: JSON.stringify(body) }),
    update: (id: string, body: Partial<Matter>) =>
      request<Matter>(`/api/matters/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  },

  documents: {
    list: (matter_id: string) => request<Document[]>(`/api/matters/${matter_id}/documents`),
    upload: async (matter_id: string, file: File) => {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE}/api/matters/${matter_id}/documents`, {
        method: "POST",
        body: form,
      });
      return res.json();
    },
  },

  queries: {
    create: (body: { query: string; matter_id: string; metadata?: Record<string, unknown> }) =>
      request<{ session_id: string }>("/api/queries", { method: "POST", body: JSON.stringify(body) }),
    get: (session_id: string) => request<AgentSession>(`/api/queries/${session_id}`),
    list: (matter_id: string, params?: { limit?: number }) => {
      const qs = new URLSearchParams({ matter_id, ...(params?.limit ? { limit: String(params.limit) } : {}) }).toString();
      return request<AgentSession[]>(`/api/queries?${qs}`);
    },
  },

  review: {
    queue: () => request<AgentSession[]>("/api/review/queue"),
    approve: (session_id: string, body: { corrected_output?: string; correction_type?: string }) =>
      request<{ session_id: string; status: string }>(`/api/review/${session_id}/approve`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    reject: (session_id: string, reason: string) =>
      request<{ session_id: string; status: string }>(`/api/review/${session_id}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
  },

  alerts: {
    list: (params?: { matter_id?: string; severity?: string; status?: string }) => {
      const qs = new URLSearchParams(params as Record<string, string> || {}).toString();
      return request<ComplianceAlert[]>(`/api/alerts${qs ? `?${qs}` : ""}`);
    },
    updateStatus: (alert_id: string, status: "read" | "dismissed") =>
      request<{ alert_id: string; status: string }>(`/api/alerts/${alert_id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
  },
};

// ── Types ─────────────────────────────────────────────────────────────────────

export interface DashboardStats {
  open_matters: number;
  pending_reviews: number;
  unread_alerts: number;
  recent_sessions: Array<{
    id: string;
    matter_id: string;
    query_text: string;
    status: string;
    created_at: string;
  }>;
}

export interface Matter {
  id: string;
  firm_id: string;
  title: string;
  matter_type: string;
  status: string;
  jurisdiction?: string;
  practice_area?: string;
  industry?: string;
  created_at: string;
}

export interface Document {
  id: string;
  matter_id: string;
  filename: string;
  doc_type?: string;
  ingestion_status: string;
  chunk_count: number;
  created_at: string;
}

export interface SourceChunk {
  id: string;
  text: string;
  source_doc_id?: string;
  page_number?: number;
  confidence_score?: number;
  rank_position?: number;
}

export interface AgentSession {
  id: string;
  matter_id: string;
  query_text: string;
  final_output?: string;
  confidence_score?: number;
  status: string;
  agent_route?: string;
  created_at: string;
  source_chunks?: SourceChunk[];
  user_id?: string;
}

export interface ComplianceAlert {
  id: string;
  matter_id?: string;
  regulation_title: string;
  regulation_url?: string;
  delta_summary: string;
  severity: "low" | "medium" | "high" | "critical";
  status: "unread" | "read" | "dismissed";
  created_at: string;
}

export function getWsUrl(path: string): string {
  const base = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
    .replace("https://", "wss://")
    .replace("http://", "ws://");
  return `${base}${path}`;
}
