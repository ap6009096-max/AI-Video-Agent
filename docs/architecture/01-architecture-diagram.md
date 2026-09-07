# Architecture Diagram — Nested Creator OS

## Overview

The AI Creator Platform uses a **Main Graph supervisor** that orchestrates six pipeline subgraphs. Agents remain intact; large payloads live on disk; graph state carries **paths** (plus dual-write packs during migration).

```mermaid
flowchart TD
  UI[Streamlit_UI] --> Main[MainGraph_Supervisor]
  Main --> InputG[InputGraph]
  Main --> AnalysisG[AnalysisGraph]
  Main --> ContentG[ContentGraph]
  Main --> LocG[LocalizationGraph]
  Main --> RenderG[RenderingGraph]
  Main --> GrowthG[GrowthGraph]
  InputG --> Disk[Project_Filesystem]
  AnalysisG --> Disk
  ContentG --> Disk
  LocG --> Disk
  RenderG --> Disk
  GrowthG --> Disk
  AnalysisG --> SharedAI[shared_ai_analysis_json]
  GrowthG --> TrendCache[cache_trends_json]
  GrowthG --> CompCache[cache_competitors]
```

## Main Graph

Coarse sequence: `input_pipeline` → `analysis_pipeline` → `content_pipeline` → `localization_pipeline` → `render_pipeline` → `growth_pipeline` → END.

Supervisor duties: soft-skip gates, feature flags, resume/checkpoint thread continuity.

## Compatibility

`build_video_graph` / `run_video_workflow` remain public. Nested compile is the preferred path; flat wiring is preserved as an internal fallback during migration.
