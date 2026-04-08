"""Phase 3 — Keyframe Image Generation.

Produces N+1 keyframe images:
  - Frame 0:   initial character reference via Imagen 3
  - Frames 1…N: expression-transition frames via Gemini 2.0 Flash Image model
"""

import base64
import logging
from typing import Callable, Optional

from google import genai
from google.genai import types

from .. import config
from ..ai.imagen_client import imagen_client
from ..models import ClipPrompt, KeyFrame, ProductionBrief
from ..prompts.system_imager import IMAGEN_PROMPT_TEMPLATE, SYSTEM_IMAGER

logger = logging.getLogger(__name__)

# Separate genai client for the image-generation model (uses SDK default API version).
_image_client = genai.Client(api_key=config.GOOGLE_API_KEY)


def generate_keyframes(
    brief: ProductionBrief,
    clips: list[ClipPrompt],
    on_keyframe: Optional[Callable[[KeyFrame, int], None]] = None,
) -> list[KeyFrame]:
    """Generate N+1 keyframe JPEG images for a video job.

    Index 0 is the initial character reference (Imagen 3).
    Index 1…N are expression-transition frames (Gemini 2.0 Flash Image).

    Args:
        brief: Validated ProductionBrief (character spec + locked background).
        clips: Verified ClipPrompt list from Phase 2.

    Returns:
        list[KeyFrame] of length len(clips) + 1, all with image_b64 populated.
    """
    keyframes: list[KeyFrame] = []

    # ── Frame 0: Imagen 3 character reference ──────────────────────────────
    total = len(clips) + 1
    frame_0 = _generate_reference_frame(brief, clips)
    keyframes.append(frame_0)
    logger.info("Phase 3: frame 0 generated via Imagen 3 (%d b64 chars)", len(frame_0.image_b64))
    if on_keyframe:
        on_keyframe(frame_0, total)

    # ── Frames 1…N: Gemini Image transition frames ─────────────────────────
    for i, clip in enumerate(clips):
        prev_frame = keyframes[i]
        target_emotion = clip.end_emotion

        logger.info(
            "Phase 3: generating frame %d (end_emotion of clip %d: %s)",
            i + 1, clip.clip_number, target_emotion[:60],
        )
        next_frame = _generate_transition_frame(
            prev_frame=prev_frame,
            frame_index=i + 1,
            target_emotion=target_emotion,
            brief=brief,
            clip=clip,
        )
        keyframes.append(next_frame)
        if on_keyframe:
            on_keyframe(next_frame, total)

    logger.info("Phase 3 complete — %d keyframes generated", len(keyframes))
    return keyframes


def regenerate_single_keyframe(
    frame_index: int,
    prev_keyframe: KeyFrame,
    target_emotion: str,
    brief: ProductionBrief,
    clip: Optional[ClipPrompt] = None,
) -> KeyFrame:
    """Regenerate a single keyframe (called from the regen-image API endpoint).

    For frame_index == 0, regenerates the Imagen 3 reference image.
    For frame_index > 0, runs the Gemini Image transition from prev_keyframe.

    Args:
        frame_index:    Index of the keyframe to regenerate.
        prev_keyframe:  The preceding keyframe (frame_index - 1).
                        Ignored when frame_index == 0.
        target_emotion: Desired end expression.
        brief:          ProductionBrief (character spec + background).
        clip:           Corresponding ClipPrompt (used for description).

    Returns:
        A new KeyFrame with updated image_b64.
    """
    if frame_index == 0:
        # _generate_reference_frame reads emotional_state from brief.clips, not from clips arg
        return _generate_reference_frame(brief, [])

    return _generate_transition_frame(
        prev_frame=prev_keyframe,
        frame_index=frame_index,
        target_emotion=target_emotion,
        brief=brief,
        clip=clip,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Frame 0 — Imagen 3 initial reference
# ---------------------------------------------------------------------------

def _generate_reference_frame(
    brief: ProductionBrief,
    clips: list[ClipPrompt],
) -> KeyFrame:
    char = brief.character
    accessories_str = (
        ", ".join(char.accessories) if char.accessories else "none"
    )
    marks_str = (
        ", ".join(char.distinguishing_marks) if char.distinguishing_marks else "none"
    )
    # emotional_state lives on ClipBrief (brief.clips), not ClipPrompt
    first_emotional_state = (
        brief.clips[0].emotional_state if brief.clips else "neutral, attentive"
    )

    prompt = IMAGEN_PROMPT_TEMPLATE.format(
        age=char.age,
        skin_tone=char.skin_tone,
        skin_hex=char.skin_hex,
        face_shape=char.face_shape,
        hair=char.hair,
        outfit=char.outfit,
        accessories_str=accessories_str,
        marks_str=marks_str,
        locked_background=brief.locked_background,
    )
    # Append the opening emotional state so Imagen sets the right starting expression
    prompt += f"\n\nOpening expression: {first_emotional_state}."

    # Try Imagen 3 first; fall back to Gemini 2.0 Flash image generation
    image_b64: str | None = None
    try:
        image_bytes = imagen_client.generate_character_image(prompt)
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        logger.info("Phase 3: frame 0 generated via Imagen 3")
    except RuntimeError as exc:
        logger.warning(
            "Phase 3: Imagen 3 failed (%s) — falling back to Gemini image generation", exc
        )
        image_b64 = _call_gemini_image_text_to_image(prompt)
        if not image_b64:
            raise RuntimeError(
                f"Frame 0 generation failed: Imagen error was '{exc}', "
                "and Gemini image fallback also returned no image."
            ) from exc

    return KeyFrame(
        index=0,
        image_b64=image_b64,
        mime_type="image/jpeg",
        description=f"Initial character reference — {first_emotional_state}",
        approved=False,
    )


# ---------------------------------------------------------------------------
# Frames 1…N — Gemini 2.0 Flash Image expression transitions
# ---------------------------------------------------------------------------

def _generate_transition_frame(
    prev_frame: KeyFrame,
    frame_index: int,
    target_emotion: str,
    brief: ProductionBrief,
    clip: ClipPrompt,
) -> KeyFrame:
    char = brief.character
    accessories_str = (
        ", ".join(char.accessories) if char.accessories else "none"
    )
    marks_str = (
        ", ".join(char.distinguishing_marks) if char.distinguishing_marks else "none"
    )

    instruction = (
        f"{SYSTEM_IMAGER}\n\n"
        f"Change ONLY the facial expression to: {target_emotion}\n\n"
        f"Keep EVERYTHING else identical:\n"
        f"  Skin hex: {char.skin_hex}\n"
        f"  Hair: {char.hair}\n"
        f"  Outfit: {char.outfit}\n"
        f"  Accessories: {accessories_str}\n"
        f"  Distinguishing marks: {marks_str}\n"
        f"  Background: {brief.locked_background[:300]}…\n"
        f"  Camera: TIGHT MCU — chin to mid-chest, eye-level\n"
        f"  Output: 9:16 portrait, photorealistic, no text, no overlays"
    )

    result_b64 = _call_gemini_image(
        prev_b64=prev_frame.image_b64,
        instruction=instruction,
    )

    if not result_b64:
        # Fallback: reuse previous frame rather than leaving the slot empty
        logger.warning(
            "Phase 3: Gemini Image returned no image for frame %d — reusing previous frame",
            frame_index,
        )
        result_b64 = prev_frame.image_b64

    return KeyFrame(
        index=frame_index,
        image_b64=result_b64,
        mime_type="image/jpeg",
        description=f"Clip {clip.clip_number} end-frame — {target_emotion[:80]}",
        approved=False,
    )


def _extract_image_b64(response, context: str) -> str | None:
    """Extract the first image part from a Gemini generate_content response.

    Returns base64-encoded image string, or None if no image part found.
    """
    candidates = getattr(response, "candidates", None) or []
    logger.debug("Gemini %s: %d candidate(s) in response", context, len(candidates))

    for ci, candidate in enumerate(candidates):
        finish_reason = getattr(candidate, "finish_reason", None)
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        logger.debug(
            "Gemini %s: candidate[%d] finish_reason=%s, %d part(s)",
            context, ci, finish_reason, len(parts),
        )
        for pi, part in enumerate(parts):
            inline = getattr(part, "inline_data", None)
            text = getattr(part, "text", None)
            if text:
                logger.debug("Gemini %s: candidate[%d].part[%d] text=%r", context, ci, pi, text[:200])
            if inline is not None:
                mime = getattr(inline, "mime_type", None)
                data = getattr(inline, "data", None)
                logger.debug(
                    "Gemini %s: candidate[%d].part[%d] inline_data mime=%s data_len=%s",
                    context, ci, pi, mime, len(data) if data else 0,
                )
                if data:
                    if isinstance(data, bytes):
                        return base64.b64encode(data).decode("utf-8")
                    return data  # already a base64 string

    # Log any prompt feedback (safety blocks etc.)
    feedback = getattr(response, "prompt_feedback", None)
    if feedback:
        logger.warning("Gemini %s: prompt_feedback=%s", context, feedback)

    # Dump full response repr so we can diagnose unexpected structures
    logger.warning("Gemini %s: full response repr: %r", context, response)
    logger.warning("Gemini %s: response contained no image parts", context)
    return None


def _call_gemini_image_text_to_image(prompt: str) -> str | None:
    """Generate a character image from a text prompt via Gemini image model.

    Used as a fallback when Imagen 3 is unavailable on the API key.
    Returns base64-encoded JPEG, or None on failure.
    """
    try:
        response = _image_client.models.generate_content(
            model=config.GEMINI_IMAGE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                # Must include TEXT alongside IMAGE — IMAGE alone causes the
                # model to return only a text caption with no image part.
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
    except Exception as exc:
        logger.error("Gemini image text-to-image fallback failed: %s", exc)
        return None

    return _extract_image_b64(response, "text-to-image fallback")


def _call_gemini_image(prev_b64: str, instruction: str) -> str | None:
    """Send a base64 JPEG + instruction to Gemini image model for editing.

    Returns the generated image as a base64 string, or None if no image part
    was found in the response.
    """
    try:
        response = _image_client.models.generate_content(
            model=config.GEMINI_IMAGE_MODEL,
            contents=[
                types.Content(
                    parts=[
                        types.Part(
                            inline_data=types.Blob(
                                mime_type="image/jpeg",
                                data=prev_b64,
                            )
                        ),
                        types.Part(text=instruction),
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
    except Exception as exc:
        logger.error("Gemini Image API call failed: %s", exc)
        return None

    return _extract_image_b64(response, "image-edit")
