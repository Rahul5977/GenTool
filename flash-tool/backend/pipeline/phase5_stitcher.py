"""Phase 5 — Stitch & Finalize.

Assembles normalized clips, applies loudnorm, appends a trimmed CTA,
and produces the final output video.
"""

import logging
import os

from .. import config
from ..video.ffmpeg_ops import (
    concat_clips,
    generate_black_pause,
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

    # ── Step 4: Loudnorm the ad ────────────────────────────────────────────
    logger.info("Phase 5 step 4: loudnorm on ad")
    ad_normalized = _tmp("ad_normalized.mp4")
    _require(
        loudnorm(trimmed, ad_normalized, target=config.LOUDNORM_TARGET),
        "loudnorm failed on trimmed ad",
    )

    # ── Step 5: Trim CTA leading black ────────────────────────────────────
    logger.info("Phase 5 step 5: trimming CTA leading black")
    cta_clean = _tmp("cta_clean.mp4")
    _require(
        trim_leading_black(cta_path, cta_clean),
        f"trim_leading_black failed on CTA: {cta_path}",
    )

    # ── Step 6: Loudnorm the CTA ──────────────────────────────────────────
    logger.info("Phase 5 step 6: loudnorm on CTA")
    cta_normalized = _tmp("cta_normalized.mp4")
    _require(
        loudnorm(cta_clean, cta_normalized, target=config.LOUDNORM_TARGET),
        "loudnorm failed on CTA",
    )

    # ── Step 7: Generate 0.3 s black pause buffer ─────────────────────────
    logger.info("Phase 5 step 7: generating black pause")
    pause = _tmp("pause.mp4")
    _require(
        generate_black_pause(pause, duration=0.3),
        "generate_black_pause failed",
    )

    # ── Step 8: Final concatenation: ad + pause + CTA ─────────────────────
    logger.info("Phase 5 step 8: final concat (ad + pause + CTA)")
    _require(
        concat_clips([ad_normalized, pause, cta_normalized], output_path),
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
