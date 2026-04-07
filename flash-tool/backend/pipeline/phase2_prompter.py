"""Phase 2 — Prompt Generation.

Converts a ProductionBrief into a list of verified Veo ClipPrompts.
"""

import json
import logging

from ..ai.gemini_client import gemini_client
from ..ai.verifier import verify_prompts
from ..models import ClipPrompt, ProductionBrief
from ..prompts.system_prompter import SYSTEM_PROMPTER

logger = logging.getLogger(__name__)


def generate_prompts(brief: ProductionBrief) -> list[ClipPrompt]:
    """Generate and verify per-clip Veo prompts from a ProductionBrief.

    The locked background and character appearance are injected verbatim into
    the user message so the model copies them exactly into LOCATION and
    OUTFIT blocks without paraphrasing.

    Args:
        brief: Validated ProductionBrief from Phase 1.

    Returns:
        Verified list of ClipPrompt objects (one per clip).
    """
    user_message = _build_user_message(brief)

    logger.info("Phase 2: calling Gemini to generate %d clip prompts", len(brief.clips))
    raw_clips: list[dict] = gemini_client.generate_json(
        system_prompt=SYSTEM_PROMPTER,
        user_prompt=user_message,
        temperature=0.2,
    )

    if not isinstance(raw_clips, list):
        raise RuntimeError(
            f"SYSTEM_PROMPTER expected a JSON array, got {type(raw_clips).__name__}"
        )

    clip_prompts = _parse_clip_prompts(raw_clips)

    # Verifier applies the 13 rules and auto-fixes issues in-place
    logger.info("Phase 2: running verifier on %d clips", len(clip_prompts))
    clip_prompts = verify_prompts(clip_prompts)

    logger.info(
        "Phase 2 complete — %d verified clips, issues: %s",
        len(clip_prompts),
        [c.verification_issues for c in clip_prompts],
    )
    return clip_prompts


# ---------------------------------------------------------------------------
# User message builder
# ---------------------------------------------------------------------------

def _build_user_message(brief: ProductionBrief) -> str:
    """Serialize the brief for the prompter with critical fields highlighted.

    The background and character appearance are surfaced at the top of the
    message with explicit "COPY VERBATIM" instructions so the model treats
    them as immutable anchor text, not creative input.
    """
    char = brief.character
    accessories_str = ", ".join(char.accessories) if char.accessories else "none"
    marks_str = ", ".join(char.distinguishing_marks) if char.distinguishing_marks else "none"

    character_block = (
        f"Age: {char.age}, Gender: {char.gender}\n"
        f"Skin tone: {char.skin_tone} ({char.skin_hex})\n"
        f"Face shape: {char.face_shape}\n"
        f"Hair: {char.hair}\n"
        f"Outfit: {char.outfit}\n"
        f"Accessories: {accessories_str}\n"
        f"Distinguishing marks: {marks_str}"
    )

    clips_json = json.dumps(
        [
            {
                "clip_number": c.clip_number,
                "duration_seconds": c.duration_seconds,
                "dialogue": c.dialogue,
                "word_count": c.word_count,
                "emotional_state": c.emotional_state,
                "end_emotion": c.end_emotion,
            }
            for c in brief.clips
        ],
        ensure_ascii=False,
        indent=2,
    )

    return f"""
════════════════════════════════════════════
LOCKED BACKGROUND — COPY VERBATIM INTO EVERY CLIP'S LOCATION BLOCK
════════════════════════════════════════════
{brief.locked_background}

════════════════════════════════════════════
CHARACTER APPEARANCE — COPY VERBATIM INTO EVERY CLIP'S OUTFIT & APPEARANCE BLOCK
════════════════════════════════════════════
{character_block}

════════════════════════════════════════════
PRODUCTION METADATA
════════════════════════════════════════════
Coach: {brief.coach}
Aspect ratio: {brief.aspect_ratio}
Setting: {brief.setting}

════════════════════════════════════════════
CLIP BRIEFS — Generate one Veo prompt per clip
════════════════════════════════════════════
{clips_json}
""".strip()


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_clip_prompts(raw_clips: list[dict]) -> list[ClipPrompt]:
    """Convert raw Gemini output dicts into ClipPrompt objects."""
    result: list[ClipPrompt] = []
    for i, item in enumerate(raw_clips):
        try:
            cp = ClipPrompt(
                clip_number=item["clip_number"],
                duration_seconds=item["duration_seconds"],
                scene_summary=item.get("scene_summary", ""),
                prompt=item["prompt"],
                dialogue=item.get("dialogue", ""),
                word_count=item.get("word_count", 0),
                end_emotion=item.get("end_emotion", ""),
            )
        except (KeyError, TypeError) as exc:
            raise RuntimeError(
                f"SYSTEM_PROMPTER returned invalid clip at index {i}: {exc}\n"
                f"Raw entry: {item!r}"
            ) from exc
        result.append(cp)
    return result
