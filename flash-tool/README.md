# flash-tool

AI-powered Hindi/Hinglish video ad generation pipeline for **SuperLiving** — an Indian health app.

## What it does

Given a raw Hindi/Hinglish script, flash-tool produces a short-form vertical video ad (9:16) featuring a consistent AI coach character, by running a 5-phase pipeline:

| Phase | Name | Description |
|-------|------|-------------|
| 1 | Script Analysis | Parse the script into a `ProductionBrief` (clip breakdown, character spec, setting) |
| 2 | Prompt Generation | Generate and self-verify per-clip Veo prompts |
| 3 | Image Generation | Produce keyframe reference images via Imagen / Gemini |
| 4 | Video Generation | Drive Google Veo to render each clip from the keyframe |
| 5 | Stitch | Concatenate clips, apply loudnorm, append CTA via ffmpeg |

A human approval gate sits between Phase 3 and Phase 4 — the operator reviews keyframes before video generation begins.

## Stack

- **Backend**: FastAPI + Python 3.12
- **AI**: Gemini 2.5 Pro (text), Gemini 2.0 Flash (image understanding), Imagen 3 (keyframes), Veo 3 (video)
- **Video processing**: ffmpeg
- **Frontend**: TBD

## Quick start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in GOOGLE_API_KEY
uvicorn main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs`.

## API overview

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v2/jobs/create` | Submit a script, start pipeline |
| `GET` | `/api/v2/jobs/{id}/status` | Poll job status |
| `GET` | `/api/v2/jobs/{id}/stream` | SSE progress stream |
| `POST` | `/api/v2/jobs/{id}/approve` | Approve keyframes, unblock Phase 4 |
| `POST` | `/api/v2/jobs/{id}/regen-image` | Re-generate a single keyframe |
| `POST` | `/api/v2/jobs/{id}/regen-clip` | Re-generate a single video clip |
| `GET` | `/api/v2/video/{filename}` | Serve a generated video file |
| `GET` | `/api/v2/health` | Health check |
