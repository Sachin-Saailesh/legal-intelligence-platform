"use client";

import { useCallback, useEffect, useState } from "react";
import { api, DiscoveryItem, DiscoveryStats, PatternAnalysis } from "@/lib/api";

// ── Constants ────────────────────────────────────────────────────────────────

const ITEM_TYPES = ["interrogatory", "document_request", "deposition", "admission", "subpoena", "expert_disclosure", "other"] as const;
const STATUSES = ["pending", "in_progress", "responded", "objected", "overdue", "completed"] as const;
const PRIORITIES = ["critical", "high", "medium", "low"] as const;

const TYPE_LABEL: Record<string, string> = {
  interrogatory: "Interrogatory",
  document_request: "Doc Request",
  deposition: "Deposition",
  admission: "Admission",
  subpoena: "Subpoena",
  expert_disclosure: "Expert Disc.",
  other: "Other",
};

const STATUS_STYLE: Record<string, string> = {
  pending:    "bg-slate-700/60 text-slate-300 border-slate-600/40",
  in_progress:"bg-sky-900/60 text-sky-300 border-sky-700/40",
  responded:  "bg-emerald-900/60 text-emerald-300 border-emerald-700/40",
  objected:   "bg-red-900/60 text-red-300 border-red-700/40",
  overdue:    "bg-red-900/60 text-red-400 border-red-700/40 animate-pulse",
  completed:  "bg-emerald-900/30 text-emerald-400 border-emerald-700/20",
};

const PRIORITY_STYLE: Record<string, { dot: string; chip: string }> = {
  critical: { dot: "bg-red-500 animate-pulse",    chip: "bg-red-900/50 text-red-400 border-red-700/40" },
  high:     { dot: "bg-orange-500",               chip: "bg-orange-900/50 text-orange-400 border-orange-700/40" },
  medium:   { dot: "bg-amber-500",                chip: "bg-amber-900/40 text-amber-400 border-amber-700/40" },
  low:      { dot: "bg-slate-500",                chip: "bg-slate-700/50 text-slate-400 border-slate-600/40" },
};

const PATTERN_SEVERITY: Record<string, { bg: string; border: string; text: string; icon: string }> = {
  critical: { bg: "bg-red-900/30",   border: "border-red-700/40",   text: "text-red-400",   icon: "emergency" },
  warning:  { bg: "bg-amber-900/20", border: "border-amber-700/30", text: "text-amber-400", icon: "warning" },
  info:     { bg: "bg-sky-900/20",   border: "border-sky-700/30",   text: "text-sky-400",   icon: "info" },
};

// ── Deadline helper ──────────────────────────────────────────────────────────

function DeadlineLabel({ deadline }: { deadline?: string }) {
  if (!deadline) return <span className="text-slate-600 text-xs">—</span>;
  const days = Math.ceil((new Date(deadline).getTime() - Date.now()) / 86_400_000);
  if (days < 0)  return <span className="text-red-400 text-xs font-mono">{Math.abs(days)}d overdue</span>;
  if (days === 0) return <span className="text-red-400 text-xs font-bold animate-pulse">Due today</span>;
  if (days <= 3)  return <span className="text-red-300 text-xs font-mono">{days}d left</span>;
  if (days <= 7)  return <span className="text-amber-400 text-xs font-mono">{days}d left</span>;
  return <span className="text-slate-400 text-xs font-mono">{new Date(deadline).toLocaleDateString([], { month: "short", day: "numeric" })}</span>;
}

// ── Stats card ───────────────────────────────────────────────────────────────

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className={`bg-[#0A192F] border rounded-xl px-5 py-4 ${color}`}>
      <p className="text-2xl font-extrabold text-white">{value}</p>
      <p className="text-[10px] font-bold uppercase tracking-wider mt-0.5 opacity-70">{label}</p>
    </div>
  );
}

// ── Add/Edit form ────────────────────────────────────────────────────────────

interface ItemFormData {
  item_type: string;
  title: string;
  description: string;
  deadline: string;
  status: string;
  priority: string;
  assigned_to: string;
  notes: string;
}

const EMPTY_ITEM_FORM: ItemFormData = {
  item_type: "interrogatory",
  title: "",
  description: "",
  deadline: "",
  status: "pending",
  priority: "medium",
  assigned_to: "",
  notes: "",
};

function ItemForm({
  initial,
  onSave,
  onCancel,
  saving,
}: {
  initial?: ItemFormData;
  onSave: (data: ItemFormData) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const [form, setForm] = useState<ItemFormData>(initial ?? EMPTY_ITEM_FORM);
  const set = (k: keyof ItemFormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((p) => ({ ...p, [k]: e.target.value }));

  return (
    <div className="bg-[#0d1f35] border border-sky-500/30 rounded-xl p-5 space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <div className="space-y-1">
          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Type</label>
          <select value={form.item_type} onChange={set("item_type")} className="w-full bg-[#1A1A2E] border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500/50">
            {ITEM_TYPES.map((t) => <option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Priority</label>
          <select value={form.priority} onChange={set("priority")} className="w-full bg-[#1A1A2E] border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500/50">
            {PRIORITIES.map((p) => <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>)}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Status</label>
          <select value={form.status} onChange={set("status")} className="w-full bg-[#1A1A2E] border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500/50">
            {STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}</option>)}
          </select>
        </div>
      </div>
      <div className="space-y-1">
        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Title *</label>
        <input value={form.title} onChange={set("title")} placeholder="e.g. Interrogatory Set #1 — Financial Records" className="w-full bg-[#1A1A2E] border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500/50" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Deadline</label>
          <input type="date" value={form.deadline} onChange={set("deadline")} className="w-full bg-[#1A1A2E] border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500/50" />
        </div>
        <div className="space-y-1">
          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Assigned To</label>
          <input value={form.assigned_to} onChange={set("assigned_to")} placeholder="Attorney name" className="w-full bg-[#1A1A2E] border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500/50" />
        </div>
      </div>
      <div className="space-y-1">
        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Description</label>
        <textarea value={form.description} onChange={set("description")} rows={2} placeholder="Optional details…" className="w-full bg-[#1A1A2E] border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500/50 resize-none" />
      </div>
      <div className="space-y-1">
        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Notes</label>
        <textarea value={form.notes} onChange={set("notes")} rows={2} placeholder="Internal notes, objections, response status…" className="w-full bg-[#1A1A2E] border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500/50 resize-none" />
      </div>
      <div className="flex gap-2 justify-end pt-1">
        <button onClick={onCancel} className="px-4 py-2 text-xs text-slate-400 border border-slate-700/50 rounded-lg hover:bg-slate-700/30 transition-colors">Cancel</button>
        <button onClick={() => onSave(form)} disabled={saving || !form.title.trim()} className="px-4 py-2 text-xs font-bold bg-sky-600 text-white rounded-lg disabled:opacity-40 hover:bg-sky-500 transition-colors">
          {saving ? "Saving…" : "Save Item"}
        </button>
      </div>
    </div>
  );
}

// ── Pattern analysis panel ───────────────────────────────────────────────────

function PatternPanel({
  analysis,
  onDismiss,
}: {
  analysis: PatternAnalysis;
  onDismiss: () => void;
}) {
  return (
    <div className="bg-[#080f1c] border border-violet-500/30 rounded-2xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-violet-400 text-base">pattern</span>
          <span className="text-sm font-bold text-white">Pattern Analysis</span>
          <span className="text-[10px] font-mono text-slate-500">{analysis.patterns.length} pattern{analysis.patterns.length !== 1 ? "s" : ""} found</span>
        </div>
        <button onClick={onDismiss} className="text-slate-500 hover:text-slate-300 text-xs">✕</button>
      </div>

      {/* Summary */}
      {analysis.summary && (
        <p className="text-sm text-slate-300 leading-relaxed border-l-2 border-violet-500/40 pl-3">{analysis.summary}</p>
      )}

      {/* Patterns */}
      {analysis.patterns.length > 0 && (
        <div className="space-y-2">
          {analysis.patterns.map((p, i) => {
            const sev = PATTERN_SEVERITY[p.severity] ?? PATTERN_SEVERITY.info;
            return (
              <div key={i} className={`rounded-xl border p-4 ${sev.bg} ${sev.border}`}>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`material-symbols-outlined text-sm ${sev.text}`}>{sev.icon}</span>
                  <span className={`text-[9px] font-bold uppercase tracking-widest ${sev.text}`}>{p.type.replace(/_/g, " ")}</span>
                  <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded border ${sev.bg} ${sev.border} ${sev.text}`}>{p.severity}</span>
                </div>
                <p className="text-sm font-semibold text-white">{p.title}</p>
                <p className="text-xs text-slate-400 mt-1 leading-relaxed">{p.description}</p>
                {p.items?.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {p.items.map((item, j) => (
                      <span key={j} className="text-[9px] font-mono bg-slate-800/60 border border-slate-700/30 text-slate-500 px-1.5 py-0.5 rounded">{item}</span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Recommendations */}
      {analysis.recommendations.length > 0 && (
        <div className="border-t border-slate-800/60 pt-3 space-y-1.5">
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Recommendations</p>
          {analysis.recommendations.map((r, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-slate-400">
              <span className="text-sky-500 font-bold flex-shrink-0">{i + 1}.</span>
              <span>{r}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

export function DiscoveryTracker({ matterId }: { matterId: string }) {
  const [items, setItems] = useState<DiscoveryItem[]>([]);
  const [stats, setStats] = useState<DiscoveryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<PatternAnalysis | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const params: Record<string, string> = {};
    if (statusFilter !== "all") params.status = statusFilter;
    if (typeFilter !== "all") params.item_type = typeFilter;
    const [itemsRes, statsRes] = await Promise.all([
      api.discovery.list(matterId, params),
      api.discovery.stats(matterId),
    ]);
    if (!itemsRes.error) setItems(itemsRes.data);
    if (!statsRes.error) setStats(statsRes.data);
    setLoading(false);
  }, [matterId, statusFilter, typeFilter]);

  useEffect(() => { setLoading(true); load(); }, [load]);

  const handleCreate = async (form: ItemFormData) => {
    setSaving(true);
    await api.discovery.create(matterId, {
      item_type: form.item_type as DiscoveryItem["item_type"],
      title: form.title,
      description: form.description || undefined,
      deadline: form.deadline ? new Date(form.deadline).toISOString() : undefined,
      status: form.status as DiscoveryItem["status"],
      priority: form.priority as DiscoveryItem["priority"],
      assigned_to: form.assigned_to || undefined,
      notes: form.notes || undefined,
    });
    setShowAddForm(false);
    await load();
    setSaving(false);
  };

  const handleUpdate = async (id: string, form: ItemFormData) => {
    setSaving(true);
    await api.discovery.update(matterId, id, {
      item_type: form.item_type as DiscoveryItem["item_type"],
      title: form.title,
      description: form.description || undefined,
      deadline: form.deadline ? new Date(form.deadline).toISOString() : undefined,
      status: form.status as DiscoveryItem["status"],
      priority: form.priority as DiscoveryItem["priority"],
      assigned_to: form.assigned_to || undefined,
      notes: form.notes || undefined,
    });
    setEditingId(null);
    await load();
    setSaving(false);
  };

  const handleStatusChange = async (id: string, status: string) => {
    await api.discovery.update(matterId, id, { status: status as DiscoveryItem["status"] });
    await load();
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this discovery item?")) return;
    await api.discovery.delete(matterId, id);
    await load();
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    const res = await api.discovery.analyzePatterns(matterId);
    if (!res.error) setAnalysis(res.data);
    setAnalyzing(false);
  };

  const editingItem = items.find((i) => i.id === editingId);
  const editingForm: ItemFormData | undefined = editingItem
    ? {
        item_type: editingItem.item_type,
        title: editingItem.title,
        description: editingItem.description ?? "",
        deadline: editingItem.deadline?.slice(0, 10) ?? "",
        status: editingItem.status,
        priority: editingItem.priority,
        assigned_to: editingItem.assigned_to ?? "",
        notes: editingItem.notes ?? "",
      }
    : undefined;

  const completionPct = stats && stats.total > 0 ? Math.round((stats.completed / stats.total) * 100) : 0;

  return (
    <div className="space-y-5">
      {/* Stats row */}
      {stats && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Total" value={stats.total} color="border-slate-700/50" />
            <StatCard label="Pending" value={stats.pending + stats.in_progress} color="border-sky-700/30" />
            <StatCard label="Overdue" value={stats.overdue} color={stats.overdue > 0 ? "border-red-700/40" : "border-slate-700/50"} />
            <StatCard label="Completed" value={stats.completed} color="border-emerald-700/30" />
          </div>

          {/* Progress bar */}
          {stats.total > 0 && (
            <div className="space-y-1">
              <div className="flex justify-between text-[10px] font-mono text-slate-500">
                <span>Discovery Progress</span>
                <span>{completionPct}%</span>
              </div>
              <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-sky-500 to-emerald-500 rounded-full transition-all duration-500"
                  style={{ width: `${completionPct}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Status filter */}
        <div className="flex flex-wrap gap-1.5">
          {(["all", ...STATUSES] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wide transition-colors ${
                statusFilter === s
                  ? "bg-sky-500 text-white"
                  : "bg-[#1E3A5F]/30 text-slate-500 border border-white/5 hover:text-slate-300"
              }`}
            >
              {s === "all" ? "All" : s.replace("_", " ")}
            </button>
          ))}
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold bg-violet-600/20 border border-violet-500/30 text-violet-400 rounded-lg hover:bg-violet-600/30 transition-colors disabled:opacity-50"
          >
            {analyzing
              ? <><span className="animate-spin material-symbols-outlined text-sm">refresh</span> Analyzing…</>
              : <><span className="material-symbols-outlined text-sm">pattern</span> Find Patterns</>
            }
          </button>
          <button
            onClick={() => { setShowAddForm(true); setEditingId(null); }}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold bg-sky-600 text-white rounded-lg hover:bg-sky-500 transition-colors"
          >
            <span className="material-symbols-outlined text-sm">add</span> Add Item
          </button>
        </div>
      </div>

      {/* Type filter */}
      <div className="flex flex-wrap gap-1.5">
        <button onClick={() => setTypeFilter("all")} className={`px-2.5 py-1 rounded text-[10px] font-bold uppercase tracking-wide transition-colors ${typeFilter === "all" ? "text-sky-300 bg-sky-500/10 border border-sky-500/20" : "text-slate-600 hover:text-slate-400"}`}>All Types</button>
        {ITEM_TYPES.map((t) => (
          <button key={t} onClick={() => setTypeFilter(typeFilter === t ? "all" : t)} className={`px-2.5 py-1 rounded text-[10px] font-bold uppercase tracking-wide transition-colors ${typeFilter === t ? "text-sky-300 bg-sky-500/10 border border-sky-500/20" : "text-slate-600 hover:text-slate-400"}`}>
            {TYPE_LABEL[t]}
          </button>
        ))}
      </div>

      {/* Pattern analysis result */}
      {analysis && <PatternPanel analysis={analysis} onDismiss={() => setAnalysis(null)} />}

      {/* Add form */}
      {showAddForm && (
        <ItemForm onSave={handleCreate} onCancel={() => setShowAddForm(false)} saving={saving} />
      )}

      {/* Items table */}
      {loading ? (
        <div className="text-slate-500 text-sm py-16 text-center">Loading discovery items…</div>
      ) : items.length === 0 ? (
        <div className="bg-[#0d1f35]/50 border border-slate-700/30 rounded-2xl p-14 text-center space-y-3">
          <span className="material-symbols-outlined text-4xl text-slate-700">folder_open</span>
          <p className="text-slate-500 text-sm">No discovery items yet.</p>
          <p className="text-slate-600 text-xs">Track interrogatories, document requests, depositions, and other discovery obligations.</p>
        </div>
      ) : (
        <div className="bg-[#0d1f35] rounded-2xl border border-slate-700/30 overflow-hidden">
          <table className="w-full text-left">
            <thead className="bg-[#1E3A5F]/20 border-b border-slate-700/30">
              <tr>
                {["Priority", "Type", "Title", "Deadline", "Assigned", "Status", ""].map((h) => (
                  <th key={h} className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {items.map((item) => {
                const pStyle = PRIORITY_STYLE[item.priority] ?? PRIORITY_STYLE.medium;
                const sStyle = STATUS_STYLE[item.status] ?? STATUS_STYLE.pending;
                const isExpanded = expandedId === item.id;
                const isEditing = editingId === item.id;

                return (
                  <>
                    <tr key={item.id} className="hover:bg-white/[0.02] transition-colors group">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <div className={`w-2 h-2 rounded-full flex-shrink-0 ${pStyle.dot}`} />
                          <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded border ${pStyle.chip}`}>{item.priority}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-[10px] font-mono text-slate-400 bg-slate-800/60 border border-slate-700/30 px-1.5 py-0.5 rounded">
                          {TYPE_LABEL[item.item_type] ?? item.item_type}
                        </span>
                      </td>
                      <td className="px-4 py-3 max-w-xs">
                        <button
                          onClick={() => setExpandedId(isExpanded ? null : item.id)}
                          className="text-sm text-slate-200 font-medium text-left hover:text-sky-300 transition-colors truncate block max-w-full"
                        >
                          {item.title}
                        </button>
                        {item.description && !isExpanded && (
                          <p className="text-[10px] text-slate-600 truncate mt-0.5">{item.description}</p>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <DeadlineLabel deadline={item.deadline} />
                      </td>
                      <td className="px-4 py-3">
                        {item.assigned_to
                          ? <span className="text-xs text-slate-400">{item.assigned_to}</span>
                          : <span className="text-slate-700 text-xs">—</span>
                        }
                      </td>
                      <td className="px-4 py-3">
                        <select
                          value={item.status}
                          onChange={(e) => handleStatusChange(item.id, e.target.value)}
                          className={`text-[10px] font-bold uppercase border rounded px-2 py-0.5 bg-transparent cursor-pointer focus:outline-none ${sStyle}`}
                        >
                          {STATUSES.map((s) => (
                            <option key={s} value={s} className="bg-[#1A1A2E] normal-case">{s.replace("_", " ")}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button onClick={() => { setEditingId(item.id); setExpandedId(null); }} className="p-1 text-slate-500 hover:text-sky-400 transition-colors">
                            <span className="material-symbols-outlined text-sm">edit</span>
                          </button>
                          <button onClick={() => handleDelete(item.id)} className="p-1 text-slate-500 hover:text-red-400 transition-colors">
                            <span className="material-symbols-outlined text-sm">delete</span>
                          </button>
                        </div>
                      </td>
                    </tr>

                    {/* Expanded detail row */}
                    {isExpanded && !isEditing && (
                      <tr key={`${item.id}-detail`} className="bg-[#080f1c]">
                        <td colSpan={7} className="px-4 py-3">
                          <div className="space-y-2">
                            {item.description && (
                              <div>
                                <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wide">Description</span>
                                <p className="text-sm text-slate-300 mt-0.5">{item.description}</p>
                              </div>
                            )}
                            {item.notes && (
                              <div>
                                <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wide">Notes</span>
                                <p className="text-sm text-slate-400 mt-0.5 italic">{item.notes}</p>
                              </div>
                            )}
                            <p className="text-[10px] font-mono text-slate-700">
                              Created {new Date(item.created_at).toLocaleDateString()} · Updated {new Date(item.updated_at).toLocaleDateString()}
                            </p>
                          </div>
                        </td>
                      </tr>
                    )}

                    {/* Edit form inline */}
                    {isEditing && (
                      <tr key={`${item.id}-edit`} className="bg-[#080f1c]">
                        <td colSpan={7} className="p-4">
                          <ItemForm
                            initial={editingForm}
                            onSave={(form) => handleUpdate(item.id, form)}
                            onCancel={() => setEditingId(null)}
                            saving={saving}
                          />
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
