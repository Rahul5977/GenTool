"""Pipeline Orchestrator.

Runs all 5 phases sequentially in a background thread, updating the job
store and emitting SSE events at every milestone.

Public surface used by main.py:
  run_pipeline(job_id, request)   — start in threading.Thread
  emit_event(job_id, type, data)  — push an event onto the SSE queue
  _job_event_queues               — SSE endpoint reads from this
  _approval_events                — /approve endpoint signals this
  _approval_data                  — /approve endpoint writes here
"""

import logging
import os
import threading
from typing import Any

from .. import config
from ..job_store import job_store
from ..models import (
    CreateJobRequest,
    JobStatus,
    KeyFrame,
    PipelinePhase,
)
from ..pipeline.phase1_analyser import analyse_script
from ..pipeline.phase2_prompter import generate_prompts
from ..pipeline.phase3_imager import generate_keyframes
from ..pipeline.phase4_generator import generate_all_clips_parallel
from ..pipeline.phase5_stitcher import stitch_and_finalize

logger = logging.getLogger(__name__)

# ── SSE event storage ────────────────────────────────────────────────────────
# Keyed by job_id. Append-only list of {"type": str, "data": dict} entries.
# The SSE endpoint in main.py polls this list.
_job_event_queues: dict[str, list[dict]] = {}

# ── Prompt approval signals (Phase 2 → Phase 3 gate) ─────────────────────────
# Human reviews/edits clip prompts before image generation starts.
_prompt_approval_events: dict[str, threading.Event] = {}

# ── Image approval signals (Phase 3 → Phase 4 gate) ──────────────────────────
# Orchestrator blocks on _approval_events[job_id].wait().
# The /approve endpoint stores the request body then sets the event.
_approval_events: dict[str, threading.Event] = {}
_approval_data: dict[str, Any] = {}   # stores ApproveImagesRequest


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def emit_event(job_id: str, event_type: str, data: dict) -> None:
    """Append an SSE event to the job's queue."""
    _job_event_queues.setdefault(job_id, []).append(
        {"type": event_type, "data": data}
    )


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline(job_id: str, request: CreateJobRequest) -> None:
    """Execute the full 5-phase pipeline for a job.

    Designed to run inside a daemon threading.Thread.  Updates job_store and
    emits SSE events at every milestone.  Any unhandled exception transitions
    the job to FAILED.

    Pipeline flow:
      Phase 1 → Phase 2 → [HUMAN PROMPT REVIEW] → Phase 3 → [HUMAN IMAGE REVIEW] → Phase 4 → Phase 5
    """
    # Ensure SSE queue and both approval events exist before anything can race
    _job_event_queues.setdefault(job_id, [])
    _prompt_approval_events[job_id] = threading.Event()
    _approval_events[job_id] = threading.Event()

    try:
        _phase1(job_id, request)
        _phase2(job_id)
        _wait_for_prompt_approval(job_id)   # ← NEW: human edits/approves clip prompts
        _phase3(job_id)
        _wait_for_approval(job_id)
        _phase4(job_id, request)
        _phase5(job_id, request)

    except Exception as exc:
        logger.exception("Pipeline FAILED for job %s: %s", job_id, exc)
        job_store.set_status(job_id, JobStatus.FAILED, error=str(exc))
        emit_event(job_id, "error", {"message": str(exc)})

    finally:
        # Clean up approval state to free memory
        _prompt_approval_events.pop(job_id, None)
        _approval_events.pop(job_id, None)
        _approval_data.pop(job_id, None)


# ---------------------------------------------------------------------------
# Phase implementations
# ---------------------------------------------------------------------------

def _phase1(job_id: str, request: CreateJobRequest) -> None:
    job_store.set_status(
        job_id, JobStatus.ANALYSING, phase=PipelinePhase.PHASE_1, progress=5
    )
    emit_event(job_id, "phase_start", {"phase": 1, "message": "Analysing script..."})

    brief = analyse_script(request.script, request.num_clips, request.coach)
    job_store.update(job_id, production_brief=brief)

    char = brief.character
    emit_event(job_id, "phase_done", {
        "phase": 1,
        "character": {
            "age": char.age,
            "gender": char.gender,
            "skin_tone": char.skin_tone,
            "skin_hex": char.skin_hex,
            "face_shape": char.face_shape,
            "hair": char.hair,
            "outfit": char.outfit,
            "accessories": char.accessories,
            "distinguishing_marks": char.distinguishing_marks,
        },
        "setting": brief.setting,
        "background": brief.locked_background,
        "coach": brief.coach,
        "num_clips": len(brief.clips),
    })
    logger.info("Job %s: Phase 1 complete", job_id)


def _phase2(job_id: str) -> None:
    job = job_store.get(job_id)
    brief = job.production_brief  # type: ignore[union-attr]

    job_store.set_status(
        job_id, JobStatus.PROMPTING, phase=PipelinePhase.PHASE_2, progress=20
    )
    emit_event(job_id, "phase_start", {"phase": 2, "message": "Generating clip prompts..."})

    clips = generate_prompts(brief)
    job_store.update(job_id, clips=clips)

    emit_event(job_id, "phase_done", {
        "phase": 2,
        "clips": [
            {
                "clip_number": c.clip_number,
                "duration_seconds": c.duration_seconds,
                "scene_summary": c.scene_summary,
                "dialogue": c.dialogue,
                "word_count": c.word_count,
                "end_emotion": c.end_emotion,
                "verified": c.verified,
                "verification_issues": c.verification_issues,
                "prompt_preview": c.prompt[:500],
            }
            for c in clips
        ],
    })
    logger.info("Job %s: Phase 2 complete (%d clips)", job_id, len(clips))

    # Transition to prompt review state — human edits prompts before images are generated
    job_store.set_status(job_id, JobStatus.AWAITING_PROMPT_REVIEW, phase=PipelinePhase.PHASE_2_REVIEW, progress=30)
    emit_event(job_id, "awaiting_prompt_review", {"num_clips": len(clips)})


def _phase3(job_id: str) -> None:
    job = job_store.get(job_id)
    brief = job.production_brief  # type: ignore[union-attr]
    clips = job.clips

    job_store.set_status(
        job_id, JobStatus.IMAGING, phase=PipelinePhase.PHASE_3, progress=35
    )
    emit_event(job_id, "phase_start", {"phase": 3, "message": "Generating keyframes..."})

    # Accumulate keyframes incrementally and update store + emit SSE after each
    accumulated: list[KeyFrame] = []

    def _on_keyframe(frame: KeyFrame, total: int) -> None:
        accumulated.append(frame)
        job_store.update(job_id, keyframes=list(accumulated))
        emit_event(job_id, "keyframe_ready", {
            "index": frame.index,
            "total": total,
            "preview_url": f"/api/v2/keyframe/{job_id}/{frame.index}",
        })
        logger.info("Job %s: keyframe %d/%d ready", job_id, frame.index + 1, total)

    generate_keyframes(brief, clips, on_keyframe=_on_keyframe)

    job_store.set_status(job_id, JobStatus.AWAITING, progress=50)
    num_images = len(accumulated)
    emit_event(job_id, "awaiting_approval", {"num_images": num_images})
    logger.info("Job %s: Phase 3 complete — awaiting approval for %d images", job_id, num_images)


def _wait_for_prompt_approval(job_id: str) -> None:
    """Block the pipeline thread until the /approve-prompts endpoint fires the event.

    During this pause, the operator can call PUT /jobs/{job_id}/clips/{clip_index}
    to update individual clip prompts before image generation begins.
    """
    logger.info("Job %s: waiting for prompt review/approval…", job_id)
    event = _prompt_approval_events.get(job_id)
    if event:
        event.wait()  # indefinite — UI drives this
    logger.info("Job %s: prompt approval received — proceeding to Phase 3", job_id)


def _wait_for_approval(job_id: str) -> None:
    """Block the pipeline thread until the /approve endpoint fires the event."""
    logger.info("Job %s: waiting for operator approval…", job_id)
    event = _approval_events.get(job_id)
    if event:
        event.wait()  # indefinite — UI drives this

    # Apply approved flags to keyframes in the store
    approval = _approval_data.get(job_id)
    if approval:
        job = job_store.get(job_id)
        if job:
            keyframes = list(job.keyframes)
            for idx in approval.approved_indices:
                if 0 <= idx < len(keyframes):
                    keyframes[idx].approved = True
            job_store.update(job_id, keyframes=keyframes)

    logger.info("Job %s: approval received — proceeding to Phase 4", job_id)


def _phase4(job_id: str, request: CreateJobRequest) -> None:
    job = job_store.get(job_id)
    keyframes = job.keyframes  # type: ignore[union-attr]
    clips = job.clips

    completed = [0]  # mutable counter for closure

    job_store.set_status(
        job_id, JobStatus.GENERATING, phase=PipelinePhase.PHASE_4, progress=55
    )
    emit_event(job_id, "phase_start", {"phase": 4, "message": "Generating video clips..."})

    def _progress_callback(clip_label: str, done: int, total: int) -> None:
        completed[0] = done
        new_progress = 55 + int(40 * done / total)
        job_store.set_status(job_id, JobStatus.GENERATING, progress=new_progress)
        emit_event(job_id, "clip_done", {
            "clip": clip_label,
            "completed": done,
            "total": total,
        })

    clip_paths = generate_all_clips_parallel(
        keyframes=keyframes,
        clips=clips,
        veo_model=request.veo_model,
        aspect_ratio=request.aspect_ratio,
        job_id=job_id,
        progress_callback=_progress_callback,
    )
    job_store.update(job_id, clip_paths=clip_paths)

    emit_event(job_id, "phase_done", {"phase": 4})
    logger.info("Job %s: Phase 4 complete (%d clips)", job_id, len(clip_paths))


def _phase5(job_id: str, request: CreateJobRequest) -> None:
    job = job_store.get(job_id)
    clip_paths = job.clip_paths  # type: ignore[union-attr]

    job_store.set_status(
        job_id, JobStatus.STITCHING, phase=PipelinePhase.PHASE_5, progress=95
    )
    emit_event(job_id, "phase_start", {"phase": 5, "message": "Stitching final video..."})

    output_path = os.path.join(config.TMP_DIR, job_id, "final.mp4")
    final_path = stitch_and_finalize(
        clip_paths=clip_paths,
        cta_path=config.CTA_ASSET_PATH,
        output_path=output_path,
        aspect_ratio=request.aspect_ratio,
    )
    job_store.update(job_id, final_video_path=final_path)
    job_store.set_status(job_id, JobStatus.DONE, progress=100)

    # Derive a public URL from the final file path
    filename = os.path.basename(final_path)
    video_url = f"/api/v2/video/{job_id}/{filename}"
    emit_event(job_id, "done", {"video_url": video_url})
    logger.info("Job %s: Phase 5 complete — final video at %s", job_id, final_path)
