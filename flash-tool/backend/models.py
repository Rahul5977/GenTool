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
    POST_PRODUCING        = "post_producing"
    DONE                  = "done"
    FAILED                = "failed"


class PipelinePhase(str, Enum):
    PHASE_1       = "script_analysis"
    PHASE_2       = "prompt_generation"
    PHASE_2_REVIEW = "prompt_review"
    PHASE_3       = "image_generation"
    PHASE_4       = "video_generation"
    PHASE_5       = "stitch"
    PHASE_5_5     = "post_production"


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


class VisualState(BaseModel):
    """Per-clip visual state — goes beyond facial expression to encode body language."""
    posture: str              # e.g., "slight slouch, shoulders forward 10°, head tilted down 5°"
    styling_state: str        # e.g., "hair covering sides of face, dupatta draped loose as shield"
    energy_level: str         # "low" | "medium" | "high" — maps to movement speed/frequency
    eye_contact_pattern: str  # "avoidant" | "intermittent" | "direct" | "warm_direct"
    voice_register: str       # "whisper" | "low" | "conversational" | "warm_confident"
    lighting_warmth: str      # "cooler_single_source" | "neutral" | "warmer_positioned"


class ClipBrief(BaseModel):
    clip_number: int
    duration_seconds: int
    dialogue: str
    word_count: int
    emotional_state: str
    end_emotion: str
    visual_state: Optional[VisualState] = None       # per-clip body language state


class ProductionBrief(BaseModel):
    clips: list[ClipBrief]
    character: CharacterSpec
    locked_background: str
    aspect_ratio: str = "9:16"
    coach: str = "Rishika"
    setting: str
    voice_characteristics: str = ""
    domain: str = "general"                          # health domain detected from script
    coach_clip: int = 3                              # which clip introduces the coach (1-indexed)
    pre_coach_visual_markers: list[str] = []         # domain-specific visual cues for clips 1 to coach_clip
    post_coach_visual_markers: list[str] = []        # domain-specific visual cues for clips after coach_clip
    visual_states: list[VisualState] = []            # one per clip — full body language state


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
    validation_issues: list[str] = []  # populated by validate_keyframe_quality()


class VideoJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    phase: Optional[PipelinePhase] = None
    progress: int = 0
    script_raw: str = ""
    coach: str = "Rishika"
    num_clips: int = 4
    aspect_ratio: str = "9:16"
    domain: str = "general"
    veo_model: str = ""  # set on create from CreateJobRequest; used for regen-clip
    post_production: Optional["PostProductionConfig"] = None
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
    domain: Optional[str] = None                     # if None, auto-detect from script
    post_production: Optional["PostProductionConfig"] = None  # overlay/transition config


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


class DomainProfile(BaseModel):
    """Domain-specific visual markers for pre-coach and post-coach clips."""
    domain: str                          # "weight"|"skin"|"stress"|"muscle"|"sexual"|"hairloss"|"energy"|"general"
    pre_coach_appearance_modifiers: list[str]   # Added to OUTFIT & APPEARANCE for clips 1 to coach_clip
    post_coach_appearance_modifiers: list[str]  # Added to OUTFIT & APPEARANCE for clips after coach_clip
    pre_coach_visual_states: dict[str, str]     # Keys: posture, styling, energy, eye_contact, voice, lighting
    post_coach_visual_states: dict[str, str]    # Same keys
    imagen_character_modifiers: list[str]       # Extra descriptors for Frame 0 Imagen prompt
    veo_safe: bool = True                       # All terms here must be Veo-safe


class PostProductionConfig(BaseModel):
    """Configuration for Phase 5.5 post-production overlays and transitions."""
    text_overlays: list["TextOverlay"] = []
    image_overlays: list["ImageOverlay"] = []
    transitions: list["TransitionEffect"] = []


class TextOverlay(BaseModel):
    text: str                        # Hindi text e.g. "SuperLiving me coach se baat krne ke baad..."
    start_time: float                # seconds from start of stitched video
    duration: float                  # how long to show
    position: str = "bottom_center"  # "bottom_center"|"top_left"|"top_right"|"bottom_left"|"center"
    font_size: int = 36
    font_color: str = "white"
    bg_color: str = "black@0.6"      # FFmpeg format — semi-transparent black
    animation: str = "fade"          # "fade"|"slide_up"|"none"


class ImageOverlay(BaseModel):
    image_path: str                  # path to PNG/JPEG asset
    start_time: float
    duration: float
    position: str = "top_right"
    width: int = 150                 # pixels
    opacity: float = 0.9


class TransitionEffect(BaseModel):
    type: str                        # "flash_white"|"fade_black"|"text_card"|"blur_shift"
    insert_after_clip: int           # e.g., 3 (between clip 3 and clip 4)
    duration: float = 1.0
    text: Optional[str] = None       # for text_card type
    font_size: int = 48
    bg_color: str = "black"
