"""Phase 4 — Parallel Video Generation.

Fires all Veo clip generations simultaneously via ThreadPoolExecutor,
collects results in order, and saves MP4 files to TMP_DIR.
"""

import base64
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from ..ai.veo_client import ContentPolicyError, veo_client
from ..ai.gemini_client import gemini_client
from .. import config
from ..models import ClipPrompt, KeyFrame

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
_TRANSIENT_SLEEP_BASE = 15  # seconds; multiplied by attempt number


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

    current_prompt = prompt
    last_exc: Exception = RuntimeError("No attempts made")

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info(
            "Phase 4: clip %d/%d — attempt %d/%d", clip_number, total, attempt, MAX_RETRIES
        )
        try:
            # Step 1 — sanitize block words
            sanitized = veo_client.sanitize_prompt(current_prompt)

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
                "Phase 4: clip %d — RAI block on attempt %d: %s",
                clip_number, attempt, exc,
            )
            if attempt < MAX_RETRIES:
                current_prompt = _rephrase_blocked_prompt(current_prompt, str(exc))

        except Exception as exc:
            last_exc = exc
            is_transient = _is_transient(exc)
            logger.warning(
                "Phase 4: clip %d — %s error on attempt %d: %s",
                clip_number, "transient" if is_transient else "non-transient", attempt, exc,
            )
            if is_transient and attempt < MAX_RETRIES:
                sleep_sec = _TRANSIENT_SLEEP_BASE * attempt
                logger.info("Phase 4: sleeping %ds before retry", sleep_sec)
                time.sleep(sleep_sec)
            elif not is_transient:
                # Non-transient errors (e.g. bad request) won't improve with retries
                break

    raise RuntimeError(
        f"clip_{clip_number:02d} failed after {MAX_RETRIES} attempts. "
        f"Last error: {last_exc}"
    ) from last_exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_transient(exc: Exception) -> bool:
    """Return True for errors that may resolve on retry (503, timeout, etc.)."""
    msg = str(exc).lower()
    transient_signals = ("503", "timeout", "timed out", "temporarily unavailable",
                         "service unavailable", "connection", "reset by peer")
    return any(s in msg for s in transient_signals)


def _rephrase_blocked_prompt(prompt: str, block_reason: str) -> str:
    """Use Gemini to rephrase a RAI-blocked Veo prompt.

    Only the ACTION and DIALOGUE blocks are rephrased; structural sections
    (FACE LOCK, CAMERA, AUDIO, etc.) are preserved verbatim.
    """
    system = (
        "A Veo video generation prompt was blocked by a content safety filter. "
        "Rephrase the ACTION and DIALOGUE sections to remove anything that could "
        "trigger safety filters while preserving the emotional intent. "
        "Return the complete prompt with all other sections unchanged. "
        f"Block reason: {block_reason}"
    )
    try:
        rephrased = gemini_client.generate_text(
            system_prompt=system,
            user_prompt=prompt,
            temperature=0.3,
        )
        logger.info("Phase 4: prompt rephrased after RAI block")
        return rephrased
    except Exception as exc:
        logger.warning("Phase 4: prompt rephrase failed (%s) — using original", exc)
        return prompt
