"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

const COACHES = ["Rishika", "Rashmi", "Seema", "Pankaj", "Dev", "Arjun"];
const CLIP_COUNTS = [3, 4, 5, 6, 7, 8];
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
  const [domain, setDomain] = useState("");
  const [transitionType, setTransitionType] = useState("text_card");
  const [transitionText, setTransitionText] = useState("SuperLiving me coach se\nbaat krne ke baad...");
  const [textOverlays, setTextOverlays] = useState<Array<{
    text: string;
    start_time: number;
    duration: number;
    position: string;
  }>>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const estSeconds = numClips * 8;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!script.trim()) { setError("Please paste your script first."); return; }
    setSubmitting(true);
    setError("");
    try {
      const res = await api.createJob({
        script,
        coach,
        num_clips: numClips,
        aspect_ratio: aspectRatio,
        veo_model: veoModel,
        domain: domain || undefined,
        post_production: {
          transitions: transitionType !== "none"
            ? [
                {
                  type: transitionType,
                  insert_after_clip: 3,
                  duration: transitionType === "text_card" ? 1.0 : 0.5,
                  text: transitionType === "text_card" ? transitionText : null,
                },
              ]
            : [],
          text_overlays: textOverlays.filter((o) => o.text.trim()),
          image_overlays: [],
        },
      });
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

        <div className="p-5 rounded-xl bg-[#161616] border border-[#2a2a2a]">
          <label className="block text-xs font-semibold text-[#9ca3af] uppercase tracking-widest mb-2">
            Health Domain
          </label>
          <select
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            className="w-full p-2 border border-[#2a2a2a] rounded bg-[#0f0f0f] text-white"
          >
            <option value="">Auto-detect from script</option>
            <option value="weight">Weight / Body Image</option>
            <option value="skin">Skin / Face</option>
            <option value="stress">Stress / Anxiety / Sleep</option>
            <option value="muscle">Muscle / Fitness / Body Building</option>
            <option value="sexual">Sexual Health / Performance</option>
            <option value="hairloss">Hair Loss / Hair Thinning</option>
            <option value="energy">Energy / Fatigue</option>
            <option value="general">General Health</option>
          </select>

          <div className="mt-4 p-4 border border-[#2a2a2a] rounded">
            <h3 className="font-bold mb-2 text-white">Mid-Ad Transition (between pre/post coach)</h3>
            <select
              value={transitionType}
              onChange={(e) => setTransitionType(e.target.value)}
              className="w-full p-2 border border-[#2a2a2a] rounded bg-[#0f0f0f] text-white"
            >
              <option value="text_card">Text Card (recommended)</option>
              <option value="flash_white">Flash White</option>
              <option value="fade_black">Fade to Black</option>
              <option value="none">No Transition</option>
            </select>

            {transitionType === "text_card" && (
              <textarea
                value={transitionText}
                onChange={(e) => setTransitionText(e.target.value)}
                placeholder="SuperLiving me coach se baat krne ke baad..."
                className="w-full p-2 mt-2 border border-[#2a2a2a] rounded bg-[#0f0f0f] text-white"
                rows={2}
              />
            )}
          </div>

          <details className="mt-4">
            <summary className="cursor-pointer font-bold text-white">Text Overlays (Advanced)</summary>
            <div className="p-4 border-t border-[#2a2a2a]">
              {textOverlays.map((overlay, i) => (
                <div key={i} className="mb-3 p-3 bg-[#0f0f0f] rounded border border-[#2a2a2a]">
                  <input
                    placeholder="Text (Hindi)"
                    value={overlay.text}
                    onChange={(e) => {
                      setTextOverlays((prev) =>
                        prev.map((o, idx) => (idx === i ? { ...o, text: e.target.value } : o))
                      );
                    }}
                    className="w-full p-2 border border-[#2a2a2a] rounded bg-[#111] text-white"
                  />
                  <div className="flex gap-2 mt-1">
                    <input
                      type="number"
                      placeholder="Start (sec)"
                      value={overlay.start_time}
                      onChange={(e) => {
                        setTextOverlays((prev) =>
                          prev.map((o, idx) =>
                            idx === i ? { ...o, start_time: Number(e.target.value) } : o
                          )
                        );
                      }}
                      className="w-full p-2 border border-[#2a2a2a] rounded bg-[#111] text-white"
                    />
                    <input
                      type="number"
                      placeholder="Duration (sec)"
                      value={overlay.duration}
                      onChange={(e) => {
                        setTextOverlays((prev) =>
                          prev.map((o, idx) =>
                            idx === i ? { ...o, duration: Number(e.target.value) } : o
                          )
                        );
                      }}
                      className="w-full p-2 border border-[#2a2a2a] rounded bg-[#111] text-white"
                    />
                    <select
                      value={overlay.position}
                      onChange={(e) => {
                        setTextOverlays((prev) =>
                          prev.map((o, idx) =>
                            idx === i ? { ...o, position: e.target.value } : o
                          )
                        );
                      }}
                      className="w-full p-2 border border-[#2a2a2a] rounded bg-[#111] text-white"
                    >
                      <option value="bottom_center">Bottom Center</option>
                      <option value="top_left">Top Left</option>
                      <option value="top_right">Top Right</option>
                      <option value="center">Center</option>
                    </select>
                  </div>
                  <button
                    type="button"
                    onClick={() => setTextOverlays((prev) => prev.filter((_, idx) => idx !== i))}
                    className="text-red-500 text-sm mt-1"
                  >
                    Remove
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() =>
                  setTextOverlays((prev) => [
                    ...prev,
                    { text: "", start_time: 0, duration: 2, position: "bottom_center" },
                  ])
                }
                className="text-blue-500 text-sm"
              >
                + Add Text Overlay
              </button>
            </div>
          </details>
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
          <span className="text-[#1a5c3a]">|</span>
          <span>Domain: <b>{domain || "auto"}</b></span>
          <span className="text-[#1a5c3a]">|</span>
          <span>Transition: <b>{transitionType}</b></span>
          {textOverlays.some((o) => o.text.trim()) && (
            <>
              <span className="text-[#1a5c3a]">|</span>
              <span>Text overlays: <b>{textOverlays.filter((o) => o.text.trim()).length}</b></span>
            </>
          )}
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
