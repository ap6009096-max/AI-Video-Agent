"""Gemini chat model helpers via LangChain."""

from __future__ import annotations

import re
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from config.settings import get_settings
from core.errors import (
    AnalyticsAgentError,
    ConfigurationError,
    CulturalAdaptationError,
    HumorLocalizationError,
    ImageAgentError,
    LanguageAgentError,
    ScriptAgentError,
    StoryAgentError,
    StoryboardAgentError,
    TextAgentError,
    DirectorAgentError,
    CharacterAgentError,
    CameraAgentError,
    MotionGraphicsAgentError,
    DocumentaryAgentError,
    ResearchAgentError,
    SupervisorAgentError,
    VideoGenerationAgentError,
    TrendAgentError,
    CalendarAgentError,
    BrandAgentError,
    RepurposeAgentError,
    GeminiAuthenticationError,
    GeminiGenerationError,
    GeminiModelUnavailableError,
    GeminiQuotaExhaustedError,
    GeminiTemporaryRateLimitError,
)
from core.logging import get_logger
from prompts.cultural_adaptation_agent import (
    CULTURAL_ADAPTATION_SYSTEM,
    build_cultural_adaptation_user_prompt,
)
from prompts.humor_localization_agent import (
    HUMOR_LOCALIZATION_SYSTEM,
    build_humor_localization_user_prompt,
)
from prompts.language_agent import LANGUAGE_AGENT_SYSTEM, build_language_agent_user_prompt
from prompts.script_agent import SCRIPT_AGENT_SYSTEM, build_script_agent_user_prompt
from prompts.story_agent import STORY_AGENT_SYSTEM, build_story_agent_user_prompt
from prompts.text_agent import TEXT_AGENT_SYSTEM, build_text_agent_user_prompt
from prompts.trend_agent import TREND_AGENT_SYSTEM, build_trend_agent_user_prompt
from prompts.repurpose_agent import (
    REPURPOSE_AGENT_SYSTEM,
    build_repurpose_agent_user_prompt,
)
from prompts.calendar_agent import (
    CALENDAR_AGENT_SYSTEM,
    build_calendar_agent_user_prompt,
)
from prompts.brand_agent import (
    BRAND_AGENT_SYSTEM,
    build_brand_agent_user_prompt,
)
from prompts.analytics_agent import (
    ANALYTICS_AGENT_SYSTEM,
    build_analytics_agent_user_prompt,
)
from prompts.image_agent import (
    IMAGE_AGENT_SYSTEM,
    build_image_agent_user_prompt,
)
from prompts.storyboard_agent import (
    STORYBOARD_AGENT_SYSTEM,
    build_storyboard_agent_user_prompt,
)
from prompts.video_generation_agent import (
    VIDEO_GENERATION_AGENT_SYSTEM,
    build_video_generation_agent_user_prompt,
)
from prompts.director_agent import (
    DIRECTOR_AGENT_SYSTEM,
    build_director_agent_user_prompt,
)
from prompts.character_agent import (
    CHARACTER_AGENT_SYSTEM,
    build_character_agent_user_prompt,
)
from prompts.camera_agent import (
    CAMERA_AGENT_SYSTEM,
    build_camera_agent_user_prompt,
)
from prompts.motion_graphics_agent import (
    MOTION_GRAPHICS_AGENT_SYSTEM,
    build_motion_graphics_agent_user_prompt,
)
from prompts.documentary_agent import (
    DOCUMENTARY_AGENT_SYSTEM,
    build_documentary_agent_user_prompt,
)
from prompts.research_agent import (
    RESEARCH_AGENT_SYSTEM,
    build_research_enrich_user_prompt,
)
from prompts.supervisor_agent import (
    SUPERVISOR_AGENT_SYSTEM,
    build_supervisor_user_prompt,
)
from schemas.localization import (
    GeminiCulturalBatch,
    GeminiHumorBatch,
    GeminiLocalizedBatch,
)
from schemas.story import (
    GeminiClipScript,
    GeminiClipStory,
    GeminiScriptsBatch,
    GeminiStoriesBatch,
)
from schemas.transcript import (
    GeminiScriptAnalysis,
    ScriptSection,
    ScriptSentence,
)
from schemas.trend import GeminiTrendAnalysis
from schemas.repurpose import GeminiRepurposeBatch
from schemas.calendar import GeminiCalendarBatch
from schemas.brand import GeminiBrandBatch
from schemas.analytics import GeminiAnalyticsAnalysis
from schemas.image import GeminiImageBatch
from schemas.storyboard import GeminiStoryboardBatch
from schemas.video_generation import GeminiVideoGenerationBatch
from schemas.director import GeminiDirectorBatch
from schemas.character import GeminiCharacterBatch
from schemas.camera import GeminiCameraBatch
from schemas.motion_graphics import GeminiMotionGraphicsBatch
from schemas.documentary import GeminiDocumentaryBatch
from schemas.research import (
    GeminiResearchEnrichment,
    ResearchClaim,
    ResearchOutlineSection,
    ResearchSource,
)
from schemas.supervisor import GeminiSupervisorDecision

logger = get_logger(__name__)


def get_chat_model(
    *, temperature: float = 0.2, model_name: str | None = None
) -> ChatGoogleGenerativeAI:
    """Return a configured Gemini chat model (requires GEMINI_API_KEY)."""
    settings = get_settings()
    api_key = settings.require_gemini_api_key()
    return ChatGoogleGenerativeAI(
        model=model_name or settings.gemini_model,
        google_api_key=api_key,
        temperature=temperature,
        # Application code owns bounded retries so daily quota errors are not
        # multiplied by LangChain's default retry loop.
        retries=0,
    )


def classify_gemini_error(exc: BaseException) -> str:
    """Classify a Gemini failure without depending on one SDK exception type."""
    text = str(exc).lower()
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = None
    daily_markers = (
        "generaterequestsperday",
        "generate_content_free_tier_requests",
        "quota exceeded",
        "perdayperprojectpermodel",
    )
    if any(marker in text for marker in daily_markers):
        return "daily_quota_exhausted"
    if status == 401 or any(
        marker in text for marker in ("api key", "authentication", "permission denied", "unauthenticated")
    ):
        return "authentication"
    if status in {400, 404} or any(
        marker in text for marker in ("model not found", "invalid argument", "invalid request", "not found")
    ):
        return "model_or_request_invalid"
    if status == 429 or "429" in text or "rate limit" in text or "resource_exhausted" in text:
        return "temporary_rate_limit"
    if status in {500, 502, 503, 504} or any(
        marker in text for marker in ("500", "502", "503", "504", "internal server error", "service unavailable")
    ):
        return "server_temporary"
    return "unexpected"


def _configured_fallback_models() -> list[str]:
    configured = get_settings().gemini_fallback_models
    return list(dict.fromkeys(item.strip() for item in configured.split(",") if item.strip()))


def _retry_delay(exc: BaseException, attempt: int) -> float:
    settings = get_settings()
    retry_after = getattr(exc, "retry_after", None) or getattr(exc, "retry_delay", None)
    if retry_after is None:
        match = re.search(r"retry(?:ing| after)?[^0-9]*(\d+(?:\.\d+)?)\s*s", str(exc), re.I)
        retry_after = float(match.group(1)) if match else None
    delay = float(retry_after) if retry_after is not None else settings.gemini_retry_base_seconds * (2**attempt)
    return max(0.0, min(delay, settings.gemini_retry_max_seconds))


def _raise_gemini_failure(
    exc: BaseException,
    *,
    model_name: str,
    classification: str,
    attempted_models: list[str],
) -> None:
    message = f"Gemini story generation failed ({classification}) on model {model_name}: {exc}"
    kwargs = {
        "model": model_name,
        "classification": classification,
        "attempted_models": attempted_models,
    }
    if classification == "daily_quota_exhausted":
        raise GeminiQuotaExhaustedError(message, **kwargs) from exc
    if classification == "temporary_rate_limit":
        raise GeminiTemporaryRateLimitError(message, **kwargs) from exc
    if classification == "authentication":
        raise GeminiAuthenticationError(message, **kwargs) from exc
    if classification == "model_or_request_invalid":
        raise GeminiModelUnavailableError(message, **kwargs) from exc
    raise GeminiGenerationError(message, **kwargs) from exc


def analyze_script_structure(
    cleaned_text: str,
    sentences: list[ScriptSentence],
    sections: list[ScriptSection],
    *,
    model: Any | None = None,
) -> GeminiScriptAnalysis:
    """Run structured Gemini analysis over a cleaned script."""
    if not cleaned_text.strip():
        raise TextAgentError("Cannot analyze empty script text.")

    sentence_lines = [f"{s.index}: {s.text}" for s in sentences]
    section_summaries = [
        f"{i}: chars {sec.start_char}-{sec.end_char}: {cleaned_text[sec.start_char:sec.end_char][:160]}"
        for i, sec in enumerate(sections)
    ]
    user_prompt = build_text_agent_user_prompt(
        cleaned_text, sentence_lines, section_summaries
    )

    try:
        chat = model or get_chat_model()
        structured = chat.with_structured_output(GeminiScriptAnalysis)
        result = structured.invoke(
            [
                SystemMessage(content=TEXT_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        logger.warning("GEMINI_API_KEY missing — using heuristic script analysis")
        return _heuristic_script_analysis(cleaned_text, sentences, sections)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini script analysis failed")
        raise TextAgentError(f"Gemini script analysis failed: {exc}") from exc

    if isinstance(result, GeminiScriptAnalysis):
        return result
    if isinstance(result, dict):
        return GeminiScriptAnalysis.model_validate(result)
    raise TextAgentError("Unexpected Gemini structured output type.")


def _heuristic_script_analysis(
    cleaned_text: str,
    sentences: list[ScriptSentence],
    sections: list[ScriptSection],
) -> GeminiScriptAnalysis:
    from schemas.transcript import (
        GeminiClipBoundary,
        GeminiHook,
        GeminiImportantStatement,
    )

    words = [w for w in cleaned_text.replace("\n", " ").split() if len(w) > 3][:12]
    topics = list(dict.fromkeys(words[:5])) or ["general"]
    titles = [
        (sec.title or f"Section {i + 1}") for i, sec in enumerate(sections)
    ] or ["Opening"]
    hooks = []
    important = []
    boundaries = []
    if sentences:
        hooks.append(
            GeminiHook(
                sentence_index=sentences[0].index,
                reason="Opening sentence (heuristic)",
                score=0.7,
            )
        )
        mid = sentences[len(sentences) // 2]
        important.append(
            GeminiImportantStatement(
                sentence_index=mid.index,
                reason="Midpoint statement (heuristic)",
            )
        )
        if len(sentences) > 2:
            boundaries.append(
                GeminiClipBoundary(
                    after_sentence_index=sentences[min(2, len(sentences) - 1)].index,
                    reason="Early beat (heuristic)",
                    suggested_title=_truncate_words(sentences[0].text, 6),
                )
            )
    return GeminiScriptAnalysis(
        language="en",
        topics=topics,
        section_titles=titles,
        hooks=hooks,
        important_statements=important,
        clip_boundaries=boundaries,
    )


def _truncate_words(text: str, n: int = 6) -> str:
    parts = [w for w in (text or "").split() if w]
    return " ".join(parts[:n]) if parts else "Clip"


def generate_clip_stories(
    clip_blocks: list[str],
    *,
    project_id: str = "",
    video_type: str = "Shorts",
    country: str = "",
    video_type_block: str = "",
    visual_style_block: str = "",
    environment_block: str = "",
    research_block: str = "",
    model: Any | None = None,
) -> GeminiStoriesBatch:
    """Generate HOOK→CONTEXT→VALUE/EVENT→PAYOFF→CTA structures for clips."""
    if not clip_blocks:
        return GeminiStoriesBatch(stories=[])

    user_prompt = build_story_agent_user_prompt(
        clip_blocks,
        video_type=video_type,
        country=country,
        video_type_block=video_type_block,
        visual_style_block=visual_style_block,
        environment_block=environment_block,
        research_block=research_block,
    )
    settings = get_settings()
    model_names = [settings.gemini_model, *_configured_fallback_models()]
    attempted_models: list[str] = []
    max_retries = max(0, int(settings.gemini_max_retries))
    last_error: tuple[BaseException, str, str] | None = None

    for model_index, model_name in enumerate(dict.fromkeys(model_names)):
        attempted_models.append(model_name)
        for attempt in range(max_retries + 1):
            try:
                chat = model if model is not None and model_index == 0 else get_chat_model(
                    temperature=0.3, model_name=model_name
                )
                structured = chat.with_structured_output(GeminiStoriesBatch)
                result = structured.invoke(
                    [
                        SystemMessage(content=STORY_AGENT_SYSTEM),
                        HumanMessage(content=user_prompt),
                    ]
                )
                if isinstance(result, GeminiStoriesBatch):
                    return result
                if isinstance(result, dict):
                    return GeminiStoriesBatch.model_validate(result)
                raise StoryAgentError("Unexpected Gemini story structured output type.")
            except ConfigurationError as exc:
                _raise_gemini_failure(
                    exc,
                    model_name=model_name,
                    classification="authentication",
                    attempted_models=attempted_models,
                )
            except StoryAgentError:
                raise
            except Exception as exc:  # noqa: BLE001 - classify only provider failures
                classification = classify_gemini_error(exc)
                last_error = (exc, model_name, classification)
                logger.warning(
                    "Gemini story attempt failed project_id=%s stage=story_generation model=%s "
                    "classification=%s status=%s retry_count=%s attempted_models=%s",
                    project_id,
                    model_name,
                    classification,
                    getattr(exc, "status_code", None) or getattr(exc, "code", None),
                    attempt,
                    attempted_models,
                )
                if classification in {"daily_quota_exhausted", "authentication", "unexpected"}:
                    break
                if classification == "model_or_request_invalid":
                    break
                if attempt < max_retries:
                    delay = _retry_delay(exc, attempt)
                    logger.info("Retrying Gemini story model=%s in %.2f seconds", model_name, delay)
                    time.sleep(delay)
                    continue
                break

        if last_error is None:
            continue
        _, _, classification = last_error
        if classification == "daily_quota_exhausted" and model_index > 0:
            break
        if classification in {
            "daily_quota_exhausted",
            "model_or_request_invalid",
            "temporary_rate_limit",
            "server_temporary",
        }:
            continue
        break

    if last_error is not None:
        exc, model_name, classification = last_error
        logger.error(
            "Gemini story generation failed project_id=%s stage=story_generation model=%s "
            "error_type=%s status=%s fallback_models=%s retry_count=%s",
            project_id,
            model_name,
            classification,
            getattr(exc, "status_code", None) or getattr(exc, "code", None),
            attempted_models[1:],
            max_retries if classification in {"temporary_rate_limit", "server_temporary"} else 0,
        )
        _raise_gemini_failure(
            exc,
            model_name=model_name,
            classification=classification,
            attempted_models=attempted_models,
        )

    raise GeminiGenerationError(
        "Gemini story generation failed without a provider response.",
        attempted_models=attempted_models,
    )


def _heuristic_stories_batch(clip_blocks: list[str]) -> GeminiStoriesBatch:
    stories = []
    for i, block in enumerate(clip_blocks):
        text = (block or "").strip()
        first = " ".join(text.split()[:12]) or f"Clip {i + 1}"
        stories.append(
            GeminiClipStory(
                clip_id=i,
                hook=first,
                context="Context from source clip (heuristic).",
                value_event=_truncate_words(text, 18) or first,
                payoff="Key takeaway from this segment.",
                cta="Follow for more",
            )
        )
    return GeminiStoriesBatch(stories=stories)


def generate_clip_scripts(
    clip_blocks: list[str],
    *,
    video_type: str = "Shorts",
    country: str = "",
    video_type_block: str = "",
    visual_style_block: str = "",
    environment_block: str = "",
    research_block: str = "",
    model: Any | None = None,
) -> GeminiScriptsBatch:
    """Generate title/hook/script/caption/CTA/thumbnail/keywords for clips."""
    if not clip_blocks:
        return GeminiScriptsBatch(scripts=[])

    user_prompt = build_script_agent_user_prompt(
        clip_blocks,
        video_type=video_type,
        country=country,
        video_type_block=video_type_block,
        visual_style_block=visual_style_block,
        environment_block=environment_block,
        research_block=research_block,
    )
    try:
        chat = model or get_chat_model(temperature=0.35)
        structured = chat.with_structured_output(GeminiScriptsBatch)
        result = structured.invoke(
            [
                SystemMessage(content=SCRIPT_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        logger.warning("GEMINI_API_KEY missing — using heuristic clip scripts")
        return _heuristic_scripts_batch(clip_blocks)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini script generation failed")
        raise ScriptAgentError(f"Gemini script generation failed: {exc}") from exc

    if isinstance(result, GeminiScriptsBatch):
        return result
    if isinstance(result, dict):
        return GeminiScriptsBatch.model_validate(result)
    raise ScriptAgentError("Unexpected Gemini script structured output type.")


def _heuristic_scripts_batch(clip_blocks: list[str]) -> GeminiScriptsBatch:
    scripts = []
    for i, block in enumerate(clip_blocks):
        text = (block or "").strip()
        title = _truncate_words(text, 8) or f"Clip {i + 1}"
        hook = _truncate_words(text, 12) or title
        scripts.append(
            GeminiClipScript(
                clip_id=i,
                title=title,
                hook=hook,
                short_script=text[:500] or f"{hook}. Follow for more.",
                caption=_truncate_words(text, 20) or title,
                cta="Follow for more",
                thumbnail_text=_truncate_words(title, 4) or "WATCH",
                keywords=[w.lower().strip(".,!?") for w in text.split()[:6] if len(w) > 3],
            )
        )
    return GeminiScriptsBatch(scripts=scripts)


def localize_clip_scripts(
    script_blocks: list[str],
    *,
    locale_block: str,
    model: Any | None = None,
) -> GeminiLocalizedBatch:
    """Naturally localize clip scripts for one locale pack."""
    if not script_blocks:
        return GeminiLocalizedBatch(scripts=[])

    user_prompt = build_language_agent_user_prompt(locale_block, script_blocks)
    try:
        chat = model or get_chat_model(temperature=0.4)
        structured = chat.with_structured_output(GeminiLocalizedBatch)
        result = structured.invoke(
            [
                SystemMessage(content=LANGUAGE_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        logger.warning("GEMINI_API_KEY missing — passthrough localization")
        return _heuristic_localize_batch(script_blocks)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini localization failed")
        raise LanguageAgentError(f"Gemini localization failed: {exc}") from exc

    if isinstance(result, GeminiLocalizedBatch):
        return result
    if isinstance(result, dict):
        return GeminiLocalizedBatch.model_validate(result)
    raise LanguageAgentError("Unexpected Gemini localization structured output type.")


def _heuristic_localize_batch(script_blocks: list[str]) -> GeminiLocalizedBatch:
    from schemas.localization import GeminiLocalizedClip

    out = []
    for i, block in enumerate(script_blocks):
        text = (block or "").strip()
        title = _truncate_words(text, 8) or f"Clip {i + 1}"
        out.append(
            GeminiLocalizedClip(
                clip_id=i,
                title=title,
                hook=_truncate_words(text, 12) or title,
                short_script=text[:500] or title,
                caption=_truncate_words(text, 20) or title,
                cta="Follow for more",
                thumbnail_text=_truncate_words(title, 4) or "WATCH",
                keywords=[w.lower().strip(".,!?") for w in text.split()[:6] if len(w) > 3],
                voice_direction="Clear, natural delivery",
            )
        )
    return GeminiLocalizedBatch(scripts=out)


def analyze_cultural_adaptation(
    script_blocks: list[str],
    *,
    locale_block: str,
    audience: str = "General",
    model: Any | None = None,
) -> GeminiCulturalBatch:
    """Analyze scripts for cultural adaptation findings."""
    if not script_blocks:
        return GeminiCulturalBatch(findings=[], cultural_summary="")

    user_prompt = build_cultural_adaptation_user_prompt(
        locale_block, audience, script_blocks
    )
    try:
        chat = model or get_chat_model(temperature=0.3)
        structured = chat.with_structured_output(GeminiCulturalBatch)
        result = structured.invoke(
            [
                SystemMessage(content=CULTURAL_ADAPTATION_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        logger.warning("GEMINI_API_KEY missing — empty cultural adaptation")
        return GeminiCulturalBatch(
            findings=[],
            cultural_summary="Heuristic: no cultural changes without Gemini.",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini cultural adaptation failed")
        raise CulturalAdaptationError(
            f"Gemini cultural adaptation failed: {exc}"
        ) from exc

    if isinstance(result, GeminiCulturalBatch):
        return result
    if isinstance(result, dict):
        return GeminiCulturalBatch.model_validate(result)
    raise CulturalAdaptationError("Unexpected Gemini cultural structured output type.")


def plan_humor_localization(
    script_blocks: list[str],
    *,
    mode: str,
    humor_style: str = "None",
    audience: str = "General",
    locale_block: str = "",
    cultural_summary: str = "",
    model: Any | None = None,
) -> GeminiHumorBatch:
    """Plan humor localization strategies per clip."""
    if not script_blocks:
        return GeminiHumorBatch(items=[], humor_summary="")

    user_prompt = build_humor_localization_user_prompt(
        mode=mode,
        humor_style=humor_style,
        audience=audience,
        locale_block=locale_block,
        cultural_summary=cultural_summary,
        script_blocks=script_blocks,
    )
    try:
        chat = model or get_chat_model(temperature=0.35)
        structured = chat.with_structured_output(GeminiHumorBatch)
        result = structured.invoke(
            [
                SystemMessage(content=HUMOR_LOCALIZATION_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        logger.warning("GEMINI_API_KEY missing — empty humor localization")
        return GeminiHumorBatch(
            items=[],
            humor_summary="Heuristic: no humor rewrite without Gemini.",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini humor localization failed")
        raise HumorLocalizationError(
            f"Gemini humor localization failed: {exc}"
        ) from exc

    if isinstance(result, GeminiHumorBatch):
        return result
    if isinstance(result, dict):
        return GeminiHumorBatch.model_validate(result)
    raise HumorLocalizationError("Unexpected Gemini humor structured output type.")


def analyze_trends(
    *,
    platform: str,
    audience: str = "General",
    title: str = "",
    description: str = "",
    tags: list[str] | None = None,
    hashtags: list[str] | None = None,
    keywords: list[str] | None = None,
    viral_hooks: list[str] | None = None,
    seed_block: str = "",
    model: Any | None = None,
) -> GeminiTrendAnalysis:
    """Analyze content signals for trend score, topics, and recommended tags."""
    user_prompt = build_trend_agent_user_prompt(
        platform=platform or "YouTube",
        audience=audience or "General",
        title=title or "",
        description=description or "",
        tags=list(tags or []),
        hashtags=list(hashtags or []),
        keywords=list(keywords or []),
        viral_hooks=list(viral_hooks or []),
        seed_block=seed_block or "",
    )
    try:
        chat = model or get_chat_model(temperature=0.3)
        structured = chat.with_structured_output(GeminiTrendAnalysis)
        result = structured.invoke(
            [
                SystemMessage(content=TREND_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini trend analysis failed")
        raise TrendAgentError(f"Gemini trend analysis failed: {exc}") from exc

    if isinstance(result, GeminiTrendAnalysis):
        return result
    if isinstance(result, dict):
        return GeminiTrendAnalysis.model_validate(result)
    raise TrendAgentError("Unexpected Gemini trend structured output type.")


def analyze_repurpose(
    *,
    source_kind: str,
    platform: str = "YouTube",
    audience: str = "General",
    source_excerpt: str = "",
    title: str = "",
    hook: str = "",
    hashtags: list[str] | None = None,
    trend_topics: list[str] | None = None,
    format_hints: str = "",
    model: Any | None = None,
) -> GeminiRepurposeBatch:
    """Convert one source excerpt into multiple distribution formats."""
    user_prompt = build_repurpose_agent_user_prompt(
        source_kind=source_kind or "video",
        platform=platform or "YouTube",
        audience=audience or "General",
        source_excerpt=source_excerpt or "",
        title=title or "",
        hook=hook or "",
        hashtags=list(hashtags or []),
        trend_topics=list(trend_topics or []),
        format_hints=format_hints or "",
    )
    try:
        chat = model or get_chat_model(temperature=0.35)
        structured = chat.with_structured_output(GeminiRepurposeBatch)
        result = structured.invoke(
            [
                SystemMessage(content=REPURPOSE_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini repurpose analysis failed")
        raise RepurposeAgentError(f"Gemini repurpose analysis failed: {exc}") from exc

    if isinstance(result, GeminiRepurposeBatch):
        return result
    if isinstance(result, dict):
        return GeminiRepurposeBatch.model_validate(result)
    raise RepurposeAgentError("Unexpected Gemini repurpose structured output type.")


def enrich_calendar_topics(
    *,
    platform: str = "YouTube",
    video_type: str = "Shorts",
    audience: str = "General",
    seed_topics: list[str] | None = None,
    dates: list[str] | None = None,
    model: Any | None = None,
) -> GeminiCalendarBatch:
    """Enrich calendar slot topics from seeds (titles only)."""
    user_prompt = build_calendar_agent_user_prompt(
        platform=platform or "YouTube",
        video_type=video_type or "Shorts",
        audience=audience or "General",
        seed_topics=list(seed_topics or []),
        dates=list(dates or []),
    )
    try:
        chat = model or get_chat_model(temperature=0.35)
        structured = chat.with_structured_output(GeminiCalendarBatch)
        result = structured.invoke(
            [
                SystemMessage(content=CALENDAR_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini calendar enrichment failed")
        raise CalendarAgentError(f"Gemini calendar enrichment failed: {exc}") from exc

    if isinstance(result, GeminiCalendarBatch):
        return result
    if isinstance(result, dict):
        return GeminiCalendarBatch.model_validate(result)
    raise CalendarAgentError("Unexpected Gemini calendar structured output type.")


def enrich_brand_kit(
    *,
    brand_name: str = "Brand",
    audience: str = "General",
    platform: str = "YouTube",
    tone: str = "",
    tagline: str = "",
    pillars: list[str] | None = None,
    model: Any | None = None,
) -> GeminiBrandBatch:
    """Refine brand voice / CTA / messaging text only."""
    user_prompt = build_brand_agent_user_prompt(
        brand_name=brand_name or "Brand",
        audience=audience or "General",
        platform=platform or "YouTube",
        tone=tone or "",
        tagline=tagline or "",
        pillars=list(pillars or []),
    )
    try:
        chat = model or get_chat_model(temperature=0.3)
        structured = chat.with_structured_output(GeminiBrandBatch)
        result = structured.invoke(
            [
                SystemMessage(content=BRAND_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini brand enrichment failed")
        raise BrandAgentError(f"Gemini brand enrichment failed: {exc}") from exc

    if isinstance(result, GeminiBrandBatch):
        return result
    if isinstance(result, dict):
        return GeminiBrandBatch.model_validate(result)
    raise BrandAgentError("Unexpected Gemini brand structured output type.")


def analyze_analytics(
    *,
    platform: str,
    audience: str = "General",
    title: str = "",
    hook: str = "",
    description: str = "",
    tags: list[str] | None = None,
    hashtags: list[str] | None = None,
    keywords: list[str] | None = None,
    trend_score: float = 0.0,
    viral_final: float = 0.0,
    viral_shareability: float = 0.0,
    thumbnail_text: str = "",
    thumbnail_emotion: str = "",
    thumbnail_layout: str = "",
    weight_block: str = "",
    model: Any | None = None,
) -> GeminiAnalyticsAnalysis:
    """Predict engagement/retention/shareability (and watch-time/CTR) scores."""
    user_prompt = build_analytics_agent_user_prompt(
        platform=platform or "YouTube",
        audience=audience or "General",
        title=title or "",
        hook=hook or "",
        description=description or "",
        tags=list(tags or []),
        hashtags=list(hashtags or []),
        keywords=list(keywords or []),
        trend_score=float(trend_score or 0.0),
        viral_final=float(viral_final or 0.0),
        viral_shareability=float(viral_shareability or 0.0),
        thumbnail_text=thumbnail_text or "",
        thumbnail_emotion=thumbnail_emotion or "",
        thumbnail_layout=thumbnail_layout or "",
        weight_block=weight_block or "",
    )
    try:
        chat = model or get_chat_model(temperature=0.3)
        structured = chat.with_structured_output(GeminiAnalyticsAnalysis)
        result = structured.invoke(
            [
                SystemMessage(content=ANALYTICS_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini analytics prediction failed")
        raise AnalyticsAgentError(
            f"Gemini analytics prediction failed: {exc}"
        ) from exc

    if isinstance(result, GeminiAnalyticsAnalysis):
        return result
    if isinstance(result, dict):
        return GeminiAnalyticsAnalysis.model_validate(result)
    raise AnalyticsAgentError("Unexpected Gemini analytics structured output type.")


def analyze_images(
    *,
    style: str = "Cinematic",
    environment: str = "Wildlife/Nature Forest",
    audience: str = "General",
    title: str = "",
    hook: str = "",
    scene_block: str = "",
    script_block: str = "",
    transcript_excerpt: str = "",
    kind_hints: str = "",
    model: Any | None = None,
) -> GeminiImageBatch:
    """Plan image prompts for scenes, storyboard, B-roll, thumbnails, backgrounds."""
    user_prompt = build_image_agent_user_prompt(
        style=style or "Cinematic",
        environment=environment or "Wildlife/Nature Forest",
        audience=audience or "General",
        title=title or "",
        hook=hook or "",
        scene_block=scene_block or "",
        script_block=script_block or "",
        transcript_excerpt=transcript_excerpt or "",
        kind_hints=kind_hints or "",
    )
    try:
        chat = model or get_chat_model(temperature=0.4)
        structured = chat.with_structured_output(GeminiImageBatch)
        result = structured.invoke(
            [
                SystemMessage(content=IMAGE_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini image planning failed")
        raise ImageAgentError(f"Gemini image planning failed: {exc}") from exc

    if isinstance(result, GeminiImageBatch):
        return result
    if isinstance(result, dict):
        return GeminiImageBatch.model_validate(result)
    raise ImageAgentError("Unexpected Gemini image structured output type.")


def analyze_storyboard(
    *,
    style: str = "Cinematic",
    environment: str = "Wildlife/Nature Forest",
    audience: str = "General",
    title: str = "",
    hook: str = "",
    script_block: str = "",
    transcript_excerpt: str = "",
    scene_block: str = "",
    story_block: str = "",
    camera_vocab: str = "",
    transition_vocab: str = "",
    model: Any | None = None,
) -> GeminiStoryboardBatch:
    """Plan a timed shot list with camera, visual, VO, and transitions."""
    user_prompt = build_storyboard_agent_user_prompt(
        style=style or "Cinematic",
        environment=environment or "Wildlife/Nature Forest",
        audience=audience or "General",
        title=title or "",
        hook=hook or "",
        script_block=script_block or "",
        transcript_excerpt=transcript_excerpt or "",
        scene_block=scene_block or "",
        story_block=story_block or "",
        camera_vocab=camera_vocab or "",
        transition_vocab=transition_vocab or "",
    )
    try:
        chat = model or get_chat_model(temperature=0.35)
        structured = chat.with_structured_output(GeminiStoryboardBatch)
        result = structured.invoke(
            [
                SystemMessage(content=STORYBOARD_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini storyboard planning failed")
        raise StoryboardAgentError(
            f"Gemini storyboard planning failed: {exc}"
        ) from exc

    if isinstance(result, GeminiStoryboardBatch):
        return result
    if isinstance(result, dict):
        return GeminiStoryboardBatch.model_validate(result)
    raise StoryboardAgentError("Unexpected Gemini storyboard structured output type.")


def analyze_video_generation(
    *,
    mode: str = "Cinematic",
    style: str = "Cinematic",
    environment: str = "Wildlife/Nature Forest",
    audience: str = "General",
    title: str = "",
    hook: str = "",
    script_block: str = "",
    storyboard_block: str = "",
    mode_suffix: str = "",
    camera_vocab: str = "",
    model: Any | None = None,
) -> GeminiVideoGenerationBatch:
    """Plan provider-agnostic scene prompts, shot sequence, and camera moves."""
    user_prompt = build_video_generation_agent_user_prompt(
        mode=mode or "Cinematic",
        style=style or "Cinematic",
        environment=environment or "Wildlife/Nature Forest",
        audience=audience or "General",
        title=title or "",
        hook=hook or "",
        script_block=script_block or "",
        storyboard_block=storyboard_block or "",
        mode_suffix=mode_suffix or "",
        camera_vocab=camera_vocab or "",
    )
    try:
        chat = model or get_chat_model(temperature=0.35)
        structured = chat.with_structured_output(GeminiVideoGenerationBatch)
        result = structured.invoke(
            [
                SystemMessage(content=VIDEO_GENERATION_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini video generation planning failed")
        raise VideoGenerationAgentError(
            f"Gemini video generation planning failed: {exc}"
        ) from exc

    if isinstance(result, GeminiVideoGenerationBatch):
        return result
    if isinstance(result, dict):
        return GeminiVideoGenerationBatch.model_validate(result)
    raise VideoGenerationAgentError(
        "Unexpected Gemini video generation structured output type."
    )


def analyze_director(
    *,
    style: str = "Cinematic",
    environment: str = "Wildlife/Nature Forest",
    audience: str = "General",
    title: str = "",
    hook: str = "",
    script_block: str = "",
    storyboard_block: str = "",
    story_block: str = "",
    camera_vocab: str = "",
    model: Any | None = None,
) -> GeminiDirectorBatch:
    """Plan scene order, continuity notes, and camera flow."""
    user_prompt = build_director_agent_user_prompt(
        style=style or "Cinematic",
        environment=environment or "Wildlife/Nature Forest",
        audience=audience or "General",
        title=title or "",
        hook=hook or "",
        script_block=script_block or "",
        storyboard_block=storyboard_block or "",
        story_block=story_block or "",
        camera_vocab=camera_vocab or "",
    )
    try:
        chat = model or get_chat_model(temperature=0.35)
        structured = chat.with_structured_output(GeminiDirectorBatch)
        result = structured.invoke(
            [
                SystemMessage(content=DIRECTOR_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini director planning failed")
        raise DirectorAgentError(f"Gemini director planning failed: {exc}") from exc

    if isinstance(result, GeminiDirectorBatch):
        return result
    if isinstance(result, dict):
        return GeminiDirectorBatch.model_validate(result)
    raise DirectorAgentError("Unexpected Gemini director structured output type.")


def analyze_characters(
    *,
    style: str = "Cinematic",
    environment: str = "Wildlife/Nature Forest",
    audience: str = "General",
    title: str = "",
    hook: str = "",
    script_block: str = "",
    storyboard_block: str = "",
    story_block: str = "",
    voice_hint: str = "",
    avatar_hint: str = "",
    role_defaults: str = "",
    model: Any | None = None,
) -> GeminiCharacterBatch:
    """Plan a cast bible for cross-scene character consistency."""
    user_prompt = build_character_agent_user_prompt(
        style=style or "Cinematic",
        environment=environment or "Wildlife/Nature Forest",
        audience=audience or "General",
        title=title or "",
        hook=hook or "",
        script_block=script_block or "",
        storyboard_block=storyboard_block or "",
        story_block=story_block or "",
        voice_hint=voice_hint or "",
        avatar_hint=avatar_hint or "",
        role_defaults=role_defaults or "",
    )
    try:
        chat = model or get_chat_model(temperature=0.35)
        structured = chat.with_structured_output(GeminiCharacterBatch)
        result = structured.invoke(
            [
                SystemMessage(content=CHARACTER_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini character planning failed")
        raise CharacterAgentError(f"Gemini character planning failed: {exc}") from exc

    if isinstance(result, GeminiCharacterBatch):
        return result
    if isinstance(result, dict):
        return GeminiCharacterBatch.model_validate(result)
    raise CharacterAgentError("Unexpected Gemini character structured output type.")


def analyze_camera(
    *,
    style: str = "Cinematic",
    environment: str = "Wildlife/Nature Forest",
    audience: str = "General",
    title: str = "",
    hook: str = "",
    script_block: str = "",
    storyboard_block: str = "",
    character_block: str = "",
    shot_vocab: str = "",
    model: Any | None = None,
) -> GeminiCameraBatch:
    """Plan per-scene camera shot types, movement, and instructions."""
    user_prompt = build_camera_agent_user_prompt(
        style=style or "Cinematic",
        environment=environment or "Wildlife/Nature Forest",
        audience=audience or "General",
        title=title or "",
        hook=hook or "",
        script_block=script_block or "",
        storyboard_block=storyboard_block or "",
        character_block=character_block or "",
        shot_vocab=shot_vocab or "",
    )
    try:
        chat = model or get_chat_model(temperature=0.35)
        structured = chat.with_structured_output(GeminiCameraBatch)
        result = structured.invoke(
            [
                SystemMessage(content=CAMERA_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini camera planning failed")
        raise CameraAgentError(f"Gemini camera planning failed: {exc}") from exc

    if isinstance(result, GeminiCameraBatch):
        return result
    if isinstance(result, dict):
        return GeminiCameraBatch.model_validate(result)
    raise CameraAgentError("Unexpected Gemini camera structured output type.")


def analyze_motion_graphics(
    *,
    style: str = "Cinematic",
    environment: str = "Wildlife/Nature Forest",
    audience: str = "General",
    video_type: str = "",
    title: str = "",
    hook: str = "",
    script_block: str = "",
    storyboard_block: str = "",
    director_block: str = "",
    camera_block: str = "",
    character_block: str = "",
    kind_vocab: str = "",
    model: Any | None = None,
) -> GeminiMotionGraphicsBatch:
    """Plan graphic-layer overlays (titles, kinetics, charts, educational)."""
    user_prompt = build_motion_graphics_agent_user_prompt(
        style=style or "Cinematic",
        environment=environment or "Wildlife/Nature Forest",
        audience=audience or "General",
        video_type=video_type or "",
        title=title or "",
        hook=hook or "",
        script_block=script_block or "",
        storyboard_block=storyboard_block or "",
        director_block=director_block or "",
        camera_block=camera_block or "",
        character_block=character_block or "",
        kind_vocab=kind_vocab or "",
    )
    try:
        chat = model or get_chat_model(temperature=0.35)
        structured = chat.with_structured_output(GeminiMotionGraphicsBatch)
        result = structured.invoke(
            [
                SystemMessage(content=MOTION_GRAPHICS_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini motion graphics planning failed")
        raise MotionGraphicsAgentError(
            f"Gemini motion graphics planning failed: {exc}"
        ) from exc

    if isinstance(result, GeminiMotionGraphicsBatch):
        return result
    if isinstance(result, dict):
        return GeminiMotionGraphicsBatch.model_validate(result)
    raise MotionGraphicsAgentError(
        "Unexpected Gemini motion graphics structured output type."
    )


def analyze_documentary(
    *,
    style: str = "Cinematic",
    environment: str = "Wildlife/Nature Forest",
    audience: str = "General",
    video_type: str = "",
    title: str = "",
    hook: str = "",
    script_block: str = "",
    storyboard_block: str = "",
    director_block: str = "",
    character_block: str = "",
    templates_block: str = "",
    model: Any | None = None,
) -> GeminiDocumentaryBatch:
    """Plan documentary introduction, chapters, and conclusion."""
    user_prompt = build_documentary_agent_user_prompt(
        style=style or "Cinematic",
        environment=environment or "Wildlife/Nature Forest",
        audience=audience or "General",
        video_type=video_type or "",
        title=title or "",
        hook=hook or "",
        script_block=script_block or "",
        storyboard_block=storyboard_block or "",
        director_block=director_block or "",
        character_block=character_block or "",
        templates_block=templates_block or "",
    )
    try:
        chat = model or get_chat_model(temperature=0.35)
        structured = chat.with_structured_output(GeminiDocumentaryBatch)
        result = structured.invoke(
            [
                SystemMessage(content=DOCUMENTARY_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini documentary planning failed")
        raise DocumentaryAgentError(
            f"Gemini documentary planning failed: {exc}"
        ) from exc

    if isinstance(result, GeminiDocumentaryBatch):
        return result
    if isinstance(result, dict):
        return GeminiDocumentaryBatch.model_validate(result)
    raise DocumentaryAgentError(
        "Unexpected Gemini documentary structured output type."
    )


def enrich_research_report(
    *,
    topic: str,
    sources: list[ResearchSource],
    claims: list[ResearchClaim],
    outline: list[ResearchOutlineSection],
    summary: str,
    model: Any | None = None,
) -> GeminiResearchEnrichment | None:
    """Optionally enrich topic/outline/summary; never invent claims/sources."""
    settings = get_settings()
    if not settings.has_gemini_api_key:
        return None

    sources_block = "\n".join(
        f"- {s.id}: [{s.kind}] {s.title} :: {_short(s.excerpt)}" for s in sources[:40]
    )
    claims_block = "\n".join(
        f"- {c.id} (sources={','.join(c.source_ids)}): {_short(c.text)}"
        for c in claims[:40]
    )
    outline_block = "\n".join(
        f"- {o.id}: {o.title} | claims={','.join(o.claim_ids)} | {_short(o.summary)}"
        for o in outline
    )
    user_prompt = build_research_enrich_user_prompt(
        topic=topic,
        sources_block=sources_block,
        claims_block=claims_block,
        outline_block=outline_block,
        summary=summary,
    )
    try:
        chat = model or get_chat_model(temperature=0.25)
        structured = chat.with_structured_output(GeminiResearchEnrichment)
        result = structured.invoke(
            [
                SystemMessage(content=RESEARCH_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        return None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini research enrich failed")
        raise ResearchAgentError(f"Gemini research enrich failed: {exc}") from exc

    if isinstance(result, GeminiResearchEnrichment):
        return result
    if isinstance(result, dict):
        return GeminiResearchEnrichment.model_validate(result)
    raise ResearchAgentError("Unexpected Gemini research structured output type.")


def _short(text: str, n: int = 160) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def decide_next_crew_agent(
    *,
    pack_status: str,
    task_board: str,
    retry_counts: str,
    last_messages: str,
    crew_step: int,
    max_steps: int,
    model: Any | None = None,
) -> GeminiSupervisorDecision | None:
    """Ask Gemini which crew worker to run next (or FINISH)."""
    settings = get_settings()
    if not settings.has_gemini_api_key:
        return None

    user_prompt = build_supervisor_user_prompt(
        pack_status=pack_status,
        task_board=task_board,
        retry_counts=retry_counts,
        last_messages=last_messages,
        crew_step=crew_step,
        max_steps=max_steps,
    )
    try:
        chat = model or get_chat_model(temperature=0.2)
        structured = chat.with_structured_output(GeminiSupervisorDecision)
        result = structured.invoke(
            [
                SystemMessage(content=SUPERVISOR_AGENT_SYSTEM),
                HumanMessage(content=user_prompt),
            ]
        )
    except ConfigurationError:
        return None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini supervisor decide failed")
        raise SupervisorAgentError(f"Gemini supervisor decide failed: {exc}") from exc

    if isinstance(result, GeminiSupervisorDecision):
        return result
    if isinstance(result, dict):
        return GeminiSupervisorDecision.model_validate(result)
    raise SupervisorAgentError("Unexpected Gemini supervisor structured output type.")


def call_gemini_json(prompt: str, *, system_prompt: str = "Return only valid JSON.", temperature: float = 0.2) -> dict[str, Any]:
    """Helper to call Gemini and parse a JSON response dict."""
    import json
    import re
    settings = get_settings()
    if not settings.has_gemini_api_key:
        raise ConfigurationError("GEMINI_API_KEY missing")

    chat = get_chat_model(temperature=temperature)
    res = chat.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt),
        ]
    )
    content = str(res.content).strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if match:
        content = match.group(1)
    return json.loads(content)

