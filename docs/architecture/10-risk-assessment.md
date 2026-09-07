# Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Nested graphs + checkpointer thread_id semantics | Resume skips / duplicates | Share one SqliteSaver; document resume at pipeline boundaries; keep flat graph fallback |
| Dual-write → path-only breaks UI expecting packs | Missing results panel data | Rehydrate loads packs from paths; dual-write until UI bridged |
| Whisper `tiny` quality (non-English) | Bad transcripts / localization | Document `base` for localization jobs; env override |
| Shared AI analysis schema drift | Downstream miss fields | Versioned JSON + graceful fallbacks to prior Gemini path |
| Competitor scaffold mistaken for live scrapes | Wrong growth advice | Mark offline/heuristic; plugin hook for live later |
| Object tool CPU cost | Slow analysis | Soft-skip; keyframes only; feature flag |
| ThreadPool + Streamlit session | Race on progress | Job runner owns futures; UI polls status only |

## Residual

Phase 4 Docker memory caps and automated Gemini counters remain follow-ups.
