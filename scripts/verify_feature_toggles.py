"""Static checks for feature toggle session_state hardening."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FEATURE_TOGGLES = ROOT / "ui" / "feature_toggles.py"
SESSION_UTILS = ROOT / "ui" / "session_state_utils.py"


def _fail(msg: str) -> None:
    raise AssertionError(msg)


def main() -> None:
    assert SESSION_UTILS.is_file(), "ui/session_state_utils.py missing"
    utils_src = SESSION_UTILS.read_text(encoding="utf-8")
    assert "def init_state(" in utils_src, "init_state helper missing"

    src = FEATURE_TOGGLES.read_text(encoding="utf-8")
    assert "from ui.session_state_utils import init_state" in src
    assert "init_state(session_key" in src or 'init_state(f"feature_' in src or "init_state(" in src

    # Find All must use keyless display-only checkboxes.
    assert "Keyless display-only" in src or "no widget key" in src.lower() or "Display-only" in src
    assert "disabled=True" in src
    assert 'st.session_state[f"feature_{key}"] = True' not in src

    # Unique FEATURE_TOGGLE_DEFS keys (runtime assert + static import check).
    assert "FEATURE_TOGGLE_DEFS has duplicate keys" in src
    from ui.constants import FEATURE_TOGGLE_DEFS

    keys = [k for k, _ in FEATURE_TOGGLE_DEFS]
    if len(keys) != len(set(keys)):
        _fail(f"FEATURE_TOGGLE_DEFS duplicate keys: {keys}")

    # No session_state assignment after the checkbox loop in render_feature_toggles.
    tree = ast.parse(src)
    render_fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "render_feature_toggles":
            render_fn = node
            break
    assert render_fn is not None, "render_feature_toggles not found"

    # Locate the for-loop that creates feature checkboxes (enumerate FEATURE_TOGGLE_DEFS).
    checkbox_loop: ast.For | None = None
    for node in ast.walk(render_fn):
        if not isinstance(node, ast.For):
            continue
        # for i, (key, label) in enumerate(FEATURE_TOGGLE_DEFS)
        if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name):
            if node.iter.func.id == "enumerate":
                checkbox_loop = node
                break
    assert checkbox_loop is not None, "feature checkbox loop not found"

    loop_end = checkbox_loop.end_lineno or checkbox_loop.lineno
    after_loop = src.splitlines()[loop_end:]
    after_text = "\n".join(after_loop)
    # Reject any st.session_state[...] = after the checkbox loop.
    if re.search(r"st\.session_state\[.+\]\s*=", after_text):
        _fail("Found st.session_state[...] = after the feature checkbox loop")

    # Preset + rerun may still assign feature_* before widgets; that is OK.
    assert "Apply Creator OS preset" in src
    assert "st.rerun()" in src
    assert "apply_creator_os_preset" in src

    from ui.feature_toggles import merge_creator_os_preset

    assert merge_creator_os_preset()
    # Importing the module runs the unique-key guard at module load.
    import ui.feature_toggles  # noqa: F401

    print("feature_toggles verification OK")


if __name__ == "__main__":
    main()
