"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, DashboardStats, ComplianceAlert } from "@/lib/api";
import { NavShell } from "@/components/nav-shell";

function ConfidenceBars({ score }: { score: number | null }) {
  const filled = score == null ? 0 : score >= 0.9 ? 4 : score >= 0.7 ? 3 : score >= 0.5 ? 2 : 1;
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4].map((i) => (
        <div
          key={i}
          className={`h-3 w-3 rounded-[1px] ${i <= filled ? "bg-sky-500" : "bg-slate-700"}`}
        />
      ))}
    </div>
  );
}

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
  const color = map[status] || "text-slate-400";
  return (
    <span className={`flex items-center gap-1.5 text-xs font-semibold ${color}`}>
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

  return (
    <NavShell>
      <div className="p-8 space-y-8">
        {/* Metric Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Link href="/matters" className="bg-[#1A1A2E] p-6 rounded-xl border border-slate-700/50 hover:border-sky-500/30 transition-colors shadow-lg group">
            <div className="flex justify-between items-start mb-4">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Open Matters</span>
              <span className="material-symbols-outlined text-sky-400">folder_open</span>
            </div>
            <div className="flex items-baseline gap-3">
              <span className="text-3xl font-bold text-white">{stats?.open_matters ?? "—"}</span>
            </div>
            <div className="mt-2 text-[10px] text-slate-500 font-mono uppercase">Active legal matters</div>
          </Link>

          <Link href="/review" className="bg-[#1A1A2E] p-6 rounded-xl border border-slate-700/50 hover:border-amber-500/30 transition-colors shadow-lg">
            <div className="flex justify-between items-start mb-4">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Pending Reviews</span>
              <span className="material-symbols-outlined text-amber-500">pending_actions</span>
            </div>
            <div className="flex items-baseline gap-3">
              <span className="text-3xl font-bold text-white">{stats?.pending_reviews ?? "—"}</span>
              {(stats?.pending_reviews ?? 0) > 0 && (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-amber-500/20 text-amber-400 border border-amber-500/30">
                  Needs Attention
                </span>
              )}
            </div>
            <div className="mt-2 text-[10px] text-slate-500 font-mono uppercase">Attorney review required</div>
          </Link>

          <Link href="/alerts" className="bg-[#1A1A2E] p-6 rounded-xl border border-slate-700/50 hover:border-red-500/30 transition-colors shadow-lg">
            <div className="flex justify-between items-start mb-4">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Unread Alerts</span>
              <span className="material-symbols-outlined text-red-500">warning</span>
            </div>
            <div className="flex items-baseline gap-3">
              <span className="text-3xl font-bold text-white">{stats?.unread_alerts ?? "—"}</span>
              {(stats?.unread_alerts ?? 0) > 0 && (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-red-500/20 text-red-400 border border-red-500/30">
                  Critical
                </span>
              )}
            </div>
            <div className="mt-2 text-[10px] text-slate-500 font-mono uppercase">Compliance alerts</div>
          </Link>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Recent Sessions + Alerts */}
        <div className="grid grid-cols-1 lg:grid-cols-10 gap-6">
          {/* Recent Sessions Table */}
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
                          <span className="text-[10px] font-mono text-slate-600 mt-0.5 block">
                            #{s.id.slice(0, 8)}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <StatusBadge status={s.status} />
                        </td>
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
              <div className="flex-1 flex items-center justify-center p-8 text-slate-500 text-sm">
                No unread alerts.
              </div>
            ) : (
              <div className="p-5 space-y-5 flex-1 overflow-y-auto">
                {alerts.map((a, i) => (
                  <div key={a.id} className={`flex gap-3 ${i > 0 ? "border-t border-slate-700/40 pt-4" : ""}`}>
                    <SeverityDot sev={a.severity} />
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-start mb-1">
                        <SeverityBadge sev={a.severity} />
                        <span className="text-[10px] font-mono text-slate-500">
                          {new Date(a.created_at).toLocaleDateString()}
                        </span>
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
