import logging
import time

import httpx
from google import genai
from google.genai import types

from .. import config

logger = logging.getLogger(__name__)

_ALLOWED_ASPECT_RATIOS = {"9:16", "16:9"}
_POLL_INTERVAL_SEC = 10
_TIMEOUT_SEC = 360

# Veo block words: English and Hindi/Hinglish equivalents
_BLOCK_WORDS = [
    "skin type", "त्वचा का प्रकार",
    "acne", "pimples", "मुंहासे", "दाने",
    "weight loss", "वज़न कम", "वजन कम",
    "transformation", "before/after", "before after",
    "doctor", "medicine", "medication", "दवा",
    "diabetes", "diabetic", "मधुमेह",
    "blood pressure", "BP", "hypertension",
    "surgery", "operation", "treatment", "therapy", "cure",
    "guaranteed", "clinically proven", "results",
]


class ContentPolicyError(Exception):
    """Raised when Veo rejects a generation due to safety/RAI filters."""


class VeoClient:
    def __init__(self) -> None:
        self._client = genai.Client(
            api_key=config.GOOGLE_API_KEY,
            http_options={"api_version": "v1alpha"},
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_clip(
        self,
        prompt: str,
        first_frame_bytes: bytes,
        last_frame_bytes: bytes,
        aspect_ratio: str = "9:16",
        model: str = config.VEO_MODEL,
    ) -> bytes:
        """Generate a video clip using Veo with image conditioning.

        Args:
            prompt:            Fully-formed Veo prompt string (Hindi).
            first_frame_bytes: JPEG bytes for the first frame image condition.
            last_frame_bytes:  JPEG bytes for the last frame image condition.
            aspect_ratio:      "9:16" (default) or "16:9".
            model:             Veo model ID (default from config).

        Returns:
            Raw MP4 bytes of the generated clip.

        Raises:
            ValueError:         If aspect_ratio is not supported.
            ContentPolicyError: If Veo's RAI filter blocks the generation.
            RuntimeError:       On timeout, empty response, or download failure.
        """
        if aspect_ratio not in _ALLOWED_ASPECT_RATIOS:
            raise ValueError(
                f"Unsupported aspect_ratio '{aspect_ratio}'. "
                f"Must be one of: {_ALLOWED_ASPECT_RATIOS}"
            )

        first_frame = types.Image(
            image_bytes=first_frame_bytes,
            mime_type="image/jpeg",
        )
        last_frame = types.Image(
            image_bytes=last_frame_bytes,
            mime_type="image/jpeg",
        )
        video_config = types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio,
            number_of_videos=1,
            resolution="1080p",
            enhance_prompt=True,
            last_frame=last_frame,
        )

        logger.info("Submitting Veo generation request (model=%s)", model)
        try:
            operation = self._client.models.generate_videos(
                model=model,
                prompt=prompt,
                image=first_frame,
                config=video_config,
            )
        except Exception as exc:
            raise RuntimeError(f"Veo API call failed: {exc}") from exc

        # ------------------------------------------------------------------
        # Poll until done or timeout
        # ------------------------------------------------------------------
        elapsed = 0
        while not operation.done:
            if elapsed >= _TIMEOUT_SEC:
                raise RuntimeError(
                    f"Veo generation timed out after {_TIMEOUT_SEC}s"
                )
            logger.debug("Veo operation in progress… (%ds elapsed)", elapsed)
            time.sleep(_POLL_INTERVAL_SEC)
            elapsed += _POLL_INTERVAL_SEC
            operation = self._client.operations.get(operation)

        # ------------------------------------------------------------------
        # Check for RAI / safety blocks
        # ------------------------------------------------------------------
        self._check_rai(operation)

        # ------------------------------------------------------------------
        # Extract video URI and download
        # ------------------------------------------------------------------
        generated = self._extract_generated_videos(operation)
        video_uri = generated[0].video.uri
        if not video_uri:
            raise RuntimeError("Veo returned a video entry with no URI.")

        logger.info("Veo generation complete — downloading from URI")
        return self._download_video(video_uri)

    def sanitize_prompt(self, prompt: str) -> str:
        """Remove Veo block words from a prompt using Gemini Flash.

        Args:
            prompt: Raw Veo prompt that may contain blocked terms.

        Returns:
            Sanitized prompt with blocked words replaced by safe alternatives.
        """
        # Fast path: check if any block word is present before calling API
        prompt_lower = prompt.lower()
        if not any(w.lower() in prompt_lower for w in _BLOCK_WORDS):
            return prompt

        from .gemini_client import gemini_client  # local import to avoid circularity

        system = (
            "You are a Veo prompt sanitizer. Remove or replace any of these blocked "
            "terms with safe, neutral alternatives that preserve meaning:\n"
            + ", ".join(_BLOCK_WORDS)
            + "\n\nReplacement guidelines:\n"
            "- 'skin type / त्वचा का प्रकार' → 'त्वचा की देखभाल'\n"
            "- 'acne / pimples / मुंहासे' → 'चेहरे की समस्या'\n"
            "- 'weight loss / वज़न कम' → 'बेहतर महसूस करना'\n"
            "- 'transformation / before/after' → 'बदलाव'\n"
            "- 'doctor / medicine / दवा' → omit or 'सलाह'\n"
            "- 'diabetes / BP / hypertension' → omit entirely\n"
            "- 'surgery / treatment / cure' → 'देखभाल'\n"
            "- 'guaranteed / clinically proven' → omit\n\n"
            "Return ONLY the corrected prompt. No explanation. No commentary."
        )
        return gemini_client.generate_text(
            system_prompt=system,
            user_prompt=prompt,
            temperature=0.1,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_rai(operation) -> None:
        """Raise ContentPolicyError if the operation was blocked by RAI filters."""
        # The RAI block surfaces differently depending on SDK version; check both.
        response = getattr(operation, "response", None)
        if response is None:
            raise RuntimeError("Veo operation completed but has no response object.")

        # Some SDK versions surface a top-level blocked flag
        if getattr(response, "blocked", False):
            raise ContentPolicyError(
                "Veo generation blocked by content policy (RAI filter)."
            )

        # Others surface it per-video
        videos = getattr(response, "generated_videos", None) or []
        for v in videos:
            if getattr(v, "rai_media_filtered_reason", None):
                raise ContentPolicyError(
                    f"Veo RAI filter blocked the clip: {v.rai_media_filtered_reason}"
                )

    @staticmethod
    def _extract_generated_videos(operation) -> list:
        response = getattr(operation, "response", None)
        videos = getattr(response, "generated_videos", None) or []
        if not videos:
            raise RuntimeError(
                "Veo returned no generated videos despite reporting success."
            )
        return videos

    @staticmethod
    def _download_video(uri: str) -> bytes:
        """Download the video from the Veo-provided URI, injecting the API key."""
        headers = {"X-Goog-Api-Key": config.GOOGLE_API_KEY}
        try:
            response = httpx.get(uri, headers=headers, timeout=120, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Failed to download Veo video: {exc}") from exc

        content = response.content
        if not content:
            raise RuntimeError("Downloaded video file is empty.")

        logger.info("Video downloaded (%d bytes)", len(content))
        return content


# Singleton
veo_client = VeoClient()
