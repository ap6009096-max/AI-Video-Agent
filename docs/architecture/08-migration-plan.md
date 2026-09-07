# Migration Plan

## Phase 1 — Foundation (this PR)

1. Docs 01–10
2. `ProjectRefs` + layout `cache/` / `logs/`
3. Dual-write packs **and** paths
4. Nested Main + 6 pipeline wrappers
5. Shared AI analysis, Whisper `tiny`, trend cache, face gate, thumbnail top-3

## Phase 2 — Memory & async

1. Prefer path-only in checkpoints; expand rehydrate
2. ThreadPool FFmpeg / render / export
3. Split app / render / graph logs

## Phase 3 — Vision & plugins

1. Keyframe object detection tool
2. Competitor pack + 7d cache
3. Plugin provider registry

## Phase 4 — Hardening

- Docker 8GB notes, smoke tests, Gemini call counters

## Compatibility rules

- Do not delete agents
- Keep `build_video_graph` / `run_video_workflow`
- Soft-skip + feature flags unchanged
- Creator OS UI stages remain a view over the same pipeline
