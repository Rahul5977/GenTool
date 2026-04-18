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
from ..pipeline.domain_profiler import (
    get_domain_profile,
    detect_domain,
    build_visual_states,
    detect_coach_clip,
)
from ..prompts.system_analyser import SYSTEM_ANALYSER

logger = logging.getLogger(__name__)

# Speech-to-the-Edge word counts — extended to prevent Veo edge hallucination.
# Dialogue must reach second 7.8+ to keep Veo locked on lip sync until clip end.
# Only 8-second clips are supported.
_WORD_RANGES: dict[int, tuple[int, int]] = {
    8: (24, 27),  # Extended from (20, 25) — CRITICAL FIX for edge hallucination
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
    domain_hint: str | None = None,
) -> ProductionBrief:
    """Parse a raw Hindi/Hinglish script into a validated ProductionBrief.

    Args:
        script:       Raw ad script text.
        num_clips:    Requested number of clips (3–8).
        coach:        Coach name (e.g. "Rishika").
        domain_hint:  If set (from CreateJobRequest after auto-detect / user pick),
                      this domain wins over Gemini's JSON ``domain`` field so the
                      pipeline matches the UI.

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

    if domain_hint and str(domain_hint).strip():
        logger.info(
            "Phase 1: calling Gemini (%d clips) — domain_hint=%r will override model domain",
            num_clips,
            domain_hint.strip().lower(),
        )
    else:
        logger.info("Phase 1: calling Gemini to analyse script (%d clips)", num_clips)

    # Gemini can occasionally return fewer clips than requested.
    # Retry a few times with stricter instructions so the pipeline does not
    # silently proceed with the wrong clip count.
    max_attempts = 3
    brief: ProductionBrief | None = None
    for attempt in range(1, max_attempts + 1):
        attempt_message = user_message
        if attempt > 1:
            attempt_message += (
                "\n\nCRITICAL RETRY INSTRUCTION:\n"
                f"You MUST return exactly {num_clips} clips in the clips array. "
                "Do not return fewer or more clips."
            )

        raw: dict = gemini_client.generate_json(
            system_prompt=SYSTEM_ANALYSER,
            user_prompt=attempt_message,
            temperature=0.1,
        )

        candidate = _parse_brief(raw, coach, script, domain_hint=domain_hint)
        candidate = _validate_and_fix(candidate, num_clips)

        if len(candidate.clips) == num_clips:
            brief = candidate
            break

        logger.warning(
            "Phase 1 attempt %d/%d returned %d clips (requested %d) — retrying",
            attempt, max_attempts, len(candidate.clips), num_clips,
        )
        brief = candidate

    if brief is None:
        raise RuntimeError("Phase 1 failed to produce a valid ProductionBrief")
    if len(brief.clips) != num_clips:
        raise ValueError(
            f"Phase 1 could not produce requested clip count after {max_attempts} attempts: "
            f"requested={num_clips}, got={len(brief.clips)}"
        )

    logger.info("Phase 1 complete — %d clips, character: %s skin", len(brief.clips), brief.character.skin_tone)
    return brief


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_brief(
    raw: dict,
    coach: str,
    script_text: str,
    domain_hint: str | None = None,
) -> ProductionBrief:
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

    brief = ProductionBrief(
        clips=clips,
        character=character,
        locked_background=locked_background,
        aspect_ratio=raw.get("aspect_ratio", "9:16"),
        coach=raw.get("coach", coach),
        setting=raw.get("setting", ""),
        voice_characteristics=_build_voice_characteristics(character.age, character.gender),
    )

    # ── Domain profiler integration ──
    if domain_hint and str(domain_hint).strip():
        domain = str(domain_hint).strip().lower()
    else:
        domain = raw.get("domain", None) or detect_domain(script_text)
    coach_clip = raw.get("coach_clip", None) or detect_coach_clip(clips, len(clips))

    profile = get_domain_profile(domain)
    visual_states = build_visual_states(profile, num_clips=len(clips), coach_clip=coach_clip)

    for i, clip in enumerate(clips):
        if i < len(visual_states):
            clip.visual_state = visual_states[i]

    brief.domain = domain
    brief.coach_clip = coach_clip
    brief.pre_coach_visual_markers = profile.pre_coach_appearance_modifiers
    brief.post_coach_visual_markers = profile.post_coach_appearance_modifiers
    brief.visual_states = visual_states
    return brief


# ---------------------------------------------------------------------------
# Voice characteristics
# ---------------------------------------------------------------------------

def _build_voice_characteristics(age: int, gender: str) -> str:
    """Derive locked voice characteristics from character age and gender.

    These are copied verbatim into every clip's AUDIO block so the voice
    stays identical across the entire ad.
    """
    gender_lower = gender.lower()
    is_female = "female" in gender_lower or "महिला" in gender_lower
    person = "भारतीय महिला" if is_female else "भारतीय पुरुष"
    accent = "Authentic Tier 2–3 India accent (Raipur/Patna/Kanpur style)"
    quality = "Close-mic (15cm), -14 LUFS, zero reverb, zero echo, zero background noise"

    if is_female:
        if age <= 25:
            return (
                f"युवा {age} वर्षीय {person} की आवाज़, स्वाभाविक और ऊर्जावान। "
                f"warm medium pitch — not high, not low। {accent}। {quality}।"
            )
        elif age <= 35:
            return (
                f"{age} वर्षीय {person} की आवाज़, आत्मविश्वास से भरी, संतुलित। "
                f"warm medium pitch, moderate conversational pace। {accent}। {quality}।"
            )
        else:
            return (
                f"परिपक्व {age} वर्षीय {person} की आवाज़, गर्म और धीर-गंभीर। "
                f"warm medium-low pitch, steady measured pace। {accent}। {quality}।"
            )
    else:
        if age <= 25:
            return (
                f"युवा {age} वर्षीय {person} की आवाज़, स्वाभाविक और ऊर्जावान। "
                f"warm medium pitch। {accent}। {quality}।"
            )
        elif age <= 35:
            return (
                f"{age} वर्षीय {person} की आवाज़, आत्मविश्वास से भरी, संतुलित। "
                f"warm medium-low pitch, moderate conversational pace। {accent}। {quality}।"
            )
        else:
            return (
                f"परिपक्व {age} वर्षीय {person} की आवाज़, गर्म और धीर-गंभीर। "
                f"warm low pitch, steady measured pace। {accent}। {quality}।"
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

    # Allow 1–2 words outside range — meaning preservation takes priority.
    # Only auto-correct when deviation is 3+ words.
    _LENIENCY = 2

    if actual > hi + _LENIENCY:
        clip.dialogue = _trim_dialogue(clip.dialogue, hi)
        clipped_count = _count_words(clip.dialogue)
        issues.append(
            f"Clip {clip.clip_number}: word count {actual} exceeded {hi + _LENIENCY} for {duration}s — "
            f"trimmed to {clipped_count} words (fillers removed)"
        )
        clip.word_count = clipped_count

    elif actual > hi:
        # 1–2 words over — log warning but preserve meaning, do not trim
        issues.append(
            f"Clip {clip.clip_number}: word count {actual} is {actual - hi} over ideal max "
            f"{hi} for {duration}s — kept for meaning preservation"
        )
        clip.word_count = actual

    elif actual < lo - _LENIENCY:
        clip.dialogue, new_count = _expand_dialogue(clip.dialogue, lo)
        # Expansion can overshoot the ceiling — trim if needed
        if new_count > hi:
            clip.dialogue = _trim_dialogue(clip.dialogue, hi)
            new_count = _count_words(clip.dialogue)
        issues.append(
            f"Clip {clip.clip_number}: word count {actual} below {lo - _LENIENCY} for {duration}s — "
            f"expanded to {new_count} words"
        )
        clip.word_count = new_count

    elif actual < lo:
        # 1–2 words under — log warning but do not pad (avoids unnatural expansion)
        issues.append(
            f"Clip {clip.clip_number}: word count {actual} is {lo - actual} under ideal min "
            f"{lo} for {duration}s — kept as-is (natural pacing)"
        )
        clip.word_count = actual

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
