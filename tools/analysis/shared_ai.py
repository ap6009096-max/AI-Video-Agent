"""Shared Gemini analysis report — one batch for downstream agents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from core.logging import get_logger

logger = get_logger(__name__)

AnalyzeFn = Callable[[str], str | dict[str, Any] | None]

SHARED_AI_REL = "analysis/shared_ai_analysis.json"


def shared_ai_path(project_dir: str | Path) -> Path:
    return Path(project_dir) / SHARED_AI_REL


def load_shared_ai_analysis(project_dir: str | Path | None) -> dict[str, Any] | None:
    if not project_dir:
        return None
    path = shared_ai_path(project_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("shared_ai load failed: %s", exc)
        return None


def _transcript_excerpt(transcript: dict[str, Any] | None, *, limit: int = 4000) -> str:
    if not isinstance(transcript, dict):
        return ""
    text = str(
        transcript.get("text")
        or transcript.get("full_text")
        or transcript.get("transcript")
        or ""
    ).strip()
    if not text:
        segs = transcript.get("segments") or transcript.get("chunks") or []
        if isinstance(segs, list):
            parts = [
                str(s.get("text") or "")
                for s in segs
                if isinstance(s, dict) and s.get("text")
            ]
            text = " ".join(parts)
    return text[:limit]


def _heuristic_report(
    *,
    excerpt: str,
    job: dict[str, Any] | None,
) -> dict[str, Any]:
    words = [w for w in excerpt.replace("\n", " ").split() if w][:40]
    topic = " ".join(words[:8]) if words else "general content"
    platform = ""
    if isinstance(job, dict):
        cfg = job.get("config") or {}
        if isinstance(cfg, dict):
            platform = str(cfg.get("platform") or "")
    return {
        "version": 1,
        "source": "heuristic",
        "topics": [topic] if topic else ["general"],
        "hooks": [
            f"Watch: {topic}" if topic else "Don't miss this",
            "Key insight in the first 10 seconds",
        ],
        "seo_seeds": {
            "title": topic[:70] if topic else "Untitled",
            "description": excerpt[:160] if excerpt else "",
            "tags": [w.strip(",.?!") for w in words[:8] if len(w) > 3],
            "keywords": [w.strip(",.?!") for w in words[:12] if len(w) > 3],
        },
        "tone": "informative",
        "cta_hints": ["Subscribe for more", "Comment your take", "Share with a friend"],
        "platform_hint": platform or "YouTube",
        "notes": "Shared AI analysis (heuristic fallback — no Gemini).",
    }


def _parse_gemini_json(raw: str | dict[str, Any] | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def build_shared_ai_analysis(
    *,
    project_dir: str | Path,
    transcript: dict[str, Any] | None = None,
    job: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    analyze_fn: AnalyzeFn | None = None,
) -> dict[str, Any]:
    """Build and persist analysis/shared_ai_analysis.json (single Gemini batch)."""
    root = Path(project_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "analysis").mkdir(parents=True, exist_ok=True)

    excerpt = _transcript_excerpt(transcript)
    if not excerpt and isinstance(analysis, dict):
        excerpt = str(analysis.get("summary") or analysis.get("overview") or "")[:4000]

    report = _heuristic_report(excerpt=excerpt, job=job)

    if analyze_fn is not None and excerpt:
        prompt = (
            "Return ONLY JSON with keys: topics (list), hooks (list), "
            "seo_seeds (object with title, description, tags, keywords), "
            "tone (string), cta_hints (list). Base on this transcript excerpt:\n\n"
            f"{excerpt}"
        )
        try:
            parsed = _parse_gemini_json(analyze_fn(prompt))
            if parsed:
                report = {
                    "version": 1,
                    "source": "gemini",
                    "topics": list(parsed.get("topics") or report["topics"]),
                    "hooks": list(parsed.get("hooks") or report["hooks"]),
                    "seo_seeds": dict(parsed.get("seo_seeds") or report["seo_seeds"]),
                    "tone": str(parsed.get("tone") or report["tone"]),
                    "cta_hints": list(parsed.get("cta_hints") or report["cta_hints"]),
                    "platform_hint": report.get("platform_hint") or "YouTube",
                    "notes": "Shared AI analysis (Gemini batch).",
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("shared_ai Gemini failed, using heuristic: %s", exc)
            report["notes"] = f"Shared AI heuristic after Gemini error: {exc}"

    path = shared_ai_path(root)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["path"] = str(path)
    logger.info("Wrote shared AI analysis → %s source=%s", path, report.get("source"))
    return report
