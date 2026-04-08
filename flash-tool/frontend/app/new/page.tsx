"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

const COACHES = ["Rishika", "Rashmi", "Seema", "Pankaj", "Dev", "Arjun"];
const CLIP_COUNTS = [3, 4, 5, 6];
const VEO_MODELS = [
  { id: "veo-3.1-generate-preview", label: "Veo 3.1 Preview" },
  { id: "veo-3.0-generate-preview", label: "Veo 3.0 Preview" },
];

export default function NewJobPage() {
  const router = useRouter();
  const [script, setScript] = useState("");
  const [coach, setCoach] = useState("Rishika");
  const [numClips, setNumClips] = useState(4);
  const [aspectRatio, setAspectRatio] = useState("9:16");
  const [veoModel, setVeoModel] = useState("veo-3.1-generate-preview");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const estSeconds = numClips * 8;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!script.trim()) { setError("Please paste your script first."); return; }
    setSubmitting(true);
    setError("");
    try {
      const res = await api.createJob({ script, coach, num_clips: numClips, aspect_ratio: aspectRatio, veo_model: veoModel });
      router.push(`/jobs/${res.job_id}/progress`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create job");
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen px-6 py-10 max-w-3xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-[#4b5563] mb-8">
        <Link href="/" className="hover:text-white transition-colors">Flash Tool</Link>
        <span>/</span>
        <span className="text-white">New Ad</span>
      </div>

      <h2 className="text-xl font-bold text-white mb-1">Generate a New Ad</h2>
      <p className="text-[#6b7280] text-sm mb-8">Paste your Hindi/Hinglish script and configure the shoot.</p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        {/* Script textarea */}
        <div>
          <label className="block text-xs font-semibold text-[#9ca3af] uppercase tracking-widest mb-2">
            Script
          </label>
          <textarea
            value={script}
            onChange={(e) => setScript(e.target.value)}
            placeholder="यहाँ अपना Hindi/Hinglish script paste करें…"
            className="w-full min-h-[320px] p-4 rounded-xl bg-[#161616] border border-[#2a2a2a] text-white placeholder-[#4b5563] text-sm leading-relaxed resize-y mono focus:border-green-500/50 focus:bg-[#181818] transition-all outline-none"
          />
          <div className="flex justify-between mt-1.5">
            <span className="text-xs text-[#4b5563]">Devanagari or Hinglish both work</span>
            <span className="text-xs mono text-[#4b5563]">{script.split(/\s+/).filter(Boolean).length} words</span>
          </div>
        </div>

        {/* Config row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 p-5 rounded-xl bg-[#161616] border border-[#2a2a2a]">
          {/* Coach */}
          <div>
            <label className="block text-xs font-semibold text-[#9ca3af] uppercase tracking-widest mb-2">
              Coach
            </label>
            <div className="grid grid-cols-3 gap-2">
              {COACHES.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCoach(c)}
                  className={`py-2 px-2 rounded-lg text-xs font-medium border transition-all ${
                    coach === c
                      ? "bg-[#1a5c3a]/40 border-green-500/50 text-green-300"
                      : "bg-[#1a1a1a] border-[#2a2a2a] text-[#9ca3af] hover:border-[#3a3a3a] hover:text-white"
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>

          {/* Num clips */}
          <div>
            <label className="block text-xs font-semibold text-[#9ca3af] uppercase tracking-widest mb-2">
              Clips
            </label>
            <div className="flex gap-2">
              {CLIP_COUNTS.map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setNumClips(n)}
                  className={`flex-1 py-2 rounded-lg text-xs font-bold border transition-all mono ${
                    numClips === n
                      ? "bg-[#1a5c3a]/40 border-green-500/50 text-green-300"
                      : "bg-[#1a1a1a] border-[#2a2a2a] text-[#9ca3af] hover:border-[#3a3a3a]"
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
            <p className="text-xs text-[#4b5563] mono mt-2">
              {numClips} clips × ~8s ≈ <span className="text-green-400">{estSeconds}s</span>
            </p>
          </div>

          {/* Aspect ratio */}
          <div>
            <label className="block text-xs font-semibold text-[#9ca3af] uppercase tracking-widest mb-2">
              Format
            </label>
            <div className="flex gap-2">
              {[
                { value: "9:16", label: "9:16 Reels" },
                { value: "16:9", label: "16:9 YouTube" },
              ].map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setAspectRatio(opt.value)}
                  className={`flex-1 py-2 px-3 rounded-lg text-xs font-medium border transition-all ${
                    aspectRatio === opt.value
                      ? "bg-[#1a5c3a]/40 border-green-500/50 text-green-300"
                      : "bg-[#1a1a1a] border-[#2a2a2a] text-[#9ca3af] hover:border-[#3a3a3a] hover:text-white"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Veo model */}
          <div>
            <label className="block text-xs font-semibold text-[#9ca3af] uppercase tracking-widest mb-2">
              Veo Model
            </label>
            <div className="flex flex-col gap-2">
              {VEO_MODELS.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setVeoModel(m.id)}
                  className={`py-2 px-3 rounded-lg text-xs font-medium border transition-all text-left ${
                    veoModel === m.id
                      ? "bg-[#1a5c3a]/40 border-green-500/50 text-green-300"
                      : "bg-[#1a1a1a] border-[#2a2a2a] text-[#9ca3af] hover:border-[#3a3a3a] hover:text-white"
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Summary strip */}
        <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-[#0d1a12] border border-[#1a5c3a]/40 text-xs text-green-300 mono flex-wrap">
          <span>Coach: <b>{coach}</b></span>
          <span className="text-[#1a5c3a]">|</span>
          <span>Clips: <b>{numClips}</b></span>
          <span className="text-[#1a5c3a]">|</span>
          <span>Format: <b>{aspectRatio}</b></span>
          <span className="text-[#1a5c3a]">|</span>
          <span>Model: <b>{veoModel.split("-").slice(0, 2).join(" ")}</b></span>
        </div>

        {error && (
          <div className="px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={submitting || !script.trim()}
          className="w-full py-3.5 rounded-xl font-semibold text-sm transition-all bg-[#1a5c3a] text-white hover:bg-[#22703f] border border-green-500/20 disabled:opacity-40 disabled:cursor-not-allowed shadow-[0_0_24px_rgba(26,92,58,0.4)] hover:shadow-[0_0_32px_rgba(26,92,58,0.5)]"
        >
          {submitting ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white spin" />
              Starting pipeline…
            </span>
          ) : (
            "Generate Ad →"
          )}
        </button>
      </form>
    </main>
  );
}
