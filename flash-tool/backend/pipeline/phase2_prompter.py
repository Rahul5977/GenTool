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

# Devanagari primary block is U+0900–U+097F; these ranges are other Indic scripts
# that must not appear in dialogue (Veo TTS / lip-sync language drift).
_NON_DEVANAGARI_INDIC_RANGES = [
    (0x0980, 0x09FF),  # Bengali
    (0x0A00, 0x0A7F),  # Gurmukhi
    (0x0A80, 0x0AFF),  # Gujarati
    (0x0B00, 0x0B7F),  # Oriya
    (0x0B80, 0x0BFF),  # Tamil
    (0x0C00, 0x0C7F),  # Telugu
    (0x0C80, 0x0CFF),  # Kannada
    (0x0D00, 0x0D7F),  # Malayalam
    (0x0D80, 0x0DFF),  # Sinhala
]


def _contains_non_devanagari_indic(text: str) -> tuple[bool, str]:
    """Return (True, offending_char) if text contains non-Devanagari Indic script."""
    for char in text:
        cp = ord(char)
        for start, end in _NON_DEVANAGARI_INDIC_RANGES:
            if start <= cp <= end:
                return True, char
    return False, ""


def _enforce_devanagari_dialogue(clip_prompts: list[ClipPrompt]) -> list[ClipPrompt]:
    """Hard guard: dialogue must not contain non-Devanagari Indic scripts."""
    for clip in clip_prompts:
        has_bad, bad_char = _contains_non_devanagari_indic(clip.dialogue)
        if has_bad:
            raise RuntimeError(
                f"CRITICAL: Clip {clip.clip_number} dialogue contains non-Devanagari "
                f"Indic character '{bad_char}' (U+{ord(bad_char):04X}). "
                f"This will cause Veo TTS to switch languages and break lip-sync. "
                f"Dialogue: {clip.dialogue[:200]}"
            )
    return clip_prompts


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

    # Enforce verbatim background lock — safety net in case Gemini paraphrased
    clip_prompts = _enforce_background_lock(clip_prompts, brief.locked_background)

    # Verifier applies the rules and auto-fixes issues in-place
    logger.info("Phase 2: running verifier on %d clips", len(clip_prompts))
    clip_prompts = verify_prompts(clip_prompts)
    clip_prompts = _enforce_devanagari_dialogue(clip_prompts)

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

    # ── Domain-specific visual markers ─────────────────────────────────────
    domain_block = ""
    if brief.domain and brief.domain != "general":
        domain_block = f"""
════════════════════════════════════════════
⚠️ DOMAIN-SPECIFIC VISUAL DIRECTION — {brief.domain.upper()}
════════════════════════════════════════════
This ad is for the {brief.domain} domain. The character's VISUAL APPEARANCE
must match the emotional arc. Coach is introduced in clip {brief.coach_clip}.

PRE-COACH CLIPS (1 to {brief.coach_clip}) — CHARACTER SHOWS THE PROBLEM:
{chr(10).join(f'  • {m}' for m in brief.pre_coach_visual_markers)}

POST-COACH CLIPS ({brief.coach_clip + 1} to {len(brief.clips)}) — CHARACTER SHOWS CONFIDENCE:
{chr(10).join(f'  • {m}' for m in brief.post_coach_visual_markers)}

CRITICAL: The PHYSICAL BODY does NOT change. NO transformation. NO before/after.
What changes: POSTURE, STYLING, EYE CONTACT, ENERGY, VOICE REGISTER.
The same person, same build, same outfit — but how they CARRY themselves changes.

PER-CLIP VISUAL STATES (inject into ACTION section of each clip):
"""
        for i, clip in enumerate(brief.clips):
            if clip.visual_state:
                vs = clip.visual_state
                domain_block += f"""
Clip {clip.clip_number}:
  POSTURE: {vs.posture}
  STYLING: {vs.styling_state}
  ENERGY: {vs.energy_level}
  EYE CONTACT: {vs.eye_contact_pattern}
  VOICE: {vs.voice_register}
  LIGHTING WARMTH: {vs.lighting_warmth}
"""

    return f"""
════════════════════════════════════════════
⚠️ LOCKED BACKGROUND — COPY WORD-FOR-WORD INTO EVERY CLIP'S LOCATION BLOCK
════════════════════════════════════════════
DO NOT paraphrase. DO NOT summarize. DO NOT add or remove any detail.
Copy the following text CHARACTER-FOR-CHARACTER into every clip's LOCATION block,
then append the freeze line immediately after it.

{brief.locked_background}

Freeze line (append verbatim after the background in every clip):
"पृष्ठभूमि पूरी तरह स्थिर और अपरिवर्तित रहती है — कोई नई वस्तु नहीं आएगी,
कोई वस्तु गायब नहीं होगी, रंग नहीं बदलेगा।"

DEPTH OF FIELD NOTE: Background should appear with natural depth-of-field blur —
sharp focus on the character's face, background softly out of focus (f/2.8 equivalent).
This is REQUIRED in every clip's CAMERA block.

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

{domain_block}

════════════════════════════════════════════
CLIP BRIEFS — Generate one Veo prompt per clip
════════════════════════════════════════════
{clips_json}
""".strip()


# ---------------------------------------------------------------------------
# Background lock enforcement
# ---------------------------------------------------------------------------

_FREEZE_LINE = (
    "पृष्ठभूमि पूरी तरह स्थिर और अपरिवर्तित रहती है — कोई नई वस्तु नहीं आएगी, "
    "कोई वस्तु गायब नहीं होगी, रंग नहीं बदलेगा।"
)

# Section markers that follow LOCATION in the prompt
_AFTER_LOCATION_MARKERS = ["ACTION:", "AUDIO:", "CAMERA:", "DIALOGUE:", "LIGHTING:"]


def _enforce_background_lock(clips: list[ClipPrompt], locked_background: str) -> list[ClipPrompt]:
    """Post-generation safety net: ensure every clip's LOCATION block contains
    the locked background verbatim and the freeze line.

    Gemini occasionally paraphrases the background despite explicit instructions.
    This function detects deviations and replaces the LOCATION block in-place.
    """
    canonical = f"{locked_background}\n\n{_FREEZE_LINE}"

    for clip in clips:
        prompt = clip.prompt

        if "LOCATION:" not in prompt:
            logger.warning(
                "Phase 2: Clip %d has no LOCATION block — skipping background enforcement",
                clip.clip_number,
            )
            continue

        loc_start = prompt.index("LOCATION:") + len("LOCATION:")

        # Find the next section marker after LOCATION
        next_idx = None
        for marker in _AFTER_LOCATION_MARKERS:
            search_from = loc_start
            pos = prompt.find(marker, search_from)
            if pos != -1 and (next_idx is None or pos < next_idx):
                next_idx = pos

        if next_idx is None:
            logger.warning(
                "Phase 2: Clip %d LOCATION block has no following section — skipping",
                clip.clip_number,
            )
            continue

        current_location = prompt[loc_start:next_idx].strip()

        # Check if background AND freeze line are already verbatim
        has_bg = locked_background in current_location
        has_freeze = _FREEZE_LINE.split("—")[0].strip() in current_location  # partial match

        if has_bg and has_freeze:
            continue  # Already correct

        # Replace LOCATION block with canonical version
        before = prompt[:loc_start]
        after = prompt[next_idx:]
        clip.prompt = f"{before}\n{canonical}\n\n{after}"

        logger.info(
            "Phase 2: Clip %d LOCATION block replaced (had_bg=%s, had_freeze=%s)",
            clip.clip_number, has_bg, has_freeze,
        )

    return clips


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
