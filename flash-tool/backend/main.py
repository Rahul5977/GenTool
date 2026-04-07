import logging
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse

from .models import (
    CreateJobRequest,
    ApproveImagesRequest,
    RegenImageRequest,
    RegenClipRequest,
    VideoJob,
    JobStatus,
)
from .job_store import job_store
from . import config

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


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/v2/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


# ---------------------------------------------------------------------------
# Job lifecycle
# ---------------------------------------------------------------------------

@app.post("/api/v2/jobs/create", status_code=201)
async def create_job(body: CreateJobRequest):
    """Create a new video-ad generation job and kick off the pipeline."""
    job = VideoJob(
        script_raw=body.script,
        coach=body.coach,
        num_clips=body.num_clips,
        aspect_ratio=body.aspect_ratio,
    )
    job_store.create(job)
    # TODO (Phase 2): launch pipeline orchestrator in background
    raise HTTPException(status_code=501, detail="Pipeline not yet implemented")


@app.get("/api/v2/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    """Return current status snapshot for a job."""
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # TODO: return a richer status DTO once pipeline is wired
    raise HTTPException(status_code=501, detail="Not yet implemented")


@app.get("/api/v2/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    """SSE stream of job progress events."""
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        # TODO: yield real progress events from the orchestrator
        yield {"event": "ping", "data": "connected"}

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# Approval / regen
# ---------------------------------------------------------------------------

@app.post("/api/v2/jobs/{job_id}/approve")
async def approve_images(job_id: str, body: ApproveImagesRequest):
    """Mark keyframes as approved and unblock video generation."""
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.AWAITING:
        raise HTTPException(status_code=409, detail="Job is not awaiting approval")
    # TODO: mark approved keyframes and resume pipeline
    raise HTTPException(status_code=501, detail="Not yet implemented")


@app.post("/api/v2/jobs/{job_id}/regen-image")
async def regen_image(job_id: str, body: RegenImageRequest):
    """Re-generate a single keyframe image."""
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.AWAITING:
        raise HTTPException(status_code=409, detail="Job is not awaiting approval")
    # TODO: call imager for the specific keyframe
    raise HTTPException(status_code=501, detail="Not yet implemented")


@app.post("/api/v2/jobs/{job_id}/regen-clip")
async def regen_clip(job_id: str, body: RegenClipRequest):
    """Re-generate a single video clip."""
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # TODO: re-run Veo for the specific clip index
    raise HTTPException(status_code=501, detail="Not yet implemented")


# ---------------------------------------------------------------------------
# Video file serving
# ---------------------------------------------------------------------------

@app.get("/api/v2/video/{filename}")
async def serve_video(filename: str):
    """Serve a generated video file from TMP_DIR."""
    # Sanitise to prevent path traversal
    safe_name = os.path.basename(filename)
    path = os.path.join(config.TMP_DIR, safe_name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(path, media_type="video/mp4")
