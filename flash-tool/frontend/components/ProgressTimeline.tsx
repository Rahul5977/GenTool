"use client";

import { useRouter } from "next/navigation";

export type PhaseState = "done" | "active" | "idle";

export interface TimelinePhase {
  id: string;
  label: string;
  state: PhaseState;
  sublabel?: string;
}

interface Props {
  phases: TimelinePhase[];
  jobId: string;
  showReviewButton?: boolean;
  showDoneButton?: boolean;
  videoUrl?: string;
}

function PhaseIcon({ state }: { state: PhaseState }) {
  if (state === "done")
    return (
      <span className="w-8 h-8 rounded-full bg-green-500/20 border border-green-500/40 flex items-center justify-center text-green-400 text-sm font-bold">
        ✓
      </span>
    );
  if (state === "active")
    return (
      <span className="w-8 h-8 rounded-full bg-blue-500/20 border border-blue-400/40 flex items-center justify-center glow-pulse">
        <span className="w-3 h-3 rounded-full border-2 border-blue-400 border-t-transparent spin" />
      </span>
    );
  return (
    <span className="w-8 h-8 rounded-full border border-[#2a2a2a] flex items-center justify-center">
      <span className="w-2 h-2 rounded-full bg-[#3a3a3a]" />
    </span>
  );
}

export default function ProgressTimeline({ phases, jobId, showReviewButton, showDoneButton, videoUrl }: Props) {
  const router = useRouter();
  return (
    <div className="flex flex-col gap-0">
      {phases.map((phase, i) => (
        <div key={phase.id} className="flex gap-4">
          {/* Icon + connector */}
          <div className="flex flex-col items-center">
            <PhaseIcon state={phase.state} />
            {i < phases.length - 1 && (
              <div
                className={`w-px flex-1 mt-1 mb-1 min-h-[20px] transition-colors duration-700 ${
                  phase.state === "done" ? "bg-green-500/30" : "bg-[#2a2a2a]"
                }`}
              />
            )}
          </div>
          {/* Label */}
          <div className="pb-5 pt-1 flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <span
                className={`text-sm font-medium transition-colors duration-300 ${
                  phase.state === "done"
                    ? "text-green-400"
                    : phase.state === "active"
                    ? "text-white"
                    : "text-[#4b5563]"
                }`}
              >
                {phase.label}
              </span>
              {phase.sublabel && (
                <span className="text-xs text-[#6b7280] mono">{phase.sublabel}</span>
              )}
              {phase.id === "awaiting" && showReviewButton && (
                <button
                  onClick={() => router.push(`/jobs/${jobId}/review`)}
                  className="ml-auto px-3 py-1 rounded text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30 hover:bg-amber-500/30 transition-colors"
                >
                  Review Images →
                </button>
              )}
              {phase.id === "done" && showDoneButton && videoUrl && (
                <button
                  onClick={() => router.push(`/jobs/${jobId}/result`)}
                  className="ml-auto px-3 py-1 rounded text-xs font-semibold bg-green-500/20 text-green-300 border border-green-500/30 hover:bg-green-500/30 transition-colors"
                >
                  Watch Ad →
                </button>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
