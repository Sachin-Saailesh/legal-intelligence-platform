"use client";

import { useEffect, useState } from "react";

// ── Types ────────────────────────────────────────────────────────────────────

export type PipelineStage =
  | "idle"
  | "classifying"
  | "routing"
  | "agents_running"
  | "synthesizing"
  | "guarding"
  | "complete"
  | "review";

export type AgentId =
  | "contract_analyst"
  | "case_researcher"
  | "compliance_monitor"
  | "legal_drafter"
  | "litigation_risk";

type AgentStatus = "idle" | "running" | "complete";

interface AgentInfo {
  id: AgentId;
  label: string;
  shortLabel: string;
  icon: string;
  color: string;
  activeColor: string;
  doneColor: string;
  borderColor: string;
  activeBorderColor: string;
  description: string;
}

// ── Agent definitions ────────────────────────────────────────────────────────

const AGENTS: AgentInfo[] = [
  {
    id: "contract_analyst",
    label: "Contract Analyst",
    shortLabel: "Contract",
    icon: "contract",
    color: "text-slate-400",
    activeColor: "text-sky-300",
    doneColor: "text-sky-400",
    borderColor: "border-slate-700/50",
    activeBorderColor: "border-sky-500/70",
    description: "Identifies clause risks, dependencies & missing protections",
  },
  {
    id: "case_researcher",
    label: "Case Researcher",
    shortLabel: "Research",
    icon: "search",
    color: "text-slate-400",
    activeColor: "text-violet-300",
    doneColor: "text-violet-400",
    borderColor: "border-slate-700/50",
    activeBorderColor: "border-violet-500/70",
    description: "Finds precedents, analogous cases & legal authority",
  },
  {
    id: "compliance_monitor",
    label: "Compliance Monitor",
    shortLabel: "Compliance",
    icon: "shield_check",
    color: "text-slate-400",
    activeColor: "text-emerald-300",
    doneColor: "text-emerald-400",
    borderColor: "border-slate-700/50",
    activeBorderColor: "border-emerald-500/70",
    description: "Checks Federal Register & SEC EDGAR for live regulatory changes",
  },
  {
    id: "legal_drafter",
    label: "Legal Drafter",
    shortLabel: "Drafting",
    icon: "edit_document",
    color: "text-slate-400",
    activeColor: "text-amber-300",
    doneColor: "text-amber-400",
    borderColor: "border-slate-700/50",
    activeBorderColor: "border-amber-500/70",
    description: "Generates and revises clause language with market-standard alternatives",
  },
  {
    id: "litigation_risk",
    label: "Litigation Risk",
    shortLabel: "Risk",
    icon: "warning",
    color: "text-slate-400",
    activeColor: "text-red-300",
    doneColor: "text-red-400",
    borderColor: "border-slate-700/50",
    activeBorderColor: "border-red-500/70",
    description: "Predicts win probability, settlement range & key risk factors",
  },
];

// ── Pulse dot ────────────────────────────────────────────────────────────────

function PulseDot({ color = "bg-sky-500" }: { color?: string }) {
  return (
    <span className="relative flex h-2 w-2">
      <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${color} opacity-75`} />
      <span className={`relative inline-flex rounded-full h-2 w-2 ${color}`} />
    </span>
  );
}

// ── Stage node ───────────────────────────────────────────────────────────────

function StageNode({
  label,
  icon,
  state,
  small = false,
}: {
  label: string;
  icon: string;
  state: "idle" | "active" | "done";
  small?: boolean;
}) {
  const base =
    "flex flex-col items-center justify-center gap-1 rounded-xl border transition-all duration-500 select-none";
  const size = small
    ? "w-24 h-16 text-[10px]"
    : "w-28 h-20 text-[10px]";

  const stateStyles = {
    idle: "bg-[#0d1f35] border-slate-700/50 text-slate-500",
    active:
      "bg-[#0d2744] border-sky-500/60 text-sky-300 shadow-[0_0_18px_-4px_rgba(56,189,248,0.35)]",
    done: "bg-[#0a2a1a] border-emerald-600/50 text-emerald-400",
  };

  return (
    <div className={`${base} ${size} ${stateStyles[state]}`}>
      <div className="flex items-center gap-1">
        <span className={`material-symbols-outlined ${small ? "text-base" : "text-xl"}`}>
          {state === "done" ? "check_circle" : icon}
        </span>
        {state === "active" && (
          <span className="material-symbols-outlined text-xs animate-spin">refresh</span>
        )}
      </div>
      <span className="font-bold tracking-wide uppercase text-center leading-tight px-1">
        {label}
      </span>
    </div>
  );
}

// ── Connector arrow ──────────────────────────────────────────────────────────

function Arrow({ active, vertical = false }: { active: boolean; vertical?: boolean }) {
  return vertical ? (
    <div className="flex flex-col items-center h-6 justify-center">
      <div
        className={`w-0.5 h-4 transition-colors duration-500 ${
          active ? "bg-sky-500/70" : "bg-slate-700/40"
        }`}
      />
      <span
        className={`material-symbols-outlined text-xs -mt-0.5 transition-colors duration-500 ${
          active ? "text-sky-500/70" : "text-slate-700/40"
        }`}
      >
        arrow_drop_down
      </span>
    </div>
  ) : (
    <div className="flex items-center w-8 justify-center">
      <div
        className={`h-0.5 w-5 transition-colors duration-500 ${
          active ? "bg-sky-500/70" : "bg-slate-700/40"
        }`}
      />
      <span
        className={`material-symbols-outlined text-xs -ml-0.5 transition-colors duration-500 ${
          active ? "text-sky-500/70" : "text-slate-700/40"
        }`}
      >
        arrow_right
      </span>
    </div>
  );
}

// ── Agent card ───────────────────────────────────────────────────────────────

function AgentCard({ info, status }: { info: AgentInfo; status: AgentStatus }) {
  const isActive = status === "running";
  const isDone = status === "complete";

  return (
    <div
      className={`relative rounded-xl border transition-all duration-500 px-3 py-2.5 flex flex-col gap-1 min-w-[130px] ${
        isActive
          ? `bg-[#0d1f35] ${info.activeBorderColor} shadow-lg`
          : isDone
          ? "bg-[#0a1c0a] border-emerald-800/40"
          : `bg-[#0d1f35]/50 ${info.borderColor}`
      }`}
    >
      <div className="flex items-center gap-1.5">
        <span
          className={`material-symbols-outlined text-base transition-colors duration-500 ${
            isActive ? info.activeColor : isDone ? "text-emerald-400" : info.color
          }`}
        >
          {isDone ? "check_circle" : info.icon}
        </span>
        <span
          className={`text-[10px] font-bold uppercase tracking-wide transition-colors duration-500 ${
            isActive ? info.activeColor : isDone ? "text-emerald-400" : info.color
          }`}
        >
          {info.shortLabel}
        </span>
        {isActive && (
          <span className="ml-auto">
            <span className={`material-symbols-outlined text-[14px] animate-spin ${info.activeColor}`}>refresh</span>
          </span>
        )}
        {isDone && (
          <span className="ml-auto text-[10px] font-mono text-emerald-500">✓</span>
        )}
      </div>
      <p className="text-[9px] text-slate-500 leading-tight">{info.description}</p>
    </div>
  );
}

// ── RAG pipeline badge ───────────────────────────────────────────────────────

function RagBadge({ active }: { active: boolean }) {
  const steps = ["Qdrant Dense", "BM25 Sparse", "RRF Merge", "FlashRank"];
  return (
    <div
      className={`rounded-xl border px-3 py-2 transition-all duration-500 ${
        active
          ? "bg-[#0d2744] border-sky-500/50 shadow-[0_0_14px_-4px_rgba(56,189,248,0.25)]"
          : "bg-[#0d1f35]/50 border-slate-700/40"
      }`}
    >
      <p
        className={`text-[9px] font-bold uppercase tracking-widest mb-1.5 ${
          active ? "text-sky-400" : "text-slate-600"
        }`}
      >
        Hybrid RAG Pipeline
      </p>
      <div className="flex items-center gap-1 flex-wrap">
        {steps.map((s, i) => (
          <span key={s} className="flex items-center gap-1">
            <span
              className={`text-[9px] font-mono px-1.5 py-0.5 rounded border transition-colors duration-500 ${
                active
                  ? "bg-sky-500/10 border-sky-600/30 text-sky-300"
                  : "bg-slate-800/50 border-slate-700/30 text-slate-600"
              }`}
            >
              {s}
            </span>
            {i < steps.length - 1 && (
              <span className={`text-[8px] ${active ? "text-sky-600" : "text-slate-700"}`}>→</span>
            )}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Guard badge ──────────────────────────────────────────────────────────────

function GuardBadge({
  state,
  confidence,
}: {
  state: "idle" | "active" | "passed" | "failed";
  confidence: number | null;
}) {
  const stateMap = {
    idle: "bg-[#0d1f35]/50 border-slate-700/40 text-slate-600",
    active:
      "bg-[#1a1000] border-amber-500/60 text-amber-300 shadow-[0_0_14px_-4px_rgba(245,158,11,0.3)]",
    passed: "bg-[#0a1c0a] border-emerald-600/50 text-emerald-400",
    failed: "bg-[#1c0808] border-red-600/50 text-red-400",
  };

  return (
    <div
      className={`rounded-xl border px-4 py-2.5 flex flex-col items-center gap-1 transition-all duration-500 min-w-[130px] ${stateMap[state]}`}
    >
      <div className="flex items-center gap-1.5">
        <span className="material-symbols-outlined text-lg">
          {state === "passed" ? "verified" : state === "failed" ? "gpp_bad" : "security"}
        </span>
        {state === "active" && <span className="material-symbols-outlined text-[14px] animate-spin text-amber-500">refresh</span>}
      </div>
      <span className="text-[10px] font-bold uppercase tracking-wide">Hallucination Guard</span>
      {confidence != null && (
        <span className="text-[10px] font-mono">
          {(confidence * 100).toFixed(0)}% confidence
        </span>
      )}
      {state === "idle" && (
        <span className="text-[9px] font-mono opacity-60">threshold: 70%</span>
      )}
    </div>
  );
}

// ── Main pipeline visualization ───────────────────────────────────────────────

interface AgentPipelineVizProps {
  stage: PipelineStage;
  intent: string | null;
  activeAgents: AgentId[];
  doneAgents: AgentId[];
  confidence: number | null;
  compact?: boolean;
}

export function AgentPipelineViz({
  stage,
  intent,
  activeAgents,
  doneAgents,
  confidence,
  compact = false,
}: AgentPipelineVizProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Fade in after mount
    const t = setTimeout(() => setVisible(true), 50);
    return () => clearTimeout(t);
  }, []);

  const intentToRoute: Record<string, AgentId[]> = {
    contract_review: ["contract_analyst"],
    case_research: ["case_researcher"],
    compliance_check: ["compliance_monitor"],
    drafting: ["legal_drafter", "contract_analyst"],
    litigation_risk: ["litigation_risk", "case_researcher"],
  };

  // Compact summary bar shown once synthesis starts (output is already streaming)
  if (compact) {
    const stageLabel =
      stage === "synthesizing" ? "Synthesizing…" :
      stage === "guarding" ? "Verifying…" :
      stage === "complete" ? "Complete" :
      stage === "review" ? "Pending Review" : stage.replace(/_/g, " ");
    const isDoneStage = stage === "complete" || stage === "review";
    return (
      <div className={`transition-all duration-700 ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"}`}>
        <div className="flex items-center gap-3 bg-[#080f1c] border border-slate-700/40 rounded-xl px-4 py-2.5 flex-wrap">
          {isDoneStage ? (
            <span className={`material-symbols-outlined text-sm ${stage === "complete" ? "text-emerald-400" : "text-amber-400"}`}>
              {stage === "complete" ? "check_circle" : "pending_actions"}
            </span>
          ) : (
            <PulseDot />
          )}
          <span className={`text-xs font-mono ${isDoneStage ? (stage === "complete" ? "text-emerald-400" : "text-amber-400") : "text-slate-400"}`}>
            {stageLabel}
          </span>
          {intent && (
            <span className="bg-sky-500/10 border border-sky-500/20 text-sky-400 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide">
              {intent.replace(/_/g, " ")}
            </span>
          )}
          {doneAgents.map((a) => {
            const info = AGENTS.find((ag) => ag.id === a);
            return info ? (
              <span key={a} className="text-[10px] text-slate-500 font-mono border border-slate-700/40 px-1.5 py-0.5 rounded">
                {info.shortLabel}
              </span>
            ) : null;
          })}
          {confidence != null && (
            <span className="ml-auto text-[10px] font-mono text-slate-500">
              {(confidence * 100).toFixed(0)}% confidence
            </span>
          )}
        </div>
      </div>
    );
  }

  const routedAgents = intent ? (intentToRoute[intent] ?? AGENTS.map((a) => a.id)) : [];

  const guardState =
    stage === "guarding"
      ? "active"
      : stage === "complete"
      ? "passed"
      : stage === "review"
      ? "failed"
      : "idle";

  const isPostClassify = stage !== "idle" && stage !== "classifying";
  const isPostRoute = ["agents_running", "synthesizing", "guarding", "complete", "review"].includes(stage);
  const isSynthesizing = ["synthesizing", "guarding", "complete", "review"].includes(stage);

  return (
    <div
      className={`transition-all duration-700 ${
        visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"
      }`}
    >
      <div className="bg-[#080f1c] border border-slate-700/40 rounded-2xl p-5 space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-sky-400 text-base">account_tree</span>
            <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">
              Agent Pipeline
            </span>
            {intent && (
              <span className="bg-sky-500/10 border border-sky-500/20 text-sky-400 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide">
                {intent.replace(/_/g, " ")}
              </span>
            )}
          </div>
          <span
            className={`text-[10px] font-mono uppercase tracking-widest ${
              stage === "complete"
                ? "text-emerald-400"
                : stage === "review"
                ? "text-amber-400"
                : "text-slate-500"
            }`}
          >
            {stage.replace(/_/g, " ")}
          </span>
        </div>

        {/* Pipeline flow */}
        <div className="flex flex-col gap-1">
          {/* Row 1: Classify → Route → [Agents] */}
          <div className="flex items-center gap-1 flex-wrap">
            {/* Classify */}
            <StageNode
              label="Classify Intent"
              icon="psychology"
              state={
                stage === "classifying"
                  ? "active"
                  : isPostClassify
                  ? "done"
                  : "idle"
              }
              small
            />

            <Arrow active={isPostClassify} />

            {/* Router */}
            <StageNode
              label="Router"
              icon="call_split"
              state={
                stage === "routing"
                  ? "active"
                  : isPostRoute
                  ? "done"
                  : "idle"
              }
              small
            />

            <Arrow active={isPostRoute} />

            {/* Agents grid */}
            <div className="flex flex-wrap gap-2 flex-1 min-w-0">
              {AGENTS.filter((a) =>
                routedAgents.length > 0 ? routedAgents.includes(a.id) : true
              ).map((agent) => {
                const isActive = activeAgents.includes(agent.id);
                const isDone = doneAgents.includes(agent.id);
                const status: AgentStatus = isActive ? "running" : isDone ? "complete" : "idle";
                return <AgentCard key={agent.id} info={agent} status={status} />;
              })}
              {/* Show inactive agents dimmed */}
              {AGENTS.filter(
                (a) =>
                  routedAgents.length > 0 && !routedAgents.includes(a.id)
              ).map((agent) => (
                <AgentCard key={agent.id} info={agent} status="idle" />
              ))}
            </div>
          </div>

          {/* RAG Pipeline row */}
          <div className="pl-[calc(56px+2rem+56px+2rem)] flex items-center gap-1">
            <div className="flex flex-col items-center mr-1">
              <Arrow active={isPostRoute} vertical />
            </div>
            <RagBadge active={isPostRoute && !isSynthesizing} />
          </div>

          {/* Row 2: Synthesize → Guard → Output */}
          <div className="flex items-center gap-1">
            <div className="w-[112px] flex justify-center">
              {/* spacer to align under Classify */}
            </div>
            <div className="flex items-center gap-1 ml-auto">
              <Arrow active={isSynthesizing} />
              <StageNode
                label="Synthesize"
                icon="auto_awesome"
                state={
                  stage === "synthesizing"
                    ? "active"
                    : ["guarding", "complete", "review"].includes(stage)
                    ? "done"
                    : "idle"
                }
                small
              />
              <Arrow active={["guarding", "complete", "review"].includes(stage)} />
              <GuardBadge state={guardState} confidence={confidence} />
              <Arrow active={stage === "complete" || stage === "review"} />
              <StageNode
                label={stage === "review" ? "Review Queue" : "Output"}
                icon={stage === "review" ? "pending_actions" : "task_alt"}
                state={
                  stage === "complete"
                    ? "done"
                    : stage === "review"
                    ? "active"
                    : "idle"
                }
                small
              />
            </div>
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 border-t border-slate-800/60 pt-3">
          <span className="text-[9px] text-slate-600 uppercase tracking-widest font-bold">Legend</span>
          {[
            { color: "border-slate-700/50 bg-slate-800/20 text-slate-500", label: "Idle" },
            { color: "border-sky-500/60 bg-sky-900/20 text-sky-300", label: "Active" },
            { color: "border-emerald-600/50 bg-emerald-900/20 text-emerald-400", label: "Complete" },
          ].map(({ color, label }) => (
            <div key={label} className="flex items-center gap-1.5">
              <div
                className={`w-4 h-4 rounded border text-[8px] flex items-center justify-center ${color}`}
              />
              <span className="text-[9px] text-slate-500">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
