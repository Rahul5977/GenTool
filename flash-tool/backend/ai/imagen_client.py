import logging

from google import genai
from google.genai import types

from .. import config

logger = logging.getLogger(__name__)


class ImagenClient:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=config.GOOGLE_API_KEY)

    def generate_character_image(self, prompt: str) -> bytes:
        """Generate an initial character reference image via Imagen 3.

        Args:
            prompt: Full Imagen prompt built from IMAGEN_PROMPT_TEMPLATE.

        Returns:
            Raw JPEG bytes of the generated image.

        Raises:
            RuntimeError: If the API returns no images or an unexpected error.
        """
        try:
            response = self._client.models.generate_images(
                model=config.IMAGEN_MODEL,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    aspect_ratio="9:16",
                    number_of_images=1,
                ),
            )
        except Exception as exc:
            raise RuntimeError(f"Imagen generation failed: {exc}") from exc

        images = response.generated_images
        if not images:
            raise RuntimeError(
                "Imagen returned no images — the prompt may have been blocked."
            )

        image_bytes = images[0].image.image_bytes
        if not image_bytes:
            raise RuntimeError("Imagen returned an image with no byte content.")

        logger.info("Imagen character image generated (%d bytes)", len(image_bytes))
        return image_bytes


# Singleton
imagen_client = ImagenClient()
