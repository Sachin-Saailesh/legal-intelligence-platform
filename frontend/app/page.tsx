"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, DashboardStats, ComplianceAlert } from "@/lib/api";
import { NavShell } from "@/components/nav-shell";

// ── Shared helpers ────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    complete: "text-emerald-400",
    approved: "text-emerald-400",
    processing: "text-sky-400",
    pending_review: "text-amber-400",
    rejected: "text-red-400",
  };
  const icon: Record<string, string> = {
    complete: "check_circle",
    approved: "check_circle",
    processing: "autorenew",
    pending_review: "schedule",
    rejected: "cancel",
  };
  return (
    <span className={`flex items-center gap-1.5 text-xs font-semibold ${map[status] || "text-slate-400"}`}>
      <span className="material-symbols-outlined text-sm">{icon[status] || "radio_button_unchecked"}</span>
      {status.replace(/_/g, " ")}
    </span>
  );
}

function SeverityDot({ sev }: { sev: string }) {
  const c: Record<string, string> = {
    critical: "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]",
    high: "bg-orange-500",
    medium: "bg-amber-500",
    low: "bg-sky-500",
  };
  return <span className={`w-2 h-2 rounded-full block flex-shrink-0 mt-1 ${c[sev] || "bg-slate-500"}`} />;
}

function SeverityBadge({ sev }: { sev: string }) {
  const c: Record<string, string> = {
    critical: "bg-red-500",
    high: "bg-orange-500",
    medium: "bg-amber-500",
    low: "bg-sky-600",
  };
  return (
    <span className={`px-2 py-0.5 rounded-[4px] text-[8px] font-extrabold text-white uppercase tracking-tighter ${c[sev] || "bg-slate-600"}`}>
      {sev}
    </span>
  );
}

// ── Deadline countdown ────────────────────────────────────────────────────────

function DeadlineChip({ iso }: { iso: string | null }) {
  if (!iso) return null;
  const diff = Math.ceil((new Date(iso).getTime() - Date.now()) / 86400000);
  if (diff < 0)
    return <span className="text-[10px] font-bold text-red-400 bg-red-400/10 px-1.5 py-0.5 rounded">{Math.abs(diff)}d overdue</span>;
  if (diff === 0)
    return <span className="text-[10px] font-bold text-orange-400 bg-orange-400/10 px-1.5 py-0.5 rounded">Due today</span>;
  if (diff <= 3)
    return <span className="text-[10px] font-bold text-orange-400 bg-orange-400/10 px-1.5 py-0.5 rounded">{diff}d left</span>;
  if (diff <= 7)
    return <span className="text-[10px] font-bold text-amber-400 bg-amber-400/10 px-1.5 py-0.5 rounded">{diff}d left</span>;
  return <span className="text-[10px] text-slate-500 font-mono">{new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>;
}

// ── Event type icon ───────────────────────────────────────────────────────────

const EVENT_ICONS: Record<string, string> = {
  filing: "description", hearing: "gavel", deposition: "record_voice_over",
  deadline: "timer", discovery: "search", settlement: "handshake",
  motion: "edit_document", order: "balance", other: "event",
};
const EVENT_COLORS: Record<string, string> = {
  filing: "text-sky-400", hearing: "text-violet-400", deposition: "text-amber-400",
  deadline: "text-red-400", discovery: "text-emerald-400", settlement: "text-teal-400",
  motion: "text-indigo-400", order: "text-orange-400", other: "text-slate-400",
};
const PRIORITY_COLOR: Record<string, string> = {
  critical: "text-red-400", high: "text-orange-400", medium: "text-amber-400", low: "text-sky-400",
};
const TYPE_ICON: Record<string, string> = {
  interrogatory: "quiz", document_request: "description", deposition: "record_voice_over",
  admission: "fact_check", subpoena: "policy", expert_disclosure: "science", other: "folder_open",
};

// ── Dashboard page ────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [alerts, setAlerts] = useState<ComplianceAlert[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.dashboard.stats().then((res) => {
      if (res.error) setError(res.error.message);
      else setStats(res.data);
    });
    api.alerts.list({ status: "unread" }).then((res) => {
      if (!res.error) setAlerts(res.data.slice(0, 4));
    });
  }, []);

  const overdueTimeline = stats?.overdue_timeline ?? 0;
  const criticalDeadlines = stats?.critical_deadlines ?? 0;

  return (
    <NavShell>
      <div className="p-8 space-y-7">

        {/* ── Metric cards row ───────────────────────────────────────────── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">

          <Link href="/matters" className="bg-[#1A1A2E] p-5 rounded-xl border border-slate-700/50 hover:border-sky-500/30 transition-colors shadow-lg group xl:col-span-1">
            <div className="flex justify-between items-start mb-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Open Matters</span>
              <span className="material-symbols-outlined text-sky-400 text-lg">folder_open</span>
            </div>
            <span className="text-3xl font-bold text-white">{stats?.open_matters ?? "—"}</span>
            <p className="mt-1 text-[10px] text-slate-500 font-mono uppercase">Active legal matters</p>
          </Link>

          <Link href="/review" className="bg-[#1A1A2E] p-5 rounded-xl border border-slate-700/50 hover:border-amber-500/30 transition-colors shadow-lg xl:col-span-1">
            <div className="flex justify-between items-start mb-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Pending Reviews</span>
              <span className="material-symbols-outlined text-amber-500 text-lg">pending_actions</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-white">{stats?.pending_reviews ?? "—"}</span>
              {(stats?.pending_reviews ?? 0) > 0 && (
                <span className="text-[9px] font-bold uppercase bg-amber-500/20 text-amber-400 border border-amber-500/30 px-1.5 py-0.5 rounded">Action needed</span>
              )}
            </div>
            <p className="mt-1 text-[10px] text-slate-500 font-mono uppercase">Attorney review required</p>
          </Link>

          <Link href="/alerts" className="bg-[#1A1A2E] p-5 rounded-xl border border-slate-700/50 hover:border-red-500/30 transition-colors shadow-lg xl:col-span-1">
            <div className="flex justify-between items-start mb-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Unread Alerts</span>
              <span className="material-symbols-outlined text-red-500 text-lg">warning</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-white">{stats?.unread_alerts ?? "—"}</span>
              {(stats?.unread_alerts ?? 0) > 0 && (
                <span className="text-[9px] font-bold uppercase bg-red-500/20 text-red-400 border border-red-500/30 px-1.5 py-0.5 rounded">Critical</span>
              )}
            </div>
            <p className="mt-1 text-[10px] text-slate-500 font-mono uppercase">Compliance alerts</p>
          </Link>

          <Link href="/timeline" className="bg-[#1A1A2E] p-5 rounded-xl border border-slate-700/50 hover:border-violet-500/30 transition-colors shadow-lg xl:col-span-1">
            <div className="flex justify-between items-start mb-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Overdue Events</span>
              <span className={`material-symbols-outlined text-lg ${overdueTimeline > 0 ? "text-red-400" : "text-slate-500"}`}>timeline</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className={`text-3xl font-bold ${overdueTimeline > 0 ? "text-red-400" : "text-white"}`}>{overdueTimeline}</span>
              {overdueTimeline > 0 && (
                <span className="text-[9px] font-bold uppercase bg-red-500/20 text-red-400 border border-red-500/30 px-1.5 py-0.5 rounded">Overdue</span>
              )}
            </div>
            <p className="mt-1 text-[10px] text-slate-500 font-mono uppercase">Past-due timeline events</p>
          </Link>

          <Link href="/discovery" className="bg-[#1A1A2E] p-5 rounded-xl border border-slate-700/50 hover:border-orange-500/30 transition-colors shadow-lg xl:col-span-1">
            <div className="flex justify-between items-start mb-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Due This Week</span>
              <span className={`material-symbols-outlined text-lg ${criticalDeadlines > 0 ? "text-orange-400" : "text-slate-500"}`}>folder_open</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className={`text-3xl font-bold ${criticalDeadlines > 0 ? "text-orange-400" : "text-white"}`}>{criticalDeadlines}</span>
              {criticalDeadlines > 0 && (
                <span className="text-[9px] font-bold uppercase bg-orange-500/20 text-orange-400 border border-orange-500/30 px-1.5 py-0.5 rounded">Urgent</span>
              )}
            </div>
            <p className="mt-1 text-[10px] text-slate-500 font-mono uppercase">Discovery deadlines</p>
          </Link>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm">{error}</div>
        )}

        {/* ── Timeline + Discovery row ────────────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

          {/* Upcoming Timeline Events */}
          <div className="bg-[#1A1A2E] rounded-xl border border-slate-700/50 shadow-lg flex flex-col">
            <div className="px-6 py-4 border-b border-slate-700/50 flex justify-between items-center">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-violet-400 text-lg">timeline</span>
                <h3 className="font-semibold text-white text-sm">Upcoming Timeline Events</h3>
              </div>
              <Link href="/timeline" className="text-xs font-bold text-sky-400 uppercase tracking-widest hover:underline">
                View All
              </Link>
            </div>
            {!stats || stats.upcoming_events.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
                <span className="material-symbols-outlined text-slate-700 text-4xl mb-2">timeline</span>
                <p className="text-slate-500 text-sm">No upcoming events.</p>
                <p className="text-slate-600 text-xs mt-1">Events auto-extract when you upload documents.</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-800/60">
                {stats.upcoming_events.map((ev) => (
                  <Link
                    key={ev.id}
                    href={`/matters/${ev.matter_id}?tab=timeline`}
                    className="flex items-start gap-3 px-5 py-3.5 hover:bg-slate-800/30 transition-colors"
                  >
                    <span className={`material-symbols-outlined text-base mt-0.5 flex-shrink-0 ${EVENT_COLORS[ev.event_type] || "text-slate-400"}`}>
                      {EVENT_ICONS[ev.event_type] || "event"}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-200 font-medium truncate">{ev.title}</p>
                      <p className="text-[10px] text-slate-500 mt-0.5 truncate">{ev.matter_title}</p>
                    </div>
                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <span className="text-[10px] font-mono text-slate-400">
                        {new Date(ev.event_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                      </span>
                      <span className="text-[9px] capitalize text-slate-600">{ev.event_type.replace("_", " ")}</span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
            {(stats?.upcoming_events.length ?? 0) > 0 && (
              <div className="px-5 py-3 border-t border-slate-800/60 bg-[#0A192F]/40">
                <Link href="/timeline" className="text-xs text-slate-400 hover:text-sky-400 transition-colors">
                  View full timeline →
                </Link>
              </div>
            )}
          </div>

          {/* Critical Discovery Deadlines */}
          <div className="bg-[#1A1A2E] rounded-xl border border-slate-700/50 shadow-lg flex flex-col">
            <div className="px-6 py-4 border-b border-slate-700/50 flex justify-between items-center">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-orange-400 text-lg">folder_open</span>
                <h3 className="font-semibold text-white text-sm">Discovery Deadlines</h3>
              </div>
              <Link href="/discovery" className="text-xs font-bold text-sky-400 uppercase tracking-widest hover:underline">
                View All
              </Link>
            </div>
            {!stats || stats.critical_discovery.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
                <span className="material-symbols-outlined text-slate-700 text-4xl mb-2">folder_open</span>
                <p className="text-slate-500 text-sm">No pending deadlines.</p>
                <p className="text-slate-600 text-xs mt-1">Add discovery items to track them here.</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-800/60">
                {stats.critical_discovery.map((item) => (
                  <Link
                    key={item.id}
                    href={`/matters/${item.matter_id}?tab=discovery`}
                    className="flex items-start gap-3 px-5 py-3.5 hover:bg-slate-800/30 transition-colors"
                  >
                    <span className="material-symbols-outlined text-base mt-0.5 flex-shrink-0 text-slate-500">
                      {TYPE_ICON[item.item_type] || "folder_open"}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <p className="text-sm text-slate-200 font-medium truncate">{item.title}</p>
                        <span className={`text-[9px] font-bold uppercase flex-shrink-0 ${PRIORITY_COLOR[item.priority] || "text-slate-400"}`}>
                          {item.priority}
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-500 truncate">{item.matter_title}</p>
                    </div>
                    <div className="flex-shrink-0">
                      <DeadlineChip iso={item.deadline} />
                    </div>
                  </Link>
                ))}
              </div>
            )}
            {(stats?.critical_discovery.length ?? 0) > 0 && (
              <div className="px-5 py-3 border-t border-slate-800/60 bg-[#0A192F]/40">
                <Link href="/discovery" className="text-xs text-slate-400 hover:text-sky-400 transition-colors">
                  View all discovery →
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* ── Sessions + Alerts row ──────────────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-10 gap-6">

          {/* Recent Agent Sessions */}
          <div className="lg:col-span-6 bg-[#1A1A2E] rounded-xl border border-slate-700/50 shadow-lg overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-slate-700/50 flex justify-between items-center">
              <h3 className="font-semibold text-white text-sm">Recent Agent Sessions</h3>
              <Link href="/review" className="text-xs font-bold text-sky-400 uppercase tracking-widest hover:underline">
                View Queue
              </Link>
            </div>
            {!stats || stats.recent_sessions.length === 0 ? (
              <div className="flex-1 flex items-center justify-center p-8 text-slate-500 text-sm">
                No sessions yet. Upload a document and run a query to get started.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead className="bg-[#1E3A5F]/60">
                    <tr>
                      {["Query", "Status", "Time"].map((h) => (
                        <th key={h} className="px-6 py-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700/30">
                    {stats.recent_sessions.map((s) => (
                      <tr key={s.id} className="hover:bg-slate-800/30 transition-colors">
                        <td className="px-6 py-4">
                          <Link href={`/matters/${s.matter_id}?tab=query&session=${s.id}`} className="text-xs text-slate-300 max-w-[240px] truncate block hover:text-sky-400 transition-colors">
                            {s.query_text}
                          </Link>
                          <span className="text-[10px] font-mono text-slate-600 mt-0.5 block">#{s.id.slice(0, 8)}</span>
                        </td>
                        <td className="px-6 py-4"><StatusBadge status={s.status} /></td>
                        <td className="px-6 py-4 text-xs font-mono text-slate-500">
                          {new Date(s.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Compliance Alerts Feed */}
          <div className="lg:col-span-4 bg-[#1A1A2E] rounded-xl border border-slate-700/50 shadow-lg flex flex-col">
            <div className="px-6 py-4 border-b border-slate-700/50 flex justify-between items-center">
              <h3 className="font-semibold text-white text-sm">Compliance Alerts</h3>
              <Link href="/alerts" className="text-xs font-bold text-sky-400 uppercase tracking-widest hover:underline">
                View All
              </Link>
            </div>
            {alerts.length === 0 ? (
              <div className="flex-1 flex items-center justify-center p-8 text-slate-500 text-sm">No unread alerts.</div>
            ) : (
              <div className="p-5 space-y-5 flex-1 overflow-y-auto">
                {alerts.map((a, i) => (
                  <div key={a.id} className={`flex gap-3 ${i > 0 ? "border-t border-slate-700/40 pt-4" : ""}`}>
                    <SeverityDot sev={a.severity} />
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-start mb-1">
                        <SeverityBadge sev={a.severity} />
                        <span className="text-[10px] font-mono text-slate-500">{new Date(a.created_at).toLocaleDateString()}</span>
                      </div>
                      <p className="text-sm font-bold text-white leading-tight mb-0.5 truncate">{a.regulation_title}</p>
                      <p className="text-[11px] text-slate-400 line-clamp-2">{a.delta_summary}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div className="p-4 bg-[#1E3A5F]/40 border-t border-slate-700/40 text-center">
              <Link href="/alerts" className="text-xs font-semibold text-slate-300 hover:text-white transition-colors">
                Manage All Alerts →
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* FAB */}
      <Link
        href="/matters"
        className="fixed bottom-8 right-8 w-14 h-14 bg-gradient-to-br from-sky-600 to-sky-800 text-white rounded-xl shadow-[0_8px_30px_rgba(0,0,0,0.4)] flex items-center justify-center hover:scale-105 active:scale-95 transition-all z-50 border border-sky-400/20"
      >
        <span className="material-symbols-outlined text-2xl">add</span>
      </Link>
    </NavShell>
  );
}
