"use client";

import { useRef, useState } from "react";

interface Props {
  src: string;
  aspectRatio?: "9:16" | "16:9";
  autoPlay?: boolean;
}

export default function VideoPlayer({ src, aspectRatio = "9:16", autoPlay = true }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(autoPlay);

  const is916 = aspectRatio === "9:16";

  return (
    <div
      className={`relative rounded-2xl overflow-hidden border border-[#2a2a2a] shadow-2xl bg-black mx-auto ${
        is916 ? "max-w-[360px] w-full" : "max-w-[640px] w-full"
      }`}
      style={{ aspectRatio: is916 ? "9/16" : "16/9" }}
    >
      <video
        ref={videoRef}
        src={src}
        autoPlay={autoPlay}
        controls
        loop
        playsInline
        className="absolute inset-0 w-full h-full object-contain"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
      />
      {/* Subtle green border glow when playing */}
      {playing && (
        <div className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-green-500/20" />
      )}
    </div>
  );
}
