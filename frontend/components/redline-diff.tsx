"use client";

import { diffWords } from "diff";

interface RedlineDiffProps {
  original: string;
  revised: string;
}

export function RedlineDiff({ original, revised }: RedlineDiffProps) {
  const parts = diffWords(original, revised);

  return (
    <div className="grid grid-cols-2 gap-4 text-sm font-mono">
      <div>
        <p className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">
          Original
        </p>
        <div className="border rounded p-3 bg-white leading-relaxed whitespace-pre-wrap">
          {parts.map((part, i) =>
            part.removed ? (
              <mark key={i} className="bg-red-100 text-red-700 line-through">
                {part.value}
              </mark>
            ) : !part.added ? (
              <span key={i}>{part.value}</span>
            ) : null
          )}
        </div>
      </div>
      <div>
        <p className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">
          Revised
        </p>
        <div className="border rounded p-3 bg-white leading-relaxed whitespace-pre-wrap">
          {parts.map((part, i) =>
            part.added ? (
              <mark key={i} className="bg-green-100 text-green-700 font-medium">
                {part.value}
              </mark>
            ) : !part.removed ? (
              <span key={i}>{part.value}</span>
            ) : null
          )}
        </div>
      </div>
    </div>
  );
}
