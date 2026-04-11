"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api, type ClipPrompt } from "@/lib/api";

interface EditState {
  [clipIndex: number]: string; // clip index → current prompt text
}

interface SaveState {
  [clipIndex: number]: "saving" | "saved" | "error";
}

export default function ReviewPromptsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [clips, setClips] = useState<ClipPrompt[]>([]);
  const [editState, setEditState] = useState<EditState>({});
  const [saveState, setSaveState] = useState<SaveState>({});
  const [expandedClip, setExpandedClip] = useState<number | null>(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [jobError, setJobError] = useState("");
  const [uploadError, setUploadError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchClips = useCallback(async () => {
    try {
      // Get clips from SSE events stored in job. We use the status endpoint
      // to verify the job is in the right state, then build the clips from
      // the job store via a dedicated endpoint.
      // For now we read clips from a GET that mirrors job status but with clips.
      const resp = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v2/jobs/${id}/clips`
      );
      if (resp.ok) {
        const data = await resp.json();
        const fetchedClips: ClipPrompt[] = data.clips ?? [];
        setClips(fetchedClips);
        // Initialize edit state with current prompt values
        const initial: EditState = {};
        fetchedClips.forEach((c, i) => { initial[i] = c.prompt; });
        setEditState(initial);
        setExpandedClip(fetchedClips.length > 0 ? 0 : null);
      } else {
        setJobError("Could not load clip prompts. Make sure the job is in prompt review state.");
      }
    } catch {
      setJobError("Failed to connect to backend.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { fetchClips(); }, [fetchClips]);

  function handlePromptChange(clipIndex: number, value: string) {
    setEditState((prev) => ({ ...prev, [clipIndex]: value }));
    // Clear previous save state when user edits
    setSaveState((prev) => { const next = { ...prev }; delete next[clipIndex]; return next; });
  }

  function handleDownload() {
    const payload = {
      job_id: id,
      exported_at: new Date().toISOString(),
      clips: clips.map((c, i) => ({
        clip_number: c.clip_number,
        duration_seconds: c.duration_seconds,
        scene_summary: c.scene_summary,
        dialogue: c.dialogue,
        prompt: editState[i] ?? c.prompt,
      })),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `prompts_${id.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleUploadClick() {
    setUploadError("");
    fileInputRef.current?.click();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const parsed = JSON.parse(ev.target?.result as string);
        const importedClips: { clip_number: number; prompt: string }[] =
          parsed.clips ?? [];

        if (!Array.isArray(importedClips) || importedClips.length === 0) {
          setUploadError("Invalid file: no clips array found.");
          return;
        }

        // Match by clip_number so order in file doesn't matter
        setEditState((prev) => {
          const next = { ...prev };
          importedClips.forEach((imported) => {
            const idx = clips.findIndex((c) => c.clip_number === imported.clip_number);
            if (idx !== -1 && typeof imported.prompt === "string") {
              next[idx] = imported.prompt;
            }
          });
          return next;
        });
        // Clear save states so user can save explicitly
        setSaveState({});
        setUploadError("");
      } catch {
        setUploadError("Could not parse file — make sure it is valid JSON.");
      }
    };
    reader.readAsText(file);
    // Reset so the same file can be re-uploaded if needed
    e.target.value = "";
  }

  async function handleSaveClip(clipIndex: number) {
    const prompt = editState[clipIndex];
    if (!prompt?.trim()) return;

    setSaveState((prev) => ({ ...prev, [clipIndex]: "saving" }));
    try {
      await api.updateClipPrompt(id, clipIndex, { prompt });
      setSaveState((prev) => ({ ...prev, [clipIndex]: "saved" }));
    } catch (e: unknown) {
      setSaveState((prev) => ({ ...prev, [clipIndex]: "error" }));
      setError(e instanceof Error ? e.message : "Save failed");
    }
  }

  async function handleApproveAll() {
    setSubmitting(true);
    setError("");
    try {
      // Save any unsaved changes first
      const unsavedIndices = clips
        .map((_, i) => i)
        .filter((i) => editState[i] !== clips[i]?.prompt && saveState[i] !== "saved");

      await Promise.all(
        unsavedIndices.map((i) => api.updateClipPrompt(id, i, { prompt: editState[i] }))
      );

      await api.approvePrompts(id);
      router.push(`/jobs/${id}/progress`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Approval failed");
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-green-500 border-t-transparent animate-spin" />
      </main>
    );
  }

  if (jobError) {
    return (
      <main className="min-h-screen flex flex-col items-center justify-center gap-4 px-6">
        <p className="text-red-400 text-sm text-center">{jobError}</p>
        <Link href={`/jobs/${id}/progress`} className="text-xs text-green-400 underline underline-offset-2">
          ← Back to progress
        </Link>
      </main>
    );
  }

  const hasUnsaved = clips.some((c, i) => editState[i] !== c.prompt && saveState[i] !== "saved");

  return (
    <main className="min-h-screen px-6 py-10 max-w-4xl mx-auto">
      {/* Hidden file input for upload */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".json,application/json"
        className="hidden"
        onChange={handleFileChange}
      />

      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-[#4b5563] mb-8">
        <Link href="/" className="hover:text-white transition-colors">Flash Tool</Link>
        <span>/</span>
        <Link href={`/jobs/${id}/progress`} className="hover:text-white transition-colors mono text-xs">
          {id.slice(0, 8)}…
        </Link>
        <span>/</span>
        <span className="text-white">Review Prompts</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between gap-6 mb-6 flex-wrap">
        <div>
          <h2 className="text-xl font-bold text-white mb-1">Review Clip Prompts</h2>
          <p className="text-[#6b7280] text-sm">
            {clips.length} clips — edit prompts here or download, edit offline, and upload back.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0 flex-wrap">
          {/* Download */}
          <button
            onClick={handleDownload}
            disabled={clips.length === 0}
            className="px-3 py-2 rounded-lg text-xs font-medium border border-[#2a2a2a] text-[#9ca3af] hover:border-[#3a3a3a] hover:text-white disabled:opacity-40 transition-all flex items-center gap-1.5"
            title="Download prompts as JSON"
          >
            ↓ Download
          </button>
          {/* Upload */}
          <button
            onClick={handleUploadClick}
            className="px-3 py-2 rounded-lg text-xs font-medium border border-[#2a2a2a] text-[#9ca3af] hover:border-violet-500/40 hover:text-violet-300 transition-all flex items-center gap-1.5"
            title="Upload edited JSON to restore prompts"
          >
            ↑ Upload
          </button>
          {/* Approve */}
          <button
            onClick={handleApproveAll}
            disabled={submitting}
            className="px-5 py-2.5 rounded-xl font-semibold text-sm bg-[#1a5c3a] text-white border border-green-500/20 hover:bg-[#22703f] disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-[0_0_20px_rgba(26,92,58,0.3)]"
          >
            {submitting ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                Starting…
              </span>
            ) : (
              hasUnsaved ? "Save All & Generate Images →" : "Approve & Generate Images →"
            )}
          </button>
        </div>
      </div>

      {/* Info banner */}
      <div className="p-4 rounded-xl bg-violet-500/10 border border-violet-500/30 mb-8 text-xs text-violet-300/90 leading-relaxed">
        <span className="text-violet-400 font-semibold">How to use: </span>
        Each clip has its full Veo prompt below the summary. Edit any section — dialogue,
        action, audio — to fine-tune the output. Click <strong>Save</strong> to persist changes.
        When satisfied, click <strong>Approve & Generate Images</strong> to proceed.
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          {error}
        </div>
      )}

      {uploadError && (
        <div className="mb-4 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm flex items-center justify-between gap-4">
          <span>{uploadError}</span>
          <button onClick={() => setUploadError("")} className="text-red-400/60 hover:text-red-400 text-xs shrink-0">✕</button>
        </div>
      )}

      {/* Clip cards */}
      {clips.length === 0 ? (
        <div className="text-center py-20 border border-dashed border-[#2a2a2a] rounded-2xl">
          <p className="text-[#6b7280] text-sm">No clips found.</p>
          <Link href={`/jobs/${id}/progress`} className="inline-block mt-3 text-xs text-green-400 underline underline-offset-2">
            ← Back to progress
          </Link>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {clips.map((clip, clipIndex) => {
            const isExpanded = expandedClip === clipIndex;
            const currentPrompt = editState[clipIndex] ?? clip.prompt;
            const isDirty = currentPrompt !== clip.prompt;
            const saved = saveState[clipIndex];

            return (
              <div
                key={clip.clip_number}
                className="rounded-xl bg-[#161616] border border-[#2a2a2a] overflow-hidden"
              >
                {/* Header */}
                <button
                  onClick={() => setExpandedClip(isExpanded ? null : clipIndex)}
                  className="w-full flex items-center justify-between px-4 py-3 hover:bg-[#1a1a1a] transition-colors"
                >
                  <div className="flex items-center gap-3 text-left">
                    <span className="w-6 h-6 rounded bg-[#1a5c3a]/40 text-green-400 text-xs font-bold flex items-center justify-center mono shrink-0">
                      {clip.clip_number}
                    </span>
                    <div>
                      <p className="text-sm font-medium text-white leading-tight">
                        {clip.scene_summary || `Clip ${clip.clip_number}`}
                      </p>
                      <p className="text-xs text-[#4b5563] mono mt-0.5">
                        {clip.duration_seconds}s ·{" "}
                        <span
                          className={
                            clip.word_count < 24
                              ? "text-red-400 font-semibold"
                              : clip.word_count <= 27
                              ? "text-green-400"
                              : "text-amber-400"
                          }
                          title={
                            clip.word_count < 24
                              ? "⚠ Below 24 words — hallucination risk at clip end"
                              : clip.word_count <= 27
                              ? "✓ In anti-hallucination safe zone (24–27)"
                              : "Word count above 27 — may cause chipmunk speech"
                          }
                        >
                          {clip.word_count}w
                        </span>
                        {clip.word_count < 24 && (
                          <span className="text-red-400 ml-1" title="Below 24 words — Veo may hallucinate face at clip end">⚠ hallucination risk</span>
                        )}
                        {clip.verified && <span className="text-green-500 ml-2">✓ verified</span>}
                        {isDirty && <span className="text-amber-400 ml-2">· unsaved changes</span>}
                        {saved === "saved" && <span className="text-green-400 ml-2">· saved</span>}
                        {saved === "error" && <span className="text-red-400 ml-2">· save failed</span>}
                      </p>
                    </div>
                  </div>
                  <span className="text-xs text-[#4b5563] mono shrink-0 ml-2">
                    {isExpanded ? "▲" : "▼"}
                  </span>
                </button>

                {isExpanded && (
                  <div className="border-t border-[#2a2a2a] p-4 flex flex-col gap-4">
                    {/* Dialogue preview */}
                    <div className="p-3 rounded-lg bg-[#0f0f0f] border border-[#1e1e1e]">
                      <p className="text-xs text-[#4b5563] mono mb-1">Dialogue</p>
                      <p className="text-sm text-[#e5e7eb] italic leading-relaxed">
                        &ldquo;{clip.dialogue}&rdquo;
                      </p>
                    </div>

                    {/* End emotion */}
                    {clip.end_emotion && (
                      <div>
                        <p className="text-xs text-[#4b5563] mono mb-1">End emotion (keyframe target)</p>
                        <p className="text-xs text-[#9ca3af]">{clip.end_emotion}</p>
                      </div>
                    )}

                    {/* Verification issues */}
                    {clip.verification_issues && clip.verification_issues.length > 0 && (
                      <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                        <p className="text-xs text-amber-400 font-semibold mb-1">Verification issues (auto-fixed)</p>
                        {clip.verification_issues.map((issue, i) => (
                          <p key={i} className="text-xs text-amber-300/80">• {issue}</p>
                        ))}
                      </div>
                    )}

                    {/* Full Veo prompt editor */}
                    <div>
                      <div className="flex items-center justify-between mb-1.5">
                        <p className="text-xs text-[#4b5563] mono">Full Veo Prompt</p>
                        <div className="flex items-center gap-2">
                          {isDirty && (
                            <button
                              onClick={() => handlePromptChange(clipIndex, clip.prompt)}
                              className="text-xs text-[#4b5563] hover:text-[#9ca3af] transition-colors"
                            >
                              Reset
                            </button>
                          )}
                          <button
                            onClick={() => handleSaveClip(clipIndex)}
                            disabled={!isDirty || saved === "saving"}
                            className={`px-3 py-1 rounded text-xs font-medium transition-all ${
                              !isDirty
                                ? "text-[#3a3a3a] border border-[#2a2a2a] cursor-default"
                                : saved === "saving"
                                ? "text-[#6b7280] border border-[#2a2a2a]"
                                : saved === "saved"
                                ? "text-green-400 border border-green-500/30 bg-green-500/10"
                                : saved === "error"
                                ? "text-red-400 border border-red-500/30 bg-red-500/10"
                                : "text-white border border-[#3a3a3a] bg-[#222] hover:border-violet-500/40 hover:text-violet-300"
                            }`}
                          >
                            {saved === "saving" ? "Saving…" : saved === "saved" ? "✓ Saved" : "Save"}
                          </button>
                        </div>
                      </div>
                      <textarea
                        value={currentPrompt}
                        onChange={(e) => handlePromptChange(clipIndex, e.target.value)}
                        rows={20}
                        className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded-lg p-3 text-xs text-[#9ca3af] mono leading-relaxed resize-y focus:outline-none focus:border-violet-500/40 transition-colors"
                        placeholder="Veo prompt…"
                        spellCheck={false}
                      />
                      <p className="text-[10px] text-[#3a3a3a] mono mt-1">
                        {currentPrompt.length} chars
                      </p>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Bottom approve */}
      {clips.length > 0 && (
        <div className="mt-10 flex items-center justify-between">
          <Link
            href={`/jobs/${id}/progress`}
            className="text-xs text-[#4b5563] hover:text-white transition-colors"
          >
            ← Back to progress
          </Link>
          <button
            onClick={handleApproveAll}
            disabled={submitting}
            className="px-6 py-3 rounded-xl font-semibold text-sm bg-[#1a5c3a] text-white border border-green-500/20 hover:bg-[#22703f] disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-[0_0_24px_rgba(26,92,58,0.4)]"
          >
            {submitting
              ? "Starting image generation…"
              : hasUnsaved
              ? "Save All & Generate Images →"
              : "Approve & Generate Images →"}
          </button>
        </div>
      )}
    </main>
  );
}
