# Optimization Report (Rules 5–19)

| Rule | Change | Status |
|------|--------|--------|
| 5 Whisper | Default `WHISPER_MODEL=tiny`; allow tiny/base | Implemented |
| 6 Sampling | Keep 1 fps; max frames; reframe ≤1–2 fps | Enforced |
| 7 Face | Gate Haar when video_type ∈ talking-head set | Implemented |
| 8 Object | Keyframe tool → `analysis/objects.json`; soft-skip | Scaffold |
| 9 Gemini | `shared_ai_analysis.json` batch report | Implemented |
| 10–11 Cache | Trend 24h; competitor 7d | Implemented |
| 12 Localization | Never expand beyond selected targets | Hardened |
| 13 Captions | Single SRT + derivatives | Documented / enforced |
| 14 Thumbnails | Cap top 3 by CTR heuristic | Implemented |
| 15 Async | ThreadPool FFmpeg runner | Implemented |
| 16 Logging | app / render / graph logs | Implemented |
| 17 Checkpoint | SqliteSaver shared across subgraphs | Preserved |
| 18 Plugins | Provider registry adapters | Scaffold |
| 19 Targets | Expect 60–80% fewer Gemini calls on growth/content | Measured via shared report + caches |

## Expected impact (8GB hosts)

- Lower Whisper RAM (`tiny` vs `base`)
- Smaller checkpoints (path-only cutover)
- Fewer concurrent Gemini payloads
- Non-blocking render via executor
