"""Post-production overlay and transition operations.

All functions use subprocess FFmpeg — no moviepy, no ffmpeg-python wrapper.
Reuses helpers from ffmpeg_ops.py.

Font requirement: Noto Sans Devanagari must be installed for Hindi text.
  apt-get install fonts-noto  OR
  download NotoSansDevanagari-Regular.ttf to /usr/share/fonts/
"""

import logging
import os
import shutil
import subprocess
from typing import Optional

from .ffmpeg_ops import _ffmpeg, _run, probe_duration

logger = logging.getLogger(__name__)

_FONT_SEARCH_PATHS = [
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/NotoSansDevanagari-Regular.ttf",
    "/usr/local/share/fonts/NotoSansDevanagari-Regular.ttf",
    os.path.join(os.path.dirname(__file__), "..", "assets", "NotoSansDevanagari-Regular.ttf"),
]


def _find_devanagari_font() -> str:
    """Find the Noto Sans Devanagari font file path."""
    for path in _FONT_SEARCH_PATHS:
        if os.path.exists(path):
            return path
    try:
        result = subprocess.run(
            ["fc-match", "--format=%{file}", "NotoSansDevanagari"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except FileNotFoundError:
        pass

    logger.warning("Noto Sans Devanagari font not found — Hindi text may not render correctly")
    return "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


_TEXT_POSITIONS = {
    "bottom_center": "x=(w-text_w)/2:y=h-th-100",
    "top_left": "x=30:y=30",
    "top_right": "x=w-text_w-30:y=30",
    "bottom_left": "x=30:y=h-th-100",
    "center": "x=(w-text_w)/2:y=(h-text_h)/2",
    "top_center": "x=(w-text_w)/2:y=60",
}

_IMAGE_POSITIONS = {
    "top_right": "W-w-30:30",
    "top_left": "30:30",
    "bottom_right": "W-w-30:H-h-30",
    "bottom_left": "30:H-h-30",
    "center": "(W-w)/2:(H-h)/2",
}


def apply_text_overlay(
    input_path: str,
    output_path: str,
    text: str,
    start_time: float,
    duration: float,
    position: str = "bottom_center",
    font_size: int = 36,
    font_color: str = "white",
    bg_color: str = "black@0.6",
    animation: str = "fade",
) -> bool:
    """Burn a text overlay onto a video at a specific time range."""
    font_path = _find_devanagari_font()
    pos = _TEXT_POSITIONS.get(position, _TEXT_POSITIONS["bottom_center"])
    end_time = start_time + duration
    escaped_text = text.replace("'", "'\\''").replace(":", "\\:")
    enable = f"between(t\\,{start_time}\\,{end_time})"

    drawtext = (
        f"drawtext=text='{escaped_text}':"
        f"fontfile='{font_path}':"
        f"fontsize={font_size}:"
        f"fontcolor={font_color}:"
        f"box=1:boxcolor={bg_color}:boxborderw=15:"
        f"{pos}:"
        f"enable='{enable}'"
    )

    if animation == "fade":
        fade_duration = min(0.3, duration / 4)
        alpha_expr = (
            f"if(lt(t\\,{start_time + fade_duration})\\,"
            f"(t-{start_time})/{fade_duration}\\,"
            f"if(gt(t\\,{end_time - fade_duration})\\,"
            f"({end_time}-t)/{fade_duration}\\,1))"
        )
        drawtext += f":alpha='{alpha_expr}'"

    cmd = [
        _ffmpeg(), "-y", "-i", input_path,
        "-vf", drawtext,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        output_path,
    ]

    result = _run(cmd)
    if result.returncode == 0:
        logger.info("Text overlay applied: '%s' at %.1fs-%.1fs", text[:30], start_time, end_time)
    return result.returncode == 0


def apply_multiple_text_overlays(
    input_path: str,
    output_path: str,
    overlays: list,
) -> bool:
    """Apply multiple text overlays in a single FFmpeg pass."""
    if not overlays:
        shutil.copy2(input_path, output_path)
        return True

    font_path = _find_devanagari_font()
    filters = []
    for ov in overlays:
        pos = _TEXT_POSITIONS.get(ov.position, _TEXT_POSITIONS["bottom_center"])
        end_time = ov.start_time + ov.duration
        escaped_text = ov.text.replace("'", "'\\''").replace(":", "\\:")
        enable = f"between(t\\,{ov.start_time}\\,{end_time})"
        drawtext = (
            f"drawtext=text='{escaped_text}':"
            f"fontfile='{font_path}':"
            f"fontsize={ov.font_size}:"
            f"fontcolor={ov.font_color}:"
            f"box=1:boxcolor={ov.bg_color}:boxborderw=15:"
            f"{pos}:"
            f"enable='{enable}'"
        )
        filters.append(drawtext)

    vf = ",".join(filters)
    cmd = [
        _ffmpeg(), "-y", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        output_path,
    ]
    result = _run(cmd)
    return result.returncode == 0


def apply_image_overlay(
    input_path: str,
    output_path: str,
    image_path: str,
    start_time: float,
    duration: float,
    position: str = "top_right",
    width: int = 150,
    opacity: float = 0.9,
) -> bool:
    """Overlay an image (logo, coach photo) on a video at a specific time range."""
    if not os.path.exists(image_path):
        logger.error("Image overlay: file not found: %s", image_path)
        return False

    pos = _IMAGE_POSITIONS.get(position, _IMAGE_POSITIONS["top_right"])
    end_time = start_time + duration
    enable = f"between(t,{start_time},{end_time})"

    filter_complex = (
        f"[1:v]scale={width}:-1,format=rgba,"
        f"colorchannelmixer=aa={opacity}[logo];"
        f"[0:v][logo]overlay={pos}:enable='{enable}'[vout]"
    )

    cmd = [
        _ffmpeg(), "-y",
        "-i", input_path,
        "-i", image_path,
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        output_path,
    ]

    result = _run(cmd)
    if result.returncode == 0:
        logger.info("Image overlay applied: %s at %.1fs-%.1fs", os.path.basename(image_path), start_time, end_time)
    return result.returncode == 0


def generate_text_card(
    text: str,
    duration: float,
    output_path: str,
    width: int = 1080,
    height: int = 1920,
    font_size: int = 48,
    font_color: str = "white",
    bg_color: str = "black",
    fps: int = 24,
) -> bool:
    """Generate a standalone text card video."""
    font_path = _find_devanagari_font()
    escaped_text = text.replace("'", "'\\''").replace(":", "\\:")
    fade_in_d = min(0.3, duration / 4)
    fade_out_start = max(0, duration - 0.3)

    vf = (
        f"drawtext=text='{escaped_text}':"
        f"fontfile='{font_path}':"
        f"fontsize={font_size}:"
        f"fontcolor={font_color}:"
        f"x=(w-text_w)/2:y=(h-text_h)/2,"
        f"fade=t=in:st=0:d={fade_in_d},"
        f"fade=t=out:st={fade_out_start}:d=0.3"
    )

    cmd = [
        _ffmpeg(), "-y",
        "-f", "lavfi", "-i", f"color=c={bg_color}:s={width}x{height}:r={fps}:d={duration}",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-vf", vf,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-video_track_timescale", "12800",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
        "-shortest",
        output_path,
    ]

    result = _run(cmd)
    if result.returncode == 0:
        logger.info("Text card generated: '%s' (%.1fs)", text[:30], duration)
    return result.returncode == 0


def generate_flash_white_transition(
    output_path: str,
    duration: float = 0.5,
    width: int = 1080,
    height: int = 1920,
    fps: int = 24,
) -> bool:
    """Generate a white flash transition video (fade in → white → fade out)."""
    half = duration / 2
    vf = f"fade=t=in:st=0:d={half}:color=white,fade=t=out:st={half}:d={half}:color=white"

    cmd = [
        _ffmpeg(), "-y",
        "-f", "lavfi", "-i", f"color=c=white:s={width}x{height}:r={fps}:d={duration}",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-vf", vf,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-video_track_timescale", "12800",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
        "-shortest",
        output_path,
    ]
    result = _run(cmd)
    return result.returncode == 0


def generate_fade_black_transition(
    output_path: str,
    duration: float = 0.8,
    width: int = 1080,
    height: int = 1920,
    fps: int = 24,
) -> bool:
    """Generate a fade-to-black-and-back transition video."""
    half = duration / 2
    vf = f"fade=t=in:st={half}:d={half}"

    cmd = [
        _ffmpeg(), "-y",
        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r={fps}:d={duration}",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-vf", vf,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-video_track_timescale", "12800",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
        "-shortest",
        output_path,
    ]
    result = _run(cmd)
    return result.returncode == 0


def generate_transition(
    transition_type: str,
    output_path: str,
    duration: float = 1.0,
    text: Optional[str] = None,
    font_size: int = 48,
    bg_color: str = "black",
    width: int = 1080,
    height: int = 1920,
) -> bool:
    """Generate a transition video clip based on type."""
    if transition_type == "flash_white":
        return generate_flash_white_transition(output_path, duration, width, height)
    if transition_type == "fade_black":
        return generate_fade_black_transition(output_path, duration, width, height)
    if transition_type == "text_card":
        card_text = text or "SuperLiving me coach se\nbaat krne ke baad..."
        return generate_text_card(
            text=card_text,
            duration=duration,
            output_path=output_path,
            width=width,
            height=height,
            font_size=font_size,
            bg_color=bg_color,
        )
    if transition_type == "blur_shift":
        logger.warning("blur_shift transition not yet implemented — falling back to fade_black")
        return generate_fade_black_transition(output_path, duration, width, height)

    logger.error("Unknown transition type: %s", transition_type)
    return False
