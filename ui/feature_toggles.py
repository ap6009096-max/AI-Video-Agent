"""Feature toggle UI and Creator OS preset helpers."""

from __future__ import annotations

from typing import Any

import streamlit as st

from schemas.creator_os import CREATOR_CAPABILITY_PRESET, apply_creator_os_preset
from schemas.job import FeatureFlags
from schemas.moments import CATEGORY_FLAG_MAP
from ui.constants import FEATURE_TOGGLE_DEFS
from ui.session_state_utils import init_state

FIND_ALL_MOMENT_KEYS = frozenset(CATEGORY_FLAG_MAP.keys())

_TOGGLE_KEYS = [key for key, _label in FEATURE_TOGGLE_DEFS]
if len(_TOGGLE_KEYS) != len(set(_TOGGLE_KEYS)):
    dupes = sorted({k for k in _TOGGLE_KEYS if _TOGGLE_KEYS.count(k) > 1})
    raise ValueError(f"FEATURE_TOGGLE_DEFS has duplicate keys: {dupes}")


def merge_creator_os_preset(features: dict[str, Any] | None = None) -> dict[str, bool]:
    """Merge Creator OS capability preset onto FeatureFlags defaults."""
    return apply_creator_os_preset(features)


def render_feature_toggles() -> dict[str, bool]:
    """Render feature checkboxes; return FeatureFlags-compatible dict."""
    defaults = FeatureFlags().model_dump()
    values = dict(defaults)
    find_all = st.checkbox(
        "Find All Moments",
        value=False,
        help=(
            "When enabled, all moment-category checkboxes below are treated as ON "
            "(viral, funny, emotional, educational, controversy, story)."
        ),
    )
    st.caption(
        "Find All Moments forces every moment category ON for this run "
        "(checkboxes below stay locked ON while Find All is active)."
    )

    # Only allowed bulk write of feature_* keys: before any feature checkboxes exist.
    if st.button("Apply Creator OS preset", help="Enable Creator OS capability flags"):
        for key, enabled in CREATOR_CAPABILITY_PRESET.items():
            st.session_state[f"feature_{key}"] = bool(enabled)
        st.rerun()

    # Batch-init all feature_* keys before any feature checkbox widgets.
    for key, _label in FEATURE_TOGGLE_DEFS:
        session_key = f"feature_{key}"
        init_state(session_key, defaults.get(key, False))

    cols = st.columns(2)
    for i, (key, label) in enumerate(FEATURE_TOGGLE_DEFS):
        with cols[i % 2]:
            if find_all and key in FIND_ALL_MOMENT_KEYS:
                # Keyless display-only: never bind feature_* session keys in Find All.
                st.checkbox(label, value=True, disabled=True)
                values[key] = True
            else:
                values[key] = st.checkbox(label, key=f"feature_{key}")
    return values
