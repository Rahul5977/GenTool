"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api, type JobStatus } from "@/lib/api";
import ProgressTimeline, { type TimelinePhase } from "@/components/ProgressTimeline";
import StatusBadge from "@/components/StatusBadge";

interface SseEvent {
  type: string;
  data: Record<string, unknown>;
  ts: string;
}

function statusToPhaseIndex(status: string): number {
  const map: Record<string, number> = {
    pending: -1,
    analysing: 0,
    prompting: 1,
    awaiting_prompt_review: 2,
    imaging: 3,
    awaiting_approval: 4,
    generating: 5,
    stitching: 6,
    done: 7,
    failed: 7,
  };
  return map[status] ?? -1;
}

function buildPhases(status: string, clipInfo: { total: number; done: string[] }): TimelinePhase[] {
  const idx = statusToPhaseIndex(status);
  const phaseOf = (i: number): "done" | "active" | "idle" =>
    i < idx ? "done" : i === idx ? "active" : "idle";

  const clipSublabel =
    clipInfo.total > 0 ? `${clipInfo.done.length}/${clipInfo.total}` : undefined;

  return [
    { id: "analysis",       label: "Analysis",       state: phaseOf(0) },
    { id: "prompting",      label: "Prompts",        state: phaseOf(1) },
    { id: "prompt-review",  label: "Edit Prompts",   state: phaseOf(2) },
    { id: "imaging",        label: "Images",         state: phaseOf(3) },
    { id: "awaiting",       label: "Review Images",  state: phaseOf(4) },
    { id: "generating",     label: "Video Gen",      state: phaseOf(5), sublabel: clipSublabel },
    { id: "stitching",      label: "Stitch",         state: phaseOf(6) },
    { id: "done",           label: "Done",           state: status === "done" ? "done" : phaseOf(7) },
  ];
}

interface CharacterData {
  age: number;
  gender: string;
  skin_tone: string;
  skin_hex: string;
  face_shape: string;
  hair: string;
  outfit: string;
  accessories: string[];
  distinguishing_marks: string[];
}

interface ClipData {
  clip_number: number;
  duration_seconds: number;
  scene_summary: string;
  dialogue: string;
  word_count: number;
  end_emotion: string;
  verified: boolean;
  verification_issues: string[];
  prompt_preview: string;
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <>
      <span className="text-[#4b5563]">{label}</span>
      <span className="text-[#e5e7eb] wrap-break-word">{value}</span>
    </>
  );
}

export default function ProgressPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [events, setEvents] = useState<SseEvent[]>([]);
  const [clipsDone, setClipsDone] = useState<string[]>([]);
  const [totalClips, setTotalClips] = useState(0);
  const [error, setError] = useState("");
  const [character, setCharacter] = useState<CharacterData | null>(null);
  const [setting, setSetting] = useState("");
  const [background, setBackground] = useState("");
  const [coach, setCoach] = useState("");
  const [clipPrompts, setClipPrompts] = useState<ClipData[]>([]);
  const [expandedClip, setExpandedClip] = useState<number | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const esRef = useRef<EventSource | null>(null);
  const statusRef = useRef<string>("pending");

  // Initial status fetch
  useEffect(() => {
    api.getJobStatus(id)
      .then(setJobStatus)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load job"));
  }, [id]);

  // SSE connection
  useEffect(() => {
    const es = api.streamJobEvents(id);
    esRef.current = es;

    const push = (type: string, data: Record<string, unknown>) => {
      setEvents((prev) => [...prev, { type, data, ts: new Date().toLocaleTimeString() }]);
    };

    const handleAny = (type: string) => (ev: MessageEvent) => {
      let data: Record<string, unknown> = {};
      try { data = JSON.parse(ev.data); } catch { /* noop */ }
      push(type, data);

      if (type === "phase_done") {
        if (data.phase === 1 && data.character) {
          setCharacter(data.character as CharacterData);
          setSetting(String(data.setting ?? ""));
          setBackground(String(data.background ?? ""));
          setCoach(String(data.coach ?? ""));
        }
        if (data.phase === 2 && Array.isArray(data.clips)) {
          setClipPrompts(data.clips as ClipData[]);
        }
      }
      if (type === "clip_done") {
        setClipsDone((prev) => [...prev, String(data.clip ?? "")]);
        setTotalClips(Number(data.total ?? 0));
      }
      if (type === "done") {
        statusRef.current = "done";
        api.getJobStatus(id).then(setJobStatus).catch(() => {});
        es.close();
        setTimeout(() => router.push(`/jobs/${id}/result`), 1200);
      }
      if (type === "awaiting_approval" || type === "awaiting_prompt_review") {
        api.getJobStatus(id).then(setJobStatus).catch(() => {});
      }
      if (type === "phase_start" || type === "phase_done" || type === "keyframe_ready") {
        api.getJobStatus(id).then(setJobStatus).catch(() => {});
      }
      if (type === "error") {
        statusRef.current = "failed";
        setError(String(data.message ?? "Pipeline error"));
        api.getJobStatus(id).then(setJobStatus).catch(() => {});
        es.close();
      }
    };

    const eventTypes = [
      "phase_start", "phase_done", "keyframe_ready",
      "awaiting_approval", "awaiting_prompt_review", "clip_done",
      "done", "error", "heartbeat", "clip_prompt_updated",
    ];
    eventTypes.forEach((t) => es.addEventListener(t, handleAny(t) as EventListener));

    es.onerror = () => {
      const s = statusRef.current;
      if (s === "done" || s === "failed") {
        es.close();
      } else {
        push("connection", { message: "SSE reconnecting…" });
      }
    };

    return () => { es.close(); };
  }, [id, router]);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  if (!jobStatus && !error) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-green-500 border-t-transparent animate-spin" />
      </main>
    );
  }

  const status = jobStatus?.status ?? "pending";
  const progress = jobStatus?.progress ?? 0;
  const phases = buildPhases(status, { total: totalClips, done: clipsDone });
  const isAwaitingPromptReview = status === "awaiting_prompt_review";
  const isAwaiting = status === "awaiting_approval";
  const isDone = status === "done";
  const isFailed = status === "failed";

  return (
    <main className="min-h-screen px-6 py-10 max-w-4xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-[#4b5563] mb-8">
        <Link href="/" className="hover:text-white transition-colors">Flash Tool</Link>
        <span>/</span>
        <span className="text-[#6b7280] mono text-xs">{id.slice(0, 8)}…</span>
        <span>/</span>
        <span className="text-white">Progress</span>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
        <div>
          <h2 className="text-xl font-bold text-white mb-1">Pipeline Progress</h2>
          <p className="text-xs mono text-[#4b5563]">{id}</p>
        </div>
        <StatusBadge status={status} />
      </div>

      {/* Progress bar */}
      <div className="mb-6">
        <div className="flex justify-between text-xs mb-1.5">
          <span className="text-[#6b7280]">Overall</span>
          <span className="mono text-green-400">{progress}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-[#1a1a1a] overflow-hidden">
          <div
            className="h-full rounded-full bg-linear-to-r from-[#1a5c3a] to-green-400 transition-all duration-700"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Timeline — horizontal */}
      <div className="mb-6 p-4 rounded-xl bg-[#161616] border border-[#2a2a2a]">
        <ProgressTimeline
          phases={phases}
          jobId={id}
          showReviewPromptsButton={isAwaitingPromptReview}
          showReviewButton={isAwaiting}
          showDoneButton={isDone}
          videoUrl={isDone ? "result" : undefined}
        />
      </div>

      {/* Error banner */}
      {(error || isFailed) && (
        <div className="mb-6 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm whitespace-pre-wrap">
          <span className="font-semibold">Pipeline failed: </span>
          {error || jobStatus?.error}
        </div>
      )}

      {/* Prompt review banner */}
      {isAwaitingPromptReview && (
        <div className="mb-6 p-4 rounded-xl bg-violet-500/10 border border-violet-500/30 flex items-center justify-between gap-4">
          <div>
            <p className="text-violet-300 font-semibold text-sm">Clip prompts ready for review</p>
            <p className="text-[#9ca3af] text-xs mt-0.5">
              {clipPrompts.length} prompts generated. Review and edit before image generation starts.
            </p>
          </div>
          <Link
            href={`/jobs/${id}/review-prompts`}
            className="shrink-0 px-4 py-2 rounded-xl text-sm font-semibold bg-violet-500/20 text-violet-300 border border-violet-500/40 hover:bg-violet-500/30 transition-colors"
          >
            Edit Prompts →
          </Link>
        </div>
      )}

      {/* Image review banner */}
      {isAwaiting && (
        <div className="mb-6 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-between gap-4">
          <div>
            <p className="text-amber-300 font-semibold text-sm">Images ready for review</p>
            <p className="text-[#9ca3af] text-xs mt-0.5">
              {jobStatus?.num_keyframes} keyframe{jobStatus?.num_keyframes !== 1 ? "s" : ""} generated.
              Approve to start video generation.
            </p>
          </div>
          <Link
            href={`/jobs/${id}/review`}
            className="shrink-0 px-4 py-2 rounded-xl text-sm font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30 transition-colors"
          >
            Review Images →
          </Link>
        </div>
      )}

      {/* Two-column layout: character card + clip prompts side by side */}
      {(character || clipPrompts.length > 0) && (
        <div className="mb-6 grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Phase 1 result — character card */}
          {character && (
            <div className="p-4 rounded-xl bg-[#161616] border border-[#2a2a2a] self-start">
              <p className="text-xs font-semibold text-[#9ca3af] uppercase tracking-widest mb-3">
                Character
              </p>
              <div className="grid grid-cols-[120px_1fr] gap-x-3 gap-y-1.5 text-xs mono">
                <Row label="Coach" value={coach} />
                <Row label="Age / Gender" value={`${character.age}y ${character.gender}`} />
                <Row label="Face shape" value={character.face_shape} />
                <Row label="Skin" value={`${character.skin_tone} (${character.skin_hex})`} />
                <Row label="Hair" value={character.hair} />
                <Row label="Outfit" value={character.outfit} />
                {character.accessories.length > 0 && (
                  <Row label="Accessories" value={character.accessories.join(", ")} />
                )}
                {character.distinguishing_marks.length > 0 && (
                  <Row label="Marks" value={character.distinguishing_marks.join(", ")} />
                )}
                {setting && <Row label="Setting" value={setting} />}
              </div>
              {background && (
                <div className="mt-3 pt-3 border-t border-[#2a2a2a]">
                  <p className="text-xs text-[#4b5563] mono mb-1">Background</p>
                  <p className="text-xs text-[#9ca3af] leading-relaxed">{background}</p>
                </div>
              )}
            </div>
          )}

          {/* Phase 2 result — clip prompts */}
          {clipPrompts.length > 0 && (
            <div className="self-start">
              <p className="text-xs font-semibold text-[#9ca3af] uppercase tracking-widest mb-3">
                Clip Prompts ({clipPrompts.length})
              </p>
              <div className="flex flex-col gap-2">
                {clipPrompts.map((c) => {
                  const isExpanded = expandedClip === c.clip_number;
                  return (
                    <div key={c.clip_number} className="rounded-xl bg-[#161616] border border-[#2a2a2a] overflow-hidden">
                      {/* Header row */}
                      <div className="flex items-center justify-between px-3 py-2">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-semibold text-green-400 mono">
                            Clip {c.clip_number}
                          </span>
                          <span className="text-xs text-[#4b5563] mono">{c.duration_seconds}s</span>
                          {c.verified ? (
                            <span className="text-xs text-green-500 mono">✓</span>
                          ) : (
                            <span className="text-xs text-amber-500 mono">⚠</span>
                          )}
                        </div>
                        <button
                          onClick={() => setExpandedClip(isExpanded ? null : c.clip_number)}
                          className="text-xs text-[#4b5563] hover:text-white transition-colors mono"
                        >
                          {isExpanded ? "▲" : "▼"}
                        </button>
                      </div>

                      {/* Dialogue */}
                      <div className="px-3 pb-2">
                        <p className="text-xs text-[#e5e7eb] italic leading-relaxed">
                          &ldquo;{c.dialogue}&rdquo;
                        </p>
                      </div>

                      {/* Expanded */}
                      {isExpanded && (
                        <div className="px-3 pb-3 border-t border-[#2a2a2a] pt-2 flex flex-col gap-2">
                          <p className="text-xs text-[#6b7280]">{c.scene_summary}</p>
                          {c.end_emotion && (
                            <p className="text-xs text-[#4b5563] mono">
                              End emotion: <span className="text-[#9ca3af]">{c.end_emotion}</span>
                            </p>
                          )}
                          {c.verification_issues.length > 0 && (
                            <div>
                              {c.verification_issues.map((issue, i) => (
                                <p key={i} className="text-xs text-amber-400">• {issue}</p>
                              ))}
                            </div>
                          )}
                          {c.prompt_preview && (
                            <pre className="text-xs text-[#6b7280] whitespace-pre-wrap leading-relaxed font-mono border-t border-[#1e1e1e] pt-2 mt-1">
                              {c.prompt_preview}…
                            </pre>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Clip tiles (visible during video generation) */}
      {totalClips > 0 && (
        <div className="mb-6">
          <p className="text-xs font-semibold text-[#9ca3af] uppercase tracking-widest mb-3">
            Clips ({clipsDone.length}/{totalClips})
          </p>
          <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">
            {[...Array(totalClips)].map((_, i) => {
              const label = `clip_${String(i + 1).padStart(2, "0")}`;
              const done = clipsDone.includes(label);
              return (
                <div
                  key={i}
                  className={`h-12 rounded-lg border flex items-center justify-center text-xs mono transition-all ${
                    done
                      ? "border-green-500/40 bg-green-500/10 text-green-400"
                      : "border-[#2a2a2a] bg-[#1a1a1a] text-[#4b5563]"
                  }`}
                >
                  {done ? (
                    <span>✓ {i + 1}</span>
                  ) : (
                    <span className="w-3.5 h-3.5 rounded-full border border-current border-t-transparent animate-spin" />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Live event log */}
      <div>
        <p className="text-xs font-semibold text-[#9ca3af] uppercase tracking-widest mb-2">
          Live Log
        </p>
        <div
          ref={logRef}
          className="h-40 overflow-y-auto rounded-xl bg-[#0a0a0a] border border-[#1e1e1e] p-3 flex flex-col gap-1"
        >
          {events.length === 0 ? (
            <p className="text-xs text-[#4b5563] mono">Connecting…</p>
          ) : (
            events.filter((e) => e.type !== "heartbeat").map((ev, i) => (
              <div key={i} className="flex items-start gap-2 text-xs mono">
                <span className="text-[#4b5563] shrink-0">{ev.ts}</span>
                <span
                  className={
                    ev.type === "error" ? "text-red-400"
                    : ev.type === "done" ? "text-green-400"
                    : ev.type === "awaiting_approval" ? "text-amber-400"
                    : ev.type === "awaiting_prompt_review" ? "text-violet-400"
                    : "text-[#9ca3af]"
                  }
                >
                  [{ev.type}]
                </span>
                <span className="text-[#6b7280] break-all">
                  {Object.entries(ev.data)
                    .filter(([k]) => !["clips", "character"].includes(k))
                    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
                    .join("  ")}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </main>
  );
}
