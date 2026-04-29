"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, AgentSession } from "@/lib/api";
import { NavShell } from "@/components/nav-shell";
import ReactMarkdown from "react-markdown";

function ReviewReasonBanner({ reason, confidence }: { reason?: string | null; confidence: number | null }) {
  const parts = reason ? reason.split("; ").filter(Boolean) : [];
  return (
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 space-y-2">
      <div className="flex items-center gap-2">
        <span className="material-symbols-outlined text-amber-400 text-base">policy</span>
        <span className="text-amber-400 text-xs font-bold">Why Review Was Triggered</span>
      </div>
      {parts.length > 0 ? (
        <div className="space-y-1">
          {parts.map((part, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-slate-300">
              <span className={`material-symbols-outlined text-[12px] mt-0.5 flex-shrink-0 ${
                part.includes("below") ? "text-amber-400" : "text-emerald-400"
              }`}>
                {part.includes("below") ? "warning" : "check_circle"}
              </span>
              <span className="leading-relaxed capitalize">{part}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-slate-400">
          Flagged for attorney review.
          {confidence != null && confidence >= 0.85 && (
            <span className="text-slate-500"> Synthesizer returned {(confidence * 100).toFixed(0)}% — review triggered by a specialist agent.</span>
          )}
        </p>
      )}
    </div>
  );
}

function ConfidenceBars({ score }: { score: number | null }) {
  const filled = score == null ? 0 : score >= 0.9 ? 4 : score >= 0.7 ? 3 : score >= 0.5 ? 2 : 1;
  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className={`h-2.5 w-2.5 rounded-[1px] ${i <= filled ? "bg-sky-500" : "bg-slate-700"}`} />
      ))}
      {score != null && (
        <span className="ml-1.5 text-[10px] font-mono text-slate-500">{(score * 100).toFixed(0)}%</span>
      )}
    </div>
  );
}

export default function ReviewPage() {
  const [sessions, setSessions] = useState<AgentSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [corrections, setCorrections] = useState<Record<string, string>>({});
  const [correctionTypes, setCorrectionTypes] = useState<Record<string, string>>({});
  const [fullSessions, setFullSessions] = useState<Record<string, AgentSession>>({});
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const load = () => {
    api.review.queue().then((res) => {
      if (!res.error) setSessions(res.data);
      setLoading(false);
    });
  };

  useEffect(load, []);

  const handleExpand = async (sessionId: string) => {
    if (expanded === sessionId) { setExpanded(null); return; }
    setExpanded(sessionId);
    if (!fullSessions[sessionId]) {
      const res = await api.queries.get(sessionId);
      if (!res.error) setFullSessions((p) => ({ ...p, [sessionId]: res.data }));
    }
  };

  const handleApprove = async (sessionId: string, originalOutput: string) => {
    const corrected = corrections[sessionId];
    await api.review.approve(sessionId, {
      corrected_output: corrected && corrected !== originalOutput ? corrected : undefined,
      correction_type: correctionTypes[sessionId],
    });
    setActionMsg(`Session approved`);
    setTimeout(() => setActionMsg(null), 3000);
    load();
  };

  const handleReject = async (sessionId: string) => {
    const reason = corrections[sessionId] || "Rejected by attorney";
    await api.review.reject(sessionId, reason);
    setActionMsg(`Session rejected`);
    setTimeout(() => setActionMsg(null), 3000);
    load();
  };

  return (
    <NavShell>
      <div className="p-8 space-y-6">
        {/* Header */}
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-500 uppercase tracking-widest mb-1">
            <span>Legal Operations</span>
            <span className="material-symbols-outlined text-[14px]">chevron_right</span>
            <span className="text-sky-400 font-bold">Review Queue</span>
          </nav>
          <h2 className="text-3xl font-extrabold text-white tracking-tight">Review Queue</h2>
          <p className="text-sm text-slate-500 mt-1">Agent sessions requiring attorney approval</p>
        </div>

        {/* Toast */}
        {actionMsg && (
          <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg px-4 py-3 text-emerald-400 text-sm flex items-center gap-2">
            <span className="material-symbols-outlined text-base">check_circle</span>
            {actionMsg}
          </div>
        )}

        {/* Queue */}
        {loading ? (
          <div className="text-center py-12 text-slate-500 text-sm">Loading…</div>
        ) : sessions.length === 0 ? (
          <div className="bg-[#1A1A2E] rounded-xl border border-slate-700/50 p-12 text-center">
            <span className="material-symbols-outlined text-4xl text-slate-700 block mb-3">task_alt</span>
            <p className="text-slate-400 font-semibold">No sessions pending review</p>
            <p className="text-slate-600 text-sm mt-1">All agent outputs have been reviewed.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {sessions.map((s) => {
              const full = fullSessions[s.id];
              const isExpanded = expanded === s.id;
              const originalOutput = s.final_output ?? "";
              const corrected = corrections[s.id] ?? originalOutput;
              const hasDiff = corrected !== originalOutput && corrected !== "";

              return (
                <div key={s.id} className="bg-[#1A1A2E] rounded-xl border border-amber-500/20 overflow-hidden">
                  {/* Session header */}
                  <div
                    className="p-5 cursor-pointer hover:bg-[#1E3A5F]/20 transition-colors"
                    onClick={() => handleExpand(s.id)}
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="px-2 py-0.5 rounded-[4px] text-[8px] font-extrabold bg-amber-500/20 text-amber-400 border border-amber-500/30 uppercase tracking-tighter">
                            Pending Review
                          </span>
                          <ConfidenceBars score={s.confidence_score ?? null} />
                        </div>
                        <p className="text-sm font-semibold text-white truncate">{s.query_text}</p>
                        <p className="text-[10px] font-mono text-slate-500 mt-0.5">
                          #{s.id.slice(0, 8)} · Matter{" "}
                          <Link
                            href={`/matters/${s.matter_id}`}
                            className="text-sky-500 hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {s.matter_id.slice(0, 8)}…
                          </Link>
                          {" · "}{new Date(s.created_at).toLocaleString()}
                        </p>
                      </div>
                      <span className="material-symbols-outlined text-slate-500 text-lg">
                        {isExpanded ? "expand_less" : "expand_more"}
                      </span>
                    </div>
                  </div>

                  {/* Expanded */}
                  {isExpanded && (
                    <div className="border-t border-slate-700/40 p-5 space-y-5 bg-[#0A192F]/20">
                      {/* Review reason */}
                      {s.review_reason && (
                        <ReviewReasonBanner reason={s.review_reason} confidence={s.confidence_score ?? null} />
                      )}

                      {/* Agent output */}
                      <div>
                        <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                          Agent Output
                        </h4>
                        <div className="bg-[#0A192F] border border-slate-700/50 rounded-xl p-5">
                          <div className="lex-prose">
                            <ReactMarkdown>{s.final_output || "_No output_"}</ReactMarkdown>
                          </div>
                        </div>
                      </div>

                      {/* Source chunks */}
                      {full?.source_chunks && full.source_chunks.length > 0 && (
                        <div>
                          <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                            Sources ({full.source_chunks.length})
                          </h4>
                          <div className="space-y-2">
                            {full.source_chunks.slice(0, 4).map((c, i) => (
                              <div key={c.id || i} className="bg-[#0A192F] border border-slate-700/30 rounded-lg p-3">
                                <div className="flex items-center justify-between text-[10px] font-mono text-slate-500 mb-1">
                                  <span>#{i + 1} · doc:{(c.source_doc_id || "").slice(0, 8)}{c.page_number ? ` · p.${c.page_number}` : ""}</span>
                                  <ConfidenceBars score={c.confidence_score ?? null} />
                                </div>
                                <p className="text-xs text-slate-300 font-serif leading-relaxed line-clamp-3">{c.text}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Correction */}
                      <div>
                        <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                          Attorney Correction (optional)
                        </h4>
                        <textarea
                          className="w-full bg-[#0A192F] border border-slate-700 rounded-lg px-4 py-3 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500 min-h-[100px] resize-none"
                          value={corrected}
                          onChange={(e) => setCorrections({ ...corrections, [s.id]: e.target.value })}
                          placeholder="Edit the output to correct factual errors, legal reasoning, or tone…"
                        />
                        <select
                          className="mt-2 bg-[#0A192F] border border-slate-700 rounded-md px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-sky-500"
                          value={correctionTypes[s.id] || "factual"}
                          onChange={(e) => setCorrectionTypes({ ...correctionTypes, [s.id]: e.target.value })}
                        >
                          <option value="factual">Factual</option>
                          <option value="legal_reasoning">Legal Reasoning</option>
                          <option value="citation">Citation</option>
                          <option value="tone">Tone</option>
                          <option value="completeness">Completeness</option>
                        </select>
                      </div>

                      {/* Actions */}
                      <div className="flex gap-3 justify-end pt-2 border-t border-slate-700/30">
                        <button
                          onClick={() => handleReject(s.id)}
                          className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold border border-red-500/30 text-red-400 rounded-md hover:bg-red-500/10 transition-colors"
                        >
                          <span className="material-symbols-outlined text-sm">cancel</span>
                          Reject
                        </button>
                        <button
                          onClick={() => handleApprove(s.id, originalOutput)}
                          className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold bg-emerald-600 text-white rounded-md hover:bg-emerald-500 transition-colors"
                        >
                          <span className="material-symbols-outlined text-sm">check_circle</span>
                          {hasDiff ? "Approve with Correction" : "Approve"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </NavShell>
  );
}
