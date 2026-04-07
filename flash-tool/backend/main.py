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
    CreateJobRequest,
    JobStatus,
    RegenClipRequest,
    RegenImageRequest,
    VideoJob,
)
from .pipeline.orchestrator import (
    _approval_data,
    _approval_events,
    _job_event_queues,
    emit_event,
    run_pipeline,
)
from .pipeline.phase3_imager import regenerate_single_keyframe
from .pipeline.phase4_generator import generate_single_clip
from .models import KeyFrame

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Flash Tool API", version="2.0.0")

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
    """SSE stream of pipeline progress events for a job."""
    job = _require_job(job_id)
    queue = _job_event_queues.setdefault(job_id, [])

    async def event_generator():
        sent_index = 0
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
                }
                sent_index += 1

            # Check terminal states — flush remaining events first
            current = job_store.get(job_id)
            if current and current.status in (JobStatus.DONE, JobStatus.FAILED):
                # One final drain
                while sent_index < len(queue):
                    entry = queue[sent_index]
                    yield {
                        "event": entry["type"],
                        "data": json.dumps(entry["data"]),
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

    new_path = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: generate_single_clip(
            clip_index=clip_index,
            clip_number=clip.clip_number,
            total=len(clips),
            prompt=clip.prompt,
            first_frame=keyframes[clip_index],
            last_frame=keyframes[clip_index + 1],
            veo_model=config.VEO_MODEL,
            aspect_ratio=job.aspect_ratio,
            job_id=job_id,
        ),
    )

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
