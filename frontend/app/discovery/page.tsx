"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, DiscoveryItemWithMatter, DiscoveryStats } from "@/lib/api";
import { NavShell } from "@/components/nav-shell";

const PRIORITY_BADGE: Record<string, string> = {
  critical: "text-red-400 bg-red-400/10 border border-red-400/20",
  high:     "text-orange-400 bg-orange-400/10 border border-orange-400/20",
  medium:   "text-amber-400 bg-amber-400/10 border border-amber-400/20",
  low:      "text-sky-400 bg-sky-400/10 border border-sky-400/20",
};

const STATUS_BADGE: Record<string, string> = {
  pending:    "text-slate-300 bg-slate-700/50 border border-slate-600",
  in_progress:"text-sky-400 bg-sky-400/10 border border-sky-400/20",
  responded:  "text-emerald-400 bg-emerald-400/10 border border-emerald-400/20",
  objected:   "text-amber-400 bg-amber-400/10 border border-amber-400/20",
  overdue:    "text-red-400 bg-red-400/10 border border-red-400/20",
  completed:  "text-teal-400 bg-teal-400/10 border border-teal-400/20",
};

const TYPE_ICON: Record<string, string> = {
  interrogatory:    "quiz",
  document_request: "description",
  deposition:       "record_voice_over",
  admission:        "fact_check",
  subpoena:         "policy",
  expert_disclosure:"science",
  other:            "folder_open",
};

function DeadlineLabel({ iso }: { iso: string | null | undefined }) {
  if (!iso) return <span className="text-slate-600 text-xs">No deadline</span>;
  const now = new Date();
  const dl = new Date(iso);
  const diffMs = dl.getTime() - now.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays < 0)
    return <span className="text-red-400 text-xs font-semibold">{Math.abs(diffDays)}d overdue</span>;
  if (diffDays === 0)
    return <span className="text-orange-400 text-xs font-semibold">Due today</span>;
  if (diffDays <= 3)
    return <span className="text-orange-400 text-xs">{diffDays}d left</span>;
  if (diffDays <= 7)
    return <span className="text-amber-400 text-xs">{diffDays}d left</span>;
  return <span className="text-slate-400 text-xs">{dl.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span>;
}

function StatsBar({ stats }: { stats: DiscoveryStats }) {
  const done = stats.completed + stats.responded + stats.objected;
  const pct = stats.total > 0 ? Math.round((done / stats.total) * 100) : 0;

  const cards = [
    { label: "Total", value: stats.total, color: "text-white" },
    { label: "Pending", value: stats.pending, color: "text-slate-400" },
    { label: "In Progress", value: stats.in_progress, color: "text-sky-400" },
    { label: "Overdue", value: stats.overdue, color: "text-red-400" },
    { label: "Completed", value: done, color: "text-emerald-400" },
  ];

  return (
    <div className="bg-[#0A192F] border border-slate-800 rounded-2xl p-5 mb-7">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div className="flex gap-6 flex-wrap">
          {cards.map((c) => (
            <div key={c.label}>
              <p className={`text-2xl font-bold ${c.color}`}>{c.value}</p>
              <p className="text-slate-500 text-xs mt-0.5">{c.label}</p>
            </div>
          ))}
        </div>
        <div className="text-right">
          <p className="text-slate-400 text-xs mb-1">Overall completion</p>
          <p className="text-2xl font-bold text-white">{pct}%</p>
        </div>
      </div>
      <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-sky-500 to-emerald-500 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      {stats.overdue > 0 && (
        <p className="text-red-400 text-xs mt-2 flex items-center gap-1">
          <span className="material-symbols-outlined text-[13px]">warning</span>
          {stats.overdue} item{stats.overdue !== 1 ? "s" : ""} past deadline
        </p>
      )}
    </div>
  );
}

export default function DiscoveryPage() {
  const [items, setItems] = useState<DiscoveryItemWithMatter[]>([]);
  const [stats, setStats] = useState<DiscoveryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterMatter, setFilterMatter] = useState("");
  const [filterPriority, setFilterPriority] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterType, setFilterType] = useState("");

  const matterOptions = Array.from(
    new Map(items.map((i) => [i.matter_id, i.matter_title])).entries()
  );

  const load = () => {
    const params: Record<string, string> = {};
    if (filterMatter) params.matter_id = filterMatter;
    if (filterPriority) params.priority = filterPriority;
    if (filterStatus) params.status = filterStatus;
    if (filterType) params.item_type = filterType;

    Promise.all([
      api.discovery.listAll(params),
      api.discovery.globalStats(),
    ]).then(([itemsRes, statsRes]) => {
      if (!itemsRes.error) setItems(itemsRes.data);
      if (!statsRes.error) setStats(statsRes.data);
      setLoading(false);
    });
  };

  useEffect(load, [filterMatter, filterPriority, filterStatus, filterType]);

  return (
    <NavShell>
      <div className="p-8 max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-7 flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Discovery Tracker</h1>
            <p className="text-slate-400 text-sm mt-1">All discovery items across active matters</p>
          </div>
        </div>

        {/* Stats */}
        {stats && <StatsBar stats={stats} />}

        {/* Filters */}
        <div className="flex items-center gap-2 flex-wrap mb-5">
          <select
            value={filterMatter}
            onChange={(e) => setFilterMatter(e.target.value)}
            className="bg-[#0A192F] border border-slate-700 text-slate-300 text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-sky-500"
          >
            <option value="">All Matters</option>
            {matterOptions.map(([id, title]) => (
              <option key={id} value={id}>{title}</option>
            ))}
          </select>
          <select
            value={filterPriority}
            onChange={(e) => setFilterPriority(e.target.value)}
            className="bg-[#0A192F] border border-slate-700 text-slate-300 text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-sky-500"
          >
            <option value="">All Priorities</option>
            {["critical", "high", "medium", "low"].map((p) => (
              <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
            ))}
          </select>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="bg-[#0A192F] border border-slate-700 text-slate-300 text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-sky-500"
          >
            <option value="">All Statuses</option>
            {["pending", "in_progress", "responded", "objected", "overdue", "completed"].map((s) => (
              <option key={s} value={s}>{s.replace("_", " ").charAt(0).toUpperCase() + s.replace("_", " ").slice(1)}</option>
            ))}
          </select>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="bg-[#0A192F] border border-slate-700 text-slate-300 text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-sky-500"
          >
            <option value="">All Types</option>
            {Object.keys(TYPE_ICON).map((t) => (
              <option key={t} value={t}>{t.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}</option>
            ))}
          </select>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <span className="material-symbols-outlined text-sky-400 text-4xl animate-spin">progress_activity</span>
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-20">
            <span className="material-symbols-outlined text-slate-600 text-5xl">folder_open</span>
            <p className="text-slate-500 mt-3 text-sm">No discovery items found</p>
            <p className="text-slate-600 text-xs mt-1">Open a matter and add items in the Discovery tab</p>
          </div>
        ) : (
          <div className="space-y-2">
            {items.map((item) => (
              <div
                key={item.id}
                className="bg-[#0A192F] border border-slate-800 rounded-xl px-5 py-4 hover:border-slate-700 transition-colors"
              >
                <div className="flex items-start gap-3 flex-wrap">
                  <span className="material-symbols-outlined text-slate-500 text-lg mt-0.5 flex-shrink-0">
                    {TYPE_ICON[item.item_type] || "folder_open"}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-white text-sm font-semibold">{item.title}</span>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-[4px] uppercase tracking-wide ${PRIORITY_BADGE[item.priority] || PRIORITY_BADGE.medium}`}>
                        {item.priority}
                      </span>
                      <span className={`text-[10px] font-medium px-2 py-0.5 rounded-[4px] capitalize ${STATUS_BADGE[item.status] || STATUS_BADGE.pending}`}>
                        {item.status.replace("_", " ")}
                      </span>
                    </div>

                    {item.description && (
                      <p className="text-slate-400 text-xs mt-1 line-clamp-1">{item.description}</p>
                    )}

                    <div className="flex items-center gap-4 mt-2 flex-wrap">
                      <Link
                        href={`/matters/${item.matter_id}?tab=discovery`}
                        className="flex items-center gap-1 text-[10px] text-sky-400 hover:text-sky-300 transition-colors"
                      >
                        <span className="material-symbols-outlined text-[11px]">folder_shared</span>
                        {item.matter_title}
                      </Link>
                      <span className="text-[10px] text-slate-600 capitalize">{item.item_type.replace("_", " ")}</span>
                      {item.assigned_to && (
                        <span className="text-[10px] text-slate-500 flex items-center gap-0.5">
                          <span className="material-symbols-outlined text-[11px]">person</span>
                          {item.assigned_to}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex-shrink-0 text-right">
                    <DeadlineLabel iso={item.deadline} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </NavShell>
  );
}
