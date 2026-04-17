"""FFmpeg operations for the flash-tool stitching pipeline.

All functions use subprocess FFmpeg only — no moviepy, no ffmpeg-python wrapper.
Each function returns True on success and False on failure (stderr is logged).
"""

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

# Resolutions keyed by aspect_ratio string
_RESOLUTIONS: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError("ffmpeg not found on PATH — please install ffmpeg")
    return path


def _run(cmd: list[str], *, capture_stderr: bool = False) -> subprocess.CompletedProcess:
    """Run an ffmpeg command, logging the full invocation on failure."""
    logger.debug("ffmpeg: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        logger.error("ffmpeg failed (rc=%d):\n  cmd: %s\n  stderr: %s",
                     result.returncode, " ".join(cmd), result.stderr[-2000:])
    return result


# ---------------------------------------------------------------------------
# normalize_clip
# ---------------------------------------------------------------------------

def normalize_clip(
    input_path: str,
    output_path: str,
    aspect_ratio: str = "9:16",
    trim_to_seconds: Optional[float] = 7.7,
    add_audio_fade: bool = True,
) -> bool:
    """Scale, pad, re-encode a clip to a consistent baseline.

    • Scales to target resolution preserving aspect ratio, pads with black.
    • Forces 24 fps, yuv420p pixel format.
    • H.264 CRF 18, AAC 192 kbps stereo 44.1 kHz.
    • Optional SURGICAL TRIM: clip can be capped to remove Veo tail artifacts.
    • Optional AUDIO FADE: 0.2s exponential fade-out on trimmed end.
    """
    if aspect_ratio not in _RESOLUTIONS:
        logger.error("normalize_clip: unsupported aspect_ratio %r", aspect_ratio)
        return False

    W, H = _RESOLUTIONS[aspect_ratio]

    # Probe original duration
    original_duration = probe_duration(input_path)
    if original_duration <= 0:
        logger.error("normalize_clip: could not probe duration for %s", input_path)
        return False

    # Optional surgical trim for Veo clips; CTA or other assets can disable this.
    if trim_to_seconds is None:
        target_duration = original_duration
    else:
        target_duration = min(original_duration, trim_to_seconds)

    # Audio fade-out starts shortly before the trimmed end to avoid tiny
    # boundary tails ("ghost" audio) when clips are hard-concatenated.
    fade_duration = 0.12
    fade_start = max(0.0, target_duration - fade_duration)

    logger.info(
        "normalize_clip: %s  %.2fs → %.2fs (trimmed %.2fs hallucination tail)",
        os.path.basename(input_path),
        original_duration,
        target_duration,
        original_duration - target_duration,
    )

    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,"
        f"fps=24,"
        f"format=yuv420p"
    )

    af_parts = ["highpass=f=80", "afftdn=nf=-25"]
    should_apply_fade_out = (
        add_audio_fade
        and target_duration > fade_duration
        and (trim_to_seconds is not None or target_duration < original_duration)
    )
    if should_apply_fade_out:
        af_parts.append(f"afade=t=out:st={fade_start}:d={fade_duration}")

    cmd = [
        _ffmpeg(), "-y", "-i", input_path,
        "-t", str(target_duration),  # SURGICAL TRIM: hard-stop at 7.7s
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        "-video_track_timescale", "12800",
        # Noise reduction + optional short fade-out for cleaner cut boundaries.
        # loudnorm is applied separately in phase5_stitcher.py — do not add here.
        "-af", ",".join(af_parts),
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
        "-shortest",
        output_path,
    ]
    result = _run(cmd)
    return result.returncode == 0


# ---------------------------------------------------------------------------
# concat_clips
# ---------------------------------------------------------------------------

def concat_clips(clip_paths: list[str], output_path: str) -> bool:
    """Concatenate clips using filter_complex concat (hard cuts, no xfade).

    All clips must already be normalized to the same resolution and codec.
    """
    if not clip_paths:
        logger.error("concat_clips: no input clips provided")
        return False

    n = len(clip_paths)

    # Build -i flags
    inputs: list[str] = []
    for path in clip_paths:
        inputs += ["-i", path]

    # Build filter_complex
    stream_labels = "".join(f"[{i}:v][{i}:a]" for i in range(n))
    filter_complex = f"{stream_labels}concat=n={n}:v=1:a=1[vout][aout]"

    cmd = [
        _ffmpeg(), "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        "-video_track_timescale", "12800",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
        output_path,
    ]
    result = _run(cmd)
    return result.returncode == 0


# ---------------------------------------------------------------------------
# trim_trailing_dark
# ---------------------------------------------------------------------------

def trim_trailing_dark(
    input_path: str,
    output_path: str,
    threshold: int = 20,
) -> bool:
    """Trim a trailing dark/black section from the end of a clip.

    Uses ffmpeg blackdetect to find the last black segment.
    If no black section is found, copies the file unchanged.
    """
    # Step 1 — detect black sections
    detect_cmd = [
        _ffmpeg(), "-i", input_path,
        "-vf", f"blackdetect=d=0.3:pix_th=0.08",
        "-an", "-f", "null", "-",
    ]
    result = subprocess.run(
        detect_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stderr = result.stderr

    # Parse all black_start timestamps
    black_starts = [
        float(m.group(1))
        for m in re.finditer(r"black_start:([\d.]+)", stderr)
    ]

    if not black_starts:
        logger.info("trim_trailing_dark: no black sections found — copying unchanged")
        return _copy_file(input_path, output_path)

    total_duration = probe_duration(input_path)
    last_black_start = max(black_starts)

    # Safety: only trim if the dark section is within the last 3 seconds.
    # A black section earlier than that is a mid-video dark scene (e.g. a Veo
    # dark handoff between clips) — trimming there would discard the rest of
    # the ad. Since normalize_clip() already strips each clip's dark tail at
    # 7.7s, mid-video black detections are always false positives here.
    if total_duration > 0 and last_black_start < total_duration - 3.0:
        logger.info(
            "trim_trailing_dark: last black at %.2fs is %.2fs before end "
            "(total=%.2fs) — skipping, likely a mid-video false positive",
            last_black_start,
            total_duration - last_black_start,
            total_duration,
        )
        return _copy_file(input_path, output_path)

    trim_end = max(last_black_start - 0.1, 0.0)

    logger.info("trim_trailing_dark: trimming to %.3fs (last black at %.3fs)",
                trim_end, last_black_start)

    cmd = [
        _ffmpeg(), "-y", "-i", input_path,
        "-t", str(trim_end),
        "-c", "copy",
        output_path,
    ]
    result = _run(cmd)
    return result.returncode == 0


# ---------------------------------------------------------------------------
# trim_leading_black
# ---------------------------------------------------------------------------

def trim_leading_black(input_path: str, output_path: str) -> bool:
    """Trim leading black frames from the start of a clip (used for CTA).

    Uses blackdetect to find the end of the first black section, then
    re-encodes from that timestamp forward.

    Safety: if trimming would remove >50% of the video, skip trimming
    to prevent accidentally hollowing out the CTA.
    """
    original_duration = probe_duration(input_path)

    detect_cmd = [
        _ffmpeg(), "-i", input_path,
        "-vf", "blackdetect=d=0.1:pix_th=0.08",
        "-an", "-f", "null", "-",
    ]
    result = subprocess.run(
        detect_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stderr = result.stderr

    black_ends = [
        float(m.group(1))
        for m in re.finditer(r"black_end:([\d.]+)", stderr)
    ]

    if not black_ends:
        logger.info("trim_leading_black: no leading black found — copying unchanged")
        return _copy_file(input_path, output_path)

    first_black_end = black_ends[0]

    # Safety: refuse to trim more than 50% of the video
    if original_duration > 0 and first_black_end > original_duration * 0.5:
        logger.warning(
            "trim_leading_black: would trim %.2fs from %.2fs video (>50%%) — skipping",
            first_black_end, original_duration,
        )
        return _copy_file(input_path, output_path)

    logger.info("trim_leading_black: seeking to %.3fs (original=%.2fs)", first_black_end, original_duration)

    cmd = [
        _ffmpeg(), "-y",
        "-ss", str(first_black_end),
        "-i", input_path,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-video_track_timescale", "12800",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
        output_path,
    ]
    result = _run(cmd)

    # Verify output has reasonable duration
    if result.returncode == 0:
        trimmed_duration = probe_duration(output_path)
        if trimmed_duration < 0.5:
            logger.error(
                "trim_leading_black: output too short (%.2fs) — falling back to original",
                trimmed_duration,
            )
            return _copy_file(input_path, output_path)

    return result.returncode == 0


# ---------------------------------------------------------------------------
# loudnorm (two-pass)
# ---------------------------------------------------------------------------

def loudnorm(
    input_path: str,
    output_path: str,
    target: float = -16.0,
    tp: float = -1.5,
) -> bool:
    """Apply EBU R128 loudness normalization using ffmpeg's two-pass loudnorm.

    Pass 1 measures the current loudness characteristics.
    Pass 2 applies the corrective filter with those measurements.
    """
    lra = 11.0

    # ── Pass 1 — measure ───────────────────────────────────────────────────
    pass1_filter = f"loudnorm=I={target}:TP={tp}:LRA={lra}:print_format=json"
    pass1_cmd = [
        _ffmpeg(), "-i", input_path,
        "-af", pass1_filter,
        "-f", "null", "-",
    ]
    p1 = subprocess.run(
        pass1_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    measurements = _parse_loudnorm_json(p1.stderr)
    if measurements is None:
        logger.error("loudnorm pass 1: failed to parse measurements from stderr")
        return False

    logger.debug("loudnorm measurements: %s", measurements)

    # ── Pass 2 — apply ─────────────────────────────────────────────────────
    pass2_filter = (
        f"loudnorm=I={target}:TP={tp}:LRA={lra}"
        f":measured_I={measurements['input_i']}"
        f":measured_TP={measurements['input_tp']}"
        f":measured_LRA={measurements['input_lra']}"
        f":measured_thresh={measurements['input_thresh']}"
        f":offset={measurements['target_offset']}"
        f":linear=true:print_format=summary"
    )
    pass2_cmd = [
        _ffmpeg(), "-y", "-i", input_path,
        "-af", pass2_filter,
        "-c:v", "copy",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
        output_path,
    ]
    result = _run(pass2_cmd)
    return result.returncode == 0


def _parse_loudnorm_json(stderr: str) -> Optional[dict]:
    """Extract the JSON block from loudnorm pass-1 stderr output."""
    match = re.search(r"\{[^{}]+\}", stderr, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError as exc:
        logger.error("loudnorm: JSON parse error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# generate_black_pause
# ---------------------------------------------------------------------------

def generate_black_pause(output_path: str, duration: float = 0.3) -> bool:
    """Generate a short black video+silent audio clip for use as a pause buffer."""
    cmd = [
        _ffmpeg(), "-y",
        "-f", "lavfi", "-i", f"color=black:size=1080x1920:rate=24:duration={duration}",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",
        "-t", str(duration),
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
        "-video_track_timescale", "12800",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
        output_path,
    ]
    result = _run(cmd)
    return result.returncode == 0


# ---------------------------------------------------------------------------
# probe_duration
# ---------------------------------------------------------------------------

def probe_duration(path: str) -> float:
    """Return the duration of a media file in seconds using ffmpeg -i."""
    cmd = [_ffmpeg(), "-i", path]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # Duration appears in stderr even for ffmpeg -i with no output
    match = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", result.stderr)
    if not match:
        logger.warning("probe_duration: could not parse duration from %s", path)
        return 0.0
    h, m, s = int(match.group(1)), int(match.group(2)), float(match.group(3))
    return h * 3600 + m * 60 + s


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _copy_file(src: str, dst: str) -> bool:
    """Byte-copy a file. Returns True on success."""
    try:
        import shutil as _shutil
        _shutil.copy2(src, dst)
        return True
    except OSError as exc:
        logger.error("_copy_file: %s → %s failed: %s", src, dst, exc)
        return False
