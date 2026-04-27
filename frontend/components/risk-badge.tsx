"use client";

interface RiskBadgeProps {
  severity: "low" | "medium" | "high" | "critical";
  className?: string;
}

const severityConfig: Record<string, { label: string; className: string }> = {
  critical: {
    label: "Critical",
    className: "bg-red-100 text-red-800 border border-red-300",
  },
  high: {
    label: "High",
    className: "bg-orange-100 text-orange-800 border border-orange-300",
  },
  medium: {
    label: "Medium",
    className: "bg-yellow-100 text-yellow-800 border border-yellow-300",
  },
  low: {
    label: "Low",
    className: "bg-green-100 text-green-800 border border-green-300",
  },
};

export function RiskBadge({ severity, className = "" }: RiskBadgeProps) {
  const config = severityConfig[severity] || severityConfig.low;
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${config.className} ${className}`}
    >
      {config.label}
    </span>
  );
}
