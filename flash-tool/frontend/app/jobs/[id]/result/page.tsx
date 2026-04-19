"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, API_BASE_URL, type JobStatus, type ClipPrompt } from "@/lib/api";
import VideoPlayer from "@/components/VideoPlayer";

interface ClipRegenState {
  showPromptEditor: boolean;
  editedPrompt: string;
}

export default function ResultPage() {
  const { id } = useParams<{ id: string }>();
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [clips, setClips] = useState<ClipPrompt[]>([]);
  const [clipRegenStates, setClipRegenStates] = useState<Record<number, ClipRegenState>>({});
  const [selectedClips, setSelectedClips] = useState<Set<number>>(new Set());
  const [regenningClips, setRegenningClips] = useState<Set<number>>(new Set());
  const [restitching, setRestitching] = useState(false);
  const [clipVideoKeys, setClipVideoKeys] = useState<Record<number, number>>({});
  const [currentVideoUrl, setCurrentVideoUrl] = useState("");
  const [openPreviewIndex, setOpenPreviewIndex] = useState<number | null>(null);
  const [regenError, setRegenError] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const [status, clipsResp] = await Promise.all([
          api.getJobStatus(id),
          fetch(`${API_BASE_URL}/api/v2/jobs/${id}/clips`).then((r) => (r.ok ? r.json() : { clips: [] })),
        ]);
        setJobStatus(status);
        if (status.final_video_path) {
          const filename = status.final_video_path.split("/").pop();
          if (filename) setCurrentVideoUrl(api.videoUrl(id, filename));
        }

        const fetchedClips: ClipPrompt[] = clipsResp.clips ?? [];
        setClips(fetchedClips);
        setClipRegenStates((prev) => {
          const next: Record<number, ClipRegenState> = { ...prev };
          fetchedClips.forEach((clip, i) => {
            if (!next[i]) {
              next[i] = { showPromptEditor: false, editedPrompt: clip.prompt };
            }
          });
          return next;
        });
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  function setClipState(clipIndex: number, patch: Partial<ClipRegenState>) {
    setClipRegenStates((prev) => {
      const current = prev[clipIndex] ?? { showPromptEditor: false, editedPrompt: clips[clipIndex]?.prompt ?? "" };
      const next = { ...prev };
      next[clipIndex] = { ...current, ...patch };
      return next;
    });
  }

  function toggleClipSelection(clipIndex: number) {
    setSelectedClips((prev) => {
      const next = new Set(prev);
      if (next.has(clipIndex)) next.delete(clipIndex);
      else next.add(clipIndex);
      return next;
    });
  }

  function selectAll() {
    setSelectedClips(new Set(clips.map((_, i) => i)));
  }

  function clearSelection() {
    setSelectedClips(new Set());
  }

  async function handleRegenSelected() {
    if (selectedClips.size === 0) return;

    const indices = [...selectedClips];
    setRegenningClips(new Set(indices));
    setRegenError("");

    const results = await Promise.allSettled(
      indices.map(async (clipIndex) => {
        const state = clipRegenStates[clipIndex];
        const clip = clips[clipIndex];
        const updatedPrompt =
          state?.editedPrompt && state.editedPrompt !== clip?.prompt
            ? state.editedPrompt
            : undefined;

        await api.regenClip(id, {
          clip_index: clipIndex,
          updated_prompt: updatedPrompt,
        });

        setClipVideoKeys((prev) => ({
          ...prev,
          [clipIndex]: (prev[clipIndex] ?? 0) + 1,
        }));

        if (updatedPrompt) {
          setClips((prev) => {
            const next = [...prev];
            if (next[clipIndex]) next[clipIndex] = { ...next[clipIndex], prompt: updatedPrompt };
            return next;
          });
        }

        return clipIndex;
      })
    );

    setRegenningClips(new Set());

    const failures = results.filter((r) => r.status === "rejected");
    if (failures.length > 0) {
      setRegenError(`${failures.length} clip(s) failed to regenerate`);
      return;
    }

    setRestitching(true);
    try {
      // Omit clip_indices so the server stitches ALL clip_paths. Passing only the
      // regen'd indices produced a final video containing just those clips (bug).
      const result = await api.restitch(id);
      setCurrentVideoUrl(`${API_BASE_URL}${result.video_url}`);
      setSelectedClips(new Set());
      setJobStatus((prev) => (prev ? { ...prev, status: "done" } : prev));
    } catch (e: unknown) {
      setRegenError(e instanceof Error ? e.message : "Restitch failed");
    } finally {
      setRestitching(false);
    }
  }

  const numClips = clips.length > 0 ? clips.length : (jobStatus?.clips_done ?? 0);
  const anyClipRegenning = regenningClips.size > 0;
  const regenButtonDisabled = selectedClips.size === 0 || restitching || anyClipRegenning;

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
        {/* Left column: Video player */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-white">Final Ad</h2>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-400" />
              <span className="text-xs text-green-400 font-semibold">Done</span>
            </div>
          </div>

          {currentVideoUrl ? (
            <div className="relative">
              <VideoPlayer key={currentVideoUrl} src={currentVideoUrl} aspectRatio="9:16" />
              {restitching && (
                <div className="absolute inset-0 rounded-2xl bg-black/55 flex items-center justify-center">
                  <div className="flex items-center gap-2 text-sm text-white">
                    <span className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                    Re-stitching...
                  </div>
                </div>
              )}
              <div className="mt-4 flex gap-3">
                <a
                  href={`${currentVideoUrl}?download=1`}
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
            </div>
          ) : (
            <div className="aspect-9/16 max-w-90 rounded-2xl bg-[#161616] border border-[#2a2a2a] flex items-center justify-center">
              <p className="text-[#4b5563] text-sm text-center px-4">
                Video not yet available.<br />Check back shortly.
              </p>
            </div>
          )}
        </div>

        {/* Right column: Clip list */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-[#9ca3af] uppercase tracking-widest">Clips</h3>
              {selectedClips.size > 0 && (
                <span className="px-2 py-0.5 rounded-full bg-green-500/10 border border-green-500/30 text-[11px] text-green-300">
                  {selectedClips.size} selected
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={selectAll}
                className="text-xs text-[#9ca3af] hover:text-white transition-colors"
              >
                Select All
              </button>
              {selectedClips.size > 0 && (
                <button
                  onClick={clearSelection}
                  className="text-xs text-[#9ca3af] hover:text-white transition-colors"
                >
                  Clear
                </button>
              )}
              <button
                onClick={handleRegenSelected}
                disabled={regenButtonDisabled}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#1a5c3a] text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {(anyClipRegenning || restitching) ? (
                  <span className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full border border-current border-t-transparent animate-spin" />
                    {selectedClips.size > 0 ? `Regen Selected (${selectedClips.size})` : "Regen Selected"}
                  </span>
                ) : (
                  selectedClips.size > 0 ? `Regen Selected (${selectedClips.size})` : "Regen Selected"
                )}
              </button>
            </div>
          </div>

          {regenError && (
            <div className="mb-4 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-center justify-between">
              <span>⚠ {regenError}</span>
              <button onClick={() => setRegenError("")} className="text-red-200 hover:text-white">×</button>
            </div>
          )}

          {numClips === 0 ? (
            <p className="text-[#4b5563] text-sm">No clip data available.</p>
          ) : (
            <div className="flex flex-col gap-3">
              {[...Array(numClips)].map((_, i) => {
                const clip = clips[i];
                const state = clipRegenStates[i];
                const hasEdits = !!(state && clip && state.editedPrompt !== clip.prompt);
                const selected = selectedClips.has(i);
                const regenning = regenningClips.has(i);
                const openPreview = openPreviewIndex === i;
                const cardClass = regenning
                  ? "border-yellow-500/30 bg-yellow-500/5 animate-pulse"
                  : selected
                  ? "border-green-500/50 bg-green-500/5"
                  : "border-[#2a2a2a] bg-[#161616]";

                return (
                  <div
                    key={i}
                    className={`rounded-xl border overflow-hidden ${cardClass}`}
                  >
                    <div
                      className="p-4 cursor-pointer"
                      onClick={() => toggleClipSelection(i)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={selected}
                            disabled={regenning}
                            onChange={() => toggleClipSelection(i)}
                            onClick={(e) => e.stopPropagation()}
                          />
                          <span className="text-sm font-medium text-white">Clip {clip?.clip_number ?? i + 1}</span>
                          {clip && (
                            <span className="text-xs text-[#4b5563] mono">
                              • {clip.duration_seconds}s • {clip.word_count}w
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setOpenPreviewIndex((prev) => (prev === i ? null : i));
                            }}
                            className="px-2 py-1 rounded text-xs border border-[#2a2a2a] text-[#9ca3af] hover:text-white"
                          >
                            Preview ▶
                          </button>
                        </div>
                      </div>

                      {clip?.dialogue && (
                        <p className="text-xs text-[#9ca3af] truncate">
                          Dialogue: &ldquo;{clip.dialogue}&rdquo;
                        </p>
                      )}
                    </div>

                    <div className="border-t border-[#1e1e1e] px-4 py-2">
                      <button
                        onClick={() => setClipState(i, { showPromptEditor: !state?.showPromptEditor })}
                        className="text-xs text-[#9ca3af] hover:text-white flex items-center gap-2"
                      >
                        <span>{state?.showPromptEditor ? "▲ Edit Prompt" : "▼ Edit Prompt"}</span>
                        {hasEdits && <span className="w-2 h-2 rounded-full bg-yellow-400" />}
                      </button>
                    </div>

                    {state?.showPromptEditor && clip && (
                      <div className="px-4 pb-4">
                        <textarea
                          value={clipRegenStates[i]?.editedPrompt ?? clip.prompt}
                          onChange={(e) =>
                            setClipState(i, { editedPrompt: e.target.value })
                          }
                          onClick={(e) => e.stopPropagation()}
                          rows={6}
                          disabled={regenning}
                          className="w-full bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg p-2.5 text-xs text-[#c5c5c5] font-mono resize-y focus:outline-none focus:border-green-500/40"
                          spellCheck={false}
                        />
                      </div>
                    )}

                    {openPreview && clip && (
                      <div className="px-4 pb-4">
                        <div className="relative rounded-lg border border-[#2a2a2a] bg-black p-2">
                          <button
                            onClick={() => setOpenPreviewIndex(null)}
                            className="absolute right-2 top-1 text-white/80 hover:text-white z-10"
                          >
                            ×
                          </button>
                          <video
                            src={`${api.clipUrl(id, clip.clip_number)}?v=${clipVideoKeys[i] ?? 0}`}
                            controls
                            autoPlay
                            className="w-full rounded"
                          />
                        </div>
                      </div>
                    )}

                    {regenning && (
                      <div className="px-4 pb-3 text-xs text-yellow-300">⟳ Regenerating clip...</div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
