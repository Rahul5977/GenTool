"""Imagen 3 client — generates the initial character reference image (Frame 0).

WHY THIS EXISTS SEPARATELY FROM gemini_image_client:
  - Imagen 3 is a dedicated text-to-image model. It generates a character
    from a text prompt with no input image.
  - Gemini Flash Image is an image-editing model. It takes an existing image
    and modifies the expression. Used for Frames 1..N.
  - They use different APIs, different configs, different capabilities.

API VERSION NOTE:
  - Imagen 3 works on the DEFAULT SDK version (v1beta).
  - Do NOT set http_options api_version — any override breaks it.
  - Model string must be bare: "imagen-3.0-generate-001" (no "models/" prefix).
"""

import logging

from google import genai
from google.genai import types

from .. import config

logger = logging.getLogger(__name__)


class ImagenClient:
    def __init__(self) -> None:
        # NO http_options override — Imagen 3 works on SDK default (v1beta).
        # Adding api_version="v1" breaks it (systemInstruction field error).
        # Adding api_version="v1alpha" also breaks it (404).
        # Leave it as default.
        self._client = genai.Client(api_key=config.GOOGLE_API_KEY)

    def generate_character_image(self, prompt: str) -> bytes:
        """Generate an initial character reference image via Imagen 3.

        This is called ONCE per job to create Frame 0 — the anchor face
        that all subsequent Gemini Image edits will be based on.

        Args:
            prompt: Full Imagen prompt built from IMAGEN_PROMPT_TEMPLATE.
                    Must NOT contain any blocked terms (skin conditions,
                    medical claims, weight loss, etc).

        Returns:
            Raw JPEG bytes of the generated image.

        Raises:
            RuntimeError: If the API returns an error, no images, or empty bytes.
        """
        # Sanitize prompt — remove any words that trigger Imagen safety filters
        clean_prompt = _sanitize_imagen_prompt(prompt)

        logger.info(
            "Imagen 3: generating character reference (prompt length=%d chars)",
            len(clean_prompt),
        )

        try:
            response = self._client.models.generate_images(
                model=config.IMAGEN_MODEL,  # must be "imagen-3.0-generate-001", no "models/" prefix
                prompt=clean_prompt,
                config=types.GenerateImagesConfig(
                    aspect_ratio="9:16",
                    number_of_images=1,
                ),
            )
        except Exception as exc:
            raise RuntimeError(f"Imagen generation failed: {exc}") from exc

        # SDK returns GenerateImagesResponse with .generated_images list
        images = getattr(response, "generated_images", None) or []
        if not images:
            raise RuntimeError(
                "Imagen returned no images. Possible causes:\n"
                "  1. Prompt contains blocked terms (skin, acne, weight, medical)\n"
                "  2. IMAGEN_MODEL in .env has 'models/' prefix — remove it\n"
                "  3. API key does not have Imagen 3 access\n"
                f"  Model used: {config.IMAGEN_MODEL}"
            )

        image_obj = images[0].image
        image_bytes = getattr(image_obj, "image_bytes", None)
        if not image_bytes:
            raise RuntimeError(
                "Imagen returned an image object with no byte content."
            )

        logger.info(
            "Imagen 3: character image generated successfully (%d bytes)",
            len(image_bytes),
        )
        return image_bytes


def _sanitize_imagen_prompt(prompt: str) -> str:
    """Remove words that trigger Imagen 3 safety filters.

    Imagen 3 is stricter than Veo. These terms cause silent rejections
    (returns no images instead of an error).
    """
    # Terms that cause Imagen to return 0 images silently
    BLOCKED = [
        "acne", "pimples", "मुंहासे", "दाने",
        "skin condition", "skin problem", "skin type",
        "weight loss", "वज़न कम", "obesity", "overweight",
        "diabetes", "blood pressure", "BP", "hypertension",
        "medicine", "medication", "treatment", "cure", "therapy",
        "before after", "transformation", "results guaranteed",
        "wrinkles", "झुर्रियां", "dark spots", "pigmentation",
        "blemish", "scar", "marks on face",
    ]
    cleaned = prompt
    for term in BLOCKED:
        if term.lower() in cleaned.lower():
            logger.warning("Imagen prompt: removing blocked term '%s'", term)
            # Replace with empty string — surrounding context handles grammar
            import re
            cleaned = re.sub(re.escape(term), "", cleaned, flags=re.IGNORECASE)

    # Collapse multiple spaces/newlines left by removals
    import re
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


# Singleton — imported by phase3_imager
imagen_client = ImagenClient()