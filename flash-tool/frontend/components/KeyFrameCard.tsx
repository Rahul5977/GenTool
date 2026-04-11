"use client";

import { useState } from "react";
import Image from "next/image";
import { api } from "@/lib/api";

interface Props {
  jobId: string;
  index: number;
  total: number;
  description: string;
  approved: boolean;
  validationIssues?: string[];
  onToggleApprove: (index: number, val: boolean) => void;
  onRegenerated: (index: number) => void;
}

export default function KeyFrameCard({
  jobId, index, total, description, approved, validationIssues = [], onToggleApprove, onRegenerated,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [imgKey, setImgKey] = useState(0);
  const [showPromptInput, setShowPromptInput] = useState(false);
  const [customPrompt, setCustomPrompt] = useState("");

  const imgUrl = api.keyframeUrl(jobId, index);

  async function handleRegen() {
    setLoading(true);
    setError("");
    try {
      await api.regenImage(jobId, {
        keyframe_index: index,
        custom_prompt: customPrompt.trim() || undefined,
      });
      setImgKey((k) => k + 1);
      setCustomPrompt("");
      setShowPromptInput(false);
      onRegenerated(index);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Regen failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className={`relative flex flex-col rounded-xl overflow-hidden border transition-all duration-200 ${
        validationIssues.length > 0
          ? "border-amber-500/50 shadow-[0_0_16px_rgba(245,158,11,0.08)]"
          : approved
          ? "border-green-500/50 shadow-[0_0_20px_rgba(34,197,94,0.08)]"
          : "border-[#2a2a2a] hover:border-[#3a3a3a]"
      }`}
      style={{ background: "var(--bg-card)" }}
    >
      {/* Image */}
      <div className="relative aspect-9/16 w-full bg-[#111] overflow-hidden">
        {loading ? (
          <div className="absolute inset-0 shimmer" />
        ) : (
          <Image
            key={imgKey}
            src={`${imgUrl}?v=${imgKey}`}
            alt={`Keyframe ${index}`}
            fill
            className="object-cover"
            unoptimized
          />
        )}
        {/* Index badge */}
        <div className="absolute top-2 left-2 px-2 py-0.5 rounded text-xs font-bold mono bg-black/70 text-white border border-white/10">
          #{index}
        </div>
        {/* Role label */}
        <div className="absolute top-2 right-2 px-2 py-0.5 rounded text-xs bg-black/70 text-[#9ca3af] border border-white/10">
          {index === 0 ? "First frame" : `End clip ${index}`}
        </div>
        {/* Validation warning badge */}
        {validationIssues.length > 0 && (
          <div className="absolute bottom-2 left-2 w-6 h-6 rounded-full bg-amber-500 flex items-center justify-center shadow-lg" title={validationIssues.join("\n")}>
            <span className="text-white text-xs font-bold">!</span>
          </div>
        )}
        {/* Approved overlay */}
        {approved && (
          <div className="absolute bottom-2 right-2 w-6 h-6 rounded-full bg-green-500 flex items-center justify-center shadow-lg">
            <span className="text-white text-xs font-bold">✓</span>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 flex flex-col gap-2">
        <p className="text-xs text-[#9ca3af] mono leading-relaxed line-clamp-2" title={description}>
          {description || "—"}
        </p>

        {/* Validation issues */}
        {validationIssues.length > 0 && (
          <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
            <p className="text-[10px] text-amber-400 font-semibold mb-1">Quality warnings</p>
            {validationIssues.map((issue, i) => (
              <p key={i} className="text-[10px] text-amber-300/80 leading-snug">• {issue}</p>
            ))}
          </div>
        )}

        {error && <p className="text-xs text-red-400">{error}</p>}

        {/* Approve checkbox + regen button */}
        <div className="flex items-center gap-2 mt-1">
          <label className="flex items-center gap-2 cursor-pointer flex-1">
            <input
              type="checkbox"
              checked={approved}
              onChange={(e) => onToggleApprove(index, e.target.checked)}
              className="w-4 h-4 rounded accent-green-500 cursor-pointer"
            />
            <span className="text-xs text-[#9ca3af]">Approve</span>
          </label>
          <button
            onClick={() => setShowPromptInput((s) => !s)}
            disabled={loading}
            className="px-2 py-1.5 rounded text-xs text-[#6b7280] border border-[#2a2a2a] hover:border-[#3a3a3a] hover:text-[#9ca3af] disabled:opacity-40 transition-all"
            title="Add custom instructions for regen"
          >
            +
          </button>
          <button
            onClick={handleRegen}
            disabled={loading}
            className="px-3 py-1.5 rounded text-xs font-medium bg-[#1e1e1e] text-[#9ca3af] border border-[#2a2a2a] hover:border-[#3a3a3a] hover:text-white disabled:opacity-40 transition-all"
          >
            {loading ? (
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full border border-current border-t-transparent animate-spin" />
                Regen…
              </span>
            ) : (
              "↺ Regen"
            )}
          </button>
        </div>

        {/* Custom prompt input (collapsible) */}
        {showPromptInput && (
          <div className="mt-1">
            <textarea
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              placeholder="Optional: describe what to fix (e.g. 'make the smile warmer', 'fix eye shadow')"
              rows={2}
              className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded-lg p-2 text-xs text-[#9ca3af] mono leading-relaxed resize-none focus:outline-none focus:border-violet-500/40 transition-colors placeholder:text-[#3a3a3a]"
            />
          </div>
        )}
      </div>
    </div>
  );
}
