# Performance Analysis

## Baseline pain (pre-refactor)

- Full packs embedded in LangGraph state → large SQLite checkpoints
- Whisper `base` default (~RAM heavy on 8GB)
- Many independent Gemini calls for SEO / story / thumbnail / trend
- Synchronous FFmpeg blocking Streamlit
- Single `app.log`

## After Phase 1–3

| Area | Before | After |
|------|--------|-------|
| Whisper | `base` | `tiny` default (`base` for localization) |
| State | Full packs | Paths + dual-write → path-only |
| Gemini (growth/content) | N separate calls | 1 shared report + optional enrich |
| Trends | Always rebuild | 24h disk cache |
| Competitors | N/A | 7d scaffold cache |
| Thumbnails | Unbounded plans | Top 3 CTR |
| Face detect | Always in reframe | Gated by video type |
| FFmpeg | Sync | ThreadPool optional |
| Logs | One file | app / render / graph |

## Measurement

- Count Gemini invocations in `logs/graph.log` before/after shared report
- Target: **60–80% reduction** on growth/content path when shared report + caches hit
