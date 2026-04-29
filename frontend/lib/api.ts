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

  timeline: {
    listAll: (params?: { matter_id?: string; event_type?: string; status?: string }) => {
      const qs = new URLSearchParams(params as Record<string, string> || {}).toString();
      return request<TimelineEventWithMatter[]>(`/api/timeline${qs ? `?${qs}` : ""}`);
    },
    list: (matter_id: string, params?: { event_type?: string; status?: string }) => {
      const qs = new URLSearchParams(params as Record<string, string> || {}).toString();
      return request<TimelineEvent[]>(`/api/matters/${matter_id}/timeline${qs ? `?${qs}` : ""}`);
    },
    create: (matter_id: string, body: Omit<TimelineEvent, "id" | "matter_id" | "created_at" | "source">) =>
      request<TimelineEvent>(`/api/matters/${matter_id}/timeline`, { method: "POST", body: JSON.stringify(body) }),
    update: (matter_id: string, event_id: string, body: Partial<TimelineEvent>) =>
      request<TimelineEvent>(`/api/matters/${matter_id}/timeline/${event_id}`, { method: "PATCH", body: JSON.stringify(body) }),
    delete: (matter_id: string, event_id: string) =>
      request<{ deleted: string }>(`/api/matters/${matter_id}/timeline/${event_id}`, { method: "DELETE" }),
    extract: (matter_id: string) =>
      request<{ events: ExtractedTimelineEvent[]; message: string | null }>(`/api/matters/${matter_id}/timeline/extract`, { method: "POST" }),
    bulkSave: (matter_id: string, events: ExtractedTimelineEvent[]) =>
      request<{ saved: number }>(`/api/matters/${matter_id}/timeline/bulk-save`, { method: "POST", body: JSON.stringify({ events }) }),
  },

  discovery: {
    listAll: (params?: { matter_id?: string; item_type?: string; status?: string; priority?: string }) => {
      const qs = new URLSearchParams(params as Record<string, string> || {}).toString();
      return request<DiscoveryItemWithMatter[]>(`/api/discovery${qs ? `?${qs}` : ""}`);
    },
    globalStats: () => request<DiscoveryStats>("/api/discovery/global-stats"),
    list: (matter_id: string, params?: { item_type?: string; status?: string; priority?: string }) => {
      const qs = new URLSearchParams(params as Record<string, string> || {}).toString();
      return request<DiscoveryItem[]>(`/api/matters/${matter_id}/discovery${qs ? `?${qs}` : ""}`);
    },
    stats: (matter_id: string) => request<DiscoveryStats>(`/api/matters/${matter_id}/discovery/stats`),
    create: (matter_id: string, body: Omit<DiscoveryItem, "id" | "matter_id" | "created_at" | "updated_at">) =>
      request<DiscoveryItem>(`/api/matters/${matter_id}/discovery`, { method: "POST", body: JSON.stringify(body) }),
    update: (matter_id: string, item_id: string, body: Partial<DiscoveryItem>) =>
      request<DiscoveryItem>(`/api/matters/${matter_id}/discovery/${item_id}`, { method: "PATCH", body: JSON.stringify(body) }),
    delete: (matter_id: string, item_id: string) =>
      request<{ deleted: string }>(`/api/matters/${matter_id}/discovery/${item_id}`, { method: "DELETE" }),
    analyzePatterns: (matter_id: string) =>
      request<PatternAnalysis>(`/api/matters/${matter_id}/discovery/analyze-patterns`, { method: "POST" }),
  },
};

// ── Types ─────────────────────────────────────────────────────────────────────

export interface DashboardStats {
  open_matters: number;
  pending_reviews: number;
  unread_alerts: number;
  overdue_timeline: number;
  critical_deadlines: number;
  recent_sessions: Array<{
    id: string;
    matter_id: string;
    query_text: string;
    status: string;
    created_at: string;
  }>;
  upcoming_events: Array<{
    id: string;
    matter_id: string;
    matter_title: string;
    event_type: string;
    title: string;
    event_date: string;
    status: string;
  }>;
  critical_discovery: Array<{
    id: string;
    matter_id: string;
    matter_title: string;
    title: string;
    item_type: string;
    deadline: string | null;
    priority: string;
    status: string;
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
  closed_at?: string | null;
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
  review_reason?: string | null;
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

export interface TimelineEvent {
  id: string;
  matter_id: string;
  event_type: "filing" | "hearing" | "deposition" | "deadline" | "discovery" | "settlement" | "motion" | "order" | "other";
  title: string;
  description?: string;
  event_date: string;
  status: "upcoming" | "completed" | "overdue" | "cancelled";
  source: string;
  document_ref?: string;
  created_at: string;
}

export interface ExtractedTimelineEvent {
  event_type: string;
  title: string;
  description?: string;
  event_date: string;
  document_ref?: string;
}

export interface DiscoveryItem {
  id: string;
  matter_id: string;
  item_type: "interrogatory" | "document_request" | "deposition" | "admission" | "subpoena" | "expert_disclosure" | "other";
  title: string;
  description?: string;
  deadline?: string;
  status: "pending" | "in_progress" | "responded" | "objected" | "overdue" | "completed";
  priority: "low" | "medium" | "high" | "critical";
  assigned_to?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface DiscoveryStats {
  total: number;
  pending: number;
  in_progress: number;
  overdue: number;
  completed: number;
  responded: number;
  objected: number;
  by_type: Record<string, number>;
  by_priority: Record<string, number>;
}

export interface PatternAnalysis {
  patterns: Array<{
    type: string;
    title: string;
    description: string;
    severity: "info" | "warning" | "critical";
    items: string[];
  }>;
  summary: string;
  recommendations: string[];
}

export interface TimelineEventWithMatter extends TimelineEvent {
  matter_title: string;
}

export interface DiscoveryItemWithMatter extends DiscoveryItem {
  matter_title: string;
}

export function getWsUrl(path: string): string {
  const base = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
    .replace("https://", "wss://")
    .replace("http://", "ws://");
  return `${base}${path}`;
}
