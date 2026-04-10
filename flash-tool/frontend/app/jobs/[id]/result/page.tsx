"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type JobStatus, type ClipPrompt } from "@/lib/api";
import VideoPlayer from "@/components/VideoPlayer";

interface ClipRegenState {
  loading: boolean;
  showPromptEditor: boolean;
  editedPrompt: string;
  saved: boolean;
}

export default function ResultPage() {
  const { id } = useParams<{ id: string }>();
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [clips, setClips] = useState<ClipPrompt[]>([]);
  const [clipRegenStates, setClipRegenStates] = useState<ClipRegenState[]>([]);
  const [regenError, setRegenError] = useState("");
  const [videoKey, setVideoKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Initial load — runs once on mount (videoKey only drives the VideoPlayer key, not data reload)
  useEffect(() => {
    async function load() {
      try {
        const [status, clipsResp] = await Promise.all([
          api.getJobStatus(id),
          fetch(
            `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v2/jobs/${id}/clips`
          ).then((r) => r.ok ? r.json() : { clips: [] }),
        ]);
        setJobStatus(status);

        const fetchedClips: ClipPrompt[] = clipsResp.clips ?? [];
        setClips(fetchedClips);
        // Only initialise states for clips that don't have one yet
        setClipRegenStates((prev) =>
          fetchedClips.map((c, i) =>
            prev[i]
              ? prev[i]
              : { loading: false, showPromptEditor: false, editedPrompt: c.prompt, saved: false }
          )
        );
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]); // videoKey removed — data reload is now manual and targeted

  function setClipState(clipIndex: number, patch: Partial<ClipRegenState>) {
    setClipRegenStates((prev) => {
      const next = [...prev];
      next[clipIndex] = { ...next[clipIndex], ...patch };
      return next;
    });
  }

  // Save prompt only (no regen) — works after the job is done
  async function handleSavePrompt(clipIndex: number) {
    const state = clipRegenStates[clipIndex];
    const clip = clips[clipIndex];
    if (!state || !clip) return;
    setRegenError("");
    try {
      await api.saveClipPrompt(id, clipIndex, { prompt: state.editedPrompt });
      // Reflect the saved prompt in the clips array so hasEdits correctly resets
      setClips((prev) => {
        const next = [...prev];
        next[clipIndex] = { ...next[clipIndex], prompt: state.editedPrompt };
        return next;
      });
      setClipState(clipIndex, { saved: true });
    } catch (e: unknown) {
      setRegenError(e instanceof Error ? e.message : "Save failed");
    }
  }

  async function handleRegenClip(clipIndex: number) {
    const state = clipRegenStates[clipIndex];
    if (!state) return;

    setClipState(clipIndex, { loading: true });
    setRegenError("");
    try {
      // Pass the edited prompt (backend will save it and use it for generation)
      const updatedPrompt =
        state.editedPrompt !== clips[clipIndex]?.prompt ? state.editedPrompt : undefined;
      await api.regenClip(id, { clip_index: clipIndex, updated_prompt: updatedPrompt });

      // Fetch updated clip list from server (only clips — not full page reload)
      const clipsResp = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v2/jobs/${id}/clips`
      ).then((r) => (r.ok ? r.json() : { clips: [] }));
      const fetchedClips: ClipPrompt[] = clipsResp.clips ?? [];
      setClips(fetchedClips);

      // Reset ONLY this clip's state — all other editors stay open and unchanged
      setClipRegenStates((prev) => {
        const next = [...prev];
        next[clipIndex] = {
          loading: false,
          showPromptEditor: false,
          editedPrompt: fetchedClips[clipIndex]?.prompt ?? "",
          saved: false,
        };
        return next;
      });

      // Re-mount the video player to pick up the new clip URL
      setVideoKey((k) => k + 1);
    } catch (e: unknown) {
      setRegenError(e instanceof Error ? e.message : "Regen failed");
      setClipState(clipIndex, { loading: false });
    }
  }

  const finalPath = jobStatus?.final_video_path ?? "";
  const filename = finalPath ? finalPath.split("/").pop() ?? "final.mp4" : "";
  const videoUrl = filename ? api.videoUrl(id, filename) : "";
  const numClips = clips.length > 0 ? clips.length : (jobStatus?.clips_done ?? 0);

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-green-500 border-t-transparent animate-spin" />
      </main>
    );
  }

  if (error || !jobStatus) {
    return (
      <main className="min-h-screen flex flex-col items-center justify-center gap-4">
        <p className="text-red-400 text-sm">{error || "Job not found"}</p>
        <Link href="/" className="text-xs text-green-400 underline underline-offset-2">← Dashboard</Link>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-10 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-[#4b5563] mb-8">
        <Link href="/" className="hover:text-white transition-colors">Flash Tool</Link>
        <span>/</span>
        <span className="mono text-xs text-[#6b7280]">{id.slice(0, 8)}…</span>
        <span>/</span>
        <span className="text-white">Result</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
        {/* Left: video player */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-white">Final Ad</h2>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-400" />
              <span className="text-xs text-green-400 font-semibold">Done</span>
            </div>
          </div>

          {videoUrl ? (
            <>
              <VideoPlayer key={videoKey} src={`${videoUrl}?v=${videoKey}`} aspectRatio="9:16" />
              <div className="mt-4 flex gap-3">
                <a
                  href={`${videoUrl}?download=1`}
                  download="superliving_ad.mp4"
                  className="flex-1 py-2.5 rounded-xl text-center text-sm font-semibold bg-[#161616] border border-[#2a2a2a] text-[#9ca3af] hover:border-green-500/40 hover:text-green-400 transition-all"
                >
                  ↓ Download
                </a>
                <Link
                  href="/new"
                  className="flex-1 py-2.5 rounded-xl text-center text-sm font-semibold bg-[#1a5c3a] text-white border border-green-500/20 hover:bg-[#22703f] transition-all"
                >
                  + New Ad
                </Link>
              </div>
            </>
          ) : (
            <div className="aspect-9/16 max-w-90 rounded-2xl bg-[#161616] border border-[#2a2a2a] flex items-center justify-center">
              <p className="text-[#4b5563] text-sm text-center px-4">
                Video not yet available.<br />Check back shortly.
              </p>
            </div>
          )}
        </div>

        {/* Right: clip breakdown */}
        <div>
          <h3 className="text-sm font-semibold text-[#9ca3af] uppercase tracking-widest mb-4">
            Clip Breakdown
          </h3>

          {regenError && (
            <div className="mb-4 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
              {regenError}
            </div>
          )}

          {numClips === 0 ? (
            <p className="text-[#4b5563] text-sm">No clip data available.</p>
          ) : (
            <div className="flex flex-col gap-3">
              {[...Array(numClips)].map((_, i) => {
                const clip = clips[i];
                const state = clipRegenStates[i];
                const hasEdits = state && clip && state.editedPrompt !== clip.prompt;

                return (
                  <div
                    key={i}
                    className="rounded-xl bg-[#161616] border border-[#2a2a2a] overflow-hidden"
                  >
                    {/* Clip header */}
                    <div className="p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="w-5 h-5 rounded bg-[#1a5c3a]/40 text-green-400 text-xs font-bold flex items-center justify-center mono">
                            {i + 1}
                          </span>
                          <span className="text-sm font-medium text-white">Clip {i + 1}</span>
                          {clip && (
                            <span className="text-xs text-[#4b5563] mono">
                              {clip.duration_seconds}s · {clip.word_count}w
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          {clip && state && (
                            <button
                              onClick={() =>
                                setClipState(i, { showPromptEditor: !state.showPromptEditor })
                              }
                              className={`px-2 py-1 rounded text-xs border transition-all ${
                                state.showPromptEditor
                                  ? "border-violet-500/40 text-violet-300 bg-violet-500/10"
                                  : "border-[#2a2a2a] text-[#6b7280] hover:border-[#3a3a3a] hover:text-[#9ca3af]"
                              }`}
                            >
                              {state.showPromptEditor ? "▲ Hide prompt" : "Edit prompt"}
                            </button>
                          )}
                          <button
                            onClick={() => handleRegenClip(i)}
                            disabled={state?.loading || clipRegenStates.some((s) => s?.loading)}
                            className="px-3 py-1 rounded-lg text-xs font-medium border border-[#2a2a2a] text-[#9ca3af] hover:border-[#3a3a3a] hover:text-white disabled:opacity-40 transition-all"
                          >
                            {state?.loading ? (
                              <span className="flex items-center gap-1.5">
                                <span className="w-3 h-3 rounded-full border border-current border-t-transparent animate-spin" />
                                Regen…
                              </span>
                            ) : (
                              hasEdits ? "↺ Regen with edits" : "↺ Regen clip"
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Dialogue preview */}
                      {clip?.dialogue && (
                        <p className="text-xs text-[#6b7280] italic mt-1">
                          &ldquo;{clip.dialogue}&rdquo;
                        </p>
                      )}
                    </div>

                    {/* Editable prompt textarea */}
                    {state?.showPromptEditor && clip && (
                      <div className="border-t border-[#1e1e1e] p-3 flex flex-col gap-2">
                        <div className="flex items-center justify-between">
                          <p className="text-xs text-[#4b5563] mono">Veo Prompt</p>
                          <div className="flex items-center gap-2">
                            {hasEdits && (
                              <button
                                onClick={() =>
                                  setClipState(i, { editedPrompt: clip.prompt, saved: false })
                                }
                                className="text-xs text-[#4b5563] hover:text-[#9ca3af] transition-colors"
                              >
                                Reset
                              </button>
                            )}
                            {hasEdits && !state.saved && (
                              <span className="text-xs text-amber-400 mono">unsaved</span>
                            )}
                            {state.saved && (
                              <span className="text-xs text-green-400 mono">✓ saved</span>
                            )}
                          </div>
                        </div>
                        <textarea
                          value={state.editedPrompt}
                          onChange={(e) =>
                            setClipState(i, { editedPrompt: e.target.value, saved: false })
                          }
                          rows={14}
                          className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded-lg p-2.5 text-xs text-[#9ca3af] mono leading-relaxed resize-y focus:outline-none focus:border-violet-500/40 transition-colors"
                          spellCheck={false}
                        />
                        <div className="flex items-center justify-between">
                          <p className="text-[10px] text-[#3a3a3a] mono">
                            {state.editedPrompt.length} chars
                          </p>
                          {hasEdits && (
                            <button
                              onClick={() => handleSavePrompt(i)}
                              disabled={state.loading}
                              className="px-3 py-1 rounded-lg text-xs font-medium border border-violet-500/40 text-violet-300 bg-violet-500/10 hover:bg-violet-500/20 disabled:opacity-40 transition-all"
                            >
                              ↓ Save edits
                            </button>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Meta */}
          <div className="mt-6 p-4 rounded-xl bg-[#0a0a0a] border border-[#1e1e1e]">
            <p className="text-xs font-semibold text-[#9ca3af] uppercase tracking-widest mb-3">Job Info</p>
            <div className="flex flex-col gap-2 text-xs mono">
              {[
                ["Job ID", id],
                ["Status", jobStatus.status],
                ["Clips", String(numClips)],
                ["Created", new Date(jobStatus.created_at).toLocaleString()],
              ].map(([k, v]) => (
                <div key={k} className="flex gap-2">
                  <span className="text-[#4b5563] w-20 shrink-0">{k}</span>
                  <span className="text-[#9ca3af] break-all">{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
