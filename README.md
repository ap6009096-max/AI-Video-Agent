# AI Video Agent

> **A global, YouTube-first AI Creator Operating System for turning ideas, experiences, knowledge, stories, videos, podcasts, and scripts into complete video content.**
>
> live link https://ai-video-agent-cqlricoiqzepckum4ka8jx.streamlit.app/

## Overview

**AI Video Agent** is an AI-powered Creator Operating System built to simplify the modern video-creation process.

Today, content creation often requires a collection of disconnected tools. Creators may research topics in one application, write scripts in another, edit video elsewhere, generate captions separately, optimize metadata manually, and prepare content for publishing through additional services.

This fragmented workflow creates unnecessary complexity, repeated work, and wasted time.

AI Video Agent brings these stages together into a **single, structured AI-assisted workflow**.

The platform helps creators move from an initial idea or source to a complete content package through research, planning, scripting, storyboarding, video production, localization, optimization, analytics, and publishing preparation.

---

## Why AI Video Agent?

The platform is built around a simple principle:

> **Creators should spend more time creating meaningful stories and less time managing disconnected tools.**

AI Video Agent provides one place to organize and automate the major stages of the content-creation process while keeping the creator in control of the story and final result.

---

## Start With Almost Anything

A project can begin with:

* A simple idea
* A personal experience
* A YouTube video
* An uploaded video
* A podcast episode
* An audio recording
* A script draft
* A story worth sharing

The system analyzes the available source and uses that information to build the appropriate content workflow.

---

## Creator Workflow

The platform provides a structured process for turning an idea or source into content.

| Stage                      | Purpose                                                           |
| -------------------------- | ----------------------------------------------------------------- |
| **Input**                  | Accept an idea, video, podcast, audio, YouTube source, or script  |
| **Research**               | Understand the subject and gather relevant information            |
| **Planning**               | Define the story, content direction, audience, and video approach |
| **Script**                 | Develop the narrative and dialogue                                |
| **Storyboard**             | Plan scenes, shots, visuals, voiceover, and transitions           |
| **Video Creation**         | Prepare visual, audio, voice, and production elements             |
| **Optimization**           | Improve platform fit, SEO, trends, thumbnails, and repurposing    |
| **Analytics**              | Provide performance predictions and content signals               |
| **Publishing Preparation** | Prepare final files and platform metadata                         |

---

## From Life Experience to Content

Valuable content does not always begin with a finished script.

It can begin with something that happened in real life.

A creator may experience something, learn from it, develop an idea, and turn that experience into a story that can be shared with an audience.

AI Video Agent is designed to support this process.

The platform can help transform:

**Experiences → Ideas → Stories → Scripts → Videos → Audience Feedback → Better Content**

This makes the system useful for personal storytelling, educational content, project documentation, creator journeys, and many other forms of video creation.

---

# Global Content Creation

AI Video Agent is designed for a **global creator ecosystem**.

The platform does not assume that one version of a video is equally effective for every audience.

The same underlying idea can be adapted for different:

* Continents
* Countries
* Regions
* Languages
* Cultures
* Professions
* Industries
* Interests
* Audience types
* Platforms
* Content categories

### Local and Global Audiences

Creators can develop content specifically for a local audience or expand the same concept toward regional and global audiences.

Examples include:

* India
* China
* Pakistan
* Japan
* South Korea
* Southeast Asia
* Europe
* Africa
* Middle East
* North America
* Latin America
* Global audiences

The underlying story can remain the same while the presentation changes for the intended audience.

---

## Audience-Aware Content

Different audiences may require different approaches.

AI Video Agent can use audience and regional context when planning:

* Language
* Cultural references
* Examples
* Story framing
* Tone
* Humor
* Visual direction
* Voice and accent
* Titles
* Descriptions
* Keywords
* Hashtags
* Thumbnail concepts
* Short-form versions
* Platform strategy

This is more than translation.

**Localization adapts the way the content is communicated for the intended audience.**

---

# Multilingual Content

AI Video Agent supports multilingual content workflows so creators can adapt one content idea for different markets.

### Supported Languages

* English
* Hindi
* Gujarati
* Bengali
* Tamil
* Telugu
* Marathi
* Japanese
* Korean
* Chinese
* French
* Spanish
* Portuguese
* German
* Arabic

### Voice Controls

* Male
* Female
* Neutral
* Country-specific accents
* Emotion
* Speaking speed
* Pitch

This allows creators to develop localized versions while preserving the original story or message.

---

# Long-Form and Short-Form Content

AI Video Agent supports both long-form and short-form content creation.

### Supported Content Types

* YouTube videos
* YouTube Shorts
* Podcast clips
* Educational videos
* Explainer videos
* Documentary-style videos
* Personal stories
* AI-assisted video concepts
* Social media content
* Repurposed content

---

## Multi-Duration Shorts

Long-form media can be analyzed to identify useful short-form moments.

Supported durations include:

* 10 seconds
* 15 seconds
* 30 seconds
* 40 seconds
* 45 seconds
* 60 seconds
* 90 seconds

Smart Clip Selection can use signals such as:

* Important moments
* Scene boundaries
* Transcript content
* Viral indicators
* Funny moments

A single long-form video can therefore become multiple short-form content assets.

---

## Selective Scene Transform (Phase 1)

The strongest edit experience is: upload a video, tell the AI what to change, change only that part, then download a real full video and a real Short.

1. Upload an authorized video (or YouTube when download is enabled).
2. The pipeline analyzes transcript, scenes, and speakers.
3. In Results, open a scene and enter a natural-language instruction (for example: “Make the guest’s answer in scene 3 shorter and funnier. Keep host, background, and music.”).
4. Click **CREATE VIDEO** again. The app writes `analysis/transform_intent.json` with **changed** vs **preserved** elements.
5. Render stitches the timeline with FFmpeg: only the target window is reworked (dialogue/voice/trim/captions where supported); other scenes are reused.
6. Outputs: `renders/final.mp4` (also under `final/`), plus `renders/shorts/short_*s_*.mp4` when Multi Shorts / Scene Transformation is on.
7. Quality validation + `validate_video` must pass before the UI shows **Video Ready** and enables downloads. Soft-skip without media is never treated as a successful video deliverable.

Real outputs only: the pipeline never invents probe fields or placeholder MP4s. Shorts are moment-selected cuts encoded to **1080×1920** (not rename-only copies). Partial Short failures keep the full video success and surface `Short creation failed. Stage: Short Render…` without broken download buttons.

Honest limits: Phase 1 does **not** synthesize new guest faces or generative video pixels. Unsupported generative requests are listed in the transform intent. Working files still use local `outputs/projects/{id}/` as a cache; **durable media is stored in Supabase Storage** when configured (see **Storage** below).

---

# AI-Assisted Capabilities

The platform brings multiple capabilities into one Creator Operating System.

### Content Intelligence

* Content understanding
* Transcription
* Scene analysis
* Speaker analysis
* Moment detection
* Smart clip selection
* Research

### Creative Development

* Story generation
* Script generation
* Localization
* Cultural adaptation
* Humor adaptation
* Storyboarding
* Character planning
* Camera planning
* Director planning
* Documentary planning

### Media Production

* Video planning
* Image planning
* Voice planning
* Avatar planning
* B-roll planning
* Dynamic captions
* Reframing
* Rendering
* Quality validation

### Content Optimization

* SEO and metadata
* Trend analysis
* Content repurposing
* Thumbnail planning
* Analytics prediction

---

# Technical Architecture

The application uses a **LangGraph-based workflow orchestration system** to coordinate the content pipeline.

The workflow manages analysis, planning, AI-assisted generation, optimization, validation, and export.

## Architecture Pipeline

```text
Input
→ Source Ingest
→ Transcript
→ Content Understanding
→ Scene Analysis
→ Audio Analysis
→ Speaker Analysis
→ Moment Detection
→ Smart Clips
→ Research
→ Story
→ Script
→ Localization
→ Storyboard
→ Video Direction
→ Motion Graphics
→ Video Planning
→ Image Planning
→ Voice Planning
→ Captions
→ Reframing
→ SEO
→ Trends
→ Repurposing
→ Thumbnail Planning
→ Analytics
→ Rendering
→ Quality Assurance
→ Export
```

Optional stages can be enabled or skipped according to project requirements.

---

# Project Artifacts

Every project produces structured artifacts that make workflows easier to inspect, reproduce, resume, and manage.

```text
outputs/projects/{project_id}/
```

### Core Files

```text
project.json
transcript.json
analysis.json
moments.json
clips.json
localization.json
video_plan.json
quality_report.json
memory.json
execution_history.jsonl
```

### Working Directories

```text
source/
transcripts/
analysis/
clips/
audio/
subtitles/
thumbnails/
images/
renders/
renders/shorts/
exports/
final/
```

---

# Project Recovery

Long-running AI workflows can fail or be interrupted.

AI Video Agent includes project recovery and resume functionality.

Creators can:

* Resume interrupted projects
* Retry failed stages
* Continue from stored checkpoints
* Restart from selected pipeline stages

This makes longer workflows more manageable and reduces the need to restart an entire project after a single failure.

---

# Storage

Supabase Storage provides **persistent** storage for project media (required on Streamlit Cloud where the filesystem is ephemeral):

* Source videos / audio
* Transcripts and analysis JSON (optional sync)
* Captions
* Rendered videos (`final.mp4`)
* Shorts
* Thumbnails and export manifests

Object layout (private bucket):

```text
projects/{project_id}/source/...
projects/{project_id}/captions/...
projects/{project_id}/renders/...
projects/{project_id}/shorts/...
projects/{project_id}/final/final.mp4
```

Local development without Supabase credentials uses a **local object mirror** under `OUTPUT_DIR/objects/` with the same key layout so tests and offline runs keep working. Configure Supabase for production durability.

If credentials are set but Storage is **unreachable** (wrong key, missing bucket, network), the app **falls back to the local mirror** and the sidebar shows `Unreachable → local fallback`. Create a **private** bucket named `ai-video-agent` (or match `SUPABASE_STORAGE_BUCKET`) in the Supabase dashboard — the app does not auto-create buckets.

**API keys**

| Key | Required for Storage? | Role |
|-----|----------------------|------|
| `SUPABASE_URL` | Yes | Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Server-side Storage upload/download/signed URLs |
| `SUPABASE_PUBLISHABLE_KEY` | No | Optional; unused by the Storage client today |
| `GEMINI_API_KEY` | No (for Storage) | LLM / understanding — separate from Storage |

Server-side only: `SUPABASE_SERVICE_ROLE_KEY` must never be exposed in the browser or committed to Git.

# YouTube

YouTube URL ingestion is **best-effort**. A video that plays in a normal browser may still fail on a hosted Streamlit server (403, unavailable, region, authentication, or bot restrictions).

* **Do not** store personal browser cookies or account credentials on Streamlit Cloud.
* On failure the UI shows a clear message and an **Upload Video Instead** control.
* Direct upload is the reliable path and always stores media in durable storage when configured.

# Deployment

AI Video Agent is designed to be simple to run in different environments.

## Local

Install dependencies:

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set at least `GEMINI_API_KEY`. Optionally set Supabase vars for durable storage.

Start the application:

```bash
python -m streamlit run app.py
# or: .\.venv\Scripts\python.exe -m streamlit run app.py
```

Open:

```text
http://localhost:8501
```

### Local test commands

```bash
python -m pytest tests/test_ingestion_youtube.py tests/test_ingestion_upload.py tests/test_supabase_storage.py tests/test_ingestion_workflow_paths.py -q
```

---

## Streamlit Cloud

1. Deploy from GitHub (Settings → main file `app.py`).
2. Add **Secrets** (Settings → Secrets), for example:

```toml
GEMINI_API_KEY = "..."
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "..."
SUPABASE_SERVICE_ROLE_KEY = "..."
SUPABASE_STORAGE_BUCKET = "ai-video-agent"
```

3. In Supabase: create a **private** Storage bucket named `ai-video-agent` (or match `SUPABASE_STORAGE_BUCKET`). Do not make the bucket public; the app uses signed URLs.
4. Do **not** set `YOUTUBE_COOKIES_FILE` on Cloud.

---

## Online / VPS

Run the application on a server:

```bash
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

Then open the application through the server address in a web browser.

For production deployments, Docker Compose or systemd can be used.

---

## Docker

### Docker Compose

```bash
docker compose up --build
```

### Manual Docker

```bash
docker build -t ai-video-agent .
```

```bash
docker run --rm -p 8501:8501 --env-file .env -v "%cd%/outputs:/app/outputs" ai-video-agent
```

macOS / Linux:

```bash
docker run --rm -p 8501:8501 --env-file .env -v "$PWD/outputs:/app/outputs" ai-video-agent
```

Open:

```text
http://localhost:8501
```

Mounting the `outputs/` directory keeps project artifacts available across container restarts.

---

# Technology Stack

| Area                    | Technology                           |
| ----------------------- | ------------------------------------ |
| **Interface**           | Streamlit                            |
| **AI**                  | Google Gemini                        |
| **Agent Orchestration** | LangGraph                            |
| **LLM Framework**       | LangChain                            |
| **Speech Recognition**  | Whisper                              |
| **Computer Vision**     | OpenCV                               |
| **Video Processing**    | FFmpeg                               |
| **Language**            | Python                               |
| **Project Storage**     | Supabase Storage (local mirror offline) |
| **Deployment**          | Streamlit Cloud, Docker, Linux VPS, local |

---

# Content Categories

AI Video Agent is designed to support many content categories.

### Education

Tutorials, explainers, courses, study content, and educational documentaries.

### Technology

AI, software, programming, devices, startups, and technology content.

### Business

Entrepreneurship, companies, careers, jobs, productivity, and industry topics.

### Entertainment

Stories, commentary, interviews, comedy, pop culture, and general entertainment.

### Politics and Current Affairs

Educational and explanatory content about politics, public policy, history, and current affairs.

### Lifestyle

Travel, food, hobbies, personal development, daily life, and experiences.

### Science and Knowledge

Science, history, engineering, research, space, and general knowledge.

### Creator Journey

Building in public, career journeys, learning journeys, project documentation, personal stories, experiments, and lessons learned.

---

# Why Content Changes by Audience

A subject can stay the same while the video changes because the audience changes.

Different audiences may have different:

* Knowledge levels
* Languages
* Cultural references
* Interests
* Problems
* Expectations
* Humor
* Search behavior
* Platform habits
* Regional context

AI Video Agent is therefore designed around **audience-aware content creation** rather than a single universal version of every video.

---

# Product Philosophy

Technology should make content creation easier without removing the creator from the process.

The creator provides:

* Experience
* Perspective
* Ideas
* Emotion
* Purpose
* Story

AI Video Agent provides the workflow and AI-assisted tools needed to transform those inputs into structured content.

The goal is not to replace the creator.

**The goal is to help creators turn more of their ideas and experiences into stories worth sharing.**

---

# Future Direction

The platform can evolve toward a broader Creator Operating System with:

* More video-generation providers
* More image-generation providers
* Advanced editing
* Stronger character consistency
* Automated visual composition
* Advanced motion graphics
* Distributed processing
* Automated publishing
* Deeper analytics
* Creator performance feedback
* Advanced content repurposing
* Collaborative creator workflows

The long-term objective is to help creators move from **local storytelling to global storytelling** while preserving the original meaning and purpose of their content.

---

# Project Status

**Status: Local MVP**

AI Video Agent currently provides an end-to-end foundation for AI-assisted YouTube and video content creation, including content analysis, structured workflow orchestration, localization, planning, optimization, project recovery, rendering, analytics prediction, and publishing preparation.

---

<div align="center">

**AI Video Agent**

*Create locally. Adapt globally. Tell better stories.*

</div>
