"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import { useAgentStream, WsFrame } from "@/lib/websocket";
import { CitationCard } from "./citation-card";
import { SourceChunk } from "@/lib/api";

interface AgentStreamProps {
  sessionId: string | null;
}

export function AgentStream({ sessionId }: AgentStreamProps) {
  const [chunks, setChunks] = useState<string[]>([]);
  const [citations, setCitations] = useState<SourceChunk[]>([]);
  const [agents, setAgents] = useState<string[]>([]);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [requiresReview, setRequiresReview] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [intent, setIntent] = useState<string | null>(null);

  const handleFrame = useCallback((frame: WsFrame) => {
    switch (frame.type) {
      case "intent_classified": setIntent(frame.intent); break;
      case "agent_start":
        setAgents((p) => p.includes(frame.agent) ? p : [...p, frame.agent]);
        break;
      case "chunk": setChunks((p) => [...p, frame.text]); break;
      case "citation": setCitations((p) => [...p, frame.chunk as unknown as SourceChunk]); break;
      case "complete":
        setConfidence(frame.confidence);
        setRequiresReview(frame.requires_review);
        break;
      case "error": setError(frame.message); break;
    }
  }, []);

  const { isConnected, isDone } = useAgentStream(sessionId, { onFrame: handleFrame });
  const fullText = chunks.join("");
  const filled = confidence == null ? 0 : confidence >= 0.9 ? 4 : confidence >= 0.7 ? 3 : confidence >= 0.5 ? 2 : 1;

  if (!sessionId) return null;

  return (
    <div className="space-y-4">
      {/* Status bar */}
      <div className="flex flex-wrap items-center gap-2">
        {!isDone && (
          <span className="flex items-center gap-1.5 text-xs text-slate-400">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-sky-500" />
            </span>
            {isConnected ? "Agent processing…" : "Connecting…"}
          </span>
        )}
        {intent && (
          <span className="bg-sky-500/10 text-sky-400 border border-sky-500/20 px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wider">
            {intent.replace(/_/g, " ")}
          </span>
        )}
        {agents.map((a) => (
          <span key={a} className="bg-[#1E3A5F]/60 text-slate-300 border border-slate-600/40 px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wider">
            {a.replace(/_/g, " ")}
          </span>
        ))}
        {confidence != null && (
          <div className="flex items-center gap-1">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className={`h-2.5 w-2.5 rounded-[1px] ${i <= filled ? "bg-sky-500" : "bg-slate-700"}`} />
            ))}
            <span className="ml-1 text-[10px] font-mono text-slate-500">{(confidence * 100).toFixed(0)}%</span>
          </div>
        )}
      </div>

      {requiresReview && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-amber-400 text-xs font-medium">
          ⚠ Pending attorney review — confidence below threshold. Check the{" "}
          <Link href="/review" className="underline">Review Queue</Link>.
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-red-400 text-xs">
          Error: {error}
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
          <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            Sources ({citations.length})
          </h3>
          {citations.map((chunk, i) => (
            <CitationCard key={chunk.id || i} chunk={chunk} rank={i} />
          ))}
        </div>
      )}
    </div>
  );
}
