"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, TimelineEventWithMatter } from "@/lib/api";
import { NavShell } from "@/components/nav-shell";

const EVENT_TYPE_STYLES: Record<string, { bg: string; border: string; dot: string; icon: string }> = {
  filing:     { bg: "bg-sky-500/10",    border: "border-sky-500/40",    dot: "bg-sky-400",    icon: "description" },
  hearing:    { bg: "bg-violet-500/10", border: "border-violet-500/40", dot: "bg-violet-400", icon: "gavel" },
  deposition: { bg: "bg-amber-500/10",  border: "border-amber-500/40",  dot: "bg-amber-400",  icon: "record_voice_over" },
  deadline:   { bg: "bg-red-500/10",    border: "border-red-500/40",    dot: "bg-red-400",    icon: "timer" },
  discovery:  { bg: "bg-emerald-500/10",border: "border-emerald-500/40",dot: "bg-emerald-400",icon: "search" },
  settlement: { bg: "bg-teal-500/10",   border: "border-teal-500/40",   dot: "bg-teal-400",   icon: "handshake" },
  motion:     { bg: "bg-indigo-500/10", border: "border-indigo-500/40", dot: "bg-indigo-400", icon: "edit_document" },
  order:      { bg: "bg-orange-500/10", border: "border-orange-500/40", dot: "bg-orange-400", icon: "balance" },
  other:      { bg: "bg-slate-500/10",  border: "border-slate-500/40",  dot: "bg-slate-400",  icon: "event" },
};

const STATUS_BADGE: Record<string, string> = {
  upcoming:  "text-sky-400 bg-sky-400/10 border border-sky-400/20",
  completed: "text-emerald-400 bg-emerald-400/10 border border-emerald-400/20",
  overdue:   "text-red-400 bg-red-400/10 border border-red-400/20",
  cancelled: "text-slate-400 bg-slate-400/10 border border-slate-400/20",
};

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function groupByYear(events: TimelineEventWithMatter[]) {
  const map = new Map<string, TimelineEventWithMatter[]>();
  for (const ev of events) {
    const year = new Date(ev.event_date).getFullYear().toString();
    if (!map.has(year)) map.set(year, []);
    map.get(year)!.push(ev);
  }
  return Array.from(map.entries()).sort(([a], [b]) => Number(b) - Number(a));
}

export default function TimelinePage() {
  const [events, setEvents] = useState<TimelineEventWithMatter[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterMatter, setFilterMatter] = useState("");
  const [filterType, setFilterType] = useState("");
  const [filterStatus, setFilterStatus] = useState("");

  const matterOptions = Array.from(
    new Map(events.map((e) => [e.matter_id, e.matter_title])).entries()
  );

  useEffect(() => {
    const params: Record<string, string> = {};
    if (filterMatter) params.matter_id = filterMatter;
    if (filterType) params.event_type = filterType;
    if (filterStatus) params.status = filterStatus;
    api.timeline.listAll(params).then((res) => {
      if (!res.error) setEvents(res.data);
      setLoading(false);
    });
  }, [filterMatter, filterType, filterStatus]);

  const grouped = groupByYear(events);

  return (
    <NavShell>
      <div className="p-8 max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8 flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Case Timeline</h1>
            <p className="text-slate-400 text-sm mt-1">All events across active matters</p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
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
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="bg-[#0A192F] border border-slate-700 text-slate-300 text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-sky-500"
            >
              <option value="">All Types</option>
              {Object.keys(EVENT_TYPE_STYLES).map((t) => (
                <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
              ))}
            </select>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="bg-[#0A192F] border border-slate-700 text-slate-300 text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-sky-500"
            >
              <option value="">All Statuses</option>
              {["upcoming", "completed", "overdue", "cancelled"].map((s) => (
                <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
              ))}
            </select>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <span className="material-symbols-outlined text-sky-400 text-4xl animate-spin">progress_activity</span>
          </div>
        ) : events.length === 0 ? (
          <div className="text-center py-20">
            <span className="material-symbols-outlined text-slate-600 text-5xl">timeline</span>
            <p className="text-slate-500 mt-3 text-sm">No timeline events found</p>
            <p className="text-slate-600 text-xs mt-1">Open a matter and add events in the Timeline tab</p>
          </div>
        ) : (
          <div className="space-y-10">
            {grouped.map(([year, yearEvents]) => (
              <div key={year}>
                <div className="flex items-center gap-4 mb-5">
                  <span className="text-slate-500 text-xs font-bold tracking-widest uppercase">{year}</span>
                  <div className="flex-1 h-px bg-slate-800" />
                  <span className="text-slate-600 text-xs">{yearEvents.length} events</span>
                </div>
                <div className="relative pl-6">
                  {/* Vertical line */}
                  <div className="absolute left-[7px] top-2 bottom-2 w-px bg-slate-800" />

                  <div className="space-y-4">
                    {yearEvents.map((ev) => {
                      const style = EVENT_TYPE_STYLES[ev.event_type] || EVENT_TYPE_STYLES.other;
                      return (
                        <div key={ev.id} className="relative flex gap-4 group">
                          {/* Dot */}
                          <div className={`absolute -left-[1px] top-4 w-3 h-3 rounded-full border-2 border-[#0F2340] ${style.dot} flex-shrink-0`} />

                          {/* Card */}
                          <div className={`flex-1 ml-6 rounded-xl border p-4 transition-all ${style.bg} ${style.border}`}>
                            <div className="flex items-start justify-between gap-3 flex-wrap">
                              <div className="flex items-center gap-2 min-w-0">
                                <span className={`material-symbols-outlined text-base flex-shrink-0 ${style.dot.replace("bg-", "text-")}`}>
                                  {style.icon}
                                </span>
                                <span className="text-white text-sm font-semibold leading-snug">{ev.title}</span>
                              </div>
                              <div className="flex items-center gap-2 flex-shrink-0">
                                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-[4px] uppercase tracking-wide ${STATUS_BADGE[ev.status] || STATUS_BADGE.upcoming}`}>
                                  {ev.status}
                                </span>
                                <span className="text-xs text-slate-400 font-mono">{formatDate(ev.event_date)}</span>
                              </div>
                            </div>

                            {ev.description && (
                              <p className="text-slate-400 text-xs mt-2 leading-relaxed line-clamp-2">{ev.description}</p>
                            )}

                            <div className="flex items-center gap-3 mt-3 flex-wrap">
                              <Link
                                href={`/matters/${ev.matter_id}?tab=timeline`}
                                className="flex items-center gap-1 text-[10px] text-sky-400 hover:text-sky-300 transition-colors"
                              >
                                <span className="material-symbols-outlined text-[11px]">folder_shared</span>
                                {ev.matter_title}
                              </Link>
                              <span className="text-[10px] text-slate-600 capitalize">{ev.event_type.replace("_", " ")}</span>
                              {ev.source === "ai_extracted" && (
                                <span className="text-[10px] text-violet-400 flex items-center gap-0.5">
                                  <span className="material-symbols-outlined text-[11px]">auto_awesome</span>
                                  AI extracted
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
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
