import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY       = os.getenv("GOOGLE_API_KEY", "")
VEO_MODEL            = os.getenv("VEO_MODEL", "veo-3.1-generate-preview")
IMAGEN_MODEL         = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-001")
GEMINI_MODEL         = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
GEMINI_IMAGE_MODEL   = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.0-flash-preview-image-generation")
MAX_PARALLEL_WORKERS = int(os.getenv("MAX_PARALLEL_WORKERS", "6"))
CLIP_RESOLUTION      = os.getenv("CLIP_RESOLUTION", "1080p")
LOUDNORM_TARGET      = float(os.getenv("LOUDNORM_TARGET", "-16"))
CTA_ASSET_PATH       = os.getenv("CTA_ASSET_PATH", "./backend/assets/cta.mp4")
TMP_DIR              = os.getenv("TMP_DIR", "/tmp/flash_tool")
