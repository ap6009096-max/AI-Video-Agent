# Agent Responsibilities (Nested Creator OS)

Agents are **not removed**. They are nested under pipeline subgraphs and write artifacts to disk.

## Input

- Resolve source (YouTube / local / script / idea)
- Normalize paths under `source/`

## Analysis

- Transcript (Whisper `tiny`/`base`)
- Understanding, scenes, audio, speakers, moments
- Funny / viral / smart clip / podcast / research
- **Shared AI analysis** — single Gemini batch → `analysis/shared_ai_analysis.json`
- Optional face (gated by video type) and object keyframe tool

## Content

- Story / script / type / style / environment / storyboard
- Character / camera / director / motion / documentary
- Video / image generation
- Brand + content calendar (feature-gated)

## Localization

- Country / regional / language / cultural / humor
- Strictly limited to UI-selected `localization_targets`

## Rendering

- B-roll, voice, avatar, music, captions (once), reframe, render, quality, export
- Async FFmpeg via ThreadPool when enabled

## Growth

- Platform, SEO (reads shared AI), trend (24h cache), competitor (7d scaffold)
- Repurpose, thumbnail (top 3 CTR), analytics
