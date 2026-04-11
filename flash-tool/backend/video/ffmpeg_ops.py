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
) -> bool:
    """Scale, pad, re-encode a clip to a consistent baseline.

    • Scales to target resolution preserving aspect ratio, pads with black.
    • Forces 24 fps, yuv420p pixel format.
    • H.264 CRF 18, AAC 192 kbps stereo 44.1 kHz.
    • CRITICAL: Applies 0.2s exponential audio fade-out to prevent ghost pops.
    """
    if aspect_ratio not in _RESOLUTIONS:
        logger.error("normalize_clip: unsupported aspect_ratio %r", aspect_ratio)
        return False

    W, H = _RESOLUTIONS[aspect_ratio]

    # Get clip duration to calculate fade-out start time
    duration = probe_duration(input_path)
    if duration <= 0:
        logger.error("normalize_clip: could not probe duration for %s", input_path)
        return False

    # Fade-out starts 0.2 seconds before clip end
    fade_start = max(0, duration - 0.2)

    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,"
        f"fps=24,"
        f"format=yuv420p"
    )

    # Audio filter chain with exponential fade-out:
    # 1. aresample=async=1 — sync audio to video
    # 2. afade=t=out:st={fade_start}:d=0.2:curve=exp — exponential fade-out last 0.2s
    # 3. apad — pad audio if needed
    af = f"aresample=async=1,afade=t=out:st={fade_start}:d=0.2:curve=exp,apad"

    cmd = [
        _ffmpeg(), "-y", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-video_track_timescale", "12800",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
        "-af", af,  # CRITICAL FIX: exponential audio fade-out prevents ghost pops
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

    last_black_start = max(black_starts)
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
    """
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
    logger.info("trim_leading_black: seeking to %.3fs", first_black_end)

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
