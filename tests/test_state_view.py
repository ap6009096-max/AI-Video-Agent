"""Tests for state projection helper."""

from __future__ import annotations

from graph.state_view import project_state_view


def test_project_state_view_flat_keys() -> None:
    state = {
        "job": {"job_id": "j1", "source_type": "script", "script_text": "hi"},
        "project": {"project_id": "p1", "source_type": "script"},
        "clips": {"clips": [{"id": 0}]},
        "stories": {"stories": []},
        "render_pack": {"plan": {"output_path": "", "skipped": True}},
        "quality_pack": {"report": {"passed": True, "skipped": True}},
        "export_pack": {
            "export_path": "manifest.json",
            "output_files": {"aliases": {}},
        },
        "steps": [],
        "error": None,
    }
    view = project_state_view(state)
    assert view["project_id"] == "p1"
    assert view["source_type"] == "script"
    assert view["selected_clips"]["clips"][0]["id"] == 0
    assert "output_files" in view
    assert "progress" in view
    assert "creator_os_stages" in view
    assert isinstance(view["creator_os_stages"], list)
    assert len(view["creator_os_stages"]) >= 8
