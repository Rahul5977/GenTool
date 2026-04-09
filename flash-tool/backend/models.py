from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime
import uuid


class JobStatus(str, Enum):
    PENDING               = "pending"
    ANALYSING             = "analysing"
    PROMPTING             = "prompting"
    AWAITING_PROMPT_REVIEW = "awaiting_prompt_review"
    IMAGING               = "imaging"
    AWAITING              = "awaiting_approval"
    GENERATING            = "generating"
    STITCHING             = "stitching"
    DONE                  = "done"
    FAILED                = "failed"


class PipelinePhase(str, Enum):
    PHASE_1       = "script_analysis"
    PHASE_2       = "prompt_generation"
    PHASE_2_REVIEW = "prompt_review"
    PHASE_3       = "image_generation"
    PHASE_4       = "video_generation"
    PHASE_5       = "stitch"


class CharacterSpec(BaseModel):
    age: int
    gender: str
    skin_tone: str
    skin_hex: str
    face_shape: str
    hair: str
    outfit: str
    accessories: list[str] = []
    distinguishing_marks: list[str] = []


class ClipBrief(BaseModel):
    clip_number: int
    duration_seconds: int
    dialogue: str
    word_count: int
    emotional_state: str
    end_emotion: str


class ProductionBrief(BaseModel):
    clips: list[ClipBrief]
    character: CharacterSpec
    locked_background: str
    aspect_ratio: str = "9:16"
    coach: str = "Rishika"
    setting: str


class ClipPrompt(BaseModel):
    clip_number: int
    duration_seconds: int
    scene_summary: str
    prompt: str
    dialogue: str
    word_count: int
    end_emotion: str
    verified: bool = False
    verification_issues: list[str] = []


class KeyFrame(BaseModel):
    index: int
    image_b64: str          # base64 encoded JPEG
    mime_type: str = "image/jpeg"
    description: str
    approved: bool = False


class VideoJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    phase: Optional[PipelinePhase] = None
    progress: int = 0
    script_raw: str = ""
    coach: str = "Rishika"
    num_clips: int = 4
    aspect_ratio: str = "9:16"
    production_brief: Optional[ProductionBrief] = None
    clips: list[ClipPrompt] = []
    keyframes: list[KeyFrame] = []
    clip_paths: list[str] = []
    final_video_path: str = ""
    error: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Request/Response models
class CreateJobRequest(BaseModel):
    script: str
    coach: str = "Rishika"
    num_clips: int = Field(default=4, ge=3, le=8)
    aspect_ratio: str = "9:16"
    veo_model: str = "veo-3.1-generate-preview"


class ApproveImagesRequest(BaseModel):
    approved_indices: list[int]  # which keyframes are approved


class ApprovePromptsRequest(BaseModel):
    """Signal to unblock Phase 3 image generation after human prompt review."""
    pass  # no payload needed — just the POST triggers the unblock


class UpdateClipPromptRequest(BaseModel):
    prompt: str


class RegenImageRequest(BaseModel):
    keyframe_index: int
    new_emotion: Optional[str] = None
    custom_prompt: Optional[str] = None  # extra user instructions for regen


class RegenClipRequest(BaseModel):
    clip_index: int  # 0-based
    updated_prompt: Optional[str] = None  # if set, use this prompt instead of stored one
