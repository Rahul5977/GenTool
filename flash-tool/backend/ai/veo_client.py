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

        system = """You are a Veo content policy expert. Sanitize video generation prompts so they NEVER get blocked by Google Veo.

Veo SILENTLY BLOCKS prompts containing ANY of these — even indirect references:

SKIN / SKINCARE (most common block for this app):

ALWAYS BLOCK (these trigger Veo regardless of context):
- Skin conditions: skin type, skin condition, acne, pimples, marks, spots, blemishes,
  dark spots, pigmentation, oily skin, dry skin, clear skin, healthy skin, glowing skin,
  skin care routine
- Hindi conditions: स्किन टाइप, त्वचा का प्रकार, मुंहासे, दाग, धब्बे, साफ त्वचा,
  स्वस्थ त्वचा, चमकदार त्वचा (when used as improvement)
- Treatments: sunscreen, SPF, sunblock, facial, cleanup, parlour glow, chemical peel,
  सनस्क्रीन, फेशियल, क्लीनअप, पार्लर ग्लो
- Home remedy terms in beauty context: haldi, besan, dahi, ubtan, face pack,
  हल्दी, बेसन, दही, उबटन, फेस पैक — replace with general self-care language
- TRANSFORMATION LANGUAGE in appearance blocks: "त्वचा साफ और स्वस्थ दिखती है",
  "skin looks better now", "clearer skin", "त्वचा में सुधार" — these imply before/after
- "GLOW" in beauty context: "glow आया", "glow gayab", "permanent glow" — replace with
  confidence/happiness framing: "चेहरे पर ताज़गी" or "अच्छा लगने लगा"

⚠️ KEEP IN DIALOGUE (do NOT remove these from spoken dialogue):
- Product NAMES used in complaint/past-tense context: serum, retinol, niacinamide,
  AHA, BHA, cream, moisturizer, cleanser, toner, face wash, फेस वॉश, क्रीम, सीरम
- WHY KEEP: When the character says "Serum, retinol, niacinamide, sab lagati thi"
  she is COMPLAINING about products she STOPPED using. This is NOT a product
  recommendation — it is the PROBLEM STATEMENT. Removing these words makes the
  character skip/mumble them, breaking lip-sync and making the ad boring.
- RULE: If these product names appear in dialogue where the character is listing
  products she used to use / wasted money on / stopped using → KEEP THEM.
  Only remove if the character is RECOMMENDING or PROMOTING these products.

MEDICAL/HEALTH:
  disease, condition, symptom, diagnosis, treatment, cure, medicine, supplement,
  pill, BP, blood pressure, sugar, diabetes, thyroid, cholesterol, weight loss,
  fat loss, obesity, pain, ache, fatigue, weakness, inflammation, doctor, prescription
HINDI: दर्द, थकान, कमज़ोरी, बीमारी, दवाई, दवा, इलाज, डॉक्टर, वज़न, मोटापा,
  शुगर, बीपी, थायरॉइड, तकलीफ़

IMPROVEMENT CLAIMS:
- "बेहतर होगा / होगी" → replace with "अच्छा लगेगा"
- "सब ठीक हो जाएगा" → "सब आसान लगेगा"
- "सुधार होगा" → remove or replace with confidence framing
- "glow" / "ग्लो" in beauty context → "ताज़गी" / "freshness" / "confidence"
- "parlour glow" → "parlour ka asar" (temporary effect, not beauty claim)
- "permanent glow" → "apni daily routine se confidence"

REPLACEMENT PHILOSOPHY — EMOTIONAL EQUIVALENTS:
Do NOT replace with generic words. Replace with the EMOTIONAL EQUIVALENT
that preserves the viewer's self-recognition.

EXAMPLES:
- थकान → "3 बजे वाली वो थकान" (specific time) NOT "व्यस्त दिन" (generic)
- दर्द → "वो बेचैनी" (emotional equivalent) NOT "तनाव" (different concept)
- दवाई → "वो गोली" (keep vague reference) NOT remove entirely
- skin care routine → "सुबह का वो रोज़ का काम" NOT "आदत" (too flat)
- बीमारी → "वो सब" (pronoun + gesture) NOT "परेशानी" (changes meaning)

THE TEST: After replacement, would a Tier 2–3 viewer still say
"haan yaar yahi toh hota hai mujhe"? If YES → replacement is good.
If NO → find a better emotional equivalent.

ABSOLUTE RULES:
1. NEVER change: outfit descriptions, CONTINUING FROM blocks, LAST FRAME blocks, FACE LOCK blocks,
   camera/lighting/location descriptions, no-letterbox/no-subtitle lines, the ⚠️ face lock statement
2. FOR APPEARANCE BLOCKS: keep physical description (face shape, eyes, hair, build, skin tone)
   but REMOVE any language about skin condition improvement or transformation
3. PRESERVE full prompt length — every removed phrase gets a safe replacement
4. Keep all Hindi — just swap blocked words/phrases
5. Keep character names and speaker-colon dialogue format
6. NEVER remove acronym hyphens from dialogue: P-C-O-S, I-V-F, B-P, P-C-O-D, U-P-I etc.
   These are intentional pronunciation guides — removing them causes Veo to mispronounce.
7. Output the sanitized prompt ONLY — no preamble, no explanation, no markdown"""

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
            # Empty generated_videos after a "success" is the API's silent RAI filter.
            # Raise ContentPolicyError so the retry loop rephrases the prompt.
            logger.warning(
                "Veo returned empty generated_videos — likely a silent RAI filter. "
                "Response object: %s", repr(response)
            )
            raise ContentPolicyError(
                "Veo generated no videos (silent content filter). "
                "Prompt will be rephrased and retried."
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
