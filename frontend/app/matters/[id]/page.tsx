"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { api, Document, Matter, SourceChunk } from "@/lib/api";
import { NavShell } from "@/components/nav-shell";
import ReactMarkdown from "react-markdown";
import { useAgentStream, WsFrame } from "@/lib/websocket";
import {
  AgentPipelineViz,
  type PipelineStage,
  type AgentId,
} from "@/components/agent-pipeline-viz";
import { TimelineView } from "@/components/timeline-view";
import { DiscoveryTracker } from "@/components/discovery-tracker";
import * as Dialog from "@radix-ui/react-dialog";

// ── Types ────────────────────────────────────────────────────────────────────

interface CompletedResult {
  output: string;
  citations: SourceChunk[];
  confidence: number | null;
  requiresReview: boolean;
  reviewReason?: string | null;
  agentRoute?: string;
  status: string;
}

interface ConversationEntry {
  sessionId: string;
  query: string;
  createdAt: string;
  result?: CompletedResult;
}

// ── Ingestion status pill ────────────────────────────────────────────────────
function IngestionBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: "bg-slate-700 text-slate-300",
    processing: "bg-sky-900/60 text-sky-300 animate-pulse",
    complete: "bg-emerald-900/60 text-emerald-300",
    failed: "bg-red-900/60 text-red-300",
  };
  return (
    <span className={`px-2 py-0.5 text-[10px] font-bold rounded-sm uppercase tracking-tighter ${map[status] || "bg-slate-700 text-slate-300"}`}>
      {status}
    </span>
  );
}

// ── Confidence bars ──────────────────────────────────────────────────────────
function ConfidenceBars({ score }: { score: number | null }) {
  const filled = score == null ? 0 : score >= 0.9 ? 4 : score >= 0.7 ? 3 : score >= 0.5 ? 2 : 1;
  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className={`h-2.5 w-2.5 rounded-[1px] ${i <= filled ? "bg-sky-500" : "bg-slate-700"}`} />
      ))}
      {score != null && <span className="ml-1.5 text-[10px] font-mono text-slate-500">{(score * 100).toFixed(0)}%</span>}
    </div>
  );
}

// ── Agent route badge ────────────────────────────────────────────────────────
function RouteBadge({ route }: { route?: string }) {
  if (!route) return null;
  const r = route.toLowerCase();
  const style =
    r.includes("contract") ? "bg-sky-900/60 text-sky-200 border border-sky-700/40" :
    r.includes("research") || r.includes("case") ? "bg-slate-700/60 text-slate-200 border border-slate-600/40" :
    r.includes("draft") ? "bg-[#1A1A2E] text-slate-300 border border-slate-600/40" :
    r.includes("compliance") ? "bg-emerald-900/60 text-emerald-300 border border-emerald-700/40" :
    r.includes("litigation") || r.includes("risk") ? "bg-red-900/60 text-red-300 border border-red-700/40" :
    "bg-slate-700/60 text-slate-300";
  const label = route.split("_")[0].toUpperCase();
  return (
    <span className={`px-2 py-0.5 rounded-[4px] text-[9px] font-bold tracking-tight uppercase ${style}`}>
      {label}
    </span>
  );
}

// ── Tooltip ──────────────────────────────────────────────────────────────────
function Tip({ text, children }: { text: string; children: React.ReactNode }) {
  return (
    <span className="relative group/tip inline-flex items-center">
      {children}
      <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-max max-w-[210px] px-2.5 py-1.5 rounded-md bg-slate-800 border border-slate-600/60 text-[11px] text-slate-200 leading-snug text-center shadow-xl opacity-0 group-hover/tip:opacity-100 transition-opacity duration-150 z-50">
        {text}
        <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800" />
      </span>
    </span>
  );
}

// ── Help Drawer ───────────────────────────────────────────────────────────────
function HelpDrawer({
  title,
  steps,
  trigger,
}: {
  title: string;
  steps: { icon: string; heading: string; body: string }[];
  trigger: React.ReactNode;
}) {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40" />
        <Dialog.Content className="fixed right-0 top-0 h-full w-80 bg-[#1A1A2E] border-l border-slate-700/60 z-50 flex flex-col shadow-2xl outline-none">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700/60">
            <Dialog.Title className="text-sm font-bold text-white">{title}</Dialog.Title>
            <Dialog.Close className="text-slate-500 hover:text-white transition-colors">
              <span className="material-symbols-outlined text-[20px]">close</span>
            </Dialog.Close>
          </div>
          <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
            {steps.map((s, i) => (
              <div key={i} className="flex gap-3">
                <div className="flex-shrink-0 w-7 h-7 rounded-full bg-[#0A192F] border border-slate-700/60 flex items-center justify-center">
                  <span className="material-symbols-outlined text-sky-400 text-[15px]">{s.icon}</span>
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-200 mb-0.5">{s.heading}</p>
                  <p className="text-xs text-slate-400 leading-relaxed">{s.body}</p>
                </div>
              </div>
            ))}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// ── Citation card ────────────────────────────────────────────────────────────
function CitationCard({ chunk, rank }: { chunk: SourceChunk; rank: number }) {
  const [open, setOpen] = useState(false);
  const conf = chunk.confidence_score ?? 0;
  return (
    <div className="bg-[#0A192F] border border-slate-700/50 rounded-lg p-3 text-xs space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-slate-500 font-mono">
          <span>#{rank + 1}</span>
          {chunk.source_doc_id && <span className="text-slate-600">doc:{chunk.source_doc_id.slice(0, 8)}</span>}
          {chunk.page_number && <span>p.{chunk.page_number}</span>}
        </div>
        <div className="flex items-center gap-2">
          <ConfidenceBars score={conf} />
          <button onClick={() => setOpen(!open)} className="text-sky-500 hover:underline text-[10px]">
            {open ? "Collapse" : "Expand"}
          </button>
        </div>
      </div>
      <p className={`text-slate-300 font-serif leading-relaxed ${open ? "whitespace-pre-wrap" : "line-clamp-2"}`}>
        {chunk.text}
      </p>
    </div>
  );
}

// ── Completed result panel (historical or just-finished) ─────────────────────
function ReviewReasonBanner({ reason, confidence }: { reason?: string | null; confidence: number | null }) {
  // Parse the reason string into structured parts for display
  // Format: "agent_name confidence X.XX is below the Y.YY threshold for intent queries; synthesizer passed at Z.ZZ — review triggered by specialist agent"
  const parts = reason ? reason.split("; ").filter(Boolean) : [];

  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 px-5 py-4 space-y-3">
      <div className="flex items-center gap-2">
        <span className="material-symbols-outlined text-amber-400 text-lg">policy</span>
        <span className="text-amber-400 text-sm font-bold">Attorney Review Required</span>
        <Link href="/review" className="ml-auto text-[10px] text-sky-400 hover:text-sky-300 font-semibold uppercase tracking-wider">
          Review Queue →
        </Link>
      </div>

      {parts.length > 0 ? (
        <div className="space-y-1.5">
          {parts.map((part, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-slate-300">
              <span className={`material-symbols-outlined text-[13px] mt-0.5 flex-shrink-0 ${
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
          This response requires attorney review before it can be used.
          {confidence != null && confidence >= 0.85 && (
            <span className="text-slate-500"> The synthesizer returned {(confidence * 100).toFixed(0)}% confidence — review was triggered by a specialist agent at an earlier pipeline stage.</span>
          )}
        </p>
      )}
    </div>
  );
}

function CompletedResultPanel({ result }: { result: CompletedResult }) {
  return (
    <div className="space-y-3">
      {/* Meta row */}
      <div className="flex items-center gap-2 flex-wrap">
        {result.agentRoute && (
          <Tip text="The specialist AI agent that handled this query">
            <RouteBadge route={result.agentRoute} />
          </Tip>
        )}
        {result.confidence != null && (
          <Tip text="How well the answer is grounded in your source documents">
            <ConfidenceBars score={result.confidence} />
          </Tip>
        )}
        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
          result.status === "pending_review"
            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
            : "bg-emerald-900/30 text-emerald-400 border border-emerald-700/20"
        }`}>
          {result.status === "pending_review" ? "Pending Review" : "Complete"}
        </span>
      </div>

      {result.requiresReview && (
        <ReviewReasonBanner reason={result.reviewReason} confidence={result.confidence} />
      )}

      {result.output && (
        <div className="bg-[#0A192F] border border-slate-700/50 rounded-xl p-5">
          <div className="lex-prose">
            <ReactMarkdown>{result.output}</ReactMarkdown>
          </div>
        </div>
      )}

      {result.citations.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
            Sources ({result.citations.length})
          </h4>
          {result.citations.map((c, i) => <CitationCard key={c.id || i} chunk={c} rank={i} />)}
        </div>
      )}
    </div>
  );
}

// ── Live agent stream panel (with pipeline visualization) ─────────────────────
function LiveAgentStreamPanel({
  sessionId,
  onComplete,
}: {
  sessionId: string;
  onComplete?: (result: CompletedResult) => void;
}) {
  const [chunks, setChunks] = useState<string[]>([]);
  const [citations, setCitations] = useState<SourceChunk[]>([]);
  const [activeAgents, setActiveAgents] = useState<AgentId[]>([]);
  const [doneAgents, setDoneAgents] = useState<AgentId[]>([]);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [requiresReview, setRequiresReview] = useState(false);
  const [intent, setIntent] = useState<string | null>(null);
  const [stage, setStage] = useState<PipelineStage>("classifying");
  const [error, setError] = useState<string | null>(null);
  const [agentRoute, setAgentRoute] = useState<string | undefined>();

  // Refs to accumulate data for the onComplete callback without stale closure issues
  const chunkAccRef = useRef<string[]>([]);
  const citationAccRef = useRef<SourceChunk[]>([]);

  const handleFrame = useCallback((frame: WsFrame) => {
    switch (frame.type) {
      case "intent_classified":
        setIntent(frame.intent);
        setStage("routing");
        setTimeout(() => setStage("agents_running"), 400);
        break;
      case "agent_start": {
        const agentId = frame.agent as AgentId;
        setStage("agents_running");
        setActiveAgents((p) => p.includes(agentId) ? p : [...p, agentId]);
        setAgentRoute(frame.agent);
        break;
      }
      case "agent_complete": {
        const agentId = frame.agent as AgentId;
        setActiveAgents((p) => p.filter((a) => a !== agentId));
        setDoneAgents((p) => p.includes(agentId) ? p : [...p, agentId]);
        break;
      }
      case "chunk":
        chunkAccRef.current.push(frame.text);
        setChunks((p) => [...p, frame.text]);
        setStage("synthesizing");
        break;
      case "citation": {
        const c = frame.chunk as unknown as SourceChunk;
        citationAccRef.current.push(c);
        setCitations((p) => [...p, c]);
        break;
      }
      case "complete":
        setConfidence(frame.confidence);
        setRequiresReview(frame.requires_review);
        setStage(frame.requires_review ? "review" : "complete");
        setActiveAgents((prev) => {
          setDoneAgents((d) => Array.from(new Set([...d, ...prev])));
          return [];
        });
        onComplete?.({
          output: chunkAccRef.current.join(""),
          citations: citationAccRef.current,
          confidence: frame.confidence,
          requiresReview: frame.requires_review,
          reviewReason: frame.review_reason ?? null,
          agentRoute,
          status: frame.requires_review ? "pending_review" : "complete",
        });
        break;
      case "error":
        setError(frame.message);
        break;
    }
  }, [onComplete, agentRoute]);

  const { isDone, close } = useAgentStream(sessionId, { onFrame: handleFrame });
  const fullText = chunks.join("");
  const isSynthesizing = ["synthesizing", "guarding", "complete", "review"].includes(stage);

  return (
    <div className="space-y-4">
      {/* Pipeline visualization — compact once output starts streaming */}
      <AgentPipelineViz
        stage={stage}
        intent={intent}
        activeAgents={activeAgents}
        doneAgents={doneAgents}
        confidence={confidence}
        compact={isSynthesizing}
      />

      {requiresReview && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-amber-400 text-xs font-medium">
          {confidence != null && confidence >= 0.80 ? (
            <>⚠ A sub-agent flagged potential risks requiring review. The confidence is {(confidence * 100).toFixed(0)}%. Go to{" "}</>
          ) : (
            <>⚠ Confidence below threshold — pending attorney review. Go to{" "}</>
          )}
          <Link href="/review" className="underline">Review Queue</Link>.
        </div>
      )}

      {/* Only show error if something genuinely broke (not session-not-found on natural close) */}
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-red-400 text-xs">
          {error}
        </div>
      )}

      {fullText && (
        <div className="bg-[#0A192F] border border-slate-700/50 rounded-xl p-5">
          <div className="lex-prose">
            <ReactMarkdown>{fullText}</ReactMarkdown>
          </div>
        </div>
      )}

      {citations.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
            Sources ({citations.length})
          </h4>
          {citations.map((c, i) => <CitationCard key={c.id || i} chunk={c} rank={i} />)}
        </div>
      )}

      {/* Cancellation Button */}
      {!isDone && (
        <div className="flex justify-start">
          <button
            onClick={() => {
              close();
              onComplete?.({
                output: chunkAccRef.current.join("") + "\n\n*[Analysis cancelled by user]*",
                citations: citationAccRef.current,
                confidence: confidence,
                requiresReview: false,
                agentRoute,
                status: "cancelled",
              });
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 mt-2 bg-slate-800 hover:bg-red-900/30 text-slate-400 hover:text-red-400 border border-slate-700 hover:border-red-900 rounded-md text-xs transition-colors"
          >
            <span className="material-symbols-outlined text-[14px]">stop_circle</span>
            Stop Analysis
          </button>
        </div>
      )}
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────
type Tab = "documents" | "query" | "timeline" | "discovery";

export default function MatterDetailPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const initialTab = (searchParams.get("tab") as Tab) || "documents";
  const prefill = searchParams.get("prefill");

  const [matter, setMatter] = useState<Matter | null>(null);
  const [tab, setTab] = useState<Tab>(initialTab);
  const [closingMatter, setClosingMatter] = useState(false);
  const [showCloseConfirm, setShowCloseConfirm] = useState(false);
  const [docs, setDocs] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [query, setQuery] = useState(prefill ? decodeURIComponent(prefill) : "");
  const [conversation, setConversation] = useState<ConversationEntry[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const conversationBottomRef = useRef<HTMLDivElement>(null);

  const isQueryRunning = conversation.some((c) => !c.result);

  // Block browser refresh / tab close while an analysis is in progress
  useEffect(() => {
    if (!isQueryRunning) return;
    const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isQueryRunning]);

  useEffect(() => {
    api.matters.get(id).then((res) => { if (!res.error) setMatter(res.data); });
  }, [id]);

  // Load query history for this matter
  useEffect(() => {
    api.queries.list(id, { limit: 20 }).then((res) => {
      if (!res.error && res.data.length > 0) {
        const historical: ConversationEntry[] = res.data
          .filter((s) => s.final_output)
          .map((s) => ({
            sessionId: s.id,
            query: s.query_text,
            createdAt: s.created_at,
            result: {
              output: s.final_output!,
              citations: s.source_chunks || [],
              confidence: s.confidence_score ?? null,
              requiresReview: s.status === "pending_review",
              reviewReason: s.review_reason ?? null,
              agentRoute: s.agent_route,
              status: s.status,
            },
          }));
        setConversation(historical);
      }
    });
  }, [id]);

  // Auto-scroll to bottom when new entries are added
  useEffect(() => {
    if (conversation.length > 0) {
      conversationBottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [conversation.length]);

  const loadDocs = () => {
    api.documents.list(id).then((res) => { if (!res.error) setDocs(res.data); });
  };

  useEffect(() => {
    loadDocs();
    const iv = setInterval(loadDocs, 5000);
    return () => clearInterval(iv);
  }, [id]);

  const uploadFile = async (file: File) => {
    setUploading(true);
    await api.documents.upload(id, file);
    setUploading(false);
    loadDocs();
  };

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) await uploadFile(file);
    e.target.value = "";
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) await uploadFile(file);
  };

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSubmitting(true);
    setQueryError(null);
    const trimmedQuery = query.trim();
    const res = await api.queries.create({ query: trimmedQuery, matter_id: id });
    if (res.error) {
      setQueryError(res.error.message);
    } else {
      setConversation((prev) => [
        ...prev,
        {
          sessionId: res.data.session_id,
          query: trimmedQuery,
          createdAt: new Date().toISOString(),
          result: undefined,
        },
      ]);
      setQuery("");
    }
    setSubmitting(false);
  };

  const handleEntryComplete = (sessionId: string, result: CompletedResult) => {
    setConversation((prev) =>
      prev.map((e) => (e.sessionId === sessionId ? { ...e, result } : e))
    );
  };

  const toggleMatterStatus = async () => {
    if (!matter) return;
    const newStatus = matter.status === "active" ? "closed" : "active";
    setClosingMatter(true);
    const res = await api.matters.update(id, { status: newStatus });
    if (!res.error) setMatter(res.data);
    setClosingMatter(false);
    setShowCloseConfirm(false);
  };

  if (!matter) {
    return (
      <NavShell>
        <div className="flex items-center justify-center h-64 text-slate-500 text-sm">Loading…</div>
      </NavShell>
    );
  }

  return (
    <NavShell>
      <div className="p-8 space-y-6">
        {/* Close confirmation modal */}
        {showCloseConfirm && (
          <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
            <div className="bg-[#1A1A2E] border border-slate-700 rounded-xl p-6 w-full max-w-sm shadow-2xl space-y-4">
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-amber-400 text-2xl">lock</span>
                <h3 className="font-bold text-white text-base">Close this matter?</h3>
              </div>
              <p className="text-slate-400 text-sm leading-relaxed">
                Closing marks this matter as inactive. All documents, timeline events, and discovery items remain accessible but the matter will no longer appear in active counts.
              </p>
              <div className="flex gap-2 justify-end pt-1">
                <button
                  onClick={() => setShowCloseConfirm(false)}
                  className="px-4 py-2 text-sm text-slate-400 hover:text-white border border-slate-700 rounded-md transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={toggleMatterStatus}
                  disabled={closingMatter}
                  className="px-4 py-2 text-sm bg-amber-600 hover:bg-amber-500 text-white rounded-md font-semibold transition-colors disabled:opacity-50"
                >
                  {closingMatter ? "Closing…" : "Close Matter"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Breadcrumb + title */}
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-500 uppercase tracking-widest mb-1">
            <Link href="/matters" className="hover:text-sky-400 transition-colors">Matters</Link>
            <span className="material-symbols-outlined text-[14px]">chevron_right</span>
            <span className="text-sky-400 font-bold truncate max-w-xs">{matter.title}</span>
          </nav>
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-2xl font-bold text-white">{matter.title}</h2>
              <span className={`px-2.5 py-1 text-xs font-bold uppercase tracking-wider rounded-md flex-shrink-0 ${
                matter.status === "active"
                  ? "bg-emerald-900/50 text-emerald-400 border border-emerald-700/30"
                  : "bg-slate-700/50 text-slate-400 border border-slate-600/30"
              }`}>
                {matter.status}
              </span>
              {matter.closed_at && (
                <span className="text-xs text-slate-500 font-mono">
                  Closed {new Date(matter.closed_at).toLocaleDateString()}
                </span>
              )}
            </div>
            {matter.status === "active" ? (
              <Tip text="Mark this matter as inactive. Documents and history are preserved.">
                <button
                  onClick={() => setShowCloseConfirm(true)}
                  className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-slate-300 border border-slate-600 rounded-md hover:border-amber-500/50 hover:text-amber-400 transition-colors flex-shrink-0"
                >
                  <span className="material-symbols-outlined text-base">lock</span>
                  Close Matter
                </button>
              </Tip>
            ) : (
              <button
                onClick={toggleMatterStatus}
                disabled={closingMatter}
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-emerald-400 border border-emerald-700/40 rounded-md hover:border-emerald-500 hover:bg-emerald-900/20 transition-colors flex-shrink-0 disabled:opacity-50"
              >
                <span className="material-symbols-outlined text-base">lock_open</span>
                {closingMatter ? "Reopening…" : "Reopen Matter"}
              </button>
            )}
          </div>
          <p className="text-sm text-slate-400 mt-1 font-mono">
            {matter.matter_type} {matter.jurisdiction ? `· ${matter.jurisdiction}` : ""} {matter.practice_area ? `· ${matter.practice_area}` : ""}
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-6 border-b border-white/10 overflow-x-auto">
          {(["documents", "timeline", "discovery", "query"] as Tab[]).map((t) => {
            const labels: Record<Tab, string> = {
              documents: "Documents",
              timeline: "Timeline",
              discovery: "Discovery",
              query: "Query Intelligence",
            };
            const icons: Record<Tab, string> = {
              documents: "description",
              timeline: "timeline",
              discovery: "folder_open",
              query: "psychology",
            };
            return (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`pb-3 flex items-center gap-1.5 text-sm font-semibold transition-colors whitespace-nowrap flex-shrink-0 ${
                  tab === t
                    ? "text-sky-400 border-b-2 border-sky-400"
                    : "text-slate-400 hover:text-white border-b-2 border-transparent"
                }`}
              >
                <span className="material-symbols-outlined text-[16px]">{icons[t]}</span>
                {labels[t]}
              </button>
            );
          })}
        </div>

        {/* Documents Tab */}
        {tab === "documents" && (
          <div className="space-y-4">
            {/* Upload zone header */}
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Upload files to make them searchable by the AI pipeline.</span>
              <HelpDrawer
                title="How to Upload Documents"
                steps={[
                  { icon: "upload_file", heading: "Choose your file", body: "Click Browse Files or drag a PDF, DOCX, or TXT file directly onto the upload area. Max size is 50MB per file." },
                  { icon: "hourglass_top", heading: "Processing starts automatically", body: "The file is sent to the server immediately. You will see its status change from Pending to Processing." },
                  { icon: "auto_fix_high", heading: "OCR and indexing", body: "The system reads the document, runs OCR on scanned pages, and splits the text into searchable chunks." },
                  { icon: "check_circle", heading: "Ready to query", body: "Once status shows Complete, the document's content is indexed and available to the AI when you run an analysis." },
                  { icon: "warning", heading: "If status shows Failed", body: "The file may be corrupted or password protected. Try exporting it as a plain PDF and uploading again." },
                ]}
                trigger={
                  <button className="flex items-center gap-1.5 text-[11px] text-slate-500 hover:text-sky-400 transition-colors font-medium">
                    <span className="material-symbols-outlined text-[14px]">help_outline</span>
                    How does uploading work?
                  </button>
                }
              />
            </div>

            {/* Upload zone */}
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileRef.current?.click()}
              className={`bg-[#0A192F] border-2 border-dashed rounded-xl p-10 flex flex-col items-center justify-center text-center cursor-pointer transition-colors ${
                dragOver ? "border-sky-500 bg-sky-500/5" : "border-slate-700 hover:border-slate-600"
              }`}
            >
              <div className="w-12 h-12 rounded-full bg-[#1E3A5F] flex items-center justify-center mb-4">
                <span className="material-symbols-outlined text-sky-400 text-2xl">upload_file</span>
              </div>
              <p className="text-white font-semibold text-sm">
                {uploading ? "Uploading…" : "Drop PDFs or DOCX files here"}
              </p>
              <p className="text-slate-500 text-xs mt-1">Max 50MB · OCR and indexing start automatically</p>
              <Tip text="Supports PDF, DOCX, DOC, and TXT files up to 50MB">
                <button className="mt-5 px-5 py-2 bg-[#1E3A5F] text-sky-400 text-xs font-semibold rounded-md border border-sky-500/20 hover:bg-[#1E3A5F]/80 transition-colors">
                  Browse Files
                </button>
              </Tip>
              <input ref={fileRef} type="file" accept=".pdf,.docx,.doc,.txt" className="hidden" onChange={handleFileInput} disabled={uploading} />
            </div>

            {/* Document list */}
            {docs.length > 0 && (
              <div className="bg-[#152a4a] rounded-xl border border-white/5 overflow-hidden">
                <div className="px-6 py-3 border-b border-white/5 flex justify-between items-center">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Documents ({docs.length})</span>
                </div>
                <table className="w-full text-left">
                  <thead className="bg-[#1E3A5F]/30">
                    <tr>
                      {["Filename", "Type", "Chunks", "Status", "Uploaded"].map((h) => (
                        <th key={h} className="px-6 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {docs.map((doc) => (
                      <tr key={doc.id} className="hover:bg-white/[0.02] transition-colors">
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <span className="material-symbols-outlined text-slate-500 text-base">description</span>
                            <span className="text-sm text-slate-300 font-medium">{doc.filename}</span>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-xs text-slate-400 uppercase font-mono">{doc.doc_type || "—"}</td>
                        <td className="px-6 py-4 text-xs text-slate-400 font-mono">{doc.chunk_count ?? 0}</td>
                        <td className="px-6 py-4"><IngestionBadge status={doc.ingestion_status} /></td>
                        <td className="px-6 py-4 text-xs text-slate-500 font-mono">
                          {new Date(doc.created_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Query Tab */}
        {tab === "query" && (
          <div className="space-y-6">
            {/* Running banner */}
            {isQueryRunning && (
              <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-sky-500/10 border border-sky-500/30 text-sky-300 text-xs font-medium">
                <span className="relative flex h-2 w-2 flex-shrink-0">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-sky-500" />
                </span>
                Analysis in progress. Stay on this page until it finishes.
              </div>
            )}

            {/* Header row with help drawer */}
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">
                {conversation.length === 0 ? "Ask the Intelligence Layer something about this matter." : `${conversation.length} quer${conversation.length === 1 ? "y" : "ies"} in this matter`}
              </span>
              <HelpDrawer
                title="How to Run an Analysis"
                steps={[
                  { icon: "edit_note", heading: "Type your question", body: "Describe what you want to know about this matter. Be specific — mention clauses, risks, or parties if relevant." },
                  { icon: "send", heading: "Submit", body: "Click Run Analysis or press Cmd + Enter. The system will route your question to the right specialist agent." },
                  { icon: "psychology", heading: "Watch the pipeline", body: "The pipeline view shows which agents are working. Contract, litigation, research, and drafting agents run in parallel when needed." },
                  { icon: "source", heading: "Review sources", body: "Every answer includes numbered source citations from your uploaded documents. Expand them to read the exact passage used." },
                  { icon: "policy", heading: "Attorney review flag", body: "If the AI confidence is low, the result is flagged for attorney review. You can find flagged responses in the Review Queue." },
                ]}
                trigger={
                  <button className="flex items-center gap-1.5 text-[11px] text-slate-500 hover:text-sky-400 transition-colors font-medium">
                    <span className="material-symbols-outlined text-[14px]">help_outline</span>
                    How does this work?
                  </button>
                }
              />
            </div>

            {/* Conversation thread */}
            {conversation.length === 0 && (
              <div className="text-center py-10 text-slate-600 text-sm">
                No queries yet.
              </div>
            )}

            <div className="space-y-8">
              {conversation.map((entry) => (
                <div key={entry.sessionId} className="space-y-3">
                  {/* User query bubble */}
                  <div className="flex justify-end">
                    <div className="bg-[#1E3A5F]/60 border border-sky-500/20 rounded-xl px-4 py-3 max-w-2xl">
                      <p className="text-sm text-slate-200">{entry.query}</p>
                      <p className="text-[10px] text-slate-500 mt-1.5 font-mono">
                        {new Date(entry.createdAt).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}
                      </p>
                    </div>
                  </div>

                  {/* Response */}
                  {entry.result ? (
                    <CompletedResultPanel result={entry.result} />
                  ) : (
                    <LiveAgentStreamPanel
                      sessionId={entry.sessionId}
                      onComplete={(result) => handleEntryComplete(entry.sessionId, result)}
                    />
                  )}
                </div>
              ))}
              <div ref={conversationBottomRef} />
            </div>

            {/* Query input — always at bottom */}
            <div className="sticky bottom-6">
              <div className="bg-[#1A1A2E] rounded-xl border border-slate-700/50 p-1 shadow-xl">
                <textarea
                  className="w-full min-h-[100px] p-4 text-sm bg-transparent border-none focus:outline-none resize-none text-slate-200 placeholder-slate-600 font-body"
                  placeholder="Ask the Intelligence Layer… e.g. 'Summarize termination clauses and flag risks' or 'Draft a limitation of liability clause'"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                      e.preventDefault();
                      handleQuery(e as unknown as React.FormEvent);
                    }
                  }}
                />
                <div className="flex items-center justify-between p-3 bg-[#1E3A5F]/30 rounded-b-lg">
                  <span className="text-[10px] text-slate-600 font-mono">⌘ + Enter to submit</span>
                  <Tip text={isQueryRunning ? "Wait for the current analysis to finish" : "Submit your question (or press Cmd + Enter)"}>
                    <button
                      onClick={handleQuery}
                      disabled={submitting || !query.trim() || isQueryRunning}
                      className="flex items-center gap-2 px-5 py-2 bg-gradient-to-br from-sky-500 to-blue-600 text-white text-xs font-bold rounded-md disabled:opacity-40 disabled:cursor-not-allowed hover:brightness-110 active:scale-95 transition-all"
                    >
                      {submitting || isQueryRunning ? (
                        <span className="animate-spin material-symbols-outlined text-base">refresh</span>
                      ) : (
                        <span className="material-symbols-outlined text-base">send</span>
                      )}
                      {submitting || isQueryRunning ? "Analysis Running..." : "Run Analysis"}
                    </button>
                  </Tip>
                </div>
              </div>

              {queryError && (
                <div className="mt-2 bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-red-400 text-sm">
                  {queryError}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Timeline Tab */}
        {tab === "timeline" && (
          <div className="space-y-2">
            <div className="flex items-center justify-between mb-1">
              <div>
                <h3 className="text-lg font-bold text-white">Case Timeline</h3>
                <p className="text-xs text-slate-500 mt-0.5">Chronological record of filings, hearings, deadlines, and key events</p>
              </div>
            </div>
            <TimelineView matterId={id} />
          </div>
        )}

        {/* Discovery Tab */}
        {tab === "discovery" && (
          <div className="space-y-2">
            <div className="flex items-center justify-between mb-1">
              <div>
                <h3 className="text-lg font-bold text-white">Discovery Management</h3>
                <p className="text-xs text-slate-500 mt-0.5">Track interrogatories, document requests, depositions, and discovery deadlines</p>
              </div>
            </div>
            <DiscoveryTracker matterId={id} />
          </div>
        )}
      </div>
    </NavShell>
  );
}
