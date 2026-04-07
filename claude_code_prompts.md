# FLASH TOOL v2 — CLAUDE CODE BUILD PROMPTS
# 8 sequential prompts. Run one at a time. Each builds on the previous.
# Paste each prompt directly into Claude Code.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROMPT 1 — PROJECT SCAFFOLD + DATA MODELS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Create a new project called `flash-tool` with the following structure.
This is a Hindi/Hinglish AI video ad generation pipeline for Indian health app SuperLiving.

PROJECT STRUCTURE:
```
flash-tool/
├── backend/
│   ├── main.py
│   ├── models.py
│   ├── job_store.py
│   ├── config.py
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── orchestrator.py
│   │   ├── phase1_analyser.py
│   │   ├── phase2_prompter.py
│   │   ├── phase3_imager.py
│   │   ├── phase4_generator.py
│   │   └── phase5_stitcher.py
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── gemini_client.py
│   │   ├── imagen_client.py
│   │   ├── veo_client.py
│   │   └── verifier.py
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── system_analyser.py
│   │   ├── system_prompter.py
│   │   ├── system_verifier.py
│   │   └── system_imager.py
│   ├── video/
│   │   ├── __init__.py
│   │   ├── ffmpeg_ops.py
│   │   └── cta_ops.py
│   ├── assets/
│   │   └── .gitkeep
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── (empty for now)
└── README.md
```

CREATE `backend/models.py` with ALL of these Pydantic models:

```python
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime
import uuid

class JobStatus(str, Enum):
    PENDING    = "pending"
    ANALYSING  = "analysing"
    PROMPTING  = "prompting"
    IMAGING    = "imaging"
    AWAITING   = "awaiting_approval"
    GENERATING = "generating"
    STITCHING  = "stitching"
    DONE       = "done"
    FAILED     = "failed"

class PipelinePhase(str, Enum):
    PHASE_1 = "script_analysis"
    PHASE_2 = "prompt_generation"
    PHASE_3 = "image_generation"
    PHASE_4 = "video_generation"
    PHASE_5 = "stitch"

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

class RegenImageRequest(BaseModel):
    keyframe_index: int
    new_emotion: Optional[str] = None

class RegenClipRequest(BaseModel):
    clip_index: int  # 0-based
```

CREATE `backend/config.py`:
```python
import os
from dotenv import load_dotenv
load_dotenv()

GOOGLE_API_KEY      = os.getenv("GOOGLE_API_KEY", "")
VEO_MODEL           = os.getenv("VEO_MODEL", "veo-3.1-generate-preview")
IMAGEN_MODEL        = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-001")
GEMINI_MODEL        = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
GEMINI_IMAGE_MODEL  = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.0-flash-exp")
MAX_PARALLEL_WORKERS = int(os.getenv("MAX_PARALLEL_WORKERS", "6"))
CLIP_RESOLUTION     = os.getenv("CLIP_RESOLUTION", "1080p")
LOUDNORM_TARGET     = float(os.getenv("LOUDNORM_TARGET", "-16"))
CTA_ASSET_PATH      = os.getenv("CTA_ASSET_PATH", "./backend/assets/cta.mp4")
TMP_DIR             = os.getenv("TMP_DIR", "/tmp/flash_tool")
```

CREATE `backend/.env.example`:
```
GOOGLE_API_KEY=your_key_here
VEO_MODEL=veo-3.1-generate-preview
IMAGEN_MODEL=imagen-3.0-generate-001
GEMINI_MODEL=gemini-2.5-pro
GEMINI_IMAGE_MODEL=gemini-2.0-flash-exp
MAX_PARALLEL_WORKERS=6
CLIP_RESOLUTION=1080p
CTA_ASSET_PATH=./backend/assets/cta.mp4
```

CREATE `backend/requirements.txt`:
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
python-dotenv==1.0.0
pydantic==2.8.0
google-genai==1.0.0
google-cloud-aiplatform==1.65.0
httpx==0.27.0
python-multipart==0.0.9
sse-starlette==2.1.0
aiofiles==24.1.0
```

CREATE `backend/job_store.py` — an in-memory job store (thread-safe):
```python
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
```

CREATE `backend/main.py` — FastAPI app skeleton with all routes defined but not yet implemented (placeholder 501 responses for now). Include CORS for localhost:3000. Routes:
- POST /api/v2/jobs/create
- GET /api/v2/jobs/{job_id}/status
- GET /api/v2/jobs/{job_id}/stream (SSE)
- POST /api/v2/jobs/{job_id}/approve
- POST /api/v2/jobs/{job_id}/regen-image
- POST /api/v2/jobs/{job_id}/regen-clip
- GET /api/v2/video/{filename}
- GET /api/v2/health

Finally create a minimal README.md explaining what this is.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROMPT 2 — PROMPT SYSTEM (THE BRAIN OF THE PIPELINE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

In `backend/prompts/`, create four system prompt files. These are the most
important files in the entire codebase — they directly determine video quality.

CREATE `backend/prompts/system_analyser.py`:
A large string constant `SYSTEM_ANALYSER` that is a Gemini system prompt.
Its job: take a raw Hindi/Hinglish ad script and produce a structured JSON
ProductionBrief. It must enforce:
- Word count per clip: 15-19 words for 8s clips, 13-17 for 7s, 10-13 for 5s
- Zero em-dashes (—) or hyphens (-) in any dialogue
- All Veo block words flagged: skin type, acne, pimples, weight loss, fatigue,
  diabetes, BP, surgery, treatment, transformation
- Coach Rishika/Seema/Rashmi never appears on screen — always quoted by protagonist
- Emotional arc: each clip gets an emotional_state AND an end_emotion
  (what expression should be at the end of the clip = transition to next clip)
- Character: full Indian appearance description with hex codes for skin tone
- Locked background: 60+ words, every object listed by exact position
- Setting: relatable Tier 3/4 India (bedroom, office desk, bathroom, kitchen,
  chai stall — never studio, gym, or aspirational)

Output format: strict JSON matching ProductionBrief schema. Temperature: 0.1.

CREATE `backend/prompts/system_prompter.py`:
A large string constant `SYSTEM_PROMPTER` that is a Gemini system prompt.
Its job: take a ProductionBrief and generate N Veo clip prompts in Hindi/Devanagari.

Each prompt MUST have these exact sections in this order:
1. CONTINUING FROM: (clips 2+ only) — exact posture, expression, background inventory
2. FACE LOCK STATEMENT: ⚠️ चेहरा पूरी तरह स्थिर और क्लिप 1 के समान रहेगा
3. OUTFIT & APPEARANCE: verbatim from character spec — never paraphrase
4. LOCATION: verbatim locked background from clip 1 + freeze line:
   "पृष्ठभूमि पूरी तरह स्थिर और अपरिवर्तित रहती है — कोई नई वस्तु नहीं आएगी,
    कोई वस्तु गायब नहीं होगी, रंग नहीं बदलेगा।"
5. ACTION: (STATIC SHOT) ONE state only. Movement rules:
   TIER 1 SAFE (use freely): microexpressions (eyebrow raise, lip corner),
   head nod once, head tilt 10-15°, slow exhale with shoulder drop, eyes briefly
   down then back, smile arriving during speech
   TIER 2 MODERATE (constrained): body lean 5-10° held entire clip, hands already
   clasped in lap with slight finger movement — NEVER hands entering frame mid-clip
   NEVER: hand gestures, head turning >30°, picking objects, posture changes mid-clip
   Always include: "शरीर बिल्कुल स्थिर, हाथ फ्रेम से बाहर।"
6. DIALOGUE: format: चरित्र: "(बातचीत के लहजे में, warm और clear आवाज़ में) संवाद"
   NO em-dashes NO hyphens in dialogue. Word count verified.
7. AUDIO: "crystal-clear, studio-quality, close-mic recording।
   कोई echo नहीं, reverb नहीं, background noise नहीं।
   आवाज़ naturally warm है।"
8. CAMERA: "टाइट मीडियम क्लोज-अप (TIGHT MCU) — ठोड़ी से मध्य-सीने तक फ्रेम।
   हाथ और बाँहें पूरी तरह फ्रेम से बाहर। आई-लेवल पर (STATIC SHOT)।
   Ultra-sharp focus, 8k resolution, highly detailed. कैमरा बिल्कुल स्थिर।"
9. LIGHTING: PRIMARY warm side-fill + SECONDARY overhead ambient.
   Always: "⚠️ आँखें clearly visible। कोई काले eye socket shadows नहीं।
   Cinematic contrast, photorealistic skin texture, extremely crisp."
10. VISUAL FORMAT PROHIBITIONS: "No cinematic letterbox bars. No black bars.
    Full 9:16 vertical portrait frame edge to edge. No subtitles. No watermarks.
    No phone UI. If phone shown, screen black only.
    Audio-visual sync: match lip movements precisely to spoken dialogue."
11. LAST FRAME: character exact state + full background inventory + camera + lighting
12. END_EMOTION: (not part of Veo prompt — separate field) target expression at
    end of clip for Gemini Image transition generation

Output: JSON array of clip prompts.

CREATE `backend/prompts/system_verifier.py`:
A string constant `SYSTEM_VERIFIER` — 13 rules, each with auto-fix logic.
Rule 1: Word count enforcement with exact fix
Rule 2: Single action (no transitions in ACTION block)
Rule 3: Dual lighting ghost-face prevention
Rule 4: No voiceover — character must be on screen
Rule 5: Phone screen = black if shown
Rule 6: LOCKED BACKGROUND verbatim across all clips
Rule 7: CONTINUING FROM + LAST FRAME present in correct clips
Rule 8: Face lock statement present every clip
Rule 9: TIGHT MCU camera only — no medium shot, no wide
Rule 10: 9:16 format prohibition block present
Rule 11: Tier 3/4 emotional register — no LinkedIn language
Rule 12: No second character in frame
Rule 13: ZERO dashes in dialogue — auto-replace with comma or connective

Output JSON: {clips: [{clip, status, issues, improved_prompt}], overall_score, summary}

CREATE `backend/prompts/system_imager.py`:
A string constant `SYSTEM_IMAGER` for generating transition keyframes.
This is the instruction sent to Gemini Image model with each previous frame.
The instruction must emphasize:
- Change ONLY the target expression
- Keep face structure, skin tone, all features IDENTICAL
- Keep outfit and all accessories IDENTICAL
- Keep background EVERY OBJECT in exact same position
- Keep camera angle TIGHT MCU chin to mid-chest
- Keep lighting direction and color temperature IDENTICAL
- 9:16 portrait output

Also create `IMAGEN_PROMPT_TEMPLATE` — a template string for generating
the initial character reference image via Imagen 3. Must include:
- "Shot on an ordinary smartphone, uneven exposure, slight grain"
- "Ultra-realistic natural skin texture, visible pores, no airbrushing"
- "No cinematic lighting, no dramatic shadows, completely unretouched"
- "Looks like a real person recording a high-trust UGC video at home"
- "Average body, not athletic or model-thin"
- The character description (outfit, appearance, setting)
- 9:16 portrait framing


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROMPT 3 — AI CLIENTS (Gemini, Imagen, Veo)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Implement the three AI client wrappers in `backend/ai/`.

CREATE `backend/ai/gemini_client.py`:
```python
# Wraps google-genai for text generation
# Functions:
# - generate_json(system_prompt, user_prompt, temperature=0.1) -> dict
#   Uses Gemini 2.5 Pro. Parses JSON from response. Handles ```json``` fences.
#   Retries 3 times on empty/invalid response.
# - generate_text(system_prompt, user_prompt, temperature=0.2) -> str
#   Uses Gemini 2.5 Pro for free-form text.
```

CREATE `backend/ai/imagen_client.py`:
```python
# Wraps Imagen 3 for character reference image generation
# Functions:
# - generate_character_image(prompt: str) -> bytes
#   Uses imagen-3.0-generate-001
#   aspect_ratio: "9:16"
#   Returns JPEG bytes
#   On failure: raises RuntimeError with message
```

CREATE `backend/ai/veo_client.py`:
```python
# Wraps Veo 3.1 for video generation with BOTH first and last frame
# Functions:
# - generate_clip(
#     prompt: str,
#     first_frame_bytes: bytes,
#     last_frame_bytes: bytes,
#     aspect_ratio: str = "9:16",
#     model: str = VEO_MODEL,
#   ) -> bytes
#   GenerateVideosConfig:
#     aspect_ratio=aspect_ratio (validated: only "9:16" or "16:9")
#     number_of_videos=1
#     resolution="1080p"
#     enhance_prompt=True
#     last_frame=types.Image(image_bytes=last_frame_bytes, mime_type="image/jpeg")
#   image=types.Image(image_bytes=first_frame_bytes, mime_type="image/jpeg")
#   Polls operation every 10s until done or 360s timeout
#   Checks for RAI filter blocks — raises ContentPolicyError if blocked
#   Downloads video bytes via URL with API key header
#   Returns: raw MP4 bytes
#
# - sanitize_prompt(prompt: str) -> str
#   Removes Veo block words using Gemini Flash:
#   Blocked: skin type, त्वचा का प्रकार, acne, pimples, मुंहासे, weight loss,
#   वज़न कम, transformation, before/after, doctor, medicine, diabetes, BP
#   Replaces with safe alternatives. Returns sanitized prompt.
```

CREATE `backend/ai/verifier.py`:
```python
# Runs the 13-rule verifier on a set of clip prompts
# Functions:
# - verify_prompts(clips: list[ClipPrompt]) -> list[ClipPrompt]
#   Calls Gemini with SYSTEM_VERIFIER prompt
#   Returns clips with verified=True and any issues fixed
#   Applies auto-fixes: word count trim, dash removal, aspect ratio correction
```

In ALL clients: use `google.genai.Client(api_key=GOOGLE_API_KEY)`.
Use `http_options={"api_version": "v1alpha"}` for Veo client only.
All clients must be importable as singletons from their modules.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROMPT 4 — PIPELINE PHASES 1, 2, 3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Implement the first three pipeline phases.

CREATE `backend/pipeline/phase1_analyser.py`:
```python
# analyse_script(script: str, num_clips: int, coach: str) -> ProductionBrief
# 
# Calls Gemini 2.5 Pro with SYSTEM_ANALYSER prompt.
# Validates output: checks word counts, dash presence, clip count.
# Auto-corrects word count issues (trim/expand dialogue).
# Returns ProductionBrief with all fields populated.
# 
# Validation rules (raise ValueError with clear message if violated):
# - Each dialogue: 15-19 words for 8s, 13-17 for 7s, 10-13 for 5s
# - Zero dashes in any dialogue field
# - locked_background must be >= 50 words
# - character.skin_hex must be present
# - end_emotion must be present for all clips
```

CREATE `backend/pipeline/phase2_prompter.py`:
```python
# generate_prompts(brief: ProductionBrief) -> list[ClipPrompt]
#
# For each clip in brief.clips:
#   1. Build clip prompt using SYSTEM_PROMPTER
#   2. Run verifier (verify_prompts)
#   3. Return verified ClipPrompt objects
#
# The LOCKED BACKGROUND must be copied VERBATIM into every clip's LOCATION block.
# The character appearance must be copied VERBATIM into every clip's OUTFIT block.
# CONTINUING FROM is generated from the previous clip's LAST FRAME section.
#
# Output: list[ClipPrompt] — one per clip, all verified
```

CREATE `backend/pipeline/phase3_imager.py`:
```python
# generate_keyframes(
#   brief: ProductionBrief,
#   clips: list[ClipPrompt],
# ) -> list[KeyFrame]   # length = num_clips + 1
#
# Image 0 — generate via Imagen 3:
#   Build Imagen prompt from IMAGEN_PROMPT_TEMPLATE + character spec +
#   locked_background + clips[0].emotional_state
#   Call imagen_client.generate_character_image(prompt)
#   Return as KeyFrame(index=0, ...)
#
# Images 1..N — generate via Gemini Image (sequential):
#   For each clip i (0-indexed):
#     previous_frame = keyframes[i].image_b64 (base64)
#     target_emotion = clips[i].end_emotion
#     
#     Call Gemini 2.0 Flash Image model with:
#       - Input: previous_frame image
#       - System: SYSTEM_IMAGER instruction
#       - User: f"Change expression to: {target_emotion}"
#     
#     Store result as KeyFrame(index=i+1, ...)
#
# Return list of N+1 KeyFrame objects with image_b64 populated
#
# Error handling: if Gemini Image returns no image, use previous frame
# (fallback — still better than no anchor)
#
# Gemini Image API call pattern:
#   client.models.generate_content(
#     model="gemini-2.0-flash-exp",
#     contents=[{
#       "parts": [
#         {"inline_data": {"mime_type": "image/jpeg", "data": prev_b64}},
#         {"text": instruction}
#       ]
#     }],
#     config={"response_modalities": ["IMAGE"], "response_mime_type": "image/jpeg"}
#   )
```


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROMPT 5 — PIPELINE PHASES 4, 5 (Parallel Veo + FFmpeg Stitch)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Implement pipeline phases 4 and 5, and the FFmpeg operations.

CREATE `backend/pipeline/phase4_generator.py`:
```python
# generate_all_clips_parallel(
#   keyframes: list[KeyFrame],       # N+1 images
#   clips: list[ClipPrompt],         # N prompts
#   veo_model: str,
#   aspect_ratio: str,
#   job_id: str,
#   progress_callback: Callable[[str, int, int], None],
# ) -> list[str]   # N clip file paths, ordered
#
# PARALLEL EXECUTION:
#   Use ThreadPoolExecutor(max_workers=len(clips))
#   Each thread calls generate_single_clip()
#   All clips fire SIMULTANEOUSLY
#   Collect results preserving order (results[clip_index] = path)
#
# generate_single_clip(
#   clip_index: int,
#   clip_number: int,
#   total: int,
#   prompt: str,
#   first_frame: KeyFrame,
#   last_frame: KeyFrame,
#   veo_model: str,
#   aspect_ratio: str,
#   job_id: str,
# ) -> str    # path to saved video file
#
#   MAX_RETRIES = 3
#   For each attempt:
#     1. sanitize_prompt(prompt)  — remove block words
#     2. Call veo_client.generate_clip(
#          prompt=sanitized_prompt,
#          first_frame_bytes=base64.b64decode(first_frame.image_b64),
#          last_frame_bytes=base64.b64decode(last_frame.image_b64),
#          aspect_ratio=aspect_ratio,
#          model=veo_model,
#        )
#     3. Save MP4 bytes to TMP_DIR/job_id/clip_{clip_number:02d}.mp4
#     4. Return path
#   On ContentPolicyError: rephrase prompt and retry
#   On TransientError (503/timeout): sleep 15s * attempt and retry
#   NEVER fall back to text-only (would lose frame anchors)
#   NEVER skip a clip — raise after max retries
```

CREATE `backend/video/ffmpeg_ops.py`:
```python
# All FFmpeg operations. No moviepy — pure subprocess FFmpeg only.
# Find ffmpeg via shutil.which("ffmpeg").
#
# normalize_clip(input_path: str, output_path: str, aspect_ratio="9:16") -> bool
#   W,H = (1080,1920) for 9:16, (1920,1080) for 16:9
#   -vf scale=W:H:force_original_aspect_ratio=decrease,pad=W:H:(ow-iw)/2:(oh-ih)/2,fps=24,format=yuv420p
#   -c:v libx264 -preset medium -crf 18
#   -pix_fmt yuv420p -video_track_timescale 12800
#   -c:a aac -ar 44100 -ac 2 -b:a 192k
#   -aresample=async=1,apad -shortest
#
# concat_clips(clip_paths: list[str], output_path: str) -> bool
#   Write concat list file. Use filter_complex concat (not stream copy).
#   Hard cuts — no xfade (frames already match at boundaries).
#   [0:v][0:a][1:v][1:a]...concat=n=N:v=1:a=1[vout][aout]
#   Final encode: crf=18, preset=medium, 192k AAC
#
# trim_trailing_dark(input_path: str, output_path: str, threshold=20) -> bool
#   Use ffmpeg blackdetect=d=0.3:pix_th=0.08 to find last dark section
#   Parse black_start timestamps from stderr
#   If found: trim to last_black_start - 0.1s using -t flag + -c copy
#
# trim_leading_black(input_path: str, output_path: str) -> bool
#   blackdetect on CTA file — find black_end of first black section
#   If found: -ss black_end re-encode
#
# loudnorm(input_path: str, output_path: str, target=-16.0, tp=-1.5) -> bool
#   Two-pass loudnorm:
#   Pass 1: analyze with loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json
#   Parse measured_I, measured_TP, measured_LRA, measured_thresh, offset
#   Pass 2: apply loudnorm with measured values
#
# generate_black_pause(output_path: str, duration=0.3) -> bool
#   -f lavfi -i color=black:size=1080x1920:rate=24:duration=0.3
#   -f lavfi -i anullsrc=r=44100:cl=stereo:d=0.3
#   -t 0.3 -c:v libx264 -crf 18 -c:a aac -video_track_timescale 12800
#
# probe_duration(path: str) -> float
#   Parse Duration from ffmpeg -i stderr
```

CREATE `backend/pipeline/phase5_stitcher.py`:
```python
# stitch_and_finalize(
#   clip_paths: list[str],
#   cta_path: str,
#   output_path: str,
#   aspect_ratio: str = "9:16",
# ) -> str    # path to final video
#
# Steps (in order):
# 1. normalize_clip() on each input clip → normalized list
# 2. concat_clips(normalized) → stitched.mp4 (hard cuts, frames match)
# 3. trim_trailing_dark(stitched) → trimmed.mp4
# 4. loudnorm(trimmed) → ad_normalized.mp4
# 5. trim_leading_black(cta_path) → cta_clean.mp4
# 6. loudnorm(cta_clean) → cta_normalized.mp4
# 7. generate_black_pause() → pause.mp4
# 8. concat_clips([ad_normalized, pause, cta_normalized]) → output_path
# Return output_path
```


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROMPT 6 — ORCHESTRATOR + FASTAPI ENDPOINTS (COMPLETE BACKEND)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Complete the backend: orchestrator + all API endpoints + SSE.

CREATE `backend/pipeline/orchestrator.py`:
```python
# run_pipeline(job_id: str, request: CreateJobRequest) -> None
# Runs in a background thread. Updates job_store at each step.
#
# PHASE 1 — Script Analysis
#   job_store.set_status(ANALYSING, PHASE_1, progress=5)
#   brief = analyse_script(request.script, request.num_clips, request.coach)
#   job_store.update(job_id, production_brief=brief)
#   emit SSE: phase_start(1, "Analysing script...")
#
# PHASE 2 — Prompt Generation
#   job_store.set_status(PROMPTING, PHASE_2, progress=20)
#   clips = generate_prompts(brief)
#   job_store.update(job_id, clips=clips)
#   emit SSE: phase_done(2)
#
# PHASE 3 — Image Generation (N+1 keyframes)
#   job_store.set_status(IMAGING, PHASE_3, progress=35)
#   For each keyframe generated:
#     emit SSE: keyframe_ready(index, total, preview_url)
#     update job keyframes in store
#   job_store.set_status(AWAITING, progress=50)
#   emit SSE: awaiting_approval(num_images=N+1)
#   PAUSE — wait for human approval via /approve endpoint
#
# PHASE 4 — Parallel Video Generation
#   job_store.set_status(GENERATING, PHASE_4, progress=55)
#   Progress callback: emit SSE clip_done(clip, total) each time a clip finishes
#   clip_paths = generate_all_clips_parallel(...)
#   Progress: 55 + (45 * clips_done / total_clips)
#
# PHASE 5 — Stitch
#   job_store.set_status(STITCHING, PHASE_5, progress=95)
#   final_path = stitch_and_finalize(clip_paths, CTA_ASSET_PATH, output)
#   job_store.update(job_id, final_video_path=final_path)
#   job_store.set_status(DONE, progress=100)
#   emit SSE: done(video_url)
#
# On any exception:
#   job_store.set_status(FAILED, error=str(e))
#   emit SSE: error(message)
```

COMPLETE `backend/main.py` — implement all endpoints:

```python
# POST /api/v2/jobs/create
#   Create VideoJob, save to job_store
#   Start run_pipeline in background thread (threading.Thread)
#   Return {job_id, status}

# GET /api/v2/jobs/{job_id}/status
#   Return full VideoJob (excluding image_bytes — return image_b64 truncated to first 100 chars as preview flag)
#   Actually: return {job_id, status, phase, progress, num_keyframes, keyframes_approved, clips_done, error}

# GET /api/v2/jobs/{job_id}/stream  — SSE endpoint
#   Use sse-starlette EventSourceResponse
#   Each job has an event queue (asyncio.Queue or simple list)
#   Stream all events for this job
#   Keep connection alive with heartbeat every 15s
#   Close when job is DONE or FAILED

# POST /api/v2/jobs/{job_id}/approve
#   Body: ApproveImagesRequest
#   Mark keyframes as approved
#   Signal orchestrator to proceed to Phase 4
#   Use threading.Event for the approval signal
#   Return {message: "approved, starting video generation"}

# POST /api/v2/jobs/{job_id}/regen-image
#   Body: RegenImageRequest (keyframe_index, optional new_emotion)
#   Regenerate that specific keyframe using Gemini Image
#   Update job_store
#   Return {keyframe: KeyFrame}

# POST /api/v2/jobs/{job_id}/regen-clip
#   Body: RegenClipRequest (clip_index 0-based)
#   Regenerate that specific clip using same keyframes[i] and keyframes[i+1]
#   Update clip_paths[clip_index]
#   Return {clip_url: str}

# GET /api/v2/video/{filename}
#   Serve from TMP_DIR using FileResponse
#   Content-Type: video/mp4

# GET /api/v2/keyframe/{job_id}/{index}
#   Return KeyFrame image as JPEG (decode base64, return as image/jpeg response)

# GET /api/v2/health
#   Return {status: "ok", version: "2.0"}
```

Add a global dict `_approval_events: dict[str, threading.Event]` so the
orchestrator can wait for approval and the /approve endpoint can signal it.

Add a global dict `_job_event_queues: dict[str, list[dict]]` for SSE events.
Orchestrator calls `emit_event(job_id, type, data)` to push events.
SSE endpoint reads and streams them.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROMPT 7 — NEXT.JS FRONTEND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Create the Next.js 14 frontend in `frontend/`. Use App Router, TypeScript,
Tailwind CSS. No external UI libraries. Dark theme throughout.

Design language: dark professional tool — charcoal background (#0f0f0f),
deep green accents (#1a5c3a), clean monospace for code/prompts, sharp edges.
This is an internal production tool for SuperLiving's ad team.

Run: `cd frontend && npx create-next-app@latest . --typescript --tailwind --app`

CREATE these pages:

`app/page.tsx` — Dashboard
- Header: "Flash Tool v2" in large text, subtitle "Script → Seamless Ad"
- "New Ad" button → /new
- List of recent jobs from GET /api/v2/jobs/list (add this endpoint)
- Each job card: status badge (color coded), coach name, num clips,
  created time, progress bar if in progress, "View" link
- Auto-refreshes every 5 seconds if any jobs are in progress

`app/new/page.tsx` — New Job
- Large textarea: "Paste your Hindi/Hinglish script here" (min-height: 300px)
- Row of config:
  - Coach select: Rishika / Rashmi / Seema / Pankaj / Dev / Arjun
  - Num clips: 3, 4, 5, 6 (radio buttons)
  - Duration label: shows "4 clips × 8s = 32s"
  - Aspect ratio: 9:16 (Reels) / 16:9 (YouTube)
  - Veo model: veo-3.1-generate-preview / veo-3.0-generate-preview
- "Generate Ad" button — calls POST /api/v2/jobs/create
- On success: redirect to /jobs/{id}/progress

`app/jobs/[id]/progress/page.tsx` — Live Progress
- Connects to SSE stream GET /api/v2/jobs/{id}/stream
- Shows current phase with animated progress bar
- Phase steps displayed as a vertical timeline:
  1. Script Analysis ✓/⟳/○
  2. Prompt Generation ✓/⟳/○
  3. Image Generation ✓/⟳/○
  4. Awaiting Approval ← when status=awaiting_approval, show "Review Images →" button
  5. Video Generation: shows N clip tiles, each with spinner then checkmark
  6. Stitching
  7. Done → "Watch Ad" button
- Live event log at the bottom (scrolling, monospace)

`app/jobs/[id]/review/page.tsx` — Image Review (Phase 3 gate)
- Title: "Review Keyframes — N+1 images for N clips"
- Explanation: "These images control the start and end of each clip.
  Image 0 = Clip 1 first frame. Image 1 = End of Clip 1 = Start of Clip 2. Etc."
- Grid of N+1 images (fetch from GET /api/v2/keyframe/{job_id}/{index})
- Each image: shows the image, index label, description (emotion), approve checkbox
- "Regenerate" button on each image → calls POST /api/v2/jobs/{id}/regen-image
- "Approve All & Generate Videos" button → calls POST /api/v2/jobs/{id}/approve
  → redirects back to /jobs/{id}/progress

`app/jobs/[id]/result/page.tsx` — Final Result
- Video player (HTML5 video, autoplay, controls, 9:16 aspect ratio)
- Download button
- Clip breakdown: list each clip with its prompt summary
- "Regenerate Clip" button on each → POST /api/v2/jobs/{id}/regen-clip
  → shows loading, then updates video
- "Start New Ad" button

CREATE `lib/api.ts` — typed API client:
```typescript
// All API calls to backend (default base: http://localhost:8000)
// Functions: createJob, getJobStatus, approveImages, regenImage,
//            regenClip, streamJobEvents (returns EventSource)
```

CREATE `components/StatusBadge.tsx` — colored status pill
CREATE `components/ProgressTimeline.tsx` — phase timeline component
CREATE `components/KeyFrameCard.tsx` — image card with regen button
CREATE `components/VideoPlayer.tsx` — 9:16 video player


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROMPT 8 — INTEGRATION TESTING + STARTUP SCRIPTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Wire everything together and make it runnable.

1. CREATE `backend/tests/test_pipeline.py`:
   A test script (not pytest — just a runnable Python script) that:
   - Tests Phase 1 with a sample MRK1 script (the UPSC failure script)
   - Prints the ProductionBrief JSON
   - Tests Phase 2 prompt generation
   - Prints all clip prompts
   - Tests word count validation for each dialogue
   - Tests dash detection
   - Does NOT call Veo or Imagen (mocks those)
   Run with: python -m backend.tests.test_pipeline

2. CREATE `start.sh` in project root:
   ```bash
   #!/bin/bash
   # Terminal 1: Backend
   cd backend && pip install -r requirements.txt
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 &
   # Terminal 2: Frontend
   cd frontend && npm install && npm run dev
   echo "Backend: http://localhost:8000"
   echo "Frontend: http://localhost:3000"
   echo "API docs: http://localhost:8000/docs"
   ```

3. CREATE `backend/tests/sample_script.py`:
   The MRK1 UPSC failure script as a Python string constant for testing:
   ```
   Script (Hindi/Hinglish):
   Teen attempt ho gaye. Prelims clear nahi hua.
   Gharwale bol rahe hain, chhod de ya shaadi kar le.
   [... full 6-clip script ...]
   ```

4. ADD to `backend/main.py`:
   - GET /api/v2/jobs/list — return last 20 jobs sorted by created_at desc
   - On startup: create TMP_DIR if not exists, log "Flash Tool v2 started"

5. FIX any import errors between all modules. Verify the import chain:
   main.py → orchestrator.py → phase1..5 → ai/clients → prompts/
   All imports must work with: `uvicorn backend.main:app --reload`

6. ADD `frontend/.env.local`:
   ```
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```
   Update `lib/api.ts` to use this env var.

7. FINAL CHECKLIST — verify each of these works:
   a. `curl http://localhost:8000/api/v2/health` → {"status":"ok","version":"2.0"}
   b. `curl -X POST http://localhost:8000/api/v2/jobs/create -H "Content-Type: application/json" -d '{"script":"test","num_clips":4,"coach":"Rishika"}'`
      → returns job_id without 500 error
   c. Frontend loads at http://localhost:3000 without console errors
   d. New job form submits and redirects to progress page
   e. python -m backend.tests.test_pipeline runs without import errors