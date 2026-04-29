"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ExtractedTimelineEvent, TimelineEvent } from "@/lib/api";

// ── Constants ────────────────────────────────────────────────────────────────

const EVENT_TYPES = ["filing", "hearing", "deposition", "deadline", "discovery", "settlement", "motion", "order", "other"] as const;
const STATUS_FILTERS = ["all", "upcoming", "completed", "overdue", "cancelled"] as const;

const TYPE_STYLE: Record<string, { dot: string; border: string; bg: string; badge: string; text: string; icon: string }> = {
  filing:     { dot: "bg-sky-500",     border: "border-sky-500/40",     bg: "bg-sky-900/10",     badge: "bg-sky-900/60 border-sky-700/40",     text: "text-sky-300",     icon: "description" },
  hearing:    { dot: "bg-violet-500",  border: "border-violet-500/40",  bg: "bg-violet-900/10",  badge: "bg-violet-900/60 border-violet-700/40", text: "text-violet-300",  icon: "gavel" },
  deposition: { dot: "bg-amber-500",   border: "border-amber-500/40",   bg: "bg-amber-900/10",   badge: "bg-amber-900/60 border-amber-700/40",   text: "text-amber-300",   icon: "record_voice_over" },
  deadline:   { dot: "bg-red-500",     border: "border-red-500/40",     bg: "bg-red-900/10",     badge: "bg-red-900/60 border-red-700/40",       text: "text-red-300",     icon: "timer" },
  discovery:  { dot: "bg-emerald-500", border: "border-emerald-500/40", bg: "bg-emerald-900/10", badge: "bg-emerald-900/60 border-emerald-700/40", text: "text-emerald-300", icon: "search" },
  settlement: { dot: "bg-teal-400",    border: "border-teal-400/40",    bg: "bg-teal-900/10",    badge: "bg-teal-900/60 border-teal-700/40",     text: "text-teal-300",    icon: "handshake" },
  motion:     { dot: "bg-slate-400",   border: "border-slate-500/40",   bg: "bg-slate-800/20",   badge: "bg-slate-700/60 border-slate-600/40",   text: "text-slate-300",   icon: "article" },
  order:      { dot: "bg-orange-400",  border: "border-orange-500/40",  bg: "bg-orange-900/10",  badge: "bg-orange-900/60 border-orange-700/40", text: "text-orange-300",  icon: "policy" },
  other:      { dot: "bg-slate-500",   border: "border-slate-600/40",   bg: "bg-slate-800/20",   badge: "bg-slate-700/60 border-slate-600/40",   text: "text-slate-400",   icon: "event" },
};

const STATUS_STYLE: Record<string, { label: string; chip: string; icon: string }> = {
  upcoming:  { label: "Upcoming",  chip: "bg-sky-500/10 text-sky-400 border border-sky-500/20",     icon: "schedule" },
  completed: { label: "Completed", chip: "bg-emerald-900/30 text-emerald-400 border border-emerald-700/20", icon: "check_circle" },
  overdue:   { label: "Overdue",   chip: "bg-red-900/40 text-red-400 border border-red-700/30 animate-pulse", icon: "warning" },
  cancelled: { label: "Cancelled", chip: "bg-slate-700/50 text-slate-500 border border-slate-600/20", icon: "cancel" },
};

// ── Inline form ──────────────────────────────────────────────────────────────

interface EventFormData {
  event_type: string;
  title: string;
  description: string;
  event_date: string;
  status: string;
  document_ref: string;
}

const EMPTY_FORM: EventFormData = {
  event_type: "other",
  title: "",
  description: "",
  event_date: new Date().toISOString().slice(0, 10),
  status: "upcoming",
  document_ref: "",
};

function EventForm({
  initial,
  onSave,
  onCancel,
  saving,
}: {
  initial?: EventFormData;
  onSave: (data: EventFormData) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const [form, setForm] = useState<EventFormData>(initial ?? EMPTY_FORM);
  const set = (k: keyof EventFormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((p) => ({ ...p, [k]: e.target.value }));

  return (
    <div className="bg-[#0d1f35] border border-sky-500/30 rounded-xl p-5 space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Event Type</label>
          <select value={form.event_type} onChange={set("event_type")} className="w-full bg-[#1A1A2E] border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500/50">
            {EVENT_TYPES.map((t) => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Status</label>
          <select value={form.status} onChange={set("status")} className="w-full bg-[#1A1A2E] border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500/50">
            {["upcoming", "completed", "overdue", "cancelled"].map((s) => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
          </select>
        </div>
      </div>
      <div className="space-y-1">
        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Title *</label>
        <input value={form.title} onChange={set("title")} placeholder="e.g. Complaint Filed" className="w-full bg-[#1A1A2E] border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500/50" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Event Date *</label>
          <input type="date" value={form.event_date} onChange={set("event_date")} className="w-full bg-[#1A1A2E] border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500/50" />
        </div>
        <div className="space-y-1">
          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Document Reference</label>
          <input value={form.document_ref} onChange={set("document_ref")} placeholder="e.g. Exhibit A" className="w-full bg-[#1A1A2E] border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500/50" />
        </div>
      </div>
      <div className="space-y-1">
        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Description</label>
        <textarea value={form.description} onChange={set("description")} rows={2} placeholder="Optional details…" className="w-full bg-[#1A1A2E] border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500/50 resize-none" />
      </div>
      <div className="flex gap-2 justify-end pt-1">
        <button onClick={onCancel} className="px-4 py-2 text-xs text-slate-400 border border-slate-700/50 rounded-lg hover:bg-slate-700/30 transition-colors">Cancel</button>
        <button onClick={() => onSave(form)} disabled={saving || !form.title.trim() || !form.event_date} className="px-4 py-2 text-xs font-bold bg-sky-600 text-white rounded-lg disabled:opacity-40 hover:bg-sky-500 transition-colors">
          {saving ? "Saving…" : "Save Event"}
        </button>
      </div>
    </div>
  );
}

// ── AI Extract review modal ──────────────────────────────────────────────────

function ExtractReviewPanel({
  extracted,
  onConfirm,
  onDismiss,
  saving,
}: {
  extracted: ExtractedTimelineEvent[];
  onConfirm: (events: ExtractedTimelineEvent[]) => void;
  onDismiss: () => void;
  saving: boolean;
}) {
  const [selected, setSelected] = useState<Set<number>>(new Set(extracted.map((_, i) => i)));

  const toggle = (i: number) =>
    setSelected((prev) => { const s = new Set(prev); s.has(i) ? s.delete(i) : s.add(i); return s; });

  return (
    <div className="bg-[#080f1c] border border-amber-500/30 rounded-2xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-amber-400 text-base">auto_awesome</span>
          <span className="text-sm font-bold text-white">AI-Extracted Events</span>
          <span className="text-[10px] font-mono text-slate-500">{extracted.length} found · {selected.size} selected</span>
        </div>
        <button onClick={onDismiss} className="text-slate-500 hover:text-slate-300 text-xs">Dismiss</button>
      </div>

      <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
        {extracted.map((ev, i) => {
          const style = TYPE_STYLE[ev.event_type] ?? TYPE_STYLE.other;
          return (
            <label key={i} className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${selected.has(i) ? `${style.bg} ${style.border}` : "bg-[#0d1f35] border-slate-700/30 opacity-50"}`}>
              <input type="checkbox" checked={selected.has(i)} onChange={() => toggle(i)} className="mt-0.5 accent-sky-500" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase border ${style.badge} ${style.text}`}>{ev.event_type}</span>
                  <span className="text-[10px] font-mono text-slate-400">{ev.event_date}</span>
                  {ev.document_ref && <span className="text-[10px] text-slate-600 truncate">{ev.document_ref}</span>}
                </div>
                <p className="text-xs text-slate-300 font-medium truncate">{ev.title}</p>
                {ev.description && <p className="text-[10px] text-slate-500 line-clamp-1">{ev.description}</p>}
              </div>
            </label>
          );
        })}
      </div>

      <div className="flex gap-2 justify-end pt-1 border-t border-slate-800/60">
        <button onClick={onDismiss} className="px-4 py-2 text-xs text-slate-400 border border-slate-700/50 rounded-lg hover:bg-slate-700/30">Cancel</button>
        <button
          onClick={() => onConfirm(extracted.filter((_, i) => selected.has(i)))}
          disabled={saving || selected.size === 0}
          className="px-4 py-2 text-xs font-bold bg-amber-600 text-white rounded-lg disabled:opacity-40 hover:bg-amber-500 transition-colors"
        >
          {saving ? "Saving…" : `Add ${selected.size} Event${selected.size !== 1 ? "s" : ""}`}
        </button>
      </div>
    </div>
  );
}

// ── Timeline event card ──────────────────────────────────────────────────────

function EventCard({
  event,
  onEdit,
  onDelete,
  onStatusChange,
}: {
  event: TimelineEvent;
  onEdit: () => void;
  onDelete: () => void;
  onStatusChange: (status: string) => void;
}) {
  const style = TYPE_STYLE[event.event_type] ?? TYPE_STYLE.other;
  const statusStyle = STATUS_STYLE[event.status] ?? STATUS_STYLE.upcoming;
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => { if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div className={`flex-1 bg-[#0A192F] border ${style.border} rounded-xl p-4 group`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase border ${style.badge} ${style.text}`}>
            {event.event_type}
          </span>
          <span className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase flex items-center gap-1 ${statusStyle.chip}`}>
            <span className="material-symbols-outlined text-[11px]">{statusStyle.icon}</span>
            {statusStyle.label}
          </span>
          {event.source === "ai_extracted" && (
            <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">✦ AI</span>
          )}
        </div>

        <div className="relative flex-shrink-0" ref={menuRef}>
          <button onClick={() => setMenuOpen(!menuOpen)} className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-slate-300 transition-opacity">
            <span className="material-symbols-outlined text-base">more_horiz</span>
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-6 z-20 bg-[#1A1A2E] border border-slate-700/50 rounded-lg shadow-xl py-1 min-w-[140px]">
              <button onClick={() => { onEdit(); setMenuOpen(false); }} className="w-full px-3 py-2 text-xs text-slate-300 hover:bg-slate-700/40 text-left flex items-center gap-2">
                <span className="material-symbols-outlined text-sm">edit</span> Edit
              </button>
              {event.status !== "completed" && (
                <button onClick={() => { onStatusChange("completed"); setMenuOpen(false); }} className="w-full px-3 py-2 text-xs text-emerald-400 hover:bg-slate-700/40 text-left flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm">check_circle</span> Mark Complete
                </button>
              )}
              {event.status === "upcoming" && (
                <button onClick={() => { onStatusChange("cancelled"); setMenuOpen(false); }} className="w-full px-3 py-2 text-xs text-slate-500 hover:bg-slate-700/40 text-left flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm">cancel</span> Cancel
                </button>
              )}
              <div className="border-t border-slate-700/30 my-1" />
              <button onClick={() => { onDelete(); setMenuOpen(false); }} className="w-full px-3 py-2 text-xs text-red-400 hover:bg-red-900/20 text-left flex items-center gap-2">
                <span className="material-symbols-outlined text-sm">delete</span> Delete
              </button>
            </div>
          )}
        </div>
      </div>

      <p className="text-sm font-semibold text-white mt-2 leading-snug">{event.title}</p>
      {event.description && (
        <p className="text-xs text-slate-400 mt-1 leading-relaxed line-clamp-2">{event.description}</p>
      )}
      {event.document_ref && (
        <p className="mt-1.5 text-[10px] font-mono text-slate-600 flex items-center gap-1">
          <span className="material-symbols-outlined text-[12px]">attach_file</span>
          {event.document_ref}
        </p>
      )}
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

export function TimelineView({ matterId }: { matterId: string }) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [extracted, setExtracted] = useState<ExtractedTimelineEvent[] | null>(null);
  const [extractMsg, setExtractMsg] = useState<string | null>(null);
  const [bulkSaving, setBulkSaving] = useState(false);

  const load = useCallback(async () => {
    const params: Record<string, string> = {};
    if (typeFilter !== "all") params.event_type = typeFilter;
    if (statusFilter !== "all") params.status = statusFilter;
    const res = await api.timeline.list(matterId, params);
    if (!res.error) setEvents(res.data);
    setLoading(false);
  }, [matterId, typeFilter, statusFilter]);

  useEffect(() => { setLoading(true); load(); }, [load]);

  const handleCreate = async (form: EventFormData) => {
    setSaving(true);
    const res = await api.timeline.create(matterId, {
      event_type: form.event_type as TimelineEvent["event_type"],
      title: form.title,
      description: form.description || undefined,
      event_date: new Date(form.event_date).toISOString(),
      status: form.status as TimelineEvent["status"],
      document_ref: form.document_ref || undefined,
    });
    if (!res.error) { setShowAddForm(false); await load(); }
    setSaving(false);
  };

  const handleUpdate = async (id: string, form: EventFormData) => {
    setSaving(true);
    await api.timeline.update(matterId, id, {
      event_type: form.event_type as TimelineEvent["event_type"],
      title: form.title,
      description: form.description || undefined,
      event_date: new Date(form.event_date).toISOString(),
      status: form.status as TimelineEvent["status"],
      document_ref: form.document_ref || undefined,
    });
    setEditingId(null);
    await load();
    setSaving(false);
  };

  const handleStatusChange = async (id: string, status: string) => {
    await api.timeline.update(matterId, id, { status: status as TimelineEvent["status"] });
    await load();
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this event?")) return;
    await api.timeline.delete(matterId, id);
    await load();
  };

  const handleExtract = async () => {
    setExtracting(true);
    setExtractMsg(null);
    const res = await api.timeline.extract(matterId);
    if (!res.error) {
      if (res.data.events.length > 0) setExtracted(res.data.events);
      else setExtractMsg(res.data.message ?? "No events found in document content.");
    }
    setExtracting(false);
  };

  const handleBulkSave = async (evs: ExtractedTimelineEvent[]) => {
    setBulkSaving(true);
    await api.timeline.bulkSave(matterId, evs);
    setExtracted(null);
    await load();
    setBulkSaving(false);
  };

  // Group events by year for section dividers
  const grouped = events.reduce<Record<string, TimelineEvent[]>>((acc, ev) => {
    const year = new Date(ev.event_date).getFullYear().toString();
    (acc[year] ??= []).push(ev);
    return acc;
  }, {});
  const sortedYears = Object.keys(grouped).sort();

  const editingEvent = events.find((e) => e.id === editingId);
  const editingForm: EventFormData | undefined = editingEvent
    ? {
        event_type: editingEvent.event_type,
        title: editingEvent.title,
        description: editingEvent.description ?? "",
        event_date: editingEvent.event_date.slice(0, 10),
        status: editingEvent.status,
        document_ref: editingEvent.document_ref ?? "",
      }
    : undefined;

  return (
    <div className="space-y-5">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Type filter chips */}
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setTypeFilter("all")}
            className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wide transition-colors ${typeFilter === "all" ? "bg-sky-500 text-white" : "bg-[#1E3A5F]/40 text-slate-400 hover:text-white border border-white/5"}`}
          >
            All
          </button>
          {EVENT_TYPES.map((t) => {
            const style = TYPE_STYLE[t];
            return (
              <button
                key={t}
                onClick={() => setTypeFilter(typeFilter === t ? "all" : t)}
                className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wide transition-colors border ${typeFilter === t ? `${style.badge} ${style.text}` : "bg-[#1E3A5F]/30 text-slate-500 border-white/5 hover:text-slate-300"}`}
              >
                {t}
              </button>
            );
          })}
        </div>

        {/* Action buttons */}
        <div className="flex gap-2">
          <button
            onClick={handleExtract}
            disabled={extracting}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold bg-amber-600/20 border border-amber-500/30 text-amber-400 rounded-lg hover:bg-amber-600/30 transition-colors disabled:opacity-50"
          >
            {extracting
              ? <><span className="animate-spin material-symbols-outlined text-sm">refresh</span> Extracting…</>
              : <><span className="material-symbols-outlined text-sm">auto_awesome</span> Extract from Docs</>
            }
          </button>
          <button
            onClick={() => { setShowAddForm(true); setEditingId(null); }}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold bg-sky-600 text-white rounded-lg hover:bg-sky-500 transition-colors"
          >
            <span className="material-symbols-outlined text-sm">add</span> Add Event
          </button>
        </div>
      </div>

      {/* Status filter pills */}
      <div className="flex gap-2">
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(statusFilter === s ? "all" : s)}
            className={`px-2.5 py-1 rounded text-[10px] font-bold uppercase tracking-wide transition-colors ${statusFilter === s ? "bg-sky-500/20 text-sky-300 border border-sky-500/30" : "text-slate-500 hover:text-slate-300"}`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* AI extract message */}
      {extractMsg && (
        <div className="text-xs text-slate-500 bg-[#0d1f35] border border-slate-700/40 rounded-lg px-4 py-3">
          {extractMsg}
        </div>
      )}

      {/* AI review panel */}
      {extracted && (
        <ExtractReviewPanel
          extracted={extracted}
          onConfirm={handleBulkSave}
          onDismiss={() => setExtracted(null)}
          saving={bulkSaving}
        />
      )}

      {/* Add form */}
      {showAddForm && (
        <EventForm onSave={handleCreate} onCancel={() => setShowAddForm(false)} saving={saving} />
      )}

      {/* Timeline */}
      {loading ? (
        <div className="text-slate-500 text-sm py-16 text-center">Loading timeline…</div>
      ) : events.length === 0 ? (
        <div className="bg-[#0d1f35]/50 border border-slate-700/30 rounded-2xl p-14 text-center space-y-3">
          <span className="material-symbols-outlined text-4xl text-slate-700">timeline</span>
          <p className="text-slate-500 text-sm">No timeline events yet.</p>
          <p className="text-slate-600 text-xs">Add events manually or use <span className="text-amber-400">Extract from Docs</span> to let AI pull dates from your documents.</p>
        </div>
      ) : (
        <div className="relative">
          {/* Continuous vertical line */}
          <div className="absolute left-[90px] top-6 bottom-6 w-px bg-slate-700/40" />

          {sortedYears.map((year) => (
            <div key={year} className="mb-6">
              {/* Year divider */}
              <div className="relative flex items-center gap-3 mb-4 ml-[90px]">
                <div className="w-px h-4 bg-slate-700/40" />
                <span className="bg-[#080f1c] border border-slate-700/50 px-3 py-0.5 rounded-full text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                  {year}
                </span>
              </div>

              {grouped[year].map((ev) => {
                const style = TYPE_STYLE[ev.event_type] ?? TYPE_STYLE.other;
                const date = new Date(ev.event_date);
                return (
                  <div key={ev.id} className="relative flex items-start gap-4 pb-4">
                    {/* Date column */}
                    <div className="w-[90px] flex-shrink-0 text-right pt-3 pr-3">
                      <span className="text-[10px] font-mono text-slate-500 leading-tight block">
                        {date.toLocaleDateString([], { month: "short", day: "numeric" })}
                      </span>
                    </div>

                    {/* Node on the line */}
                    <div className="relative flex-shrink-0 z-10 mt-3">
                      <div className={`w-3 h-3 rounded-full border-2 border-[#080f1c] ${style.dot} ${ev.status === "overdue" ? "animate-pulse ring-2 ring-red-500/30" : ""}`} />
                    </div>

                    {/* Event content */}
                    <div className="flex-1 min-w-0 pt-0.5">
                      {editingId === ev.id ? (
                        <EventForm
                          initial={editingForm}
                          onSave={(form) => handleUpdate(ev.id, form)}
                          onCancel={() => setEditingId(null)}
                          saving={saving}
                        />
                      ) : (
                        <EventCard
                          event={ev}
                          onEdit={() => setEditingId(ev.id)}
                          onDelete={() => handleDelete(ev.id)}
                          onStatusChange={(s) => handleStatusChange(ev.id, s)}
                        />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}

      {/* Legend */}
      {events.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-slate-800/60">
          <span className="text-[9px] text-slate-600 font-bold uppercase tracking-widest">Legend</span>
          {Object.entries(TYPE_STYLE).slice(0, 6).map(([type, s]) => (
            <div key={type} className="flex items-center gap-1.5">
              <div className={`w-2 h-2 rounded-full ${s.dot}`} />
              <span className="text-[9px] text-slate-500 capitalize">{type}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
