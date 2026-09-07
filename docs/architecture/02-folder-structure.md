# Project Folder Structure

## Per-project layout (`outputs/projects/{id}/`)

```text
project/
  source/           # uploaded / downloaded media
  transcripts/      # Whisper JSON + text
  analysis/         # packs, shared_ai_analysis.json, objects.json
  clips/            # smart clips + exports
  captions/         # captions.srt (+ vtt/ass derivatives)
  thumbnails/       # planned / rendered thumbs
  audio/ images/ renders/ exports/ final/ subtitles/
  cache/            # project-local ephemeral cache
  logs/             # app.log, render.log, graph.log
  memory.json
  checkpoints.sqlite
  execution_history.jsonl
```

## Global caches

- `outputs/cache/trends.json` — trend pack, TTL 24h
- `outputs/cache/competitors/{key}.json` — competitor scaffold, TTL 7d

## Helpers

- `tools/project/layout.py` — `ensure_project_layout`, dual-write aggregators
- `core/paths.py` — path resolution
- `schemas/project_refs.py` — lean path references on graph state
