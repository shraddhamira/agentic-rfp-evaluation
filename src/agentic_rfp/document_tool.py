"""Extract readable text from proposal PDFs while preserving page boundaries."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfReader


def extract_pdf_text(source: bytes | bytearray | str | Path) -> dict[str, Any]:
    """Extract page text from PDF bytes or a filesystem path.

    Returns page-aware text and warnings for pages with no extractable text. The
    original PDF is not written or retained by this tool.
    """
    stream = BytesIO(source) if isinstance(source, (bytes, bytearray)) else str(source)
    try:
        reader = PdfReader(stream)
        if reader.is_encrypted:
            try:
                unlocked = reader.decrypt("")
            except Exception as exc:  # pypdf may raise for unsupported encryption.
                raise ValueError("The PDF is encrypted and could not be opened with an empty password.") from exc
            if not unlocked:
                raise ValueError("The PDF is password-protected and cannot be evaluated.")
        pages: list[dict[str, Any]] = []
        warnings: list[str] = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if not text:
                warnings.append(f"Page {index} has no extractable text; OCR is not configured.")
            pages.append({"page_number": index, "text": text})
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Could not read the uploaded PDF: {exc}") from exc

    combined = "\n\n".join(
        f"[Page {page['page_number']}]\n{page['text']}" for page in pages if page["text"]
    )
    if not combined:
        raise ValueError("The PDF contains no extractable text.")
    return {"text": combined, "pages": pages, "warnings": warnings}
