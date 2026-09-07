"""Lightweight Streamlit CSS for the video creation studio."""

from __future__ import annotations

import streamlit as st

_CSS = """
<style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        max-width: 1100px;
    }
    h1, h2, h3 {
        letter-spacing: -0.02em;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px;
    }
    .ava-step-pending { color: #6b7280; }
    .ava-step-running { color: #2563eb; font-weight: 600; }
    .ava-step-completed { color: #059669; }
    .ava-step-failed { color: #dc2626; font-weight: 600; }
    .ava-progress-card {
        border: 1px solid rgba(0,0,0,0.08);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        background: linear-gradient(180deg, #fafbfc 0%, #f3f4f6 100%);
    }
</style>
"""


def apply_styles() -> None:
    """Inject studio CSS once per run."""
    st.markdown(_CSS, unsafe_allow_html=True)
