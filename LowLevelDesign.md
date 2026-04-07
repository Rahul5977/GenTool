# SuperLiving Flash Tool — System Design Document
## Script → Seamless AI Video Ad Pipeline
### Version 2.0 | Fresh Repository

---

## 1. EXECUTIVE SUMMARY

A pipeline that takes a Hindi/Hinglish ad script targeting Tier 3/4 Indian cities
and produces a seamless, high-quality video ad in ~2.5 minutes.

**Core Innovation:** N clips require N+1 images. All images are generated first,
human-reviewed, then all Veo video calls fire in parallel. Zero sequential bottleneck.
Zero face drift. Perfect frame alignment at every clip boundary.

**Target Output:** ₹10-15 CPI from ₹30-40 current.

---

## 2. HIGH LEVEL DESIGN

```
┌──────────────────────────────────────────────────────────────────────┐
│                         FLASH TOOL v2                                │
│                                                                      │
│  SCRIPT ──► ANALYSE ──► GEN PROMPTS ──► GEN IMAGES ──► GEN VIDEO   │
│               │              │               │               │       │
│             Gemini         Gemini          Gemini          Veo 3.1  │
│            2.5 Pro        2.5 Pro        2.0 Flash      (parallel) │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.1 Five Phases

```
Phase 1: SCRIPT ANALYSIS          (~5s)
  Input:  Raw Hindi/Hinglish ad script
  Output: Structured production brief
          - Clip count, dialogue per clip (15-19 words per 8s)
          - Emotional arc per clip
          - Character description
          - Locked background description
          - End-emotion per clip boundary

Phase 2: PROMPT GENERATION        (~10s)
  Input:  Production brief
  Output: N clip prompts (text)
          Each prompt has: APPEARANCE, LOCATION, ACTION, DIALOGUE,
                          AUDIO, CAMERA, LIGHTING, LAST FRAME spec
          Claude Verifier runs: checks all 13 rules, auto-fixes

Phase 3: IMAGE GENERATION         (~15s, sequential)
  Input:  Character description + clip prompts
  Output: N+1 keyframe images
          Image 0: Character reference (Clip 1 first frame)
          Image 1 to N: Transition frames (last of clip i = first of clip i+1)
          Human reviews all images in UI before proceeding

Phase 4: VIDEO GENERATION         (~120s, parallel workers)
  Input:  N+1 images + N prompts
  Output: N video clips
          Worker 1: Clip 1 (Image0 → Image1, Prompt1)
          Worker 2: Clip 2 (Image1 → Image2, Prompt2)
          Worker N: Clip N (ImageN-1 → ImageN, PromptN)
          All fire simultaneously. Done when slowest finishes.

Phase 5: STITCH + CTA             (~10s)
  Input:  N video clips (already frame-aligned at boundaries)
  Output: Final ad MP4
          - Hard cuts (no crossfade needed — frames match exactly)
          - Audio loudnorm to -16 LUFS
          - CTA appended (with leading black trimmed)
          - 1080p H.264, 192k AAC
```

### 2.2 The N+1 Image Architecture

```
          Image 0         Image 1         Image 2         Image 3
             │               │               │               │
          [Clip 1]        [Clip 2]        [Clip 3]        (final)
          start→end       start→end       start→end
             │               │               │
          Veo call 1      Veo call 2      Veo call 3
         (parallel)      (parallel)      (parallel)

Image 0 = Imagen-generated character reference
Image 1 = Gemini Image transform of Image 0 → emotion at end of Clip 1
Image 2 = Gemini Image transform of Image 1 → emotion at end of Clip 2
Image N = Gemini Image transform of Image N-1 → emotion at end of Clip N

Every clip boundary: last pixel of Clip i = first pixel of Clip i+1
No drift possible. No crossfade needed.
```

### 2.3 System Components

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   NEXT.JS        │    │   FASTAPI        │    │   GOOGLE AI      │
│   Frontend       │◄──►│   Backend        │◄──►│   APIs           │
│                  │    │                  │    │                  │
│ - Script input   │    │ - Job orchestrat │    │ - Gemini 2.5 Pro │
│ - Image review   │    │ - Worker pool    │    │ - Gemini Image   │
│ - Progress SSE   │    │ - Prompt engine  │    │ - Veo 3.1        │
│ - Video player   │    │ - FFmpeg stitch  │    │ - Imagen 3       │
└──────────────────┘    └──────────────────┘    └──────────────────┘
                                 │
                        ┌────────┴────────┐
                        │   JOB STORE     │
                        │   (Redis/mem)   │
                        └─────────────────┘
```

---

## 3. LOW LEVEL DESIGN

### 3.1 Data Models

```python
# ── Core models ───────────────────────────────────────────────────────────

class Script(BaseModel):
    raw_text: str                    # Hindi/Hinglish script as pasted
    language: str = "hinglish"
    target_city_tier: int = 3        # 3 or 4
    coach: str = "Rishika"           # Rishika / Rashmi / Seema / Pankaj etc
    gender: str = "female"           # protagonist gender
    num_clips: int                   # 4-6 typically

class ProductionBrief(BaseModel):
    clips: list[ClipBrief]
    character: CharacterSpec
    locked_background: str           # verbatim 60+ word background description
    aspect_ratio: str = "9:16"
    
class ClipBrief(BaseModel):
    clip_number: int
    dialogue: str                    # 15-19 words for 8s, 13-17 for 7s
    word_count: int
    duration_seconds: int            # 5, 6, 7, or 8
    emotional_state: str             # what character feels in this clip
    end_emotion: str                 # target expression at clip boundary

class CharacterSpec(BaseModel):
    age: int
    gender: str
    skin_tone: str                   # hex code + description
    face_shape: str
    hair: str                        # length, texture, style
    outfit: str                      # verbatim locked description
    accessories: list[str]           # earrings, watch, etc
    distinguishing_marks: list[str]  # moles, scars — identity anchors

class ClipPrompt(BaseModel):
    clip_number: int
    duration_seconds: int
    scene_summary: str
    prompt: str                      # full Hindi prompt
    dialogue: str
    word_count: int
    end_emotion: str                 # passed to image generation
    verified: bool = False
    verification_issues: list[str] = []

class KeyFrame(BaseModel):
    index: int                       # 0 to N
    image_bytes: bytes
    mime_type: str = "image/jpeg"
    description: str                 # what this frame represents
    approved: bool = False           # human approval flag

class VideoJob(BaseModel):
    job_id: str
    status: JobStatus
    phase: PipelinePhase
    progress: int                    # 0-100
    clips: list[ClipPrompt]
    keyframes: list[KeyFrame]        # N+1 images
    clip_paths: list[str]            # generated video paths
    final_video_path: str = ""
    error: str = ""
    created_at: datetime
    updated_at: datetime

class JobStatus(str, Enum):
    PENDING     = "pending"
    ANALYSING   = "analysing"
    PROMPTING   = "prompting"
    IMAGING     = "imaging"          # generating keyframes
    AWAITING    = "awaiting_approval" # human reviews images
    GENERATING  = "generating"       # Veo parallel generation
    STITCHING   = "stitching"
    DONE        = "done"
    FAILED      = "failed"

class PipelinePhase(str, Enum):
    PHASE_1 = "script_analysis"
    PHASE_2 = "prompt_generation"
    PHASE_3 = "image_generation"
    PHASE_4 = "video_generation"
    PHASE_5 = "stitch"
```

### 3.2 Backend Services

```
backend/
├── main.py                    # FastAPI app, routes, SSE
├── models.py                  # Pydantic models (above)
├── job_store.py               # In-memory / Redis job state
│
├── pipeline/
│   ├── __init__.py
│   ├── orchestrator.py        # Runs all 5 phases in sequence
│   ├── phase1_analyser.py     # Script → ProductionBrief
│   ├── phase2_prompter.py     # ProductionBrief → ClipPrompts
│   ├── phase3_imager.py       # ClipPrompts → N+1 KeyFrames
│   ├── phase4_generator.py    # KeyFrames + Prompts → Video clips (parallel)
│   └── phase5_stitcher.py     # Clips + CTA → Final MP4
│
├── ai/
│   ├── gemini_client.py       # Gemini 2.5 Pro wrapper
│   ├── imagen_client.py       # Imagen 3 wrapper
│   ├── veo_client.py          # Veo 3.1 wrapper
│   └── verifier.py            # Claude/Gemini prompt verification (13 rules)
│
├── prompts/
│   ├── system_analyser.py     # Phase 1 system prompt
│   ├── system_prompter.py     # Phase 2 system prompt  
│   ├── system_verifier.py     # Verifier system prompt (13 rules)
│   └── system_imager.py       # Keyframe generation instructions
│
└── video/
    ├── ffmpeg.py              # All FFmpeg operations
    ├── stitch.py              # Clip stitching logic
    └── cta.py                 # CTA append, black trim
```

### 3.3 Phase 1: Script Analyser

```python
# phase1_analyser.py

ANALYSIS_DIMENSIONS = [
    "clip_count",           # how many clips, what durations
    "dialogue_split",       # exact words per clip, counted
    "em_dash_audit",        # zero dashes in dialogue
    "emotional_arc",        # emotion per clip + transition emotion
    "character_spec",       # full appearance, outfit, accessories
    "locked_background",    # 60+ word setting description
    "veo_block_check",      # health/skin/transformation language flags
    "hook_type",            # scene-based (good) vs emotion-stating (bad)
    "coach_line_check",     # Rishika quoted, not on screen
]

# Model: Gemini 2.5 Pro at temperature 0.1
# Output: Structured ProductionBrief JSON
# Validation: word count, dash check, block word check all automated
```

### 3.4 Phase 2: Prompt Generator

```python
# phase2_prompter.py — generates one prompt per clip

PROMPT_SECTIONS_PER_CLIP = [
    "CONTINUING_FROM",      # clips 2+ only — full inventory
    "FACE_LOCK_STATEMENT",  # ⚠️ exact warning text
    "OUTFIT_APPEARANCE",    # verbatim from character spec
    "LOCATION",             # verbatim locked background + freeze line
    "ACTION",               # ONE state, Tier 1-2 movement only
    "DIALOGUE",             # 15-19 words, no dashes, bracket format
    "AUDIO",                # crystal-clear, studio-quality, close-mic
    "CAMERA",               # TIGHT MCU, eye-level, 8k, static
    "LIGHTING",             # dual source, ghost-face prevention
    "VISUAL_FORMAT_PROHIBITIONS",  # 9:16, no letterbox, no UI
    "LAST_FRAME",           # exact end state + full background inventory
    "END_EMOTION",          # what Gemini Image should generate for transition
]

# After generation: Claude Verifier checks all 13 rules
# Auto-fix applied for: word count, dashes, aspect ratio, expression transitions
# Human review: see full prompts in UI before proceeding
```

### 3.5 Phase 3: Image Generator — The Core Innovation

```python
# phase3_imager.py

def generate_all_keyframes(
    character_spec: CharacterSpec,
    clip_prompts: list[ClipPrompt],
    locked_background: str,
) -> list[KeyFrame]:
    """
    Generate N+1 images for N clips.
    All images generated BEFORE any Veo call.
    Human reviews all images in UI.
    
    Image 0: Character reference — Imagen 3
    Image 1..N: Transition frames — Gemini 2.0 Flash Image
    """
    keyframes = []
    
    # ── Image 0: Character reference via Imagen 3 ──────────────────────────
    image_0 = generate_character_reference(
        character_spec=character_spec,
        background=locked_background,
        initial_emotion=clip_prompts[0].emotional_state,
    )
    keyframes.append(KeyFrame(index=0, image_bytes=image_0,
                              description="Clip 1 first frame — character reference"))
    
    # ── Images 1..N: Transition frames via Gemini Image ────────────────────
    for i, clip_prompt in enumerate(clip_prompts):
        previous_frame = keyframes[i].image_bytes
        
        transition_frame = generate_transition_frame(
            previous_frame=previous_frame,
            end_emotion=clip_prompt.end_emotion,
            character_spec=character_spec,
            locked_background=locked_background,
        )
        
        keyframes.append(KeyFrame(
            index=i + 1,
            image_bytes=transition_frame,
            description=f"End of Clip {i+1} / Start of Clip {i+2}: {clip_prompt.end_emotion}"
        ))
    
    return keyframes  # length = num_clips + 1


def generate_character_reference(character_spec, background, initial_emotion) -> bytes:
    """
    Imagen 3 call — generates the anchor face for the entire ad.
    
    Key parameters that produce Tier 3/4 realistic characters:
    - "Shot on an ordinary smartphone: uneven exposure, slight grain"
    - "Ultra-realistic natural skin texture, visible pores, no airbrushing"
    - "No cinematic lighting, no dramatic shadows, completely unretouched"
    - "Looks like a real person recording a high-trust UGC video"
    """
    prompt = build_imagen_prompt(character_spec, background, initial_emotion)
    # Imagen 3 API call
    # Returns: bytes (JPEG)


def generate_transition_frame(
    previous_frame: bytes,
    end_emotion: str,
    character_spec: CharacterSpec,
    locked_background: str,
) -> bytes:
    """
    Gemini 2.0 Flash Image call.
    Input: previous keyframe image
    Instruction: change ONLY the expression to end_emotion
    Keep: face, outfit, background, posture, lighting IDENTICAL
    
    This is what makes the pipeline seamless:
    - Last frame of Clip i = exactly this image
    - First frame of Clip i+1 = exactly this image
    - Perfect pixel match at every cut
    """
    instruction = f"""
    This is a frame from an Indian UGC video ad.
    Generate a version of this exact frame with ONLY the expression changed.
    
    TARGET EXPRESSION: {end_emotion}
    
    KEEP IDENTICAL (do not change):
    - Face structure, skin tone, all features
    - Hair style and color
    - Outfit and all clothing
    - All accessories (earrings, watch, etc)
    - Background — every object in exact same position
    - Camera angle and distance (TIGHT MCU, chin to mid-chest)
    - Lighting direction and color temperature
    - Head position and posture
    
    OUTPUT: 9:16 portrait JPEG, same framing as input.
    """
    # Gemini 2.0 Flash Image API call
    # Returns: bytes (JPEG)
```

### 3.6 Phase 4: Parallel Video Generator

```python
# phase4_generator.py

import asyncio
from concurrent.futures import ThreadPoolExecutor

def generate_all_clips_parallel(
    keyframes: list[KeyFrame],    # N+1 images
    clip_prompts: list[ClipPrompt],  # N prompts
    veo_model: str,
    aspect_ratio: str,
    job_id: str,
    progress_callback: Callable,
) -> list[str]:
    """
    Fire all N Veo calls simultaneously.
    Each worker gets: first_frame[i], last_frame[i+1], prompt[i]
    Total time = slowest single clip (not N × single clip).
    """
    
    num_clips = len(clip_prompts)
    
    # Build worker args
    worker_args = []
    for i in range(num_clips):
        worker_args.append({
            "clip_index":   i,
            "clip_number":  i + 1,
            "total_clips":  num_clips,
            "prompt":       clip_prompts[i].prompt,
            "first_frame":  keyframes[i],      # Image i
            "last_frame":   keyframes[i + 1],  # Image i+1
            "veo_model":    veo_model,
            "aspect_ratio": aspect_ratio,
            "job_id":       job_id,
        })
    
    # Fire all in parallel using thread pool (Veo calls are I/O bound)
    with ThreadPoolExecutor(max_workers=num_clips) as executor:
        futures = {
            executor.submit(generate_single_clip, **args): args["clip_index"]
            for args in worker_args
        }
        
        results = [None] * num_clips
        for future in as_completed(futures):
            clip_index = futures[future]
            try:
                clip_path = future.result()
                results[clip_index] = clip_path
                progress_callback(
                    job_id=job_id,
                    clip_done=clip_index + 1,
                    total=num_clips,
                )
            except Exception as e:
                # Single clip failure — retry that clip only
                logger.error(f"Clip {clip_index + 1} failed: {e}")
                results[clip_index] = retry_clip(worker_args[clip_index])
        
        return results


def generate_single_clip(
    clip_index: int,
    clip_number: int,
    total_clips: int,
    prompt: str,
    first_frame: KeyFrame,
    last_frame: KeyFrame,
    veo_model: str,
    aspect_ratio: str,
    job_id: str,
) -> str:
    """
    Single Veo call with first + last frame.
    Returns: path to downloaded video file.
    
    MAX RETRIES: 3 (for transient network errors only)
    NEVER fall back to text-only — loses the frame anchors.
    """
    MAX_RETRIES = 3
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            config = GenerateVideosConfig(
                aspect_ratio=validated_ar(aspect_ratio),
                number_of_videos=1,
                resolution="1080p",
                enhance_prompt=True,
                last_frame=types.Image(
                    image_bytes=last_frame.image_bytes,
                    mime_type="image/jpeg"
                ),
            )
            
            # Pre-sanitize prompt (remove health/skin block words)
            sanitized_prompt = sanitize_for_veo(prompt)
            
            operation = video_client.models.generate_videos(
                model=veo_model,
                prompt=sanitized_prompt,
                image=types.Image(
                    image_bytes=first_frame.image_bytes,
                    mime_type="image/jpeg"
                ),
                config=config,
            )
            
            # Poll until done
            operation = poll_until_done(operation, timeout=300)
            
            # Download
            video_bytes = download_video(operation)
            path = save_clip(video_bytes, job_id, clip_number)
            return path
            
        except TransientError as e:
            if attempt < MAX_RETRIES:
                time.sleep(15 * attempt)
                continue
            raise
        except ContentPolicyError:
            # Rephrase and retry — never skip
            prompt = rephrase_blocked_prompt(prompt, attempt)
            continue
```

### 3.7 Phase 5: Stitch + CTA

```python
# phase5_stitcher.py

def stitch_and_finalize(
    clip_paths: list[str],
    cta_path: str,
    output_path: str,
    aspect_ratio: str = "9:16",
) -> str:
    """
    Because frames are pixel-matched at boundaries, NO CROSSFADE NEEDED.
    Use simple concatenation — faster and higher quality than xfade.
    
    Pipeline:
    1. Normalize all clips (1080p, 24fps, 192k AAC, yuv420p)
    2. Concat with hard cuts (frames already match — no visual jump)
    3. Trim trailing dark frames from last clip
    4. Loudnorm entire ad to -16 LUFS
    5. Trim CTA leading black (blackdetect)
    6. Concat ad + 0.3s pause + CTA
    7. Final encode: crf=18, preset=medium, b:a=192k
    """
    
    # Step 1: Normalize clips
    normalized = [normalize_clip(p, aspect_ratio) for p in clip_paths]
    
    # Step 2: Hard concat (no xfade needed — frames match)
    stitched = concat_clips(normalized, output_path="stitched.mp4")
    
    # Step 3: Trim trailing dark (Veo last clip often has dark frames)
    trimmed = trim_trailing_dark(stitched, threshold=20)
    
    # Step 4: Loudnorm the ad content
    normalized_audio = loudnorm(trimmed, target_lufs=-16, tp=-1.5)
    
    # Step 5: CTA: trim leading black + loudnorm
    cta_clean = trim_leading_black(cta_path)
    cta_normalized = loudnorm(cta_clean, target_lufs=-16, tp=-1.5)
    
    # Step 6: Final concat with 0.3s pause
    pause = generate_black_pause(duration=0.3)
    final = concat_segments([normalized_audio, pause, cta_normalized], output_path)
    
    return final


def normalize_clip(path: str, aspect_ratio: str) -> str:
    """
    - scale to 1080×1920 (9:16) or 1920×1080 (16:9)
    - fps=24, yuv420p
    - crf=18, preset=medium
    - aac 192k, 44100 Hz stereo
    - video_track_timescale=12800
    """
    TARGET = {"9:16": (1080, 1920), "16:9": (1920, 1080)}.get(aspect_ratio, (1080, 1920))
    W, H = TARGET
    # ffmpeg command...
```

### 3.8 API Endpoints

```
POST   /api/v2/jobs/create          Start full pipeline → returns job_id
GET    /api/v2/jobs/{id}/status     Poll job status + progress
GET    /api/v2/jobs/{id}/stream     SSE — real-time progress events
POST   /api/v2/jobs/{id}/approve    Human approves keyframes → triggers Phase 4
POST   /api/v2/jobs/{id}/regen-image/{index}  Regenerate one keyframe
POST   /api/v2/jobs/{id}/regen-clip/{index}   Regenerate one clip (same frames)
GET    /api/v2/video/{filename}     Serve final video

POST   /api/v2/verify-prompts       Run verifier on prompt set (standalone)
POST   /api/v2/analyse-script       Phase 1 only (dev/debug)
```

### 3.9 SSE Event Stream Schema

```python
# Every event: {"type": str, "data": dict}

EVENTS = {
    "phase_start":      {"phase": 1-5, "name": str, "message": str},
    "phase_done":       {"phase": 1-5, "duration_ms": int},
    "clip_start":       {"clip": int, "total": int},
    "clip_done":        {"clip": int, "total": int, "duration_ms": int},
    "keyframe_ready":   {"index": int, "total": int, "preview_url": str},
    "awaiting_approval": {"num_images": int, "message": str},
    "approved":         {"message": str},
    "progress":         {"percent": int, "message": str},
    "done":             {"video_url": str, "duration_s": float},
    "error":            {"clip": int, "message": str, "retrying": bool},
}
```

### 3.10 Prompt System Architecture

```
prompts/
├── system_analyser.py
│   Rules: dialogue word count enforcement, em-dash detection,
│          Veo block word detection, emotional arc validation
│
├── system_prompter.py  
│   Rules: 13-section structure, TIGHT MCU enforcement,
│          LOCKED BACKGROUND verbatim copy, Tier 1/2 movement only,
│          dual lighting ghost-face prevention, no dashes,
│          voice quality tags in AUDIO block
│
├── system_verifier.py  (13 rules — Claude or Gemini)
│   Rule 1:  Word count 15-19 per 8s / 13-17 per 7s / 10-13 per 5s
│   Rule 2:  Single action per clip (no transitions)
│   Rule 3:  Dual lighting (ghost-face prevention)
│   Rule 4:  No voiceover — character speaks on screen
│   Rule 5:  Phone screen = black if shown
│   Rule 6:  LOCKED BACKGROUND verbatim all clips
│   Rule 7:  CONTINUING FROM + LAST FRAME present
│   Rule 8:  Face lock integrity per character
│   Rule 9:  Realism checks (MCU, no theatrical expressions)
│   Rule 10: 9:16 format prohibition block present
│   Rule 11: Emotional authenticity (Tier 3/4 register)
│   Rule 12: No second character in frame
│   Rule 13: Zero dashes in dialogue text
│
└── system_imager.py
    Instructions for generating transition keyframes:
    - Keep all identity anchors identical
    - Change only the target expression
    - Preserve background object positions exactly
    - Maintain camera angle and distance
```

### 3.11 Frontend Routes

```
/                       → Dashboard (recent jobs, create new)
/new                    → Script input + config
/jobs/{id}/review       → Image review (approve N+1 keyframes)
/jobs/{id}/generating   → Real-time progress (SSE stream)
/jobs/{id}/result       → Video player + download
/jobs/{id}/clips        → Individual clip management + regen
```

### 3.12 Key Config Parameters (Environment Variables)

```bash
GOOGLE_API_KEY=...              # Gemini + Veo + Imagen
VEO_MODEL=veo-3.1-generate-preview
IMAGEN_MODEL=imagen-3.0-generate-001
GEMINI_MODEL=gemini-2.5-pro
GEMINI_IMAGE_MODEL=gemini-2.0-flash-exp  # Nano Banana for keyframes
MAX_PARALLEL_WORKERS=6          # Max simultaneous Veo calls
CLIP_RESOLUTION=1080p
ASPECT_RATIO=9:16
AUDIO_BITRATE=192k
LOUDNORM_TARGET=-16             # LUFS — social media standard
CTA_ASSET_PATH=./assets/cta.mp4
REDIS_URL=redis://localhost:6379  # Optional — falls back to in-memory
```

---

## 4. QUALITY GUARANTEES

### 4.1 Video Quality
| Parameter | Value | Why |
|-----------|-------|-----|
| Resolution | 1080p | Veo API explicit parameter |
| FPS | 24 | Standard for generated content |
| Video codec | H.264 crf=18 | Near-lossless for web |
| Bit depth | yuv420p | Browser compatible |

### 4.2 Audio Quality  
| Parameter | Value | Why |
|-----------|-------|-----|
| Audio codec | AAC | Universal |
| Bitrate | 192k | Broadcast standard |
| Sample rate | 44100 Hz | CD quality |
| Loudness | -16 LUFS | Social media standard |
| Peak | -1.5 dBTP | No clipping |

### 4.3 Seamlessness
| Issue | How Fixed |
|-------|-----------|
| Face drift | N+1 images, same face seeded every clip |
| Background drift | Gemini Image preserves background exactly |
| Camera drift | Both frame endpoints control framing |
| Clip boundary jump | last_frame[i] = first_frame[i+1] exactly |
| Within-clip glitch | TIGHT MCU — hands physically out of frame |
| Sideways look | Direct camera stated in every ACTION block |
| 14s black pause | trim_trailing_dark + CTA blackdetect |
| Hard cuts | No longer jarring — frames match |

---

## 5. WHAT THIS PIPELINE CANNOT CONTROL

1. **Veo hallucination in the middle of a clip** — the start and end are
   anchored but the 8 seconds between them is still Veo-generated.
   Mitigation: TIGHT MCU (constrained frame), one action per clip,
   no hand movements.

2. **Dialogue naturalness** — TTS quality is Veo-dependent.
   Mitigation: voice quality tags in AUDIO block, no dashes in dialogue,
   correct word count for clip duration.

3. **CTA relevance** — whether the price anchor resonates.
   Not a pipeline concern — a script concern.

4. **Hook effectiveness** — whether the first 3 seconds stop the scroll.
   Not a pipeline concern — a script concern.

---

## 6. ESTIMATED TIMELINE PER AD

```
Phase 1 — Script analysis:      5s
Phase 2 — Prompt generation:   10s
Phase 3 — Image generation:    20s   (5 images × ~4s each)
[Human image review]:          60s   (human in the loop)
Phase 4 — Parallel video gen: 120s   (all clips simultaneously)
Phase 5 — Stitch + CTA:        10s
─────────────────────────────────
Machine time:                 165s   (~2.7 min)
Total with human review:      225s   (~3.8 min)
vs current sequential:        600+s  (~10+ min)
```