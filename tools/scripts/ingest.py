"""Script file ingestion — extract plain text from txt / md / docx / pdf uploads."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Union


def extract_script_text(source: Union[str, Path, bytes, io.IOBase]) -> str:
    """Extract readable script text from a file path, bytes, or file-like object.

    Supported formats: .txt, .md, .docx, .pdf
    Falls back to raw UTF-8 decode for unknown types.

    Args:
        source: A file path, raw bytes, or file-like object.

    Returns:
        Extracted plain text (stripped), or "" on failure.
    """
    # Normalise to bytes + extension hint
    raw: bytes = b""
    ext: str = ""

    if isinstance(source, (str, Path)):
        p = Path(source)
        ext = p.suffix.lower()
        try:
            raw = p.read_bytes()
        except OSError:
            return ""
    elif isinstance(source, (bytes, bytearray)):
        raw = bytes(source)
    elif hasattr(source, "read"):
        # file-like (e.g. Streamlit UploadedFile)
        name = getattr(source, "name", "") or ""
        ext = Path(name).suffix.lower()
        try:
            raw = source.read()
            if isinstance(raw, str):
                raw = raw.encode("utf-8")
        except Exception:  # noqa: BLE001
            return ""
    else:
        return ""

    if not raw:
        return ""

    if ext in (".txt", ".md", ""):
        return _decode(raw)

    if ext == ".docx":
        return _from_docx(raw)

    if ext == ".pdf":
        return _from_pdf(raw)

    # Unknown — try plain text
    return _decode(raw)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace").strip()


def _from_docx(raw: bytes) -> str:
    try:
        import docx  # python-docx
        doc = docx.Document(io.BytesIO(raw))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs).strip()
    except ImportError:
        return "[python-docx not installed — cannot parse .docx]"
    except Exception as exc:  # noqa: BLE001
        return f"[.docx parse error: {exc}]"


def _from_pdf(raw: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text.strip())
        return "\n\n".join(pages).strip()
    except ImportError:
        return "[pypdf not installed — cannot parse .pdf]"
    except Exception as exc:  # noqa: BLE001
        return f"[.pdf parse error: {exc}]"
