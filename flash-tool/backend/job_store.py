import threading
from typing import Optional
from .models import VideoJob, JobStatus, PipelinePhase
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class JobStore:
    def __init__(self):
        self._jobs: dict[str, VideoJob] = {}
        self._lock = threading.RLock()

    def create(self, job: VideoJob) -> VideoJob:
        with self._lock:
            self._jobs[job.job_id] = job
            return job

    def get(self, job_id: str) -> Optional[VideoJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs) -> Optional[VideoJob]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            job.updated_at = datetime.utcnow()
            return job

    def set_status(self, job_id: str, status: JobStatus, phase: PipelinePhase = None,
                   progress: int = None, error: str = None):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.status = status
            if phase is not None:
                job.phase = phase
            if progress is not None:
                job.progress = progress
            if error is not None:
                job.error = error
            job.updated_at = datetime.utcnow()

    def list_jobs(self) -> list[VideoJob]:
        with self._lock:
            return list(self._jobs.values())


# Singleton
job_store = JobStore()
