"""Flash Tool configuration — loaded from .env file.

MODEL REFERENCE (as of google-genai SDK 1.0.0):
  GEMINI_MODEL        = gemini-2.5-pro-preview-03-25   (text, JSON generation)
  IMAGEN_MODEL        = imagen-3.0-generate-001        (Frame 0, text→image)
  GEMINI_IMAGE_MODEL  = gemini-2.0-flash-preview-image-generation  (Frames 1-N, image edit)
  VEO_MODEL           = veo-2.0-generate-001           (video clips)

IMPORTANT — model string rules:
  - NEVER add "models/" prefix to any model ID. The SDK adds it automatically.
  - GEMINI_MODEL works on SDK default API version (v1beta).
  - IMAGEN_MODEL works on SDK default API version (v1beta). NO override needed.
  - GEMINI_IMAGE_MODEL works on SDK default API version (v1beta). NO override needed.
  - VEO_MODEL requires http_options={"api_version": "v1alpha"} in the Veo client ONLY.
"""

import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY       = os.getenv("GOOGLE_API_KEY", "")

# Text generation — script analysis, prompt generation, verification
GEMINI_MODEL         = os.getenv("GEMINI_MODEL", "gemini-2.5-pro-preview-03-25")

# Frame 0: text-to-image (Imagen 3)
IMAGEN_MODEL         = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-001")

# Frames 1-N: image editing (Gemini Flash Image)
GEMINI_IMAGE_MODEL   = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.0-flash-preview-image-generation")

# Video generation
VEO_MODEL            = os.getenv("VEO_MODEL", "veo-2.0-generate-001")

MAX_PARALLEL_WORKERS = int(os.getenv("MAX_PARALLEL_WORKERS", "6"))
CLIP_RESOLUTION      = os.getenv("CLIP_RESOLUTION", "1080p")
LOUDNORM_TARGET      = float(os.getenv("LOUDNORM_TARGET", "-16"))
CTA_ASSET_PATH       = os.getenv("CTA_ASSET_PATH", "./backend/assets/cta.mp4")
TMP_DIR              = os.getenv("TMP_DIR", "/tmp/flash_tool")