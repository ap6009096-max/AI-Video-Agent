"""Build sourced research reports from project corpus (no live web fetch)."""

from __future__ import annotations

import re
from typing import Any, Callable

from config.settings import get_settings
from core.logging import get_logger
from schemas.job import SourceType
from schemas.research import (
    GeminiResearchEnrichment,
    ResearchClaim,
    ResearchOutlineSection,
    ResearchReport,
    ResearchSource,
    TopicAnalysis,
)

logger = get_logger(__name__)

EnrichFn = Callable[..., GeminiResearchEnrichment | None]

_CLAIM_SPLIT = re.compile(r"(?<=[.!?])\s+")


def is_research_source_type(source_type: str | SourceType | None) -> bool:
    if source_type is None:
        return False
    raw = (
        source_type.value
        if isinstance(source_type, SourceType)
        else str(source_type)
    )
    key = raw.strip().lower()
    return key in {SourceType.SCRIPT.value, SourceType.IDEA.value}


def should_enable_research(
    *,
    research_flag: bool,
    source_type: str | SourceType | None,
) -> bool:
    return bool(research_flag) or is_research_source_type(source_type)


def build_research_report(
    *,
    project_id: str,
    raw_text: str | None = None,
    transcript: dict[str, Any] | None = None,
    speech_transcript: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    source_metadata: dict[str, Any] | None = None,
    youtube_url: str | None = None,
    max_claims: int | None = None,
    max_sources: int | None = None,
    min_confidence: float | None = None,
    enrich_fn: EnrichFn | None = None,
    skipped: bool = False,
    notes: str = "",
) -> ResearchReport:
    """Assemble topic/sources/claims/outline/summary from project corpus only."""
    settings = get_settings()
    max_c = int(max_claims if max_claims is not None else settings.research_max_claims)
    max_s = int(
        max_sources if max_sources is not None else settings.research_max_sources
    )
    min_conf = float(
        min_confidence
        if min_confidence is not None
        else settings.research_min_confidence
    )

    if skipped:
        return ResearchReport(
            project_id=project_id,
            provider="disabled",
            skipped=True,
            notes=notes or "Research skipped.",
            summary_stats={"sources": 0.0, "claims": 0.0, "outline_sections": 0.0},
        )

    sources = _collect_sources(
        raw_text=raw_text,
        transcript=transcript,
        speech_transcript=speech_transcript,
        analysis=analysis,
        source_metadata=source_metadata,
        youtube_url=youtube_url,
        max_sources=max_s,
    )
    topic = _resolve_topic(
        raw_text=raw_text,
        transcript=transcript,
        source_metadata=source_metadata,
        sources=sources,
    )
    claims = _extract_claims(
        transcript=transcript,
        speech_transcript=speech_transcript,
        raw_text=raw_text,
        sources=sources,
        max_claims=max_c,
        min_confidence=min_conf,
    )
    claims = [c for c in claims if c.source_ids]
    topic_analysis = _heuristic_topic_analysis(topic, transcript, claims)
    outline = _heuristic_outline(transcript, claims, topic)
    summary = _heuristic_summary(topic, outline, claims)

    provider = "research-builder"
    enrich = enrich_fn
    if enrich is None:
        try:
            from tools.llm.gemini import enrich_research_report

            enrich = enrich_research_report
        except Exception:  # noqa: BLE001
            enrich = None

    if enrich is not None and (claims or sources):
        try:
            gem = enrich(
                topic=topic,
                sources=sources,
                claims=claims,
                outline=outline,
                summary=summary,
            )
            if gem is not None:
                topic_analysis, outline, summary = _apply_enrichment(
                    gem,
                    topic_analysis=topic_analysis,
                    outline=outline,
                    summary=summary,
                    claim_ids={c.id for c in claims},
                )
                provider = "research-builder+gemini"
        except Exception as exc:  # noqa: BLE001
            logger.info("Research Gemini enrich skipped: %s", exc)

    mean_conf = (
        sum(c.confidence for c in claims) / len(claims) if claims else 0.0
    )
    return ResearchReport(
        project_id=project_id,
        topic=topic,
        topic_analysis=topic_analysis,
        sources=sources,
        claims=claims,
        outline=outline,
        summary=summary,
        provider=provider,
        notes=notes
        or (
            "Corpus-only research; every claim references sources[]; "
            "no live web fetch."
        ),
        skipped=False,
        summary_stats={
            "sources": float(len(sources)),
            "claims": float(len(claims)),
            "outline_sections": float(len(outline)),
            "mean_confidence": round(mean_conf, 4),
        },
    )


def format_research_grounding_block(report: dict[str, Any] | ResearchReport | None) -> str:
    """Short grounding block for Story/Script Gemini prompts."""
    if report is None:
        return ""
    data = (
        report.model_dump(mode="json")
        if isinstance(report, ResearchReport)
        else dict(report)
    )
    if data.get("skipped"):
        return ""
    topic = str(data.get("topic") or "").strip()
    summary = str(data.get("summary") or "").strip()
    sources = {
        str(s.get("id")): str(s.get("title") or s.get("id") or "")
        for s in (data.get("sources") or [])
        if isinstance(s, dict)
    }
    claim_lines: list[str] = []
    for claim in (data.get("claims") or [])[:8]:
        if not isinstance(claim, dict):
            continue
        text = str(claim.get("text") or "").strip()
        if not text:
            continue
        titles = [
            sources.get(sid, sid)
            for sid in (claim.get("source_ids") or [])
            if sid
        ]
        src = f" [sources: {', '.join(titles)}]" if titles else ""
        claim_lines.append(f"- {text}{src}")
    if not (topic or summary or claim_lines):
        return ""
    parts = ["Research grounding (use only as soft context; do not invent facts):"]
    if topic:
        parts.append(f"Topic: {topic}")
    if summary:
        parts.append(f"Summary: {summary}")
    if claim_lines:
        parts.append("Top claims:")
        parts.extend(claim_lines)
    return "\n".join(parts)


def _truncate(text: str, n: int = 240) -> str:
    t = " ".join((text or "").split())
    if len(t) <= n:
        return t
    return t[: n - 1].rstrip() + "…"


def _resolve_topic(
    *,
    raw_text: str | None,
    transcript: dict[str, Any] | None,
    source_metadata: dict[str, Any] | None,
    sources: list[ResearchSource],
) -> str:
    topics = (transcript or {}).get("topics") or []
    if topics:
        first = topics[0]
        if isinstance(first, dict):
            t = str(first.get("text") or first.get("topic") or "").strip()
        else:
            t = str(first).strip()
        if t:
            return _truncate(t, 120)
    meta_title = str((source_metadata or {}).get("title") or "").strip()
    if meta_title:
        return _truncate(meta_title, 120)
    cleaned = str((transcript or {}).get("cleaned_text") or "").strip()
    if cleaned:
        return _truncate(cleaned.split("\n")[0], 120)
    raw = (raw_text or "").strip()
    if raw:
        return _truncate(raw.split("\n")[0], 120)
    if sources:
        return _truncate(sources[0].title or sources[0].excerpt, 120)
    return "Untitled topic"


def _collect_sources(
    *,
    raw_text: str | None,
    transcript: dict[str, Any] | None,
    speech_transcript: dict[str, Any] | None,
    analysis: dict[str, Any] | None,
    source_metadata: dict[str, Any] | None,
    youtube_url: str | None,
    max_sources: int,
) -> list[ResearchSource]:
    out: list[ResearchSource] = []
    seen: set[str] = set()

    def _add(src: ResearchSource) -> None:
        if src.id in seen or len(out) >= max_sources:
            return
        if not (src.excerpt or src.title):
            return
        seen.add(src.id)
        out.append(src)

    raw = (raw_text or "").strip()
    cleaned = str((transcript or {}).get("cleaned_text") or "").strip()
    if raw:
        _add(
            ResearchSource(
                id="src:user_script",
                kind="user_script",
                title="User script",
                locator="raw_text",
                excerpt=_truncate(raw, 500),
            )
        )
    if cleaned and cleaned != raw:
        _add(
            ResearchSource(
                id="src:transcript_clean",
                kind="transcript",
                title="Cleaned transcript",
                locator="transcript.cleaned_text",
                excerpt=_truncate(cleaned, 500),
            )
        )
    elif cleaned and not raw:
        _add(
            ResearchSource(
                id="src:transcript_clean",
                kind="transcript",
                title="Cleaned transcript",
                locator="transcript.cleaned_text",
                excerpt=_truncate(cleaned, 500),
            )
        )

    for i, section in enumerate((transcript or {}).get("sections") or []):
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or f"Section {i + 1}").strip()
        summary = str(
            section.get("summary") or section.get("text") or ""
        ).strip()
        sid = str(section.get("id") or f"section:{i}")
        _add(
            ResearchSource(
                id=f"src:section:{sid}",
                kind="section",
                title=title,
                locator=f"section:{sid}",
                excerpt=_truncate(summary or title, 400),
            )
        )

    for i, sent in enumerate((transcript or {}).get("sentences") or []):
        if not isinstance(sent, dict) or len(out) >= max_sources:
            break
        text = str(sent.get("text") or "").strip()
        if len(text) < 40:
            continue
        sid = str(sent.get("id") or i)
        start = sent.get("start_seconds")
        end = sent.get("end_seconds")
        locator = f"sentence:{sid}"
        if start is not None and end is not None:
            locator = f"{start:.2f}-{end:.2f}s"
        _add(
            ResearchSource(
                id=f"src:sent:{sid}",
                kind="transcript",
                title=_truncate(text, 48),
                locator=locator,
                excerpt=_truncate(text, 300),
            )
        )

    for i, seg in enumerate((speech_transcript or {}).get("segments") or []):
        if not isinstance(seg, dict) or len(out) >= max_sources:
            break
        text = str(seg.get("text") or "").strip()
        if len(text) < 40:
            continue
        try:
            start = float(seg.get("start", 0.0))
            end = float(seg.get("end", start))
        except (TypeError, ValueError):
            start, end = 0.0, 0.0
        _add(
            ResearchSource(
                id=f"src:seg:{i}",
                kind="transcript",
                title=_truncate(text, 48),
                locator=f"{start:.2f}-{end:.2f}s",
                excerpt=_truncate(text, 300),
            )
        )

    meta = source_metadata or {}
    yt = (youtube_url or str(meta.get("url") or meta.get("youtube_url") or "")).strip()
    title = str(meta.get("title") or "").strip()
    desc = str(meta.get("description") or "").strip()
    channel = str(meta.get("channel") or meta.get("channel_title") or "").strip()
    if title or desc or channel:
        _add(
            ResearchSource(
                id="src:metadata",
                kind="metadata",
                title=title or "Source metadata",
                locator="source_metadata",
                excerpt=_truncate(
                    " | ".join(p for p in (title, channel, desc) if p),
                    500,
                ),
                url=yt if yt.startswith("http") else "",
                notes="YouTube/upload metadata" if yt or channel else "",
            )
        )

    if analysis and isinstance(analysis, dict):
        props = analysis.get("properties") or {}
        notes = str(analysis.get("summary") or analysis.get("notes") or "").strip()
        if notes or props:
            _add(
                ResearchSource(
                    id="src:analysis",
                    kind="analysis",
                    title="Video analysis summary",
                    locator="analysis",
                    excerpt=_truncate(
                        notes
                        or f"duration={props.get('duration_seconds', '?')}s",
                        400,
                    ),
                )
            )

    return out[:max_sources]


def _extract_claims(
    *,
    transcript: dict[str, Any] | None,
    speech_transcript: dict[str, Any] | None,
    raw_text: str | None,
    sources: list[ResearchSource],
    max_claims: int,
    min_confidence: float,
) -> list[ResearchClaim]:
    claims: list[ResearchClaim] = []
    source_by_id = {s.id: s for s in sources}

    def _attach(text: str, preferred_ids: list[str], *, claim_type: str, conf: float) -> None:
        if len(claims) >= max_claims:
            return
        cleaned = " ".join(text.split()).strip()
        if len(cleaned) < 20:
            return
        if conf < min_confidence:
            return
        ids = [i for i in preferred_ids if i in source_by_id]
        if not ids:
            # Fallback: match excerpt overlap against any source
            ids = _match_source_ids(cleaned, sources)
        if not ids:
            return
        cid = f"claim:{len(claims)}"
        excerpts = [
            _truncate(source_by_id[i].excerpt, 160)
            for i in ids
            if i in source_by_id
        ]
        claims.append(
            ResearchClaim(
                id=cid,
                text=_truncate(cleaned, 280),
                claim_type=claim_type,
                confidence=min(1.0, conf),
                source_ids=ids[:3],
                evidence_excerpts=excerpts[:3],
            )
        )

    for item in (transcript or {}).get("important_statements") or []:
        if isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            sid = str(item.get("sentence_id") or "")
            preferred = [f"src:sent:{sid}"] if sid else []
            conf = float(item.get("score") or 0.7)
        else:
            text = str(item).strip()
            preferred = []
            conf = 0.65
        _attach(text, preferred or ["src:transcript_clean", "src:user_script"], claim_type="fact", conf=conf)

    for hook in (transcript or {}).get("hooks") or []:
        if isinstance(hook, dict):
            text = str(hook.get("text") or "").strip()
            conf = float(hook.get("score") or 0.6)
        else:
            text = str(hook).strip()
            conf = 0.55
        _attach(
            text,
            ["src:transcript_clean", "src:user_script"],
            claim_type="opinion",
            conf=conf,
        )

    for section in (transcript or {}).get("sections") or []:
        if not isinstance(section, dict):
            continue
        summary = str(section.get("summary") or "").strip()
        sid = str(section.get("id") or "")
        preferred = [f"src:section:{sid}"] if sid else ["src:transcript_clean"]
        _attach(summary, preferred, claim_type="definition", conf=0.6)

    # Sentence-level high-signal lines
    for sent in (transcript or {}).get("sentences") or []:
        if not isinstance(sent, dict) or len(claims) >= max_claims:
            break
        text = str(sent.get("text") or "").strip()
        if len(text) < 50:
            continue
        if not _looks_claim_like(text):
            continue
        sid = str(sent.get("id") or "")
        preferred = [f"src:sent:{sid}"] if sid else []
        _attach(text, preferred, claim_type="fact", conf=0.55)

    if not claims and (raw_text or "").strip():
        for part in _CLAIM_SPLIT.split(raw_text.strip()):
            if len(claims) >= max_claims:
                break
            _attach(
                part,
                ["src:user_script"],
                claim_type="fact",
                conf=0.5,
            )

    if not claims and speech_transcript:
        for i, seg in enumerate(speech_transcript.get("segments") or []):
            if not isinstance(seg, dict) or len(claims) >= max_claims:
                break
            text = str(seg.get("text") or "").strip()
            if len(text) < 50 or not _looks_claim_like(text):
                continue
            _attach(text, [f"src:seg:{i}"], claim_type="fact", conf=0.5)

    return claims[:max_claims]


def _looks_claim_like(text: str) -> bool:
    lower = text.lower()
    markers = (
        " is ",
        " are ",
        " was ",
        " were ",
        " means ",
        " because ",
        " percent",
        "%",
        " study",
        " research",
        " always ",
        " never ",
        " should ",
        " must ",
    )
    return any(m in lower for m in markers) or text[:1].isupper()


def _match_source_ids(text: str, sources: list[ResearchSource]) -> list[str]:
    needle = text.lower()[:80]
    hits: list[str] = []
    for src in sources:
        blob = f"{src.excerpt} {src.title}".lower()
        if needle and needle[:40] in blob:
            hits.append(src.id)
            continue
        # token overlap
        tokens = [t for t in re.findall(r"[a-z0-9]{4,}", needle)[:6]]
        if tokens and sum(1 for t in tokens if t in blob) >= max(2, len(tokens) // 2):
            hits.append(src.id)
    if not hits and sources:
        # Prefer primary corpus sources
        for preferred in ("src:user_script", "src:transcript_clean", "src:metadata"):
            if any(s.id == preferred for s in sources):
                return [preferred]
        return [sources[0].id]
    return hits[:3]


def _heuristic_topic_analysis(
    topic: str,
    transcript: dict[str, Any] | None,
    claims: list[ResearchClaim],
) -> TopicAnalysis:
    subtopics: list[str] = []
    for t in (transcript or {}).get("topics") or []:
        if isinstance(t, dict):
            label = str(t.get("text") or t.get("topic") or "").strip()
        else:
            label = str(t).strip()
        if label and label.lower() != topic.lower():
            subtopics.append(_truncate(label, 80))
    keywords = []
    for c in claims[:10]:
        for tok in re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", c.text):
            if tok.lower() not in {k.lower() for k in keywords}:
                keywords.append(tok)
            if len(keywords) >= 12:
                break
        if len(keywords) >= 12:
            break
    return TopicAnalysis(
        primary_topic=topic,
        subtopics=subtopics[:8],
        audience="General",
        angle="Explain key ideas from the source corpus",
        keywords=keywords,
    )


def _heuristic_outline(
    transcript: dict[str, Any] | None,
    claims: list[ResearchClaim],
    topic: str,
) -> list[ResearchOutlineSection]:
    sections: list[ResearchOutlineSection] = []
    src_sections = (transcript or {}).get("sections") or []
    if src_sections:
        for i, sec in enumerate(src_sections):
            if not isinstance(sec, dict):
                continue
            title = str(sec.get("title") or f"Section {i + 1}").strip()
            summary = str(sec.get("summary") or "").strip()
            sid = str(sec.get("id") or i)
            related = [
                c.id
                for c in claims
                if any(f"section:{sid}" in s for s in c.source_ids)
                or (summary and summary[:40].lower() in c.text.lower())
            ]
            if not related:
                related = [c.id for c in claims[i : i + 2]]
            sections.append(
                ResearchOutlineSection(
                    id=f"outline:{i}",
                    title=title,
                    summary=_truncate(summary or title, 200),
                    bullet_points=[c.text for c in claims if c.id in related][:4]
                    or ([_truncate(summary, 120)] if summary else []),
                    claim_ids=related[:6],
                )
            )
    if not sections:
        chunk = max(1, (len(claims) + 2) // 3) if claims else 1
        buckets = [claims[i : i + chunk] for i in range(0, len(claims), chunk)] or [[]]
        labels = ["Setup", "Core ideas", "Takeaways"]
        for i, bucket in enumerate(buckets[:3]):
            sections.append(
                ResearchOutlineSection(
                    id=f"outline:{i}",
                    title=labels[i] if i < len(labels) else f"Part {i + 1}",
                    summary=_truncate(
                        "; ".join(c.text for c in bucket[:2]) or topic,
                        200,
                    ),
                    bullet_points=[c.text for c in bucket[:4]],
                    claim_ids=[c.id for c in bucket],
                )
            )
    return sections


def _heuristic_summary(
    topic: str,
    outline: list[ResearchOutlineSection],
    claims: list[ResearchClaim],
) -> str:
    parts: list[str] = []
    if topic:
        parts.append(f"This piece focuses on {topic}.")
    if outline:
        titles = ", ".join(s.title for s in outline if s.title)
        if titles:
            parts.append(f"Outline covers: {titles}.")
    if claims:
        parts.append(
            "Key grounded claims: "
            + "; ".join(c.text for c in claims[:3])
            + ("…" if len(claims) > 3 else ".")
        )
    return " ".join(parts).strip() or "No corpus material available for a summary."


def _apply_enrichment(
    gem: GeminiResearchEnrichment,
    *,
    topic_analysis: TopicAnalysis,
    outline: list[ResearchOutlineSection],
    summary: str,
    claim_ids: set[str],
) -> tuple[TopicAnalysis, list[ResearchOutlineSection], str]:
    ta = topic_analysis.model_copy(deep=True)
    if gem.primary_topic.strip():
        ta.primary_topic = gem.primary_topic.strip()
    if gem.subtopics:
        ta.subtopics = [s.strip() for s in gem.subtopics if s.strip()][:8]
    if gem.audience.strip():
        ta.audience = gem.audience.strip()
    if gem.angle.strip():
        ta.angle = gem.angle.strip()
    if gem.keywords:
        ta.keywords = [k.strip() for k in gem.keywords if k.strip()][:12]

    new_outline: list[ResearchOutlineSection] = []
    if gem.outline:
        for i, sec in enumerate(gem.outline):
            valid_ids = [cid for cid in sec.claim_ids if cid in claim_ids]
            # If Gemini invented claim ids, fall back to original section ids
            if not valid_ids and i < len(outline):
                valid_ids = list(outline[i].claim_ids)
            new_outline.append(
                ResearchOutlineSection(
                    id=sec.id.strip() or (outline[i].id if i < len(outline) else f"outline:{i}"),
                    title=sec.title.strip()
                    or (outline[i].title if i < len(outline) else f"Section {i + 1}"),
                    summary=sec.summary.strip()
                    or (outline[i].summary if i < len(outline) else ""),
                    bullet_points=[b.strip() for b in sec.bullet_points if b.strip()][:6]
                    or (outline[i].bullet_points if i < len(outline) else []),
                    claim_ids=valid_ids,
                )
            )
    else:
        new_outline = outline

    new_summary = gem.summary.strip() or summary
    return ta, new_outline, new_summary
