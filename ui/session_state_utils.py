"""Safe Streamlit session_state helpers."""

from __future__ import annotations

from typing import Any

import streamlit as st


def init_state(key: str, default: Any) -> None:
    """Initialize a session_state key only if missing (before widget creation)."""
    if key not in st.session_state:
        st.session_state[key] = default
