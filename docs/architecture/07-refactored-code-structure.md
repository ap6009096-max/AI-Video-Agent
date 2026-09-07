# Refactored Code Structure

```text
ai-video-agent/
  graph/
    workflow.py          # public APIs + node implementations (preserved)
    main.py              # MainGraph supervisor
    pipelines/
      runner.py          # segment execution
      input_pipeline.py
      analysis_pipeline.py
      content_pipeline.py
      localization_pipeline.py
      rendering_pipeline.py
      growth_pipeline.py
    rehydrate.py         # disk → state
  schemas/
    project_refs.py      # lean path refs
  tools/
    project/layout.py    # cache/ + logs/ dirs
    cache/trends.py      # 24h trend cache
    cache/competitors.py # 7d competitor cache
    analysis/shared_ai.py
    vision/objects.py
    vision/face_gate.py
    ffmpeg/async_runner.py
    thumbnail/catalog.py # top-3 CTR
  plugins/
    registry.py
    providers.py
  docs/architecture/     # 01–10
```
