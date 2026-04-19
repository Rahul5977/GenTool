"""Phase 4 — Parallel Video Generation.

Fires all Veo clip generations simultaneously via ThreadPoolExecutor,
collects results in order, and saves MP4 files to TMP_DIR.
"""

import base64
import logging
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from ..ai.veo_client import ContentPolicyError, veo_client
from ..ai.gemini_client import gemini_client
from .. import config
from ..models import ClipPrompt, KeyFrame

logger = logging.getLogger(__name__)

MAX_RETRIES = 6
_TRANSIENT_SLEEP_BASE = 30  # seconds; multiplied by attempt number, plus jitter


def generate_all_clips_parallel(
    keyframes: list[KeyFrame],
    clips: list[ClipPrompt],
    veo_model: str,
    aspect_ratio: str,
    job_id: str,
    progress_callback: Callable[[str, int, int], None],
) -> list[str]:
    """Generate all video clips in parallel using Veo.

    keyframes has N+1 entries; keyframes[i] is the first frame for clips[i],
    and keyframes[i+1] is the last frame for clips[i].

    Args:
        keyframes:         N+1 approved KeyFrame objects (first frame = index 0…N-1,
                           last frame = index 1…N).
        clips:             N verified ClipPrompt objects.
        veo_model:         Veo model ID string.
        aspect_ratio:      "9:16" or "16:9".
        job_id:            Job ID used for output file naming.
        progress_callback: Called as (clip_label, completed_count, total_count)
                           each time a clip finishes (success or retry).

    Returns:
        List of N absolute file paths to the saved MP4 clips, ordered by
        clip index (not arrival order).

    Raises:
        RuntimeError: If any clip fails after MAX_RETRIES attempts.
    """
    n = len(clips)
    if len(keyframes) < n + 1:
        raise ValueError(
            f"Expected {n + 1} keyframes for {n} clips, got {len(keyframes)}"
        )

    # Ensure output directory exists
    out_dir = os.path.join(config.TMP_DIR, job_id)
    os.makedirs(out_dir, exist_ok=True)

    # Results slot — indexed by clip position (0-based)
    results: list[str | None] = [None] * n
    errors: list[Exception | None] = [None] * n

    completed_count = 0

    with ThreadPoolExecutor(max_workers=n) as executor:
        future_to_index = {
            executor.submit(
                generate_single_clip,
                clip_index=i,
                clip_number=clip.clip_number,
                total=n,
                prompt=clip.prompt,
                first_frame=keyframes[i],
                last_frame=keyframes[i + 1],
                veo_model=veo_model,
                aspect_ratio=aspect_ratio,
                job_id=job_id,
            ): i
            for i, clip in enumerate(clips)
        }

        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            clip_label = f"clip_{clips[idx].clip_number:02d}"
            try:
                path = future.result()
                results[idx] = path
                logger.info("Phase 4: %s done → %s", clip_label, path)
            except Exception as exc:
                errors[idx] = exc
                logger.error("Phase 4: %s FAILED — %s", clip_label, exc)

            completed_count += 1
            progress_callback(clip_label, completed_count, n)

    # Surface failures as a single aggregated error
    failed = [(i, e) for i, e in enumerate(errors) if e is not None]
    if failed:
        messages = [
            f"  clip_{clips[i].clip_number:02d}: {e}" for i, e in failed
        ]
        raise RuntimeError(
            f"Phase 4 failed for {len(failed)}/{n} clips:\n" + "\n".join(messages)
        )

    return results  # type: ignore[return-value]  # all slots guaranteed filled


def generate_single_clip(
    clip_index: int,
    clip_number: int,
    total: int,
    prompt: str,
    first_frame: KeyFrame,
    last_frame: KeyFrame,
    veo_model: str,
    aspect_ratio: str,
    job_id: str,
) -> str:
    """Generate one video clip with retry logic.

    Args:
        clip_index:   0-based index (used for file naming and keyframe lookup).
        clip_number:  1-based clip number from the brief (for logging).
        total:        Total number of clips (for logging context).
        prompt:       Full Veo prompt string.
        first_frame:  KeyFrame for image conditioning start.
        last_frame:   KeyFrame for image conditioning end.
        veo_model:    Veo model ID.
        aspect_ratio: "9:16" or "16:9".
        job_id:       Job ID for output path.

    Returns:
        Absolute path to the saved MP4 file.

    Raises:
        RuntimeError: After MAX_RETRIES exhausted without a successful generation.
    """
    out_dir = os.path.join(config.TMP_DIR, job_id)
    out_path = os.path.join(out_dir, f"clip_{clip_number:02d}.mp4")

    current_prompt = _strip_rephrase_markers(prompt)
    last_exc: Exception = RuntimeError("No attempts made")
    attempts_made = 0

    for attempt in range(1, MAX_RETRIES + 1):
        attempts_made = attempt
        logger.info(
            "Phase 4: clip %d/%d — attempt %d/%d", clip_number, total, attempt, MAX_RETRIES
        )
        try:
            # Step 1 — sanitize block words (never send internal markers to Veo/Gemini sanitize)
            sanitized = veo_client.sanitize_prompt(_strip_rephrase_markers(current_prompt))

            # Step 2 — generate via Veo
            mp4_bytes = veo_client.generate_clip(
                prompt=sanitized,
                first_frame_bytes=base64.b64decode(first_frame.image_b64),
                last_frame_bytes=base64.b64decode(last_frame.image_b64),
                aspect_ratio=aspect_ratio,
                model=veo_model,
            )

            # Step 3 — persist to disk
            with open(out_path, "wb") as fh:
                fh.write(mp4_bytes)

            logger.info(
                "Phase 4: clip %d saved (%d bytes) → %s",
                clip_number, len(mp4_bytes), out_path,
            )
            return out_path

        except ContentPolicyError as exc:
            last_exc = exc
            logger.warning(
                "Phase 4: clip %d — RAI/content block on attempt %d: %s",
                clip_number, attempt, exc,
            )
            if attempt < MAX_RETRIES:
                logger.info("Phase 4: clip %d — rephrasing prompt after content block", clip_number)
                current_prompt = _rephrase_blocked_prompt(current_prompt, str(exc), attempt)
            # No sleep needed for content policy — rephrase is immediate

        except Exception as exc:
            last_exc = exc
            is_transient = _is_transient(exc)
            logger.warning(
                "Phase 4: clip %d — %s error on attempt %d: %s",
                clip_number, "transient" if is_transient else "non-transient", attempt, exc,
            )
            if is_transient and attempt < MAX_RETRIES:
                jitter = random.uniform(0, 15)
                sleep_sec = _TRANSIENT_SLEEP_BASE * attempt + jitter
                logger.info(
                    "Phase 4: clip %d sleeping %.0fs before retry (attempt %d/%d)",
                    clip_number, sleep_sec, attempt, MAX_RETRIES,
                )
                time.sleep(sleep_sec)
            elif not is_transient:
                # Non-transient errors won't improve with retries
                logger.warning("Phase 4: clip %d — non-transient error, stopping retries", clip_number)
                break

    msg = str(last_exc)
    hint = ""
    if isinstance(last_exc, ContentPolicyError) or "silent content filter" in msg.lower():
        hint = (
            " Veo applied a silent safety filter (no video returned). "
            "Open prompt review for this clip, soften or remove medical / sexual-health / "
            "weight-or-skin outcome language in DIALOGUE and ACTION, save, then use "
            "Regenerate clip on the result page."
        )
    raise RuntimeError(
        f"clip_{clip_number:02d} failed after {attempts_made} attempt(s). "
        f"Last error: {last_exc}.{hint}"
    ) from last_exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPHRASE_MARKER = "__REPHRASE_ATTEMPT__"


def _strip_rephrase_markers(text: str) -> str:
    """Remove legacy internal markers so they are never sent to Veo."""
    if _REPHRASE_MARKER not in text:
        return text.strip()
    return text.replace(_REPHRASE_MARKER, "").strip()


def _is_transient(exc: Exception) -> bool:
    """Return True for errors that may resolve on retry (503, timeout, etc.)."""
    msg = str(exc).lower()
    transient_signals = (
        "503",
        "429",
        "timeout",
        "timed out",
        "temporarily unavailable",
        "service unavailable",
        "unavailable",
        "high demand",
        "connection",
        "reset by peer",
        "overloaded",
        # Veo occasionally returns code 13 for backend/internal errors.
        # These are usually transient and should be retried.
        "internal server issue",
        "video generation failed due to an internal server issue",
        "code': 13",
        "code\": 13",
    )
    return any(s in msg for s in transient_signals)


def _rephrase_blocked_prompt(prompt: str, block_reason: str, attempt: int) -> str:
    """Use Gemini to rephrase a RAI-blocked Veo prompt.

    Applies aggressive content-safe rephrasing using emotional equivalents
    while preserving structural sections (FACE LOCK, CAMERA, AUDIO, etc.) verbatim.
    """
    clean_prompt = _strip_rephrase_markers(prompt)

    system = """You are a Veo content policy expert. Sanitize video generation prompts so they NEVER get blocked by Google Veo.

Veo SILENTLY BLOCKS prompts containing ANY of these — even indirect references:

BLOCKED TRIGGERS TO ELIMINATE:
- Skin conditions: स्किन टाइप, त्वचा का प्रकार, साफ/स्वस्थ त्वचा, मुंहासे, दाग, चमकदार त्वचा
- Improvement claims: बेहतर होगा, सुधार होगा, सब ठीक होगा, will get better
- Treatments/recommendations: sunscreen, सनस्क्रीन, SPF, sunblock, facial, cleanup, फेशियल, क्लीनअप
- Home remedies (beauty): haldi, besan, dahi, ubtan, हल्दी, बेसन, दही, उबटन, face pack
- Glow (beauty): glow, parlour glow, permanent glow, ग्लो, पार्लर ग्लो, chemical glow
- Health: थकान, दर्द, कमज़ोरी, बीमारी, दवाई, वज़न, BP, sugar, diabetes
- Before/after: transformation language, physical improvement comparisons

⚠️ DO NOT REMOVE from dialogue (keep these spoken words intact):
- Product names in COMPLAINT/PAST-TENSE context: serum, retinol, niacinamide,
  AHA, BHA, cream, moisturizer, face wash, फेस वॉश, क्रीम, सीरम
- When character says 'serum, retinol sab lagati thi' she is complaining
  about products she STOPPED using. This is the problem statement, not a recommendation.
- Removing these words breaks lip-sync and makes dialogue nonsensical.

REPLACEMENTS:
- स्किन टाइप समझ → अपनी दिनचर्या समझ
- बेहतर होगा → आसान होगा / अच्छा लगेगा
- त्वचा साफ/स्वस्थ → चेहरे पर ताज़गी है
- साफ त्वचा → आत्मविश्वासी चेहरा
- sunscreen roz → apna routine follow karo / din ki shuruaat ache se karo
- हल्दी बेसन दही → घर पर अपनी दिनचर्या / apna ek chhota sa kaam
- glow/ग्लो → ताज़गी/freshness/confidence/अच्छा लगना
- parlour glow chemical → parlour ka asar temporary
- थकान→3 बजे वाली वो थकान (specific), दर्द→वो बेचैनी, कमज़ोरी→नई ऊर्जा, वज़न→आत्मविश्वास

THE TEST: After replacement, would a Tier 2–3 viewer still say
"haan yaar yahi toh hota hai mujhe"? If YES → replacement is good.
If NO → find a better emotional equivalent.

MUST KEEP EXACTLY AS-IS:
- Outfit + full physical appearance description
- ⚠️ FACE LOCK statement and ⚠️ चेहरा पूरी तरह स्थिर lines
- CONTINUING FROM: block
- LAST FRAME: block
- Camera / lighting / location lines
- No-letterbox / no-subtitle lines
- NEVER remove acronym hyphens: P-C-O-S, I-V-F, B-P, P-C-O-D

Output the rewritten prompt ONLY — no preamble, no explanation."""

    extra = ""
    if attempt >= 4:
        extra = (
            "\n\nThis is a high-attempt rephrase: aggressively simplify DIALOGUE lines "
            "that mention illness, treatment, sexual health, weight change, or "
            "skin improvement — use vague emotional Hindi the same syllable count "
            "where possible so lip-sync still works."
        )

    user_message = (
        f"This Veo prompt was BLOCKED by safety policy. "
        f"Aggressive rephrase attempt {attempt}. Block reason: {block_reason}\n\n"
        f"ORIGINAL BLOCKED PROMPT:\n{clean_prompt}"
        f"{extra}"
    )

    try:
        rephrased = gemini_client.generate_text(
            system_prompt=system,
            user_prompt=user_message,
            temperature=0.3,
        )
        logger.info("Phase 4: prompt rephrased after RAI block (attempt %d)", attempt)
        return _strip_rephrase_markers(rephrased)
    except Exception as exc:
        logger.warning("Phase 4: prompt rephrase failed (%s) — using cleaned original", exc)
        return clean_prompt
