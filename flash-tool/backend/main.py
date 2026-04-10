import asyncio
import base64
import json
import logging
import os
import threading
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from sse_starlette.sse import EventSourceResponse

from . import config
from .job_store import job_store
from .models import (
    ApproveImagesRequest,
    ApprovePromptsRequest,
    CreateJobRequest,
    JobStatus,
    RegenClipRequest,
    RegenImageRequest,
    UpdateClipPromptRequest,
    VideoJob,
)
from .pipeline.orchestrator import (
    _approval_data,
    _approval_events,
    _job_event_queues,
    _prompt_approval_events,
    emit_event,
    run_pipeline,
)
from .pipeline.phase3_imager import regenerate_single_keyframe
from .pipeline.phase4_generator import generate_single_clip
from .models import KeyFrame

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="Flash Tool API", version="2.0.0")


@app.on_event("startup")
async def _startup():
    os.makedirs(config.TMP_DIR, exist_ok=True)
    logger.info("Flash Tool v2 started — TMP_DIR=%s", config.TMP_DIR)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_SSE_POLL_INTERVAL = 0.3   # seconds between queue checks
_SSE_HEARTBEAT_SEC = 15    # seconds between keep-alive pings


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/v2/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/api/v2/jobs/list")
async def list_jobs():
    """Return a lightweight summary of all jobs (for dashboard)."""
    jobs = job_store.list_jobs()
    return [
        {
            "job_id": j.job_id,
            "status": j.status,
            "coach": j.coach,
            "num_clips": j.num_clips,
            "progress": j.progress,
            "error": j.error,
            "created_at": j.created_at.isoformat(),
            "updated_at": j.updated_at.isoformat(),
        }
        for j in sorted(jobs, key=lambda j: j.created_at, reverse=True)
    ]


# ---------------------------------------------------------------------------
# Job create
# ---------------------------------------------------------------------------

@app.post("/api/v2/jobs/create", status_code=201)
async def create_job(body: CreateJobRequest):
    """Create a VideoJob and immediately kick off the pipeline in a thread."""
    job = VideoJob(
        script_raw=body.script,
        coach=body.coach,
        num_clips=body.num_clips,
        aspect_ratio=body.aspect_ratio,
    )
    job_store.create(job)

    # Pre-create the SSE queue so the client can connect before phase 1 emits
    _job_event_queues.setdefault(job.job_id, [])

    thread = threading.Thread(
        target=run_pipeline,
        args=(job.job_id, body),
        daemon=True,
        name=f"pipeline-{job.job_id[:8]}",
    )
    thread.start()

    logger.info("Job %s created — pipeline thread started", job.job_id)
    return {"job_id": job.job_id, "status": job.status}


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@app.get("/api/v2/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    """Return a lightweight status snapshot (no raw image bytes)."""
    job = _require_job(job_id)
    approved = sum(1 for kf in job.keyframes if kf.approved)
    return {
        "job_id": job.job_id,
        "status": job.status,
        "phase": job.phase,
        "progress": job.progress,
        "num_keyframes": len(job.keyframes),
        "keyframes_approved": approved,
        "clips_done": len([p for p in job.clip_paths if p]),
        "final_video_path": job.final_video_path,
        "error": job.error,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# SSE stream
# ---------------------------------------------------------------------------

@app.get("/api/v2/jobs/{job_id}/stream")
async def stream_job(job_id: str, request: Request):
    """SSE stream of pipeline progress events for a job.

    Supports Last-Event-ID for reconnect: the client resumes from where it
    left off rather than replaying the full event history from the start.
    """
    _require_job(job_id)
    queue = _job_event_queues.setdefault(job_id, [])

    # Honor Last-Event-ID on reconnect so we don't replay history
    last_event_id_header = request.headers.get("last-event-id", "")
    try:
        start_index = int(last_event_id_header) + 1
    except (ValueError, TypeError):
        start_index = 0

    async def event_generator():
        sent_index = start_index
        last_heartbeat = time.monotonic()

        while True:
            # Client disconnected
            if await request.is_disconnected():
                logger.info("SSE client disconnected from job %s", job_id)
                break

            # Drain all pending events
            while sent_index < len(queue):
                entry = queue[sent_index]
                yield {
                    "event": entry["type"],
                    "data": json.dumps(entry["data"]),
                    "id": str(sent_index),  # client stores this as Last-Event-ID
                }
                sent_index += 1

            # Check terminal states — flush remaining events first
            current = job_store.get(job_id)
            if current and current.status in (JobStatus.DONE, JobStatus.FAILED):
                while sent_index < len(queue):
                    entry = queue[sent_index]
                    yield {
                        "event": entry["type"],
                        "data": json.dumps(entry["data"]),
                        "id": str(sent_index),
                    }
                    sent_index += 1
                break

            # Heartbeat
            now = time.monotonic()
            if now - last_heartbeat >= _SSE_HEARTBEAT_SEC:
                yield {"event": "heartbeat", "data": "{}"}
                last_heartbeat = now

            await asyncio.sleep(_SSE_POLL_INTERVAL)

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# Prompt review endpoints (Phase 2 → Phase 3 gate)
# ---------------------------------------------------------------------------

@app.get("/api/v2/jobs/{job_id}/clips")
async def get_clips(job_id: str):
    """Return the current list of clip prompts for a job."""
    job = _require_job(job_id)
    return {
        "clips": [
            {
                "clip_number": c.clip_number,
                "duration_seconds": c.duration_seconds,
                "scene_summary": c.scene_summary,
                "prompt": c.prompt,
                "dialogue": c.dialogue,
                "word_count": c.word_count,
                "end_emotion": c.end_emotion,
                "verified": c.verified,
                "verification_issues": c.verification_issues,
            }
            for c in job.clips
        ]
    }


@app.put("/api/v2/jobs/{job_id}/clips/{clip_index}")
async def update_clip_prompt(job_id: str, clip_index: int, body: UpdateClipPromptRequest):
    """Update a single clip's Veo prompt during human review (before image gen starts)."""
    job = _require_job(job_id)
    if job.status != JobStatus.AWAITING_PROMPT_REVIEW:
        raise HTTPException(
            status_code=409,
            detail=f"Can only edit prompts while job is awaiting prompt review (current: {job.status})",
        )
    clips = list(job.clips)
    if clip_index < 0 or clip_index >= len(clips):
        raise HTTPException(
            status_code=400,
            detail=f"clip_index {clip_index} out of range (0–{len(clips) - 1})",
        )
    # Update the prompt in-place (keep all other fields)
    clip = clips[clip_index]
    updated_clip = clip.model_copy(update={"prompt": body.prompt})
    clips[clip_index] = updated_clip
    job_store.update(job_id, clips=clips)

    emit_event(job_id, "clip_prompt_updated", {"clip_index": clip_index, "clip_number": clip.clip_number})
    logger.info("Job %s: clip %d prompt updated by user", job_id, clip_index)
    return {"message": "prompt updated", "clip_index": clip_index}


@app.post("/api/v2/jobs/{job_id}/approve-prompts")
async def approve_prompts(job_id: str, body: ApprovePromptsRequest):  # noqa: ARG001
    """Unblock Phase 3 image generation after human prompt review."""
    job = _require_job(job_id)
    if job.status != JobStatus.AWAITING_PROMPT_REVIEW:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not awaiting prompt review (current status: {job.status})",
        )

    event = _prompt_approval_events.get(job_id)
    if event:
        event.set()
    else:
        logger.warning("Job %s: prompt approval event not found — phase may have already advanced", job_id)

    logger.info("Job %s: prompts approved — unblocking Phase 3", job_id)
    return {"message": "prompts approved, starting image generation"}


# ---------------------------------------------------------------------------
# Approve keyframes
# ---------------------------------------------------------------------------

@app.post("/api/v2/jobs/{job_id}/approve")
async def approve_images(job_id: str, body: ApproveImagesRequest):
    """Mark keyframes as approved and unblock Phase 4."""
    job = _require_job(job_id)
    if job.status != JobStatus.AWAITING:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not awaiting approval (current status: {job.status})",
        )

    # Store approval payload so the orchestrator can read it after the event fires
    _approval_data[job_id] = body

    event = _approval_events.get(job_id)
    if event:
        event.set()
    else:
        # Orchestrator may have already cleaned up (edge case) — update store directly
        _apply_approval(job_id, body)

    logger.info("Job %s: approved indices %s", job_id, body.approved_indices)
    return {"message": "approved, starting video generation"}


# ---------------------------------------------------------------------------
# Save clip prompt (no regen — works in any job status)
# ---------------------------------------------------------------------------

@app.post("/api/v2/jobs/{job_id}/clips/{clip_index}/save-prompt")
async def save_clip_prompt(job_id: str, clip_index: int, body: UpdateClipPromptRequest):
    """Persist an edited clip prompt without triggering regeneration.

    Unlike PUT /clips/{clip_index} (which is gated to AWAITING_PROMPT_REVIEW),
    this endpoint works on a completed job so users can save edits on the
    result page before manually regenerating.
    """
    job = _require_job(job_id)
    clips = list(job.clips)
    if clip_index < 0 or clip_index >= len(clips):
        raise HTTPException(
            status_code=400,
            detail=f"clip_index {clip_index} out of range (0–{len(clips) - 1})",
        )
    clips[clip_index] = clips[clip_index].model_copy(update={"prompt": body.prompt})
    job_store.update(job_id, clips=clips)
    logger.info("Job %s: clip %d prompt saved (no regen)", job_id, clip_index)
    return {"message": "prompt saved", "clip_index": clip_index}


# ---------------------------------------------------------------------------
# Regen single keyframe
# ---------------------------------------------------------------------------

@app.post("/api/v2/jobs/{job_id}/regen-image")
async def regen_image(job_id: str, body: RegenImageRequest):
    """Re-generate a single keyframe image and update the job."""
    job = _require_job(job_id)
    if job.status != JobStatus.AWAITING:
        raise HTTPException(
            status_code=409,
            detail="Can only regenerate images while job is awaiting approval",
        )

    idx = body.keyframe_index
    keyframes = job.keyframes

    if idx < 0 or idx >= len(keyframes):
        raise HTTPException(
            status_code=400,
            detail=f"keyframe_index {idx} out of range (0–{len(keyframes) - 1})",
        )

    brief = job.production_brief
    if brief is None:
        raise HTTPException(status_code=500, detail="Job has no production brief")

    prev_kf = keyframes[idx - 1] if idx > 0 else keyframes[0]
    clip = job.clips[idx - 1] if idx > 0 and idx - 1 < len(job.clips) else None
    target_emotion = body.new_emotion or (clip.end_emotion if clip else "neutral")

    new_kf = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: regenerate_single_keyframe(
            frame_index=idx,
            prev_keyframe=prev_kf,
            target_emotion=target_emotion,
            brief=brief,
            clip=clip,
            custom_prompt=body.custom_prompt,
        ),
    )

    # Splice the new keyframe in
    updated = list(keyframes)
    updated[idx] = new_kf
    job_store.update(job_id, keyframes=updated)

    emit_event(job_id, "keyframe_ready", {
        "index": new_kf.index,
        "total": len(updated),
        "preview_url": f"/api/v2/keyframe/{job_id}/{new_kf.index}",
    })
    return {"keyframe": new_kf.model_dump(exclude={"image_b64"})}


# ---------------------------------------------------------------------------
# Regen single clip
# ---------------------------------------------------------------------------

@app.post("/api/v2/jobs/{job_id}/regen-clip")
async def regen_clip(job_id: str, body: RegenClipRequest):
    """Re-generate a single video clip using the existing keyframes."""
    job = _require_job(job_id)

    clip_index = body.clip_index
    clips = job.clips
    keyframes = job.keyframes

    if clip_index < 0 or clip_index >= len(clips):
        raise HTTPException(
            status_code=400,
            detail=f"clip_index {clip_index} out of range (0–{len(clips) - 1})",
        )
    if len(keyframes) < clip_index + 2:
        raise HTTPException(
            status_code=409,
            detail="Keyframes not yet generated for this clip",
        )

    clip = clips[clip_index]
    out_dir = os.path.join(config.TMP_DIR, job_id)
    os.makedirs(out_dir, exist_ok=True)

    # Allow user to supply a modified prompt for this regen attempt
    effective_prompt = body.updated_prompt if body.updated_prompt else clip.prompt

    new_path = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: generate_single_clip(
            clip_index=clip_index,
            clip_number=clip.clip_number,
            total=len(clips),
            prompt=effective_prompt,
            first_frame=keyframes[clip_index],
            last_frame=keyframes[clip_index + 1],
            veo_model=config.VEO_MODEL,
            aspect_ratio=job.aspect_ratio,
            job_id=job_id,
        ),
    )

    # Persist the updated prompt back to the clip store if user modified it
    if body.updated_prompt:
        updated_clips = list(job.clips)
        updated_clips[clip_index] = clip.model_copy(update={"prompt": body.updated_prompt})
        job_store.update(job_id, clips=updated_clips)

    updated_paths = list(job.clip_paths)
    # Extend the list if it's shorter than expected
    while len(updated_paths) <= clip_index:
        updated_paths.append("")
    updated_paths[clip_index] = new_path
    job_store.update(job_id, clip_paths=updated_paths)

    clip_url = f"/api/v2/video/{job_id}/clip_{clip.clip_number:02d}.mp4"
    return {"clip_url": clip_url}


# ---------------------------------------------------------------------------
# Serve video files
# ---------------------------------------------------------------------------

@app.get("/api/v2/video/{job_id}/{filename}")
async def serve_video(job_id: str, filename: str):
    """Serve a generated MP4 file from TMP_DIR."""
    safe_name = os.path.basename(filename)
    safe_job  = os.path.basename(job_id)
    path = os.path.join(config.TMP_DIR, safe_job, safe_name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(path, media_type="video/mp4")


# ---------------------------------------------------------------------------
# Serve keyframe images
# ---------------------------------------------------------------------------

@app.get("/api/v2/keyframe/{job_id}/{index}")
async def serve_keyframe(job_id: str, index: int):
    """Return a keyframe image as JPEG (decoded from the in-memory base64)."""
    job = _require_job(job_id)
    keyframes = job.keyframes

    if index < 0 or index >= len(keyframes):
        raise HTTPException(
            status_code=404,
            detail=f"Keyframe {index} not found (job has {len(keyframes)} keyframes)",
        )

    kf = keyframes[index]
    if not kf.image_b64:
        raise HTTPException(status_code=404, detail="Keyframe image not yet generated")

    image_bytes = base64.b64decode(kf.image_b64)
    return Response(content=image_bytes, media_type="image/jpeg")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_job(job_id: str) -> VideoJob:
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _apply_approval(job_id: str, body: ApproveImagesRequest) -> None:
    """Directly mark keyframes approved in the store (fallback path)."""
    job = job_store.get(job_id)
    if not job:
        return
    keyframes = list(job.keyframes)
    for idx in body.approved_indices:
        if 0 <= idx < len(keyframes):
            keyframes[idx].approved = True
    job_store.update(job_id, keyframes=keyframes)
