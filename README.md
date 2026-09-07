# AI Creator Platform

Python-first local MVP: Streamlit UI, LangGraph orchestration, LangChain + Gemini, Whisper, OpenCV, and FFmpeg. Artifacts live on the filesystem under `outputs/` — no database, no queue, no OAuth publish.

## Quick start

```bash
cd ai-video-agent
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env   # macOS / Linux
```

Set `GEMINI_API_KEY` in `.env`. Install [FFmpeg](https://ffmpeg.org/) (leave `FFMPEG_PATH` empty to use PATH).

YouTube URLs download local media by default (`YOUTUBE_DOWNLOAD_ENABLED=true`, requires `yt-dlp`). Only process content you are authorized to use. Set the flag to `false` for metadata-only. **Upload** remains fully supported.

```bash
streamlit run app.py
pytest
```

## AI Creator Operating System (Prompt 50)

One Streamlit app (`app.py`) + one LangGraph workflow orchestrates Prompts 1–50 agents as an end-to-end **Creator OS**:

```
Research → Planning → Script → Storyboard → Video Creation
  → Optimization → Analytics → Publishing Preparation
```

| Stage | Capabilities (agents / artifacts) |
|-------|-----------------------------------|
| Research | Ingest, transcript, moments, smart clips, podcast clips, research report |
| Planning | Story, video type / style / environment, brand kit, content calendar |
| Script | Script + country / region / language / cultural / humor |
| Storyboard | Storyboard, image generation, motion graphics |
| Video Creation | Video generation, B-roll, voice, avatar, music, captions, reframe, render, quality |
| Optimization | Platform, SEO, trend, repurpose, thumbnail |
| Analytics | Analytics **prediction** pack (`analysis/analytics_plan.json`) |
| Publishing Preparation | Export manifest + platform metadata (**plan-only** — not live social post) |

**How to run the full package:** open the Streamlit UI → choose idea / YouTube / upload / script → click **Apply Creator OS preset** (enables research, storyboard, video generation, SEO, thumbnail, content calendar, analytics, captions, clips, platform) → **GENERATE PACKAGE**.

Progress shows Creator OS stages first; fine-grained `PIPELINE_STEPS` stay in a collapsed expander. Results are grouped by stage.

Idea briefs use `SourceType.idea` and route through the same script ingest as pasted scripts (no separate PDF/web crawler).

## What you can do

1. Provide a YouTube URL, upload video/podcast audio, paste an idea brief, or paste a script  
2. Choose video type, visual style, environment, country, region, language, humor, platform  
3. Toggle AI features or apply the **Creator OS preset**  
4. Click **GENERATE PACKAGE**  
5. Inspect stage progress, then results: research, planning, scripts, storyboard, video, optimization, analytics, publishing prep  

### Multi-duration Shorts export

Enable **Multi Shorts Export** (feature toggle) and pick **Short Durations** (default 10 / 40 / 90 seconds; also 15/30/45/60). From a long upload or YouTube download, Smart Clip Selection harvests analysis-backed windows per duration (moments, viral/funny, scenes, transcript). Render still writes `renders/final.mp4` (concat of selected clips) **and** separate files:

- `renders/shorts/short_{duration}s_{index}.mp4`
- Copied into `exports/` and `final/` / `clips/` on export

`analysis/clips.json` tags each clip with `target_duration` and `source_signals`. Distinct from Video Gen mode strings and plan-only creative agents.

## Architecture

One LangGraph workflow (`graph/workflow.py`) with specialized agent nodes:

```
input → source ingest → transcript (video) → understanding → scene/audio/speaker
  → moments → funny?/viral? → smart clips → podcast? → research? → supervisor?
  → story → script
  → country → region → language → cultural? → humor?
  → video type → visual style → environment
  → storyboard? → character?/camera?/director?/motion?/documentary?
  → video_generation? → image_generation? → b-roll?/voice?/avatar?/music? → captions → reframe
  → platform → brand? → seo? → trend? → repurpose? → calendar? → thumbnail? → analytics?
  → render → quality (± one re-render) → export
```

Feature flags and config drive **conditional skip edges** (e.g. Original Voice skips TTS; No Avatar skips avatar; No Music skips music; Storyboard/Character Management/Camera Planning/Director/Motion Graphics/Documentary/Video Generation/Image Generation/SEO/Trend/Repurpose/Thumbnail/Analytics off skip those nodes; viral/funny/cultural off bypass those nodes). Soft-skips inside agents remain as a safety net.

LangChain is used for Gemini prompts / structured output inside agents. FFmpeg/OpenCV/Whisper run locally when available; optional providers mock/skip when not configured.

### Voice localization (Prompt 27)

Pipeline data flow:

```
Transcript → LanguageAgent (translation) → VoiceAgent (TTS) → Render audio sync → final.mp4
```

- **Languages:** English, Hindi, Gujarati, Bengali, Tamil, Telugu, Marathi, Japanese, Korean, Chinese, French, Spanish, Portuguese, German, Arabic  
- **Controls:** Male / Female / Neutral presets, country accents (`voices_accents.json`), emotion, speaking speed, pitch  
- **TTS:** set `TTS_PROVIDER=edge` (edge-tts neural voices). `none` / passthrough preserves original audio  
- **Artifacts:** `analysis/voice_plan.json`, `audio/voice_{lang}.mp3`; render muxes primary VO when generated  

### Avatar planning (Prompt 28)

Avatar Agent runs after Voice (before Music) and writes `analysis/avatar_plan.json`:

```json
{ "avatar_type": "", "voice": "", "language": "", "emotion": "" }
```

plus capability plan fields: lip sync, gesture, eye contact, expression, multi-language speaking metadata. Presenters: Male/Female/Business/Teacher/News anchor/Influencer/Custom. **Plan-only MVP** — no lip-sync ML composite yet; enable via Avatar feature toggle + avatar preset.

### Dynamic captions (Prompt 29)

ASS + FFmpeg burn-in caption engine with styles:

**TikTok · Shorts · Reels · Podcast · Gaming · Educational** (+ legacy Platform Safe / Minimal / Pop / Kinetic / High Contrast)

Effects (ASS tags, visible when burn-in is on):

- Word highlighting / karaoke (`\k`)
- Emoji insertion (style + checkbox)
- Pop / bounce / zoom (`\t` scale animation)

Artifacts: `captions/captions.srt|.vtt|.ass`, optional `captions/burned_in.mp4`.

### Thumbnail planning (Prompt 30)

Thumbnail Agent runs after Platform/SEO/Trend (before Render) and writes `analysis/thumbnail_plan.json`:

```json
{ "title": "", "hook": "", "thumbnail_text": "", "emotion": "", "layout": "" }
```

plus `face_placement`, `click_titles`, and `platform`. Supports **YouTube · Instagram · Facebook · TikTok** (aliases map Shorts/Reels). Text prefers SEO → trend topics → script/platform metadata; layout/face zones come from `config/thumbnails.json`. **Plan-only MVP** — no branded image compose; Render still extracts `thumbnail.jpg`. Enable via Thumbnail feature toggle (+ optional Thumbnail Platform override).

### SEO / Metadata (Prompt 31)

SEO Agent runs after Platform (before Trend/Thumbnail) and writes `analysis/seo_plan.json`:

```json
{ "title": "", "description": "", "tags": [], "hashtags": [], "keywords": [] }
```

Supports **YouTube · Instagram · Facebook · TikTok · LinkedIn · Pinterest**. Prefers existing platform/script metadata; clamps to per-platform limits in `config/seo.json`. **Plan-only MVP** — does not replace PlatformAgent export hints or auto-publish. Enable via SEO / Metadata feature toggle (+ optional SEO Platform override).

### Trend detection (Prompt 32)

Trend Agent runs after SEO (before Repurpose/Thumbnail) and writes `analysis/trend_plan.json`:

```json
{ "trend_score": 0, "trend_topics": [], "recommended_tags": [] }
```

plus trending hashtags/keywords, viral patterns, and audience relevance. Uses **Gemini** for topic classification / trend matching when `GEMINI_API_KEY` is set; otherwise heuristic matching against `config/trends.json` seeds. Enable via Trend Detection feature toggle.

### Content repurposing (Prompt 33)

Repurpose Agent runs after Trend (before Thumbnail) and writes `analysis/repurpose_plan.json`:

```json
{
  "source_kind": "",
  "reels": "",
  "shorts": "",
  "tiktok": "",
  "blog_summary": "",
  "linkedin_post": "",
  "twitter_thread": [],
  "instagram_caption": "",
  "newsletter_summary": ""
}
```

Workflow: **Source → AI Analysis → Multiple Output**. Input kinds: Video / Podcast / Article / Transcript (Auto maps from job source). Gemini when configured; heuristic excerpt fallback otherwise. Plan-only — no separate renders per format. Enable via Content Repurposing toggle (+ optional Repurpose Source).

### Analytics prediction (Prompt 34)

Analytics Agent runs after Thumbnail (before Render) and writes `analysis/analytics_plan.json`:

```json
{ "engagement_score": 0, "retention_score": 0, "shareability_score": 0 }
```

plus internal `watch_time_score` and `ctr_score`. Gemini when configured; otherwise heuristic blend of viral/trend/SEO/hook/thumbnail signals (`config/analytics.json`). **This is a prediction model, not a guarantee.** Plan-only — does not change render. Enable via Analytics Prediction feature toggle.

### Image generation (Prompt 36)

Image Agent runs after Video Generation (before B-roll) and writes `analysis/image_plan.json` plus PNG assets under `images/`:

```json
{
  "scene_id": "",
  "prompt": "",
  "style": "",
  "environment": "",
  "image_path": ""
}
```

Capabilities: scene prompts, storyboard frames, B-roll visuals, thumbnails, background plates (tagged via `kind`). Gemini plans prompts when configured; files are written via Imagen when available, otherwise minimal PNG placeholders (noted in plan). Does **not** replace Render’s ffmpeg thumbnail or composite into `final.mp4` yet. Enable via Image Generation feature toggle.

### Storyboard (Prompt 37)

Storyboard Agent runs after Environment (before Director / Video Generation / Image Generation) and writes `analysis/storyboard_plan.json` with timed shots:

```json
{
  "scene": 1,
  "duration": 5,
  "camera": "",
  "visual": "",
  "voiceover": "",
  "transition": ""
}
```

Also stores `shot_list` / `scene_list` (same rows) plus `camera_plan` and `transition_plan` string arrays. Distinct from Story Agent (`stories.json` narrative beats) and ImageAgent `kind=storyboard` (generated frames). Plan-only — does not drive Render yet. Enable via Storyboard feature toggle.

### Character Management (Prompt 40)

Character Management Agent runs after Storyboard (before Director) and writes `analysis/character_plan.json` — a cast bible for cross-scene consistency. Supports role types: human · narrator · ai_avatar · mascot · animated. Plan-only — distinct from late-pipeline Avatar Agent (presenter lip-sync) and from Director continuity notes.

```json
{
  "characters": [
    {
      "name": "Host",
      "role_type": "human",
      "appearance": "",
      "clothing": "",
      "voice": "",
      "personality": "",
      "expressions": ["smile", "concern"]
    }
  ],
  "consistency_notes": ["Keep Host clothing identical across scenes."]
}
```

Director may enrich `Character:` continuity notes from the cast; Video Generation may append cast consistency lines to scene prompts. Enable via Character Management feature toggle (default off).

### Camera Planning (Prompt 41)

Camera Planning Agent runs after Character Management (before Director) and writes `analysis/camera_plan.json` with per-scene camera instructions. Supported shot types: wide · medium · close_up · extreme_close_up · drone · tracking · pov · cinematic. Plan-only — distinct from Storyboard’s in-file `camera_plan` string array and from Director `camera_flow`.

```json
{
  "instructions": [
    {
      "scene": 1,
      "shot_type": "wide",
      "movement": "slow push-in",
      "instruction": "Establish environment with a locked-off wide, then gentle cinematic push."
    }
  ]
}
```

Director may seed `camera_flow` from this plan; Video Generation may prefer shot_type / movement when building prompts. Enable via Camera Planning feature toggle (default off).

### Director (Prompt 39)

Director Agent runs after Camera Planning (before Motion Graphics) and writes `analysis/director_plan.json` for scene sequencing and continuity (story, character, environment, camera). Plan-only — does not call media APIs or replace Storyboard / Video Generation / Render.

Public surface:

```json
{
  "scene_order": [1, 2, 3],
  "continuity_notes": ["Story: ...", "Character: ...", "Environment: ..."],
  "camera_flow": ["scene 1→2: establish wide then push in"]
}
```

When present, Video Generation may reorder storyboard-derived shots to match `scene_order`. Enable via Director feature toggle (default off).

### Motion Graphics (Prompt 42)

Motion Graphics Agent runs after Director (before Documentary) and writes `analysis/motion_graphics_plan.json` — a **plan-only** graphic-layer overlay list (titles, kinetic type, lower thirds, charts/stats, educational callouts). It does **not** burn overlays with After Effects, Remotion, or ffmpeg. Distinct from CaptionAgent’s kinetic caption style and from Video Generation’s `"Motion Graphics"` mode string.

Supported overlay kinds: kinetic_typography · animated_title · lower_third · data_visualization · chart · statistic · educational_overlay.

```json
{
  "overlays": [
    {
      "scene": 1,
      "kind": "animated_title",
      "text": "",
      "style": "",
      "animation": "",
      "timing": "",
      "position": ""
    }
  ]
}
```

Video Generation may append short overlay cues into scene prompts when this pack is present. Enable via Motion Graphics feature toggle (default off).

### Documentary (Prompt 43)

Documentary Agent runs after Motion Graphics (before Video Generation) and writes `analysis/documentary_plan.json` — a **plan-only** narrative arc with research, evidence, narration, interview, and timeline planning. Distinct from the video_types / Video Gen mode string `"Documentary"`.

```json
{
  "introduction": "",
  "chapters": [{"title": "", "summary": ""}],
  "conclusion": ""
}
```

Video Generation may append intro/chapter/conclusion cues into scene prompts when this pack is present. Enable via Documentary feature toggle (default off).

### Video Generation (Prompt 38)

Video Generation Agent runs after Documentary (before Image Generation) and writes a **provider-agnostic** plan to `analysis/video_generation_plan.json` — scene prompts, shot sequence, and camera movement plan for any later executor (Runway, Pika, Luma, local, etc.). It does **not** call video vendor APIs or write `.mp4`. Distinct from Render’s ffmpeg `render_plan.json`.

Modes (from job `video_type` / config aliases): Cinematic · Animation · Documentary · Explainer · AI Avatar · Motion Graphics.

```json
{
  "shots": [{ "scene": 1, "duration": 5, "prompt": "", "camera_move": "", "shot_type": "" }],
  "shot_sequence": ["scene 1: medium / slow push-in (5s)"],
  "camera_movement_plan": ["scene 1: slow push-in"],
  "scene_prompts": ["..."],
  "mode": "Cinematic",
  "provider": "gemini"
}
```

`provider` is only `none` | `gemini` | `heuristic`. Enable via Video Generation feature toggle (default off).

## Project layout

Each job writes `outputs/projects/{project_id}/` with:

| Path | Purpose |
|------|---------|
| `project.json` | Project metadata |
| `transcript.json` | Transcript (root alias) |
| `scenes.json`, `analysis.json`, `moments.json`, `clips.json` | Root aliases of analysis JSON |
| `localization.json` | Locale + cultural + humor rollup |
| `video_plan.json` | Creative + A/V + render plan rollup |
| `quality_report.json` | Quality checks alias |
| `source/`, `transcripts/`, `analysis/` | Working data |
| `clips/`, `audio/`, `subtitles/`, `thumbnails/`, `images/`, `final/` | Deliverable folders |
| `renders/shorts/` | Per-duration Short MP4s when Multi Shorts Export is on |
| `captions/`, `renders/`, `exports/` | Pipeline working + export package |
| `memory.json` | Prompt 26 orchestration index (steps, agent_outputs, retries) |
| `execution_history.jsonl` | Append-only node start/complete/fail/resume events |
| `checkpoints.sqlite` | LangGraph Sqlite checkpointer (`thread_id` = project id) |

### Resume & partial rerun

The UI **Memory & Resume** section can:

- **Resume project** — continue an incomplete/failed job from its Sqlite checkpoint  
- **Rerun from step** — clear downstream memory indexes and jump from a selected node  
- **Retry failed steps** — one retry per failed agent (default max 1)

Workflow version is stored as `workflow_version` (`26.0`). Resume refuses mismatched versions (force a full new job).

## Environment variables

See [`.env.example`](.env.example). Common keys:

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key |
| `GEMINI_MODEL` | Model id (default `gemini-3.6-flash`) |
| `GEMINI_FALLBACK_MODELS` | Comma-separated supported fallback model ids (empty by default) |
| `GEMINI_MAX_RETRIES` | Application retries per model for temporary 429/5xx errors (default `2`) |
| `GEMINI_RETRY_BASE_SECONDS` | Initial retry delay (default `2`) |
| `GEMINI_RETRY_MAX_SECONDS` | Maximum retry delay (default `30`) |
| `WHISPER_MODEL` | Whisper size (`tiny` default; `base` recommended for non-English / localization) |
| `FFMPEG_PATH` | Optional absolute path to `ffmpeg` |
| `TTS_PROVIDER` | TTS engine: `edge` (edge-tts) or `none` / passthrough |
| `OUTPUT_DIR` | Artifact root (default `outputs`) |
| `LOG_LEVEL` | Logging level |
| `APP_ENV` | `development` / `production` (affects log format) |
| `LOG_TO_FILE` | `true` writes rotating logs to `{OUTPUT_DIR}/logs/app.log` |
| `SENTRY_DSN` | Optional Sentry DSN for error reporting (empty = off) |
| `SENTRY_TRACES_SAMPLE_RATE` | Sentry traces sample rate (default `0.0`) |
| `MAX_UPLOAD_MB` | Upload size limit |

## Deployment

Final command on all targets:

```bash
streamlit run app.py
```

### Local machine

1. Create a venv and `pip install -r requirements.txt`
2. Install system [FFmpeg](https://ffmpeg.org/) (leave `FFMPEG_PATH` empty to use PATH)
3. Copy `.env.example` → `.env` and set `GEMINI_API_KEY`
4. Run `streamlit run app.py`
5. Optional VPS-style file logs: `LOG_TO_FILE=true`

### Docker

```bash
# Compose (recommended)
docker compose up --build

# Or plain Docker
docker build -t ai-video-agent .
docker run --rm -p 8501:8501 --env-file .env -v "%cd%/outputs:/app/outputs" ai-video-agent
# macOS/Linux: -v "$PWD/outputs:/app/outputs"
```

Mount `outputs/` so projects persist. FFmpeg is installed in the image. Healthcheck probes `http://127.0.0.1:8501/_stcore/health`.

### Linux VPS

**Option A — Docker on the VPS**

```bash
git clone <repo> && cd ai-video-agent
cp .env.example .env   # set GEMINI_API_KEY (and optional SENTRY_DSN)
docker compose up -d --build
```

**Option B — systemd + venv**

```bash
sudo apt-get update && sudo apt-get install -y ffmpeg python3.12 python3.12-venv
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set keys; APP_ENV=production; LOG_TO_FILE=true
```

Example unit (`/etc/systemd/system/ai-video-agent.service`):

```ini
[Unit]
Description=AI Video Agent
After=network.target

[Service]
WorkingDirectory=/opt/ai-video-agent
EnvironmentFile=/opt/ai-video-agent/.env
ExecStart=/opt/ai-video-agent/.venv/bin/streamlit run app.py --server.address=0.0.0.0 --server.port=8501
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then: `sudo systemctl enable --now ai-video-agent`.

### CI / monitoring / errors

- GitHub Actions: [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs `pytest` and `docker build`
- Monitoring: Docker/Compose healthcheck on Streamlit `/_stcore/health`
- Error reporting: set `SENTRY_DSN` to enable Sentry (no-op when empty)

## Tests

```bash
pytest
pytest -m integration   # needs FFmpeg for fixture media path
```

## Limitations (MVP)

- No OAuth / automatic publishing (platform pack stays `not_published`)  
- No hosted DB/queue — resume uses local `memory.json` + `checkpoints.sqlite` per project  
- TTS needs `TTS_PROVIDER=edge` (+ `edge-tts` package); otherwise voice plans preserve original audio  
- Emotion is prosody mapping (rate/pitch/volume), not a separate neural emotion model  
- YouTube path downloads local media via yt-dlp by default (`YOUTUBE_DOWNLOAD_ENABLED=true`; authorized use only; FFmpeg on PATH recommended). Set `false` for metadata-only. Upload remains fully supported for transcription  
- No Kubernetes / cloud auto-deploy — use Docker Compose or systemd on a VPS
