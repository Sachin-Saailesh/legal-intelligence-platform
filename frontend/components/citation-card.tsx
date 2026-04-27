"use client";

import { useState } from "react";
import { SourceChunk } from "@/lib/api";

interface CitationCardProps {
  chunk: SourceChunk;
  rank?: number;
}

export function CitationCard({ chunk, rank }: CitationCardProps) {
  const [expanded, setExpanded] = useState(false);
  const conf = chunk.confidence_score ?? 0;
  const filled = conf >= 0.9 ? 4 : conf >= 0.7 ? 3 : conf >= 0.5 ? 2 : 1;

  return (
    <div className="bg-[#0A192F] border border-slate-700/50 rounded-lg p-3 text-xs space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-slate-500 font-mono">
          {rank !== undefined && <span>#{rank + 1}</span>}
          {chunk.source_doc_id && (
            <span className="text-slate-600">doc:{chunk.source_doc_id.slice(0, 8)}</span>
          )}
          {chunk.page_number && <span>p.{chunk.page_number}</span>}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex gap-0.5">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className={`h-2.5 w-2.5 rounded-[1px] ${i <= filled ? "bg-sky-500" : "bg-slate-700"}`} />
            ))}
          </div>
          <span className="text-[10px] font-mono text-slate-500">{(conf * 100).toFixed(0)}%</span>
          <button onClick={() => setExpanded(!expanded)} className="text-sky-500 hover:underline text-[10px]">
            {expanded ? "Collapse" : "Expand"}
          </button>
        </div>
      </div>
      <p className={`text-slate-300 font-serif leading-relaxed text-xs ${expanded ? "whitespace-pre-wrap" : "line-clamp-2"}`}>
        {chunk.text}
      </p>
    </div>
  );
}
