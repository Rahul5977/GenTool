"use client";

const STATUS_CONFIG: Record<string, { label: string; dot: string; text: string; bg: string }> = {
  pending:            { label: "Pending",          dot: "bg-gray-500",        text: "text-gray-300",  bg: "bg-gray-500/10" },
  analysing:          { label: "Analysing",         dot: "bg-blue-400 spin",   text: "text-blue-300",  bg: "bg-blue-500/10" },
  prompting:          { label: "Prompting",         dot: "bg-blue-400 spin",   text: "text-blue-300",  bg: "bg-blue-500/10" },
  imaging:            { label: "Imaging",           dot: "bg-purple-400 spin", text: "text-purple-300",bg: "bg-purple-500/10" },
  awaiting_approval:  { label: "Awaiting Review",   dot: "bg-amber-400",       text: "text-amber-300", bg: "bg-amber-500/10" },
  generating:         { label: "Generating",        dot: "bg-green-400 spin",  text: "text-green-300", bg: "bg-green-500/10" },
  stitching:          { label: "Stitching",         dot: "bg-green-400 spin",  text: "text-green-300", bg: "bg-green-500/10" },
  done:               { label: "Done",              dot: "bg-green-400",       text: "text-green-300", bg: "bg-green-500/10" },
  failed:             { label: "Failed",            dot: "bg-red-400",         text: "text-red-300",   bg: "bg-red-500/10" },
};

export default function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG["pending"];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${cfg.text} ${cfg.bg}`}>
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}
