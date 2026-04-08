"""Gemini clients — text generation and image editing.

GeminiClient (gemini_client):
  Text-based client using GEMINI_MODEL (gemini-2.5-pro).
  Used for JSON generation (script analysis, prompt building) and
  free-form text generation (sanitization, rephrasing).

GeminiImageClient (gemini_image_client):
  Image editing client using GEMINI_IMAGE_MODEL.
  WHY THIS IS SEPARATE FROM imagen_client:
    - Gemini Flash Image takes an INPUT IMAGE and modifies it.
      Used for Frames 1..N: "take this frame, change expression to X".
    - Imagen 3 generates from TEXT ONLY, no input image.
      Used for Frame 0 only: "create this character from scratch".

API VERSION NOTE:
  - gemini-2.0-flash-preview-image-generation works on SDK default (v1beta).
  - response_modalities must include BOTH "IMAGE" and "TEXT" —
    IMAGE alone causes the model to return a text caption with no image.
  - The input image must be passed as inline_data with mime_type image/jpeg.
  - The base64 data must be the raw b64 string (not bytes).
"""

import base64
import json
import logging
import re

from google import genai
from google.genai import types

from .. import config

logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


class GeminiClient:
    """Text-generation client for script analysis, prompt building, and rephrasing."""

    def __init__(self) -> None:
        self._client = genai.Client(api_key=config.GOOGLE_API_KEY)

    def _call(self, system_prompt: str, user_prompt: str, temperature: float = 0.4) -> str:
        response = self._client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
            ),
        )
        return response.text or ""

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> dict:
        raw = self._call(system_prompt, user_prompt, temperature)
        # Strip markdown fences if present
        match = _JSON_FENCE_RE.search(raw)
        json_str = match.group(1) if match else raw.strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Gemini returned invalid JSON: {exc}\nRaw response:\n{raw[:500]}"
            ) from exc

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.4,
    ) -> str:
        return self._call(system_prompt, user_prompt, temperature).strip()


# Singleton
gemini_client = GeminiClient()


class GeminiImageClient:
    def __init__(self) -> None:
        # NO http_options override — same as Imagen, works on SDK default.
        self._client = genai.Client(api_key=config.GOOGLE_API_KEY)

    def edit_expression(
        self,
        image_b64: str,
        instruction: str,
    ) -> str | None:
        """Edit a keyframe image to change the character's expression.

        Takes the previous keyframe as base64 JPEG and an instruction
        describing the target expression. Returns the edited image as
        base64 JPEG string, or None if no image was returned.

        Args:
            image_b64:   Base64-encoded JPEG string of the source image.
            instruction: Full instruction text (from SYSTEM_IMAGER + target emotion).

        Returns:
            Base64 JPEG string of the edited image, or None on failure.
        """
        logger.info(
            "Gemini Image: editing expression (instruction length=%d chars)",
            len(instruction),
        )

        try:
            response = self._client.models.generate_content(
                model=config.GEMINI_IMAGE_MODEL,
                contents=[
                    types.Content(
                        parts=[
                            # Input image
                            types.Part(
                                inline_data=types.Blob(
                                    mime_type="image/jpeg",
                                    data=image_b64,  # base64 string, not bytes
                                )
                            ),
                            # Instruction text
                            types.Part(text=instruction),
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    # MUST include TEXT alongside IMAGE.
                    # IMAGE alone causes model to return only a caption.
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )
        except Exception as exc:
            logger.error("Gemini Image API call failed: %s", exc)
            return None

        return _extract_image_b64(response, context="expression-edit")

    def generate_from_text(self, prompt: str) -> str | None:
        """Generate an image from a text prompt (fallback for Frame 0).

        Used when Imagen 3 is unavailable on the API key.

        Args:
            prompt: Full character description prompt.

        Returns:
            Base64 JPEG string, or None on failure.
        """
        logger.info("Gemini Image: text-to-image fallback (prompt=%d chars)", len(prompt))

        try:
            response = self._client.models.generate_content(
                model=config.GEMINI_IMAGE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )
        except Exception as exc:
            logger.error("Gemini Image text-to-image failed: %s", exc)
            return None

        return _extract_image_b64(response, context="text-to-image-fallback")


def _extract_image_b64(response, context: str) -> str | None:
    """Extract the first image part from a Gemini generate_content response.

    Handles both bytes and string base64 data in inline_data.
    Logs detailed debug info so failures are diagnosable.

    Returns base64-encoded JPEG string, or None if no image found.
    """
    candidates = getattr(response, "candidates", None) or []
    logger.debug(
        "Gemini Image [%s]: %d candidate(s) in response", context, len(candidates)
    )

    for ci, candidate in enumerate(candidates):
        finish_reason = getattr(candidate, "finish_reason", None)
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []

        logger.debug(
            "Gemini Image [%s]: candidate[%d] finish_reason=%s, %d part(s)",
            context, ci, finish_reason, len(parts),
        )

        for pi, part in enumerate(parts):
            inline = getattr(part, "inline_data", None)
            text = getattr(part, "text", None)

            if text:
                logger.debug(
                    "Gemini Image [%s]: candidate[%d].part[%d] text=%r",
                    context, ci, pi, text[:100],
                )

            if inline is not None:
                mime = getattr(inline, "mime_type", None)
                data = getattr(inline, "data", None)
                logger.debug(
                    "Gemini Image [%s]: candidate[%d].part[%d] inline_data "
                    "mime=%s data_type=%s data_len=%s",
                    context, ci, pi, mime,
                    type(data).__name__,
                    len(data) if data else 0,
                )

                if data:
                    # data can be bytes or already a base64 string
                    if isinstance(data, bytes):
                        return base64.b64encode(data).decode("utf-8")
                    # Already a base64 string
                    return data

    # Log prompt_feedback for safety block diagnosis
    feedback = getattr(response, "prompt_feedback", None)
    if feedback:
        logger.warning(
            "Gemini Image [%s]: prompt_feedback=%s (possible safety block)",
            context, feedback,
        )

    logger.warning(
        "Gemini Image [%s]: no image part found in response. "
        "Full response repr: %r",
        context, response,
    )
    return None


# Singleton
gemini_image_client = GeminiImageClient()