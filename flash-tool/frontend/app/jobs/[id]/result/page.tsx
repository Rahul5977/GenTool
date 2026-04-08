"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type JobStatus } from "@/lib/api";
import VideoPlayer from "@/components/VideoPlayer";

export default function ResultPage() {
  const { id } = useParams<{ id: string }>();
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [regenLoading, setRegenLoading] = useState<number | null>(null);
  const [regenError, setRegenError] = useState("");
  const [videoKey, setVideoKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getJobStatus(id)
      .then(setJobStatus)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [id, videoKey]);

  async function handleRegenClip(clipIndex: number) {
    setRegenLoading(clipIndex);
    setRegenError("");
    try {
      await api.regenClip(id, { clip_index: clipIndex });
      setVideoKey((k) => k + 1); // refresh status + video
    } catch (e: unknown) {
      setRegenError(e instanceof Error ? e.message : "Regen failed");
    } finally {
      setRegenLoading(null);
    }
  }

  const finalPath = jobStatus?.final_video_path ?? "";
  const filename = finalPath ? finalPath.split("/").pop() ?? "final.mp4" : "";
  const videoUrl = filename ? api.videoUrl(id, filename) : "";

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-green-500 border-t-transparent spin" />
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

  const numClips = jobStatus.clips_done;

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
            <div className="aspect-[9/16] max-w-[360px] rounded-2xl bg-[#161616] border border-[#2a2a2a] flex items-center justify-center">
              <p className="text-[#4b5563] text-sm text-center px-4">Video not yet available.<br />Check back shortly.</p>
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
              {[...Array(numClips)].map((_, i) => (
                <div
                  key={i}
                  className="p-4 rounded-xl bg-[#161616] border border-[#2a2a2a] hover:border-[#3a3a3a] transition-all"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded bg-[#1a5c3a]/40 text-green-400 text-xs font-bold flex items-center justify-center mono">
                        {i + 1}
                      </span>
                      <span className="text-sm font-medium text-white">Clip {i + 1}</span>
                    </div>
                    <button
                      onClick={() => handleRegenClip(i)}
                      disabled={regenLoading !== null}
                      className="px-3 py-1 rounded-lg text-xs font-medium border border-[#2a2a2a] text-[#9ca3af] hover:border-[#3a3a3a] hover:text-white disabled:opacity-40 transition-all"
                    >
                      {regenLoading === i ? (
                        <span className="flex items-center gap-1.5">
                          <span className="w-3 h-3 rounded-full border border-current border-t-transparent spin" />
                          Regenerating…
                        </span>
                      ) : (
                        "↺ Regen clip"
                      )}
                    </button>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-[#4b5563]">
                    <span className="mono">~8s</span>
                    <span>·</span>
                    <span className="flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
                      Generated
                    </span>
                  </div>
                </div>
              ))}
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
