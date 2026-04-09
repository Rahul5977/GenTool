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
  showReviewPromptsButton?: boolean;
  showReviewButton?: boolean;
  showDoneButton?: boolean;
  videoUrl?: string;
}

function PhaseNode({ state, index }: { state: PhaseState; index: number }) {
  if (state === "done")
    return (
      <span className="w-7 h-7 rounded-full bg-green-500/20 border border-green-500/50 flex items-center justify-center text-green-400 text-xs font-bold shrink-0">
        ✓
      </span>
    );
  if (state === "active")
    return (
      <span className="w-7 h-7 rounded-full bg-blue-500/20 border border-blue-400/50 flex items-center justify-center shrink-0">
        <span className="w-2.5 h-2.5 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />
      </span>
    );
  return (
    <span className="w-7 h-7 rounded-full border border-[#2a2a2a] flex items-center justify-center text-[#3a3a3a] text-xs shrink-0">
      {index + 1}
    </span>
  );
}

export default function ProgressTimeline({
  phases,
  jobId,
  showReviewPromptsButton,
  showReviewButton,
  showDoneButton,
  videoUrl,
}: Props) {
  const router = useRouter();

  return (
    <div className="w-full">
      {/* Horizontal phase track */}
      <div className="flex items-start gap-0 overflow-x-auto pb-1">
        {phases.map((phase, i) => (
          <div key={phase.id} className="flex items-start flex-1 min-w-0">
            {/* Phase cell */}
            <div className="flex flex-col items-center gap-1.5 flex-1 min-w-0">
              <PhaseNode state={phase.state} index={i} />
              <div className="text-center px-1">
                <p
                  className={`text-[10px] font-medium leading-tight transition-colors duration-300 ${
                    phase.state === "done"
                      ? "text-green-400"
                      : phase.state === "active"
                      ? "text-white"
                      : "text-[#4b5563]"
                  }`}
                >
                  {phase.label}
                </p>
                {phase.sublabel && (
                  <p className="text-[9px] text-[#6b7280] mono mt-0.5">{phase.sublabel}</p>
                )}
              </div>
            </div>

            {/* Connector line (except after last) */}
            {i < phases.length - 1 && (
              <div className="flex items-center self-start mt-3.5 shrink-0">
                <div
                  className={`h-px w-6 transition-colors duration-700 ${
                    phase.state === "done" ? "bg-green-500/40" : "bg-[#2a2a2a]"
                  }`}
                />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Action buttons row */}
      {(showReviewPromptsButton || showReviewButton || showDoneButton) && (
        <div className="flex justify-end mt-3 pt-3 border-t border-[#1e1e1e] gap-2">
          {showReviewPromptsButton && (
            <button
              onClick={() => router.push(`/jobs/${jobId}/review-prompts`)}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-violet-500/20 text-violet-300 border border-violet-500/30 hover:bg-violet-500/30 transition-colors"
            >
              Edit Prompts →
            </button>
          )}
          {showReviewButton && (
            <button
              onClick={() => router.push(`/jobs/${jobId}/review`)}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30 hover:bg-amber-500/30 transition-colors"
            >
              Review Images →
            </button>
          )}
          {showDoneButton && videoUrl && (
            <button
              onClick={() => router.push(`/jobs/${jobId}/result`)}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-green-500/20 text-green-300 border border-green-500/30 hover:bg-green-500/30 transition-colors"
            >
              Watch Ad →
            </button>
          )}
        </div>
      )}
    </div>
  );
}
