"""Load and resolve country / region / language localization catalogs."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from schemas.localization import (
    CountryProfile,
    CurrencyInfo,
    LanguageProfile,
    LocalePack,
    LocalizationTarget,
    RegionProfile,
)

CONTINENTAL_REGIONS = frozenset(
    {
        "global",
        "north america",
        "europe",
        "asia",
        "mena",
        "latam",
        "africa",
        "oceania",
    }
)

_CATALOG_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "localization"


def catalog_dir() -> Path:
    return _CATALOG_DIR


def _norm(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


@lru_cache(maxsize=1)
def _load_raw() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    countries = json.loads((_CATALOG_DIR / "countries.json").read_text(encoding="utf-8"))
    regions = json.loads((_CATALOG_DIR / "regions.json").read_text(encoding="utf-8"))
    languages = json.loads((_CATALOG_DIR / "languages.json").read_text(encoding="utf-8"))
    return countries, regions, languages


def clear_catalog_cache() -> None:
    _load_raw.cache_clear()


def list_countries() -> list[CountryProfile]:
    countries, _, _ = _load_raw()
    return [CountryProfile.model_validate(c) for c in countries]


def list_regions() -> list[RegionProfile]:
    _, regions, _ = _load_raw()
    return [RegionProfile.model_validate(r) for r in regions]


def list_languages() -> list[LanguageProfile]:
    _, _, languages = _load_raw()
    return [LanguageProfile.model_validate(lang) for lang in languages]


def resolve_country(name_or_id: str) -> CountryProfile | None:
    key = _norm(name_or_id)
    if not key:
        return None
    for country in list_countries():
        if _norm(country.id) == key or _norm(country.name) == key:
            return country
    # Aliases
    aliases = {
        "usa": "us",
        "u.s.": "us",
        "u.s.a.": "us",
        "america": "us",
        "uk": "gb",
        "britain": "gb",
        "uae": "ae",
    }
    alias = aliases.get(key)
    if alias:
        for country in list_countries():
            if country.id == alias:
                return country
    return None


def resolve_language(name_or_id: str) -> LanguageProfile | None:
    key = _norm(name_or_id)
    if not key:
        return None
    for lang in list_languages():
        if (
            _norm(lang.id) == key
            or _norm(lang.name) == key
            or _norm(lang.code) == key
        ):
            return lang
    return None


def resolve_region(
    region_name: str,
    *,
    country: CountryProfile | None = None,
) -> RegionProfile | None:
    key = _norm(region_name)
    if not key or key in CONTINENTAL_REGIONS:
        return None
    country_id = country.id if country else ""
    for region in list_regions():
        if country_id and region.country_id != country_id:
            continue
        if _norm(region.id) == key or _norm(region.name) == key:
            return region
    # If country filter missed, try global name match then validate country
    for region in list_regions():
        if _norm(region.name) == key or _norm(region.id) == key:
            if not country_id or region.country_id == country_id:
                return region
    return None


def build_locale_pack(
    target: LocalizationTarget,
    *,
    include_regional_humor: bool = False,
    voice: str = "Neutral",
    country_override: CountryProfile | None = None,
    region_override: RegionProfile | None = None,
) -> LocalePack:
    country = country_override or resolve_country(target.country)
    region = region_override
    if region is None and target.region:
        region = resolve_region(target.region, country=country)

    language_name = target.language.strip()
    if not language_name and region and region.language:
        language_name = region.language
    if not language_name and country:
        language_name = country.default_language
    language = resolve_language(language_name) if language_name else None

    notes: list[str] = []
    if country:
        notes.append(f"Country: {country.name}")
        if country.cultural_notes:
            notes.append(country.cultural_notes)
        notes.append(
            f"Currency {country.currency.code} ({country.currency.symbol}); "
            f"measurements={country.measurements}; dates={country.date_format}"
        )
    if region:
        notes.append(f"Region: {region.name}")
        if region.cultural_notes:
            notes.append(region.cultural_notes)
        if region.slang_notes:
            notes.append(f"Regional slang: {region.slang_notes}")
        if region.idioms:
            notes.append(f"Regional idioms: {', '.join(region.idioms)}")
        if include_regional_humor and region.humor_notes:
            notes.append(f"Regional humor: {region.humor_notes}")
    if language:
        notes.append(f"Language: {language.name} ({language.code})")
        for field in (
            language.vocabulary_notes,
            language.slang_notes,
            language.cta_style,
            language.caption_style,
            language.voice_notes,
        ):
            if field:
                notes.append(field)
        if language.idiom_examples:
            notes.append(f"Idioms: {', '.join(language.idiom_examples)}")

    effective = LocalizationTarget(
        country=country.name if country else target.country,
        region=region.name if region else ("" if _norm(target.region) in CONTINENTAL_REGIONS else target.region),
        language=language.name if language else language_name,
    )
    return LocalePack(
        target=effective,
        country=country,
        region=region,
        language=language,
        include_regional_humor=include_regional_humor,
        voice=voice,
        summary_notes=notes,
    )


def expand_targets(
    *,
    country: str,
    region: str = "",
    language: str = "",
    localization_targets: list[LocalizationTarget] | list[dict[str, Any]] | None = None,
    cultural_adaptation: bool = False,
) -> list[LocalizationTarget]:
    """Build unique localization targets from primary config + optional extras."""
    primary = LocalizationTarget(
        country=country or "United States",
        region=region or "",
        language=language or "",
    )
    # Fill language from region/country if blank
    country_prof = resolve_country(primary.country)
    region_prof = resolve_region(primary.region, country=country_prof)
    if not primary.language.strip():
        if region_prof and region_prof.language:
            primary.language = region_prof.language
        elif country_prof:
            primary.language = country_prof.default_language
        else:
            primary.language = "English"

    targets: list[LocalizationTarget] = [primary]

    extras = localization_targets or []
    for item in extras:
        if isinstance(item, LocalizationTarget):
            targets.append(item)
        else:
            targets.append(LocalizationTarget.model_validate(item))

    # Rule 12: when UI selected explicit localization_targets, do not auto-expand
    # beyond that list (+ primary). Cultural adaptation only seeds from primary.
    if cultural_adaptation and country_prof and not extras:
        if country_prof.default_language:
            targets.append(
                LocalizationTarget(
                    country=country_prof.name,
                    region="",
                    language=country_prof.default_language,
                )
            )
        if region_prof and region_prof.language:
            targets.append(
                LocalizationTarget(
                    country=country_prof.name,
                    region=region_prof.name,
                    language=region_prof.language,
                )
            )

    # Deduplicate by normalized triple
    seen: set[tuple[str, str, str]] = set()
    unique: list[LocalizationTarget] = []
    for t in targets:
        c_prof = resolve_country(t.country) or country_prof
        r_prof = resolve_region(t.region, country=c_prof)
        lang = t.language.strip()
        if not lang:
            if r_prof and r_prof.language:
                lang = r_prof.language
            elif c_prof:
                lang = c_prof.default_language
            else:
                lang = "English"
        region_name = ""
        if r_prof:
            region_name = r_prof.name
        elif t.region and _norm(t.region) not in CONTINENTAL_REGIONS:
            region_name = t.region
        country_name = c_prof.name if c_prof else t.country
        key = (_norm(country_name), _norm(region_name), _norm(lang))
        if key in seen:
            continue
        seen.add(key)
        unique.append(
            LocalizationTarget(
                country=country_name,
                region=region_name,
                language=lang,
            )
        )
    return unique


def locale_pack_prompt_block(pack: LocalePack) -> str:
    """Render a locale pack into prompt text for Gemini."""
    lines = [
        f"Target country: {pack.target.country}",
        f"Target region: {pack.target.region or '(none)'}",
        f"Target language: {pack.target.language}",
        f"Audience: {pack.audience or 'General'}",
        f"Voice preference: {pack.voice}",
        f"Humor adaptation mode: {pack.humor_adaptation or 'none'}",
        f"Humor style preference: {pack.humor_style or 'None'}",
    ]
    if pack.cultural_summary:
        lines.append(f"Cultural adaptation summary: {pack.cultural_summary}")
    if pack.humor_summary:
        lines.append(f"Humor localization summary: {pack.humor_summary}")
    if pack.country:
        c = pack.country
        lines.extend(
            [
                f"Currency: {c.currency.code} {c.currency.symbol} (e.g. {c.currency.example})",
                f"Measurements: {c.measurements}",
                f"Date format: {c.date_format}",
                f"Example swaps: {json.dumps(c.example_swaps, ensure_ascii=False)}",
                f"Country cultural notes: {c.cultural_notes}",
                f"Country voice hints: {c.voice_hints}",
            ]
        )
    if pack.region:
        r = pack.region
        lines.extend(
            [
                f"Regional slang: {r.slang_notes}",
                f"Regional idioms: {', '.join(r.idioms)}",
                f"Regional cultural notes: {r.cultural_notes}",
            ]
        )
        if (
            pack.include_regional_humor or pack.humor_adaptation == "regional"
        ) and r.humor_notes:
            lines.append(f"Regional humor: {r.humor_notes}")
    if pack.language:
        lang = pack.language
        lines.extend(
            [
                f"Language code: {lang.code}",
                f"Script direction: {lang.script_direction}",
                f"Formality: {lang.formality}",
                f"Vocabulary: {lang.vocabulary_notes}",
                f"Slang: {lang.slang_notes}",
                f"Idiom examples: {', '.join(lang.idiom_examples)}",
                f"CTA style: {lang.cta_style}",
                f"Caption style: {lang.caption_style}",
                f"Voice notes: {lang.voice_notes}",
            ]
        )
    if pack.summary_notes:
        lines.append("Summary:")
        lines.extend(f"- {n}" for n in pack.summary_notes)
    return "\n".join(lines)
