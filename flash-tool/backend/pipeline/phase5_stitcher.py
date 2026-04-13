"""Phase 5 — Stitch & Finalize.

Assembles normalized clips, applies loudnorm, appends a trimmed CTA,
and produces the final output video.
"""

import logging
import os
import subprocess

from .. import config
from ..video.ffmpeg_ops import (
    _ffmpeg,
    _run,
    concat_clips,
    loudnorm,
    normalize_clip,
    probe_duration,
    trim_leading_black,
    trim_trailing_dark,
)

logger = logging.getLogger(__name__)


def stitch_and_finalize(
    clip_paths: list[str],
    cta_path: str,
    output_path: str,
    aspect_ratio: str = "9:16",
) -> str:
    """Assemble per-clip MP4s into a single finalized video with CTA appended.

    Processing order:
      1. normalize_clip()      — each raw Veo clip
      2. concat_clips()        — hard-cut concatenation of normalized clips
      3. trim_trailing_dark()  — remove dark tail from stitched ad
      4. loudnorm()            — EBU R128 normalize the ad
      5. trim_leading_black()  — clean CTA head
      6. loudnorm()            — EBU R128 normalize the CTA
      7. generate_black_pause()— 0.3 s silent black buffer
      8. concat_clips()        — final: ad + pause + CTA

    Args:
        clip_paths:   Ordered list of raw MP4 clip paths from Phase 4.
        cta_path:     Path to the CTA video asset.
        output_path:  Desired path for the finished video.
        aspect_ratio: "9:16" (default) or "16:9".

    Returns:
        output_path on success.

    Raises:
        RuntimeError: If any ffmpeg step fails.
    """
    work_dir = os.path.dirname(output_path)
    os.makedirs(work_dir, exist_ok=True)

    def _tmp(name: str) -> str:
        return os.path.join(work_dir, name)

    # ── CTA pre-flight validation ──────────────────────────────────────────
    if not os.path.exists(cta_path):
        raise RuntimeError(f"Phase 5: CTA file does not exist: {cta_path}")

    cta_original_duration = probe_duration(cta_path)
    if cta_original_duration <= 0:
        raise RuntimeError(f"Phase 5: CTA file has invalid duration ({cta_original_duration}s): {cta_path}")

    # Check whether CTA has an audio stream
    probe_audio = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_type",
            "-of", "default=noprint_wrappers=1:nokey=1",
            cta_path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    cta_has_audio = probe_audio.stdout.strip() == "audio"

    if not cta_has_audio:
        logger.warning(
            "Phase 5: CTA has no audio stream — adding silent audio track to prevent playback pause"
        )
        cta_with_audio = _tmp("cta_audio_fixed.mp4")
        silent_cmd = [
            _ffmpeg(), "-y",
            "-i", cta_path,
            "-f", "lavfi", "-i",
            f"anullsrc=r=44100:cl=stereo:d={cta_original_duration}",
            "-c:v", "copy",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
            "-shortest",
            cta_with_audio,
        ]
        _require(_run(silent_cmd).returncode == 0, "Failed to add silent audio to CTA")
        cta_path = cta_with_audio
        logger.info("Phase 5: CTA silent audio added → %s", cta_with_audio)
    else:
        logger.info("Phase 5: CTA validated (duration=%.2fs, has audio)", cta_original_duration)

    # ── Step 1: Normalize each clip ────────────────────────────────────────
    logger.info("Phase 5 step 1: normalizing %d clips", len(clip_paths))
    normalized_paths: list[str] = []
    for i, path in enumerate(clip_paths):
        out = _tmp(f"norm_{i:02d}.mp4")
        _require(
            normalize_clip(path, out, aspect_ratio=aspect_ratio),
            f"normalize_clip failed for clip {i}: {path}",
        )
        normalized_paths.append(out)

    # ── Step 2: Concatenate normalized clips ───────────────────────────────
    logger.info("Phase 5 step 2: concatenating clips")
    stitched = _tmp("stitched.mp4")
    _require(
        concat_clips(normalized_paths, stitched),
        "concat_clips failed on normalized clips",
    )
    logger.info("Phase 5: stitched duration=%.2fs", probe_duration(stitched))

    # ── Step 3: Trim trailing dark frames ─────────────────────────────────
    logger.info("Phase 5 step 3: trimming trailing dark")
    trimmed = _tmp("trimmed.mp4")
    _require(
        trim_trailing_dark(stitched, trimmed),
        "trim_trailing_dark failed on stitched clip",
    )
    logger.info("Phase 5: trimmed ad duration=%.2fs", probe_duration(trimmed))

    # ── Step 4: Loudnorm the ad ────────────────────────────────────────────
    logger.info("Phase 5 step 4: loudnorm on ad")
    ad_normalized = _tmp("ad_normalized.mp4")
    _require(
        loudnorm(trimmed, ad_normalized, target=config.LOUDNORM_TARGET),
        "loudnorm failed on trimmed ad",
    )
    logger.info("Phase 5: loudnorm ad duration=%.2fs", probe_duration(ad_normalized))

    # ── Step 5: Trim CTA leading black ────────────────────────────────────
    logger.info("Phase 5 step 5: trimming CTA leading black")
    cta_clean = _tmp("cta_clean.mp4")
    _require(
        trim_leading_black(cta_path, cta_clean),
        f"trim_leading_black failed on CTA: {cta_path}",
    )
    cta_clean_duration = probe_duration(cta_clean)
    logger.info("Phase 5: cta_clean duration=%.2fs", cta_clean_duration)
    if cta_clean_duration < 0.5:
        raise RuntimeError(
            f"Phase 5: CTA after leading-black trim is too short ({cta_clean_duration:.2f}s). "
            f"trim_leading_black may have removed too much content."
        )

    # ── Step 6: Loudnorm the CTA ──────────────────────────────────────────
    logger.info("Phase 5 step 6: loudnorm on CTA")
    cta_normalized = _tmp("cta_normalized.mp4")
    _require(
        loudnorm(cta_clean, cta_normalized, target=config.LOUDNORM_TARGET),
        "loudnorm failed on CTA",
    )
    cta_norm_duration = probe_duration(cta_normalized)
    logger.info("Phase 5: cta_normalized duration=%.2fs", cta_norm_duration)
    if cta_norm_duration < 0.5:
        raise RuntimeError(
            f"Phase 5: CTA after loudnorm is too short ({cta_norm_duration:.2f}s). "
            f"Audio normalization may have corrupted the file."
        )

    # ── Step 7: Normalize CTA to ad baseline (fps/colorspace/timescale) ──────
    logger.info("Phase 5 step 7: normalizing CTA to baseline")
    cta_baselined = _tmp("cta_baselined.mp4")
    _require(
        normalize_clip(
            cta_normalized,
            cta_baselined,
            aspect_ratio=aspect_ratio,
            trim_to_seconds=None,
            add_audio_fade=False,
        ),
        "normalize_clip failed on CTA baseline pass",
    )
    logger.info("Phase 5: cta_baselined duration=%.2fs", probe_duration(cta_baselined))

    # ── Step 8: Apply fade-in to CTA to hide baked-in transition effects ────
    # CTA videos often contain a light-wipe or lens-flare transition baked in
    # after the leading black frames. trim_leading_black() removes the black but
    # leaves the bright flash. A 0.5s fade-in from black covers this artifact.
    # We also skip the 0.3s black pause that previously caused the video to
    # appear frozen/buffering at the ad→CTA boundary.
    logger.info("Phase 5 step 8: applying 0.5s fade-in to CTA")
    cta_faded = _tmp("cta_faded.mp4")
    fade_cmd = [
        _ffmpeg(), "-y", "-i", cta_baselined,
        "-vf", "fps=24,format=yuv420p,fade=t=in:st=0:d=0.5",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        "-video_track_timescale", "12800",
        "-c:a", "copy",
        cta_faded,
    ]
    _require(_run(fade_cmd).returncode == 0, "CTA fade-in failed")
    logger.info("Phase 5: cta_faded duration=%.2fs", probe_duration(cta_faded))

    # ── Step 9: Final concatenation: ad + CTA (no black pause buffer) ────────
    # The black pause was removed — it caused 0.3s of solid black that looked
    # like the video had frozen/buffered. The fade-in on the CTA provides a
    # smooth transition without a visible pause.
    logger.info("Phase 5 step 9: final concat (ad + CTA)")
    _require(
        concat_clips([ad_normalized, cta_faded], output_path),
        "final concat_clips failed",
    )

    final_duration = probe_duration(output_path)
    logger.info(
        "Phase 5 complete — final video: %s (%.2fs)", output_path, final_duration
    )
    return output_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require(success: bool, message: str) -> None:
    """Raise RuntimeError if an ffmpeg step returned False."""
    if not success:
        raise RuntimeError(f"Phase 5 ffmpeg step failed: {message}")
