"use client";

import { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, ComplianceAlert } from "@/lib/api";
import { NavShell } from "@/components/nav-shell";

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

function SeverityDot({ sev }: { sev: string }) {
  const c: Record<string, string> = {
    critical: "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]",
    high: "bg-orange-500",
    medium: "bg-amber-500",
    low: "bg-sky-500",
  };
  return <span className={`w-2 h-2 rounded-full flex-shrink-0 mt-1 ${c[sev] || "bg-slate-500"}`} />;
}

function AlertsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const matterId = searchParams.get("matter_id") || undefined;
  const [alerts, setAlerts] = useState<ComplianceAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [filter, setFilter] = useState<"unread" | "all">("unread");

  const load = () => {
    api.alerts
      .list({ matter_id: matterId, status: filter === "unread" ? "unread" : undefined })
      .then((res) => {
        if (!res.error) {
          const order: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
          setAlerts([...res.data].sort((a, b) => (order[a.severity] ?? 9) - (order[b.severity] ?? 9)));
        }
        setLoading(false);
      });
  };

  useEffect(() => { setLoading(true); load(); }, [filter, matterId]);

  const markRead = async (id: string) => { await api.alerts.updateStatus(id, "read"); load(); };
  const dismiss = async (id: string) => { await api.alerts.updateStatus(id, "dismissed"); load(); };

  const investigate = async (alert: ComplianceAlert) => {
    if (!alert.matter_id) return;
    if (alert.status === "unread") await api.alerts.updateStatus(alert.id, "read");
    const prefill = encodeURIComponent(
      `Review compliance with ${alert.regulation_title}. ${alert.delta_summary}`
    );
    router.push(`/matters/${alert.matter_id}?tab=query&prefill=${prefill}`);
  };

  return (
    <NavShell>
      <div className="p-8 space-y-6">
        {/* Header */}
        <div className="flex items-end justify-between">
          <div>
            <nav className="flex items-center gap-2 text-xs text-slate-500 uppercase tracking-widest mb-1">
              <span>Legal Operations</span>
              <span className="material-symbols-outlined text-[14px]">chevron_right</span>
              <span className="text-sky-400 font-bold">Compliance Alerts</span>
            </nav>
            <h2 className="text-3xl font-extrabold text-white tracking-tight">Compliance Alerts</h2>
          </div>
          <div className="flex items-center gap-1 bg-[#1E3A5F]/40 rounded-lg p-1 border border-white/5">
            {(["unread", "all"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-1.5 text-xs font-bold uppercase tracking-wider rounded transition-colors ${
                  filter === f ? "bg-sky-500 text-white" : "text-slate-400 hover:text-white"
                }`}
              >
                {f === "unread" ? "Unread" : "All"}
              </button>
            ))}
          </div>
        </div>

        {/* Alerts list */}
        {loading ? (
          <div className="text-slate-500 text-sm py-12 text-center">Loading…</div>
        ) : alerts.length === 0 ? (
          <div className="bg-[#1A1A2E] rounded-xl border border-slate-700/50 p-12 text-center text-slate-500 text-sm">
            No alerts found.
          </div>
        ) : (
          <div className="space-y-2">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className={`bg-[#1A1A2E] rounded-xl border overflow-hidden transition-colors ${
                  alert.status === "unread" ? "border-l-4 border-l-red-500 border-slate-700/50" : "border-slate-700/30"
                }`}
              >
                {/* Alert header row */}
                <div
                  className="p-5 cursor-pointer hover:bg-[#1E3A5F]/20 transition-colors"
                  onClick={() => setExpanded(expanded === alert.id ? null : alert.id)}
                >
                  <div className="flex items-center gap-4">
                    <SeverityDot sev={alert.severity} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <SeverityBadge sev={alert.severity} />
                        <span className={`text-[10px] px-2 py-0.5 rounded font-mono ${
                          alert.status === "unread" ? "bg-red-500/10 text-red-400" : "bg-slate-700/50 text-slate-500"
                        }`}>
                          {alert.status}
                        </span>
                      </div>
                      <p className="text-sm font-bold text-white leading-tight truncate">{alert.regulation_title}</p>
                      <p className="text-[10px] font-mono text-slate-500 mt-0.5">
                        {new Date(alert.created_at).toLocaleString()}
                        {alert.matter_id && ` · Matter ${alert.matter_id.slice(0, 8)}…`}
                      </p>
                    </div>
                    <span className="material-symbols-outlined text-slate-500 text-lg">
                      {expanded === alert.id ? "expand_less" : "expand_more"}
                    </span>
                  </div>
                </div>

                {/* Expanded content */}
                {expanded === alert.id && (
                  <div className="border-t border-slate-700/40 p-5 space-y-3 bg-[#0A192F]/30">
                    <p className="text-sm text-slate-300 leading-relaxed">{alert.delta_summary}</p>

                    <div className="flex flex-wrap gap-3 text-xs">
                      {alert.regulation_url && (
                        <a href={alert.regulation_url} target="_blank" rel="noreferrer" className="text-sky-400 hover:underline flex items-center gap-1">
                          <span className="material-symbols-outlined text-sm">open_in_new</span>
                          View regulation source
                        </a>
                      )}
                      {alert.matter_id && (
                        <Link href={`/matters/${alert.matter_id}`} className="text-sky-400 hover:underline flex items-center gap-1">
                          <span className="material-symbols-outlined text-sm">folder_open</span>
                          Go to matter
                        </Link>
                      )}
                    </div>

                    <div className="flex gap-2 justify-end flex-wrap">
                      {alert.matter_id && (
                        <button
                          onClick={() => investigate(alert)}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-sky-600/20 border border-sky-500/40 text-sky-400 rounded-md hover:bg-sky-600/30 transition-colors font-semibold"
                        >
                          <span className="material-symbols-outlined text-sm">search</span>
                          Investigate in Matter
                        </button>
                      )}
                      {alert.status === "unread" && (
                        <button
                          onClick={() => markRead(alert.id)}
                          className="px-3 py-1.5 text-xs border border-slate-600 text-slate-300 rounded-md hover:bg-slate-700/50 transition-colors"
                        >
                          Mark Read
                        </button>
                      )}
                      {alert.status !== "dismissed" && (
                        <button
                          onClick={() => dismiss(alert.id)}
                          className="px-3 py-1.5 text-xs border border-slate-700 text-slate-500 rounded-md hover:bg-slate-700/30 transition-colors"
                        >
                          Dismiss
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </NavShell>
  );
}

export default function AlertsPage() {
  return (
    <Suspense fallback={
      <NavShell>
        <div className="flex items-center justify-center h-64 text-slate-500 text-sm">Loading…</div>
      </NavShell>
    }>
      <AlertsContent />
    </Suspense>
  );
}
