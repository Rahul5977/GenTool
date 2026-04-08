"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api, type JobStatus } from "@/lib/api";
import KeyFrameCard from "@/components/KeyFrameCard";

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [approved, setApproved] = useState<Set<number>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    try {
      const s = await api.getJobStatus(id);
      setJobStatus(s);
      // Pre-approve all by default
      if (s.num_keyframes > 0) {
        setApproved(new Set([...Array(s.num_keyframes)].map((_, i) => i)));
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load job");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  function handleToggle(index: number, val: boolean) {
    setApproved((prev) => {
      const next = new Set(prev);
      if (val) next.add(index); else next.delete(index);
      return next;
    });
  }

  function handleRegenerated(index: number) {
    // Un-approve the regen'd frame so user must re-check
    setApproved((prev) => { const next = new Set(prev); next.delete(index); return next; });
  }

  async function handleApproveAll() {
    if (approved.size === 0) { setError("Please approve at least one keyframe."); return; }
    setSubmitting(true);
    setError("");
    try {
      await api.approveImages(id, { approved_indices: [...approved] });
      router.push(`/jobs/${id}/progress`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Approval failed");
      setSubmitting(false);
    }
  }

  const numFrames = jobStatus?.num_keyframes ?? 0;
  const numClips = numFrames > 0 ? numFrames - 1 : 0;

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-green-500 border-t-transparent spin" />
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-10 max-w-6xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-[#4b5563] mb-8">
        <Link href="/" className="hover:text-white transition-colors">Flash Tool</Link>
        <span>/</span>
        <Link href={`/jobs/${id}/progress`} className="hover:text-white transition-colors mono text-xs">{id.slice(0, 8)}…</Link>
        <span>/</span>
        <span className="text-white">Review</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between gap-6 mb-6 flex-wrap">
        <div>
          <h2 className="text-xl font-bold text-white mb-1">
            Review Keyframes
          </h2>
          <p className="text-[#6b7280] text-sm">
            {numFrames} images for {numClips} clips.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs text-[#6b7280] mono">{approved.size}/{numFrames} approved</span>
          <button
            onClick={handleApproveAll}
            disabled={submitting || approved.size === 0}
            className="px-5 py-2.5 rounded-xl font-semibold text-sm bg-[#1a5c3a] text-white border border-green-500/20 hover:bg-[#22703f] disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-[0_0_20px_rgba(26,92,58,0.3)]"
          >
            {submitting ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white spin" />
                Starting…
              </span>
            ) : (
              "Approve & Generate Videos →"
            )}
          </button>
        </div>
      </div>

      {/* Explanation */}
      <div className="p-4 rounded-xl bg-[#0d1a12] border border-[#1a5c3a]/40 mb-8 text-xs text-green-300/80 leading-relaxed mono">
        <span className="text-green-400 font-semibold">How keyframes work: </span>
        Image 0 = Clip 1 first frame. Image 1 = End of Clip 1 = Start of Clip 2. Etc.
        Veo generates video <em>between</em> each consecutive image pair — so matching expressions at boundaries creates seamless clips.
        Regenerate any image that has the wrong expression or background inconsistency.
      </div>

      {error && (
        <div className="mb-6 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Approve All / None shortcuts */}
      <div className="flex gap-3 mb-6">
        <button
          onClick={() => setApproved(new Set([...Array(numFrames)].map((_, i) => i)))}
          className="px-3 py-1.5 rounded-lg text-xs border border-[#2a2a2a] text-[#9ca3af] hover:border-green-500/40 hover:text-green-400 transition-all"
        >
          Select all
        </button>
        <button
          onClick={() => setApproved(new Set())}
          className="px-3 py-1.5 rounded-lg text-xs border border-[#2a2a2a] text-[#9ca3af] hover:border-red-500/40 hover:text-red-400 transition-all"
        >
          Deselect all
        </button>
      </div>

      {/* Keyframe grid */}
      {numFrames === 0 ? (
        <div className="text-center py-20 border border-dashed border-[#2a2a2a] rounded-2xl">
          <p className="text-[#6b7280] text-sm">No keyframes found. Something may have gone wrong.</p>
          <Link href={`/jobs/${id}/progress`} className="inline-block mt-3 text-xs text-green-400 underline underline-offset-2">
            ← Back to progress
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {[...Array(numFrames)].map((_, i) => (
            <KeyFrameCard
              key={i}
              jobId={id}
              index={i}
              total={numFrames}
              description={
                i === 0
                  ? "Opening frame — initial character reference"
                  : `End of clip ${i} → Start of clip ${i + 1}`
              }
              approved={approved.has(i)}
              onToggleApprove={handleToggle}
              onRegenerated={handleRegenerated}
            />
          ))}
        </div>
      )}

      {/* Bottom approve button */}
      {numFrames > 0 && (
        <div className="mt-10 flex justify-end">
          <button
            onClick={handleApproveAll}
            disabled={submitting || approved.size === 0}
            className="px-6 py-3 rounded-xl font-semibold text-sm bg-[#1a5c3a] text-white border border-green-500/20 hover:bg-[#22703f] disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-[0_0_24px_rgba(26,92,58,0.4)]"
          >
            {submitting ? "Starting video generation…" : `Approve ${approved.size} frame${approved.size !== 1 ? "s" : ""} & Generate Videos →`}
          </button>
        </div>
      )}
    </main>
  );
}
