# Data Flow

## Path-first state

`WorkflowState` carries lean `ProjectRefs` paths. Agents load JSON from disk when needed and write updated paths back.

```text
UI job → MainGraph → subgraph node
  → load pack from path (if needed)
  → compute / Gemini / FFmpeg
  → write artifact under project/
  → dual-write path (+ pack during Phase 1)
  → checkpoint (prefer paths)
```

## Shared AI analysis

1. Analysis pipeline writes `analysis/shared_ai_analysis.json` once.
2. SEO, story, script, thumbnail, trend enrichers **read** that file before optional Gemini enrich.

## Caches

| Cache | Path | TTL |
|-------|------|-----|
| Trends | `outputs/cache/trends.json` | 24h |
| Competitors | `outputs/cache/competitors/{key}.json` | 7d |

## Captions

Single `captions/captions.srt`; platform exports copy/symlink — no regenerate.
