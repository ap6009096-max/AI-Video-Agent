"""Unit tests for graph routers."""

from __future__ import annotations

from graph.routers import (
    should_run_analytics,
    should_run_avatar,
    should_run_broll,
    should_run_funny,
    should_run_image_generation,
    should_run_music,
    should_run_repurpose,
    should_run_content_calendar,
    should_run_seo,
    should_run_brand,
    should_run_storyboard,
    should_run_thumbnail,
    should_run_trend,
    should_run_character,
    should_run_camera,
    should_run_director,
    should_run_motion_graphics,
    should_run_documentary,
    should_run_video_generation,
    should_run_viral,
    should_run_voice,
    should_run_podcast,
    should_run_research,
    route_after_moment,
    route_after_smart_clip,
    route_after_podcast,
    route_after_research,
    route_after_environment,
    route_after_image_generation,
    route_after_storyboard,
    route_after_character,
    route_after_camera,
    route_after_director,
    route_after_motion_graphics,
    route_after_documentary,
    route_after_video_generation,
    route_after_platform,
    route_after_brand,
    route_after_repurpose,
    route_after_calendar,
    route_after_seo,
    route_after_thumbnail,
    route_after_trend,
    route_after_voice,
)


def test_funny_skip_when_flag_off() -> None:
    state = {"job": {"features": {"funny_moments": False, "smart_clip_detection": True}}}
    assert should_run_funny(state) is False
    assert route_after_moment({**state, "status": "running"}) == "skip_funny"


def test_viral_on_by_default() -> None:
    state = {"job": {"features": {}}}
    assert should_run_viral(state) is True


def test_podcast_skip_when_flag_and_type_off() -> None:
    state = {
        "job": {
            "features": {"podcast_clips": False},
            "config": {"video_type": "Shorts"},
        },
        "status": "running",
    }
    assert should_run_podcast(state) is False
    assert route_after_smart_clip(state) == "skip_podcast"


def test_podcast_on_with_flag_or_video_type() -> None:
    flag_on = {
        "job": {
            "features": {"podcast_clips": True},
            "config": {"video_type": "Shorts"},
        },
        "status": "running",
    }
    assert should_run_podcast(flag_on) is True
    assert route_after_smart_clip(flag_on) == "podcast"
    type_on = {
        "job": {
            "features": {"podcast_clips": False},
            "config": {"video_type": "Podcast"},
        },
        "status": "running",
    }
    assert should_run_podcast(type_on) is True
    assert route_after_smart_clip(type_on) == "podcast"
    assert route_after_podcast({**type_on}) == "skip_research"


def test_research_skip_when_flag_and_not_script() -> None:
    state = {
        "job": {
            "features": {"research": False},
            "source_type": "upload",
            "config": {"video_type": "Shorts"},
        },
        "status": "running",
    }
    assert should_run_research(state) is False
    assert route_after_podcast(state) == "skip_research"


def test_research_on_with_flag_or_script() -> None:
    flag_on = {
        "job": {
            "features": {"research": True},
            "source_type": "upload",
        },
        "status": "running",
    }
    assert should_run_research(flag_on) is True
    assert route_after_podcast(flag_on) == "research"
    script_on = {
        "job": {
            "features": {"research": False},
            "source_type": "script",
        },
        "status": "running",
    }
    assert should_run_research(script_on) is True
    assert route_after_podcast(script_on) == "research"
    assert route_after_research(script_on) == "story"


def test_supervisor_crew_routes_after_research() -> None:
    on = {
        "job": {
            "features": {"supervisor_crew": True, "research": False},
            "source_type": "upload",
        },
        "status": "running",
    }
    from graph.routers import should_run_supervisor_crew

    assert should_run_supervisor_crew(on) is True
    assert route_after_research(on) == "supervisor"
    off = {
        "job": {
            "features": {"supervisor_crew": False},
            "source_type": "upload",
        },
        "status": "running",
    }
    assert should_run_supervisor_crew(off) is False
    assert route_after_research(off) == "story"


def test_voice_original_skips() -> None:
    state = {
        "job": {
            "features": {"voice": True},
            "config": {"voice": "Original Voice"},
        }
    }
    assert should_run_voice(state) is False


def test_music_no_music_skips() -> None:
    state = {
        "job": {
            "features": {"music": True},
            "config": {"music": "No Music"},
        }
    }
    assert should_run_music(state) is False


def test_avatar_no_avatar_skips() -> None:
    state = {
        "job": {
            "features": {"avatar": True},
            "config": {"avatar": "No Avatar"},
        }
    }
    assert should_run_avatar(state) is False


def test_avatar_route_after_voice() -> None:
    on = {
        "job": {
            "features": {"avatar": True},
            "config": {"avatar": "Teacher"},
        },
        "status": "running",
    }
    assert route_after_voice(on) == "avatar"
    off = {
        "job": {
            "features": {"avatar": False},
            "config": {"avatar": "Teacher"},
        },
        "status": "running",
    }
    assert route_after_voice(off) == "skip_avatar"


def test_brand_route_after_platform() -> None:
    on = {
        "job": {"features": {"brand": True, "seo": True}, "config": {"platform": "LinkedIn"}},
        "status": "running",
    }
    assert should_run_brand(on) is True
    assert route_after_platform(on) == "brand"
    off = {
        "job": {"features": {"brand": False, "seo": True}, "config": {"platform": "LinkedIn"}},
        "status": "running",
    }
    assert should_run_brand(off) is False
    assert route_after_platform(off) == "skip_brand"


def test_seo_route_after_brand() -> None:
    on = {
        "job": {"features": {"seo": True}, "config": {"platform": "LinkedIn"}},
        "status": "running",
    }
    assert should_run_seo(on) is True
    assert route_after_brand(on) == "seo"
    off = {
        "job": {"features": {"seo": False}, "config": {"platform": "LinkedIn"}},
        "status": "running",
    }
    assert should_run_seo(off) is False
    assert route_after_brand(off) == "skip_seo"


def test_trend_route_after_seo() -> None:
    on = {
        "job": {"features": {"trend": True}, "config": {"platform": "TikTok"}},
        "status": "running",
    }
    assert should_run_trend(on) is True
    assert route_after_seo(on) == "trend"
    off = {
        "job": {"features": {"trend": False}, "config": {"platform": "TikTok"}},
        "status": "running",
    }
    assert should_run_trend(off) is False
    assert route_after_seo(off) == "skip_trend"


def test_repurpose_route_after_trend() -> None:
    on = {
        "job": {"features": {"repurpose": True}, "config": {"platform": "TikTok"}},
        "status": "running",
    }
    assert should_run_repurpose(on) is True
    assert route_after_trend(on) == "repurpose"
    off = {
        "job": {"features": {"repurpose": False}, "config": {"platform": "TikTok"}},
        "status": "running",
    }
    assert should_run_repurpose(off) is False
    assert route_after_trend(off) == "skip_repurpose"


def test_calendar_route_after_repurpose() -> None:
    on = {
        "job": {
            "features": {"content_calendar": True, "thumbnail": True},
            "config": {"platform": "TikTok"},
        },
        "status": "running",
    }
    assert should_run_content_calendar(on) is True
    assert route_after_repurpose(on) == "content_calendar"
    off = {
        "job": {
            "features": {"content_calendar": False, "thumbnail": True},
            "config": {"platform": "TikTok"},
        },
        "status": "running",
    }
    assert should_run_content_calendar(off) is False
    assert route_after_repurpose(off) == "skip_calendar"


def test_thumbnail_route_after_calendar() -> None:
    on = {
        "job": {"features": {"thumbnail": True}, "config": {"platform": "TikTok"}},
        "status": "running",
    }
    assert should_run_thumbnail(on) is True
    assert route_after_calendar(on) == "thumbnail"
    off = {
        "job": {"features": {"thumbnail": False}, "config": {"platform": "TikTok"}},
        "status": "running",
    }
    assert should_run_thumbnail(off) is False
    assert route_after_calendar(off) == "skip_thumbnail"


def test_analytics_route_after_thumbnail() -> None:
    on = {
        "job": {"features": {"analytics": True}, "config": {"platform": "TikTok"}},
        "status": "running",
    }
    assert should_run_analytics(on) is True
    assert route_after_thumbnail(on) == "analytics"
    off = {
        "job": {"features": {"analytics": False}, "config": {"platform": "TikTok"}},
        "status": "running",
    }
    assert should_run_analytics(off) is False
    assert route_after_thumbnail(off) == "skip_analytics"


def test_storyboard_route_after_environment() -> None:
    on = {
        "job": {"features": {"storyboard": True}},
        "status": "running",
    }
    assert should_run_storyboard(on) is True
    assert route_after_environment(on) == "storyboard"
    off = {
        "job": {"features": {"storyboard": False}},
        "status": "running",
    }
    assert should_run_storyboard(off) is False
    assert route_after_environment(off) == "skip_storyboard"


def test_character_route_after_storyboard() -> None:
    on = {
        "job": {"features": {"character": True}},
        "status": "running",
    }
    assert should_run_character(on) is True
    assert route_after_storyboard(on) == "character"
    off = {
        "job": {"features": {"character": False}},
        "status": "running",
    }
    assert should_run_character(off) is False
    assert route_after_storyboard(off) == "skip_character"


def test_camera_route_after_character() -> None:
    on = {
        "job": {"features": {"camera": True}},
        "status": "running",
    }
    assert should_run_camera(on) is True
    assert route_after_character(on) == "camera"
    off = {
        "job": {"features": {"camera": False}},
        "status": "running",
    }
    assert should_run_camera(off) is False
    assert route_after_character(off) == "skip_camera"


def test_director_route_after_camera() -> None:
    on = {
        "job": {"features": {"director": True}},
        "status": "running",
    }
    assert should_run_director(on) is True
    assert route_after_camera(on) == "director"
    off = {
        "job": {"features": {"director": False}},
        "status": "running",
    }
    assert should_run_director(off) is False
    assert route_after_camera(off) == "skip_director"


def test_motion_graphics_route_after_director() -> None:
    on = {
        "job": {"features": {"motion_graphics": True}},
        "status": "running",
    }
    assert should_run_motion_graphics(on) is True
    assert route_after_director(on) == "motion_graphics"
    off = {
        "job": {"features": {"motion_graphics": False}},
        "status": "running",
    }
    assert should_run_motion_graphics(off) is False
    assert route_after_director(off) == "skip_motion_graphics"


def test_documentary_route_after_motion_graphics() -> None:
    on = {
        "job": {"features": {"documentary": True}},
        "status": "running",
    }
    assert should_run_documentary(on) is True
    assert route_after_motion_graphics(on) == "documentary"
    off = {
        "job": {"features": {"documentary": False}},
        "status": "running",
    }
    assert should_run_documentary(off) is False
    assert route_after_motion_graphics(off) == "skip_documentary"


def test_video_generation_route_after_documentary() -> None:
    on = {
        "job": {"features": {"video_generation": True}},
        "status": "running",
    }
    assert should_run_video_generation(on) is True
    assert route_after_documentary(on) == "video_generation"
    off = {
        "job": {"features": {"video_generation": False}},
        "status": "running",
    }
    assert should_run_video_generation(off) is False
    assert route_after_documentary(off) == "skip_video_generation"


def test_image_generation_route_after_video_generation() -> None:
    on = {
        "job": {"features": {"image_generation": True}},
        "status": "running",
    }
    assert should_run_image_generation(on) is True
    assert route_after_video_generation(on) == "image_generation"
    off = {
        "job": {"features": {"image_generation": False}},
        "status": "running",
    }
    assert should_run_image_generation(off) is False
    assert route_after_video_generation(off) == "skip_image_generation"


def test_broll_route() -> None:
    off = {"job": {"features": {"b_roll": False}}, "status": "running"}
    assert should_run_broll(off) is False
    assert route_after_image_generation(off) == "skip_broll"
    on = {"job": {"features": {"b_roll": True}}, "status": "running"}
    assert route_after_image_generation(on) == "b_roll"
