"""Phase 1 — Script Analysis.

Parses a raw Hindi/Hinglish script into a validated ProductionBrief.
"""

import json
import logging
import re

from ..ai.gemini_client import gemini_client
from ..models import (
    CharacterSpec,
    ClipBrief,
    ProductionBrief,
)
from ..prompts.system_analyser import SYSTEM_ANALYSER

logger = logging.getLogger(__name__)

# Allowed word-count ranges keyed by clip duration
_WORD_RANGES: dict[int, tuple[int, int]] = {
    8: (22, 24),
    7: (17, 20),
    5: (11, 14),
}

# Natural Hindi filler phrases for under-count expansion (each adds ~3-5 words)
_FILLERS = [
    ", aur mujhe sach mein achha laga",
    ", ye baat mujhe yaad rahegi",
    ", isliye main aaj baat kar rahi hoon",
    ", ye mera anubhav hai",
]

_DASH_RE = re.compile(r"[—\-]")


def analyse_script(
    script: str,
    num_clips: int,
    coach: str,
) -> ProductionBrief:
    """Parse a raw Hindi/Hinglish script into a validated ProductionBrief.

    Args:
        script:    Raw ad script text.
        num_clips: Requested number of clips (3–8).
        coach:     Coach name (e.g. "Rishika").

    Returns:
        A fully-populated and validated ProductionBrief.

    Raises:
        ValueError: If Gemini output fails validation and cannot be auto-corrected.
        RuntimeError: If Gemini returns invalid JSON after retries.
    """
    user_message = (
        f"Coach name: {coach}\n"
        f"Number of clips requested: {num_clips}\n\n"
        f"Script:\n{script}"
    )

    logger.info("Phase 1: calling Gemini to analyse script (%d clips)", num_clips)
    raw: dict = gemini_client.generate_json(
        system_prompt=SYSTEM_ANALYSER,
        user_prompt=user_message,
        temperature=0.1,
    )

    # -----------------------------------------------------------------------
    # Parse raw dict into model objects
    # -----------------------------------------------------------------------
    brief = _parse_brief(raw, coach)

    # -----------------------------------------------------------------------
    # Validate and auto-correct
    # -----------------------------------------------------------------------
    brief = _validate_and_fix(brief, num_clips)

    logger.info("Phase 1 complete — %d clips, character: %s skin", len(brief.clips), brief.character.skin_tone)
    return brief


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_brief(raw: dict, coach: str) -> ProductionBrief:
    """Convert the raw Gemini dict into a ProductionBrief."""
    try:
        character = CharacterSpec(**raw["character"])
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Gemini output missing or invalid 'character' block: {exc}") from exc

    raw_clips = raw.get("clips", [])
    if not raw_clips:
        raise ValueError("Gemini output contains no clips.")

    clips: list[ClipBrief] = []
    for item in raw_clips:
        try:
            clips.append(ClipBrief(**item))
        except (KeyError, TypeError) as exc:
            raise ValueError(f"Invalid clip entry in Gemini output: {item!r} — {exc}") from exc

    locked_background = raw.get("locked_background", "")
    if not locked_background:
        raise ValueError("Gemini output is missing 'locked_background'.")

    return ProductionBrief(
        clips=clips,
        character=character,
        locked_background=locked_background,
        aspect_ratio=raw.get("aspect_ratio", "9:16"),
        coach=raw.get("coach", coach),
        setting=raw.get("setting", ""),
    )


# ---------------------------------------------------------------------------
# Validation & auto-correction
# ---------------------------------------------------------------------------

def _validate_and_fix(brief: ProductionBrief, expected_num_clips: int) -> ProductionBrief:
    errors: list[str] = []

    # ── Clip count ──────────────────────────────────────────────────────────
    if len(brief.clips) != expected_num_clips:
        logger.warning(
            "Gemini returned %d clips but %d were requested — proceeding with what was returned",
            len(brief.clips), expected_num_clips,
        )

    # ── Character fields ────────────────────────────────────────────────────
    if not brief.character.skin_hex:
        errors.append("character.skin_hex is missing or empty")

    # ── Locked background length ─────────────────────────────────────────────
    bg_word_count = len(brief.locked_background.split())
    if bg_word_count < 50:
        errors.append(
            f"locked_background has only {bg_word_count} words (minimum 50)"
        )

    # ── Per-clip validation ──────────────────────────────────────────────────
    fixed_clips: list[ClipBrief] = []
    for clip in brief.clips:
        clip, clip_errors = _fix_clip(clip)
        errors.extend(clip_errors)
        fixed_clips.append(clip)

    brief.clips = fixed_clips

    if errors:
        # Non-fatal issues are logged; truly hard failures are raised
        hard_errors = [e for e in errors if "missing" in e.lower() or "skin_hex" in e]
        if hard_errors:
            raise ValueError(
                "ProductionBrief validation failed:\n" + "\n".join(f"  • {e}" for e in hard_errors)
            )
        for err in errors:
            logger.warning("Phase 1 validation warning: %s", err)

    return brief


def _fix_clip(clip: ClipBrief) -> tuple[ClipBrief, list[str]]:
    issues: list[str] = []

    # ── end_emotion present ──────────────────────────────────────────────────
    if not clip.end_emotion:
        issues.append(f"Clip {clip.clip_number}: end_emotion is missing")

    # ── Dash removal ─────────────────────────────────────────────────────────
    if _DASH_RE.search(clip.dialogue):
        original = clip.dialogue
        clip.dialogue = _remove_dashes(clip.dialogue)
        issues.append(
            f"Clip {clip.clip_number}: removed dashes from dialogue "
            f"({original!r} → {clip.dialogue!r})"
        )

    # ── Word count ───────────────────────────────────────────────────────────
    duration = clip.duration_seconds
    if duration not in _WORD_RANGES:
        issues.append(
            f"Clip {clip.clip_number}: unrecognised duration {duration}s — skipping word count check"
        )
        return clip, issues

    lo, hi = _WORD_RANGES[duration]
    actual = _count_words(clip.dialogue)

    if actual > hi:
        clip.dialogue = _trim_dialogue(clip.dialogue, hi)
        clipped_count = _count_words(clip.dialogue)
        issues.append(
            f"Clip {clip.clip_number}: word count {actual} exceeded {hi} for {duration}s — "
            f"trimmed to {clipped_count} words"
        )
        clip.word_count = clipped_count

    elif actual < lo:
        clip.dialogue, new_count = _expand_dialogue(clip.dialogue, lo)
        # Expansion can overshoot the ceiling — trim if needed
        if new_count > hi:
            clip.dialogue = _trim_dialogue(clip.dialogue, hi)
            new_count = _count_words(clip.dialogue)
        issues.append(
            f"Clip {clip.clip_number}: word count {actual} below {lo} for {duration}s — "
            f"expanded to {new_count} words"
        )
        clip.word_count = new_count

    else:
        clip.word_count = actual

    return clip, issues


# ---------------------------------------------------------------------------
# Dialogue helpers
# ---------------------------------------------------------------------------

def _count_words(text: str) -> int:
    return len(text.split())


def _remove_dashes(text: str) -> str:
    # em-dash (with or without surrounding spaces) → comma
    text = re.sub(r"\s*—\s*", ", ", text)
    # spaced hyphen " - " → " aur "
    text = re.sub(r"\s+-\s+", " aur ", text)
    # bare compound-word hyphen "word-word" → "word word"
    text = re.sub(r"(\w)-(\w)", r"\1 \2", text)
    return text.strip()


def _trim_dialogue(text: str, target_max: int) -> str:
    """Remove words from the end until word count <= target_max.

    Tries to cut at a sentence boundary (। or ,) before falling back to
    hard word truncation.
    """
    words = text.split()
    # Try to cut at the last punctuation boundary within the allowed range
    for i in range(target_max, max(target_max - 5, 0), -1):
        candidate = " ".join(words[:i])
        if candidate.endswith(("।", ",")):
            return candidate.rstrip(",").strip()
    # Hard truncation
    return " ".join(words[:target_max])


def _expand_dialogue(text: str, target_min: int) -> tuple[str, int]:
    """Append a filler phrase until word count >= target_min."""
    for filler in _FILLERS:
        candidate = text.rstrip("।").strip() + filler
        if _count_words(candidate) >= target_min:
            return candidate, _count_words(candidate)
    # Fallback: append all fillers until we reach the minimum
    result = text.rstrip("।").strip()
    for filler in _FILLERS:
        result += filler
        if _count_words(result) >= target_min:
            break
    return result, _count_words(result)
