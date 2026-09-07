# LangGraph Design — Main + Six Subgraphs

## Main Graph (`graph/main.py`)

Nodes (each invokes a compiled subgraph or segment runner):

| Node | Subgraph module |
|------|-----------------|
| `input_pipeline` | `graph/pipelines/input_pipeline.py` |
| `analysis_pipeline` | `graph/pipelines/analysis_pipeline.py` |
| `content_pipeline` | `graph/pipelines/content_pipeline.py` |
| `localization_pipeline` | `graph/pipelines/localization_pipeline.py` |
| `render_pipeline` | `graph/pipelines/rendering_pipeline.py` |
| `growth_pipeline` | `graph/pipelines/growth_pipeline.py` |

Shared `SqliteSaver` checkpointer + `thread_id` for resume across pipeline boundaries.

## Subgraph contents (preserved agents)

| Subgraph | Agents / nodes |
|----------|----------------|
| Input | input_agent, youtube/local/script ingest |
| Analysis | transcript, understanding, scene/audio/speaker, moments, funny/viral, smart_clip, podcast, research, shared Gemini writer, gated face/object tools |
| Content | story, script, video_type/style/environment, storyboard, character/camera/director/motion/documentary, video_generation, image_generation, brand, calendar |
| Localization | country/regional/language/cultural/humor — only selected targets |
| Rendering | b_roll, voice, avatar, music, captions, reframe, render, quality, export |
| Growth | platform, seo, trend (+24h cache), competitor scaffold, repurpose, thumbnail (top 3), analytics |

## Segment runner

`graph/pipelines/runner.py` executes ordered node callables with soft-skip routers so nesting does not delete conditional logic from the flat graph during Phase 1.
