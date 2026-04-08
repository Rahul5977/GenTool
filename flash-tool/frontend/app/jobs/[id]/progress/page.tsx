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

const PHASE_ORDER = [
  "script_analysis",
  "prompt_generation",
  "image_generation",
  "awaiting",
  "video_generation",
  "stitch",
  "done",
];

function statusToPhaseIndex(status: string): number {
  const map: Record<string, number> = {
    pending: -1,
    analysing: 0,
    prompting: 1,
    imaging: 2,
    awaiting_approval: 3,
    generating: 4,
    stitching: 5,
    done: 6,
    failed: 6,
  };
  return map[status] ?? -1;
}

function buildPhases(status: string, clipInfo: { total: number; done: string[] }): TimelinePhase[] {
  const idx = statusToPhaseIndex(status);
  const phaseOf = (i: number): "done" | "active" | "idle" =>
    i < idx ? "done" : i === idx ? "active" : "idle";

  const clipSublabel =
    clipInfo.total > 0
      ? `${clipInfo.done.length}/${clipInfo.total} clips`
      : undefined;

  return [
    { id: "analysis",   label: "Script Analysis",     state: phaseOf(0) },
    { id: "prompting",  label: "Prompt Generation",   state: phaseOf(1) },
    { id: "imaging",    label: "Image Generation",    state: phaseOf(2) },
    { id: "awaiting",   label: "Awaiting Review",     state: phaseOf(3) },
    { id: "generating", label: "Video Generation",    state: phaseOf(4), sublabel: clipSublabel },
    { id: "stitching",  label: "Stitching",           state: phaseOf(5) },
    { id: "done",       label: "Done",                state: status === "done" ? "done" : phaseOf(6) },
  ];
}

export default function ProgressPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [events, setEvents] = useState<SseEvent[]>([]);
  const [clipsDone, setClipsDone] = useState<string[]>([]);
  const [totalClips, setTotalClips] = useState(0);
  const [error, setError] = useState("");
  const logRef = useRef<HTMLDivElement>(null);
  const esRef = useRef<EventSource | null>(null);

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
      setEvents((prev) => [
        ...prev,
        { type, data, ts: new Date().toLocaleTimeString() },
      ]);
    };

    const handleAny = (type: string) => (ev: MessageEvent) => {
      let data: Record<string, unknown> = {};
      try { data = JSON.parse(ev.data); } catch { /* noop */ }
      push(type, data);

      // Side-effects per event type
      if (type === "clip_done") {
        setClipsDone((prev) => [...prev, String(data.clip ?? "")]);
        setTotalClips(Number(data.total ?? 0));
      }
      if (type === "done") {
        api.getJobStatus(id).then(setJobStatus).catch(() => {});
        setTimeout(() => router.push(`/jobs/${id}/result`), 1200);
      }
      if (type === "awaiting_approval") {
        api.getJobStatus(id).then(setJobStatus).catch(() => {});
      }
      if (type === "phase_start" || type === "phase_done" || type === "keyframe_ready") {
        api.getJobStatus(id).then(setJobStatus).catch(() => {});
      }
      if (type === "error") {
        setError(String(data.message ?? "Pipeline error"));
        api.getJobStatus(id).then(setJobStatus).catch(() => {});
      }
    };

    const eventTypes = [
      "phase_start", "phase_done", "keyframe_ready",
      "awaiting_approval", "clip_done", "done", "error", "heartbeat",
    ];
    eventTypes.forEach((t) => es.addEventListener(t, handleAny(t) as EventListener));

    es.onerror = () => {
      push("connection", { message: "SSE connection dropped — will retry" });
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
        <div className="w-8 h-8 rounded-full border-2 border-green-500 border-t-transparent spin" />
      </main>
    );
  }

  const status = jobStatus?.status ?? "pending";
  const progress = jobStatus?.progress ?? 0;
  const phases = buildPhases(status, { total: totalClips, done: clipsDone });
  const isAwaiting = status === "awaiting_approval";
  const isDone = status === "done";
  const isFailed = status === "failed";

  return (
    <main className="min-h-screen px-6 py-10 max-w-3xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-[#4b5563] mb-8">
        <Link href="/" className="hover:text-white transition-colors">Flash Tool</Link>
        <span>/</span>
        <span className="text-[#6b7280] mono text-xs">{id.slice(0, 8)}…</span>
        <span>/</span>
        <span className="text-white">Progress</span>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between mb-8 flex-wrap gap-4">
        <div>
          <h2 className="text-xl font-bold text-white mb-1">Pipeline Progress</h2>
          <p className="text-xs mono text-[#4b5563]">{id}</p>
        </div>
        <StatusBadge status={status} />
      </div>

      {/* Progress bar */}
      <div className="mb-8">
        <div className="flex justify-between text-xs mb-2">
          <span className="text-[#6b7280]">Overall</span>
          <span className="mono text-green-400">{progress}%</span>
        </div>
        <div className="h-2 rounded-full bg-[#1a1a1a] overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-[#1a5c3a] to-green-400 transition-all duration-700"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Error banner */}
      {(error || isFailed) && (
        <div className="mb-6 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          <span className="font-semibold">Pipeline failed: </span>
          {error || jobStatus?.error}
        </div>
      )}

      {/* Review button (awaiting approval) */}
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

      {/* Timeline */}
      <div className="mb-8 p-5 rounded-xl bg-[#161616] border border-[#2a2a2a]">
        <ProgressTimeline
          phases={phases}
          jobId={id}
          showReviewButton={isAwaiting}
          showDoneButton={isDone}
          videoUrl={isDone ? "result" : undefined}
        />
      </div>

      {/* Clip tiles (visible during video generation) */}
      {totalClips > 0 && (
        <div className="mb-8">
          <p className="text-xs font-semibold text-[#9ca3af] uppercase tracking-widest mb-3">
            Clips ({clipsDone.length}/{totalClips})
          </p>
          <div className="grid grid-cols-4 gap-2">
            {[...Array(totalClips)].map((_, i) => {
              const label = `clip_${String(i + 1).padStart(2, "0")}`;
              const done = clipsDone.includes(label);
              return (
                <div
                  key={i}
                  className={`h-14 rounded-lg border flex items-center justify-center text-xs mono transition-all ${
                    done
                      ? "border-green-500/40 bg-green-500/10 text-green-400"
                      : "border-[#2a2a2a] bg-[#1a1a1a] text-[#4b5563]"
                  }`}
                >
                  {done ? (
                    <span className="flex items-center gap-1.5">✓ {i + 1}</span>
                  ) : (
                    <span className="w-4 h-4 rounded-full border border-current border-t-transparent spin" />
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
          className="h-48 overflow-y-auto rounded-xl bg-[#0a0a0a] border border-[#1e1e1e] p-3 flex flex-col gap-1"
        >
          {events.length === 0 ? (
            <p className="text-xs text-[#4b5563] mono">Connecting…</p>
          ) : (
            events.filter((e) => e.type !== "heartbeat").map((ev, i) => (
              <div key={i} className="flex items-start gap-2 text-xs mono fade-in">
                <span className="text-[#4b5563] shrink-0">{ev.ts}</span>
                <span
                  className={
                    ev.type === "error"
                      ? "text-red-400"
                      : ev.type === "done"
                      ? "text-green-400"
                      : ev.type === "awaiting_approval"
                      ? "text-amber-400"
                      : "text-[#9ca3af]"
                  }
                >
                  [{ev.type}]
                </span>
                <span className="text-[#6b7280] break-all">
                  {Object.entries(ev.data)
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
