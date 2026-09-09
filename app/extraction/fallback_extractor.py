"""Bounded response extraction fallbacks after normal DOM extraction is exhausted."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.extraction.clipboard_extractor import ClipboardExtractor
from app.extraction.response_extractor import validate_response


class OcrReader(Protocol):
    def read(self, image_path: Path) -> str: ...


class ResponseFallbackExtractor:
    def __init__(self, clipboard: ClipboardExtractor, ocr: OcrReader | None = None) -> None:
        self.clipboard = clipboard
        self.ocr = ocr

    async def extract_from_clipboard(self, provider) -> str:
        await provider.copy_latest_response()
        return self.clipboard.extract()

    def extract_from_ocr(self, screenshot_path: Path) -> str:
        if self.ocr is None:
            raise RuntimeError("OCR fallback is not configured")
        return validate_response(self.ocr.read(screenshot_path))
