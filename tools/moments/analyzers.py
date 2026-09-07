"""Specialized multi-signal moment analyzers (heuristics, not blind classify)."""

from __future__ import annotations

import re
from typing import Callable

from schemas.moments import DetectedMoment, MomentCategory
from tools.moments.context import MomentContext, audio_with_tag, nearby_scene, text_near

AnalyzerFn = Callable[[MomentContext], list[DetectedMoment]]

_EMOTIONAL = re.compile(
    r"\b(feel|feeling|love|sorry|miss|cry|tears|heart|afraid|scared|lonely|grateful)\b",
    re.I,
)
_EDU = re.compile(
    r"\b(how|why|because|therefore|for example|step\s*\d|first|second|learn|explain)\b",
    re.I,
)
_SURPRISE = re.compile(
    r"\b(wow|whoa|omg|unexpected|suddenly|shock(?:ing|ed)?|surprise(?:d|ing)?|can't believe)\b",
    re.I,
)
_INSPIRE = re.compile(
    r"\b(believe|dream|never give up|you can|inspire|motivat|purpose|hope|future)\b",
    re.I,
)
_EXPERT = re.compile(
    r"\b(the key is|in other words|research|data shows|essentially|technically|"
    r"what this means|the insight|from experience)\b",
    re.I,
)


def _candidate(
    category: MomentCategory,
    start: float,
    end: float,
    score: float,
    reason: str,
    evidence: list[str],
    ctx: MomentContext,
) -> DetectedMoment:
    if end < start:
        start, end = end, start
    if end - start < 0.2:
        end = start + 1.0
    transcript = text_near(ctx, start, end)
    title_src = transcript[:48].strip() or category.replace("_", " ").title()
    return DetectedMoment(
        category=category,
        start=start,
        end=end,
        title=title_src,
        reason=reason,
        score=min(1.0, max(0.0, score)),
        transcript=transcript,
        evidence=evidence,
    )


def analyze_viral(ctx: MomentContext) -> list[DetectedMoment]:
    out: list[DetectedMoment] = []
    for hit in ctx.audio_hits:
        if "viral" not in hit.tags and hit.label not in ("speech_intensity", "volume_rise", "excitement"):
            continue
        mid = (hit.start + hit.end) / 2.0
        scene = nearby_scene(ctx, mid)
        score = hit.score
        evidence = [f"audio:{hit.label}@{hit.start:.1f}"]
        if scene and any(k in scene.kinds for k in ("cut", "event", "transition")):
            score = min(1.0, score + 0.15)
            evidence.append(f"scene:{','.join(scene.kinds) or 'change'}@{scene.start:.1f}")
        if score < 0.3:
            continue
        out.append(
            _candidate(
                "viral",
                hit.start,
                hit.end,
                score,
                "High intensity / volume dynamics with visual support",
                evidence,
                ctx,
            )
        )
    return out


def analyze_funny(ctx: MomentContext) -> list[DetectedMoment]:
    out: list[DetectedMoment] = []
    for hit in audio_with_tag(ctx, "funny") + [
        h for h in ctx.audio_hits if h.label == "laughter"
    ]:
        mid = (hit.start + hit.end) / 2.0
        evidence = [f"audio:{hit.label}@{hit.start:.1f}"]
        score = hit.score
        # Boost with nearby reaction
        for r in ctx.audio_hits:
            if r.label == "reaction" and abs(((r.start + r.end) / 2) - mid) < 2.0:
                score = min(1.0, score + 0.1)
                evidence.append(f"audio:reaction@{r.start:.1f}")
                break
        scene = nearby_scene(ctx, mid)
        if scene:
            evidence.append(f"scene:nearby@{scene.start:.1f}")
            score = min(1.0, score + 0.05)
        out.append(
            _candidate(
                "funny",
                hit.start,
                max(hit.end, hit.start + 1.0),
                score,
                "Laughter / humor cues fused with reaction context",
                evidence,
                ctx,
            )
        )
    return out


def analyze_emotional(ctx: MomentContext) -> list[DetectedMoment]:
    out: list[DetectedMoment] = []
    for hit in audio_with_tag(ctx, "emotional"):
        evidence = [f"audio:{hit.label}@{hit.start:.1f}"]
        out.append(
            _candidate(
                "emotional",
                hit.start,
                hit.end,
                hit.score,
                "Emotional audio/pause signal",
                evidence,
                ctx,
            )
        )
    for u in ctx.units:
        if not _EMOTIONAL.search(u.text):
            continue
        # Require supporting pause/silence nearby — not blind text match alone
        support = None
        for h in ctx.audio_hits:
            if h.label in ("pause", "silence") and abs(h.start - u.start) < 3.0:
                support = h
                break
        if support is None and not audio_with_tag(ctx, "emotional"):
            # still allow if long silence exists in context
            silences = [h for h in ctx.audio_hits if h.label == "silence" and h.score >= 0.4]
            if not silences:
                continue
            support = silences[0]
        evidence = [f"transcript:emotion_lexicon@{u.start:.1f}"]
        score = 0.55
        if support:
            evidence.append(f"audio:{support.label}@{support.start:.1f}")
            score = min(1.0, score + 0.15)
        out.append(
            _candidate(
                "emotional",
                u.start,
                u.end,
                score,
                "Emotional language supported by pause/silence context",
                evidence,
                ctx,
            )
        )
    return out


def analyze_educational(ctx: MomentContext) -> list[DetectedMoment]:
    out: list[DetectedMoment] = []
    for hit in ctx.audio_hits:
        if hit.label != "question" and "clip_boundary" not in hit.tags:
            continue
        if hit.label != "question" and not any(
            _EDU.search(u.text) for u in ctx.units if abs(u.start - hit.start) < 2
        ):
            continue
        text = text_near(ctx, hit.start, hit.end)
        if hit.label != "question" and not _EDU.search(text):
            continue
        evidence = [f"audio:{hit.label}@{hit.start:.1f}"]
        if _EDU.search(text):
            evidence.append("transcript:edu_pattern")
        out.append(
            _candidate(
                "educational",
                hit.start,
                hit.end,
                max(hit.score, 0.5),
                "Question / explanatory teaching pattern",
                evidence,
                ctx,
            )
        )
    for u in ctx.units:
        if not _EDU.search(u.text):
            continue
        q_near = any(
            h.label == "question" and abs(h.start - u.start) < 4.0 for h in ctx.audio_hits
        )
        if not q_near and "?" not in u.text:
            continue
        out.append(
            _candidate(
                "educational",
                u.start,
                u.end,
                0.55,
                "How/why/because teaching language with question context",
                [f"transcript:edu@{u.start:.1f}", "audio:question_context"],
                ctx,
            )
        )
    return out


def analyze_surprise(ctx: MomentContext) -> list[DetectedMoment]:
    out: list[DetectedMoment] = []
    for u in ctx.units:
        if not _SURPRISE.search(u.text):
            continue
        mid = (u.start + u.end) / 2.0
        vol = next(
            (
                h
                for h in ctx.audio_hits
                if h.label in ("volume_rise", "excitement") and abs(h.start - mid) < 2.0
            ),
            None,
        )
        scene = nearby_scene(ctx, mid)
        hard = scene and any(k in scene.kinds for k in ("cut", "event"))
        if not vol and not hard:
            continue
        evidence = [f"transcript:surprise@{u.start:.1f}"]
        score = 0.5
        if vol:
            evidence.append(f"audio:{vol.label}@{vol.start:.1f}")
            score += 0.2
        if hard and scene:
            evidence.append(f"scene:cut@{scene.start:.1f}")
            score += 0.15
        out.append(
            _candidate(
                "surprise",
                u.start,
                u.end,
                score,
                "Surprise language with volume spike and/or hard cut",
                evidence,
                ctx,
            )
        )
    return out


def analyze_important(ctx: MomentContext) -> list[DetectedMoment]:
    out: list[DetectedMoment] = []
    for item in ctx.important + ctx.hooks:
        # hooks/important may use sentence indices or times
        start = item.get("start_seconds")
        end = item.get("end_seconds")
        text = str(item.get("text") or item.get("reason") or "")
        if start is None:
            idx = item.get("sentence_index")
            if isinstance(idx, int) and 0 <= idx < len(ctx.units):
                start = ctx.units[idx].start
                end = ctx.units[idx].end
                text = text or ctx.units[idx].text
        try:
            s = float(start if start is not None else 0.0)
            e = float(end if end is not None else s + 2.0)
        except (TypeError, ValueError):
            continue
        score = float(item.get("score") or 0.7)
        evidence = ["transcript:important_or_hook"]
        # Boost with clip_boundary / speaker change
        for ch in ctx.speaker_changes:
            if abs(ch[0] - s) < 2.0:
                evidence.append(f"speaker:change@{ch[0]:.1f}")
                score = min(1.0, score + 0.1)
                break
        for h in ctx.audio_hits:
            if "clip_boundary" in h.tags and abs(h.start - s) < 2.0:
                evidence.append(f"audio:clip_boundary@{h.start:.1f}")
                score = min(1.0, score + 0.05)
                break
        out.append(
            _candidate(
                "important",
                s,
                e,
                score,
                str(item.get("reason") or "Highlighted important statement / hook"),
                evidence,
                ctx,
            )
        )
        if text and not out[-1].transcript:
            out[-1].transcript = text
            out[-1].title = text[:48]
    # Fallback: speaker changes + clip boundaries without hooks
    if not out:
        for ch in ctx.speaker_changes:
            hits = [
                h
                for h in ctx.audio_hits
                if "clip_boundary" in h.tags and abs(h.start - ch[0]) < 1.5
            ]
            if not hits:
                continue
            out.append(
                _candidate(
                    "important",
                    ch[0],
                    max(ch[1], ch[0] + 1.5),
                    max(ch[2], 0.45),
                    "Speaker change aligned with clip-boundary audio",
                    [f"speaker:change@{ch[0]:.1f}", f"audio:clip_boundary@{hits[0].start:.1f}"],
                    ctx,
                )
            )
    return out


def analyze_reaction(ctx: MomentContext) -> list[DetectedMoment]:
    out: list[DetectedMoment] = []
    for hit in [h for h in ctx.audio_hits if h.label == "reaction" or "reaction" in h.tags]:
        evidence = [f"audio:{hit.label}@{hit.start:.1f}"]
        score = hit.score
        for ch in ctx.speaker_changes:
            if abs(ch[0] - hit.start) < 2.0:
                evidence.append(f"speaker:change@{ch[0]:.1f}")
                score = min(1.0, score + 0.1)
                break
        out.append(
            _candidate(
                "reaction",
                hit.start,
                hit.end,
                score,
                "Short post-pause reaction burst",
                evidence,
                ctx,
            )
        )
    return out


def analyze_inspirational(ctx: MomentContext) -> list[DetectedMoment]:
    out: list[DetectedMoment] = []
    for u in ctx.units:
        if not _INSPIRE.search(u.text):
            continue
        mid = (u.start + u.end) / 2.0
        intensity = next(
            (
                h
                for h in ctx.audio_hits
                if h.label in ("speech_intensity", "excitement") and abs(h.start - mid) < 2.5
            ),
            None,
        )
        if intensity is None:
            continue
        out.append(
            _candidate(
                "inspirational",
                u.start,
                u.end,
                min(1.0, 0.5 + intensity.score * 0.3),
                "Inspirational language with elevated speech intensity",
                [
                    f"transcript:inspire@{u.start:.1f}",
                    f"audio:{intensity.label}@{intensity.start:.1f}",
                ],
                ctx,
            )
        )
    return out


def analyze_cinematic(ctx: MomentContext) -> list[DetectedMoment]:
    out: list[DetectedMoment] = []
    for sc in ctx.scenes:
        if not any(k in sc.kinds for k in ("composition", "camera", "event", "cut")):
            continue
        if sc.score < 0.25 and "cut" not in sc.kinds:
            continue
        # Prefer silence/pause just before scene start
        pre = next(
            (
                h
                for h in ctx.audio_hits
                if h.label in ("silence", "pause") and abs(h.end - sc.start) < 1.25
            ),
            None,
        )
        score = max(sc.score, 0.4)
        evidence = [f"scene:{'/'.join(sc.kinds) or 'visual'}@{sc.start:.1f}"]
        if pre:
            evidence.append(f"audio:{pre.label}@{pre.start:.1f}")
            score = min(1.0, score + 0.15)
        elif "camera" not in sc.kinds and "composition" not in sc.kinds:
            continue  # require audio support unless strong cinematic kinds
        out.append(
            _candidate(
                "cinematic",
                sc.start,
                max(sc.end, sc.start + 1.5),
                score,
                "Visual composition/camera change with pacing support",
                evidence,
                ctx,
            )
        )
    return out


def analyze_expert_insights(ctx: MomentContext) -> list[DetectedMoment]:
    out: list[DetectedMoment] = []
    for u in ctx.units:
        if not _EXPERT.search(u.text):
            continue
        # Prefer longer explanatory turns, not one-word
        if len(u.text.split()) < 6:
            continue
        edu_near = any(
            h.label == "question" and abs(h.start - u.start) < 5.0 for h in ctx.audio_hits
        )
        evidence = [f"transcript:expert_pattern@{u.start:.1f}"]
        score = 0.55
        if edu_near:
            evidence.append("audio:question_nearby")
            score += 0.1
        scene = nearby_scene(ctx, (u.start + u.end) / 2.0)
        if scene:
            evidence.append(f"scene:nearby@{scene.start:.1f}")
            score += 0.05
        out.append(
            _candidate(
                "expert_insights",
                u.start,
                u.end,
                score,
                "Explanatory expert-insight phrasing with context",
                evidence,
                ctx,
            )
        )
    return out


def analyze_best_quotes(ctx: MomentContext) -> list[DetectedMoment]:
    out: list[DetectedMoment] = []
    for item in ctx.hooks:
        idx = item.get("sentence_index")
        if isinstance(idx, int) and 0 <= idx < len(ctx.units):
            u = ctx.units[idx]
            score = float(item.get("score") or 0.65)
            evidence = ["transcript:hook"]
            pause = next(
                (
                    h
                    for h in ctx.audio_hits
                    if h.label == "pause" and abs(h.start - u.end) < 1.5
                ),
                None,
            )
            if pause:
                evidence.append(f"audio:pause@{pause.start:.1f}")
                score = min(1.0, score + 0.1)
            out.append(
                _candidate(
                    "best_quotes",
                    u.start,
                    u.end,
                    score,
                    str(item.get("reason") or "Hook / quotable line"),
                    evidence,
                    ctx,
                )
            )
    for u in ctx.units:
        words = u.text.split()
        if not (4 <= len(words) <= 18):
            continue
        punchy = u.text.endswith((".", "!")) and (
            any(c.isupper() for c in u.text) or "!" in u.text or len(words) <= 10
        )
        if not punchy:
            continue
        pause = next(
            (
                h
                for h in ctx.audio_hits
                if h.label in ("pause", "silence") and abs(h.start - u.end) < 1.25
            ),
            None,
        )
        if pause is None and not ctx.hooks:
            continue
        evidence = [f"transcript:punchy@{u.start:.1f}"]
        score = 0.5
        if pause:
            evidence.append(f"audio:{pause.label}@{pause.start:.1f}")
            score += 0.15
        out.append(
            _candidate(
                "best_quotes",
                u.start,
                u.end,
                score,
                "Short punchy line framed by pause",
                evidence,
                ctx,
            )
        )
    return out


ANALYZERS: dict[MomentCategory, AnalyzerFn] = {
    "viral": analyze_viral,
    "funny": analyze_funny,
    "emotional": analyze_emotional,
    "educational": analyze_educational,
    "surprise": analyze_surprise,
    "important": analyze_important,
    "reaction": analyze_reaction,
    "inspirational": analyze_inspirational,
    "cinematic": analyze_cinematic,
    "expert_insights": analyze_expert_insights,
    "best_quotes": analyze_best_quotes,
}
