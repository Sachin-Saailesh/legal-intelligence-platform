"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Matter } from "@/lib/api";
import { NavShell } from "@/components/nav-shell";

function TypeBadge({ type }: { type: string }) {
  const map: Record<string, string> = {
    contract: "bg-sky-900/60 text-sky-300 border border-sky-700/40",
    litigation: "bg-slate-700/60 text-slate-300 border border-slate-600/40",
    compliance: "bg-emerald-900/60 text-emerald-300 border border-emerald-700/40",
  };
  return (
    <span className={`px-2 py-0.5 text-[10px] font-bold rounded-sm uppercase tracking-tighter ${map[type] || "bg-slate-700 text-slate-300"}`}>
      {type}
    </span>
  );
}

function StatusDot({ status }: { status: string }) {
  const c: Record<string, { dot: string; text: string; label: string }> = {
    active: { dot: "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]", text: "text-emerald-400", label: "Active" },
    closed: { dot: "bg-slate-500", text: "text-slate-400", label: "Closed" },
  };
  const s = c[status] || { dot: "bg-slate-500", text: "text-slate-400", label: status };
  return (
    <div className="flex items-center gap-1.5">
      <div className={`w-2 h-2 rounded-full ${s.dot}`} />
      <span className={`text-[11px] font-bold uppercase tracking-wider ${s.text}`}>{s.label}</span>
    </div>
  );
}

export default function MattersPage() {
  const [matters, setMatters] = useState<Matter[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [filter, setFilter] = useState<"all" | "active" | "closed">("all");
  const [form, setForm] = useState({ title: "", matter_type: "contract", jurisdiction: "", practice_area: "" });

  const load = () => {
    api.matters.list().then((res) => {
      if (!res.error) setMatters(res.data);
      setLoading(false);
    });
  };

  useEffect(load, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await api.matters.create(form);
    if (!res.error) { setShowCreate(false); load(); }
  };

  const filtered = matters.filter((m) => filter === "all" || m.status === filter);

  return (
    <NavShell>
      <div className="p-8 space-y-6">
        {/* Header */}
        <div className="flex items-end justify-between">
          <div>
            <nav className="flex items-center gap-2 text-xs font-medium text-slate-500 uppercase tracking-widest mb-1">
              <span>Legal Operations</span>
              <span className="material-symbols-outlined text-[14px]">chevron_right</span>
              <span className="text-sky-400 font-bold">Matters</span>
            </nav>
            <h2 className="text-3xl font-extrabold text-white tracking-tight">Matters</h2>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-br from-sky-500 to-blue-600 text-white text-sm font-bold rounded-md shadow-lg hover:brightness-110 active:scale-95 transition-all"
          >
            <span className="material-symbols-outlined text-lg">add_circle</span>
            New Matter
          </button>
        </div>

        {/* Create Modal */}
        {showCreate && (
          <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
            <div className="bg-[#1A1A2E] border border-slate-700 rounded-xl p-6 w-full max-w-md space-y-4 shadow-2xl">
              <h3 className="font-bold text-white text-base">Create New Matter</h3>
              <form onSubmit={handleCreate} className="space-y-3">
                <input
                  className="w-full bg-[#0A192F] border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500"
                  placeholder="Matter title"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  required
                />
                <select
                  className="w-full bg-[#0A192F] border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500"
                  value={form.matter_type}
                  onChange={(e) => setForm({ ...form, matter_type: e.target.value })}
                >
                  <option value="contract">Contract</option>
                  <option value="litigation">Litigation</option>
                  <option value="compliance">Compliance</option>
                </select>
                <input
                  className="w-full bg-[#0A192F] border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500"
                  placeholder="Jurisdiction (e.g. Delaware, US Federal)"
                  value={form.jurisdiction}
                  onChange={(e) => setForm({ ...form, jurisdiction: e.target.value })}
                />
                <input
                  className="w-full bg-[#0A192F] border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500"
                  placeholder="Practice area (e.g. M&A, Securities)"
                  value={form.practice_area}
                  onChange={(e) => setForm({ ...form, practice_area: e.target.value })}
                />
                <div className="flex gap-2 justify-end pt-2">
                  <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-slate-400 hover:text-white border border-slate-700 rounded-md transition-colors">
                    Cancel
                  </button>
                  <button type="submit" className="px-4 py-2 text-sm bg-sky-500 text-white rounded-md font-semibold hover:bg-sky-400 transition-colors">
                    Create Matter
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Filter Bar */}
        <div className="bg-[#1E3A5F]/40 rounded-lg p-1.5 border border-white/5 flex items-center gap-1 w-fit">
          {(["all", "active", "closed"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-5 py-1.5 text-xs font-bold uppercase tracking-wider rounded transition-colors ${
                filter === f
                  ? "bg-sky-500 text-white shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="bg-[#152a4a] rounded-xl shadow-2xl overflow-hidden border border-white/5">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-[#1E3A5F]/50 border-b border-white/5">
                  {["Matter", "Type", "Jurisdiction", "Created", "Status", ""].map((h) => (
                    <th key={h} className="px-6 py-4 text-[11px] font-bold text-slate-400 uppercase tracking-widest">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {loading ? (
                  <tr><td colSpan={6} className="px-6 py-12 text-center text-slate-500 text-sm">Loading…</td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={6} className="px-6 py-12 text-center text-slate-500 text-sm">No matters found. Create one to get started.</td></tr>
                ) : (
                  filtered.map((m, i) => (
                    <tr
                      key={m.id}
                      className={`hover:bg-[#1E3A5F]/30 transition-colors group ${i % 2 === 1 ? "bg-white/[0.02]" : ""}`}
                    >
                      <td className="px-6 py-5">
                        <div className="flex flex-col">
                          <Link href={`/matters/${m.id}`} className="text-sm font-bold text-slate-200 leading-tight group-hover:text-sky-400 transition-colors">
                            {m.title}
                          </Link>
                          <span className="text-xs font-mono text-slate-600 mt-0.5">
                            #{m.id.slice(0, 8)}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-5"><TypeBadge type={m.matter_type} /></td>
                      <td className="px-6 py-5 text-xs text-slate-400">{m.jurisdiction || "—"}</td>
                      <td className="px-6 py-5 text-xs text-slate-400">{new Date(m.created_at).toLocaleDateString()}</td>
                      <td className="px-6 py-5"><StatusDot status={m.status} /></td>
                      <td className="px-6 py-5 text-right">
                        <Link href={`/matters/${m.id}`} className="text-slate-500 hover:text-sky-400 transition-colors p-1">
                          <span className="material-symbols-outlined text-lg">arrow_forward</span>
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <div className="px-6 py-3 bg-[#1E3A5F]/20 border-t border-white/5 flex items-center justify-between">
            <span className="text-xs text-slate-500">
              {filtered.length} matter{filtered.length !== 1 ? "s" : ""}
            </span>
          </div>
        </div>
      </div>
    </NavShell>
  );
}
