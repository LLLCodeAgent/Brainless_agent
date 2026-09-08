import asyncio
from pathlib import Path

import pytest

from app.extraction.clipboard_extractor import ClipboardExtractor
from app.extraction.fallback_extractor import ResponseFallbackExtractor
from app.extraction.response_extractor import ResponseValidationError


class CopyingProvider:
    def __init__(self) -> None:
        self.copied = False

    async def copy_latest_response(self) -> None:
        self.copied = True


class FakeOcr:
    def read(self, image_path: Path) -> str:
        return "OCR response"


def test_clipboard_fallback_uses_provider_copy_control() -> None:
    provider = CopyingProvider()
    extractor = ResponseFallbackExtractor(ClipboardExtractor(lambda: "Copied response"))
    assert asyncio.run(extractor.extract_from_clipboard(provider)) == "Copied response"
    assert provider.copied is True


def test_clipboard_fallback_rejects_empty_content() -> None:
    with pytest.raises(ResponseValidationError):
        ClipboardExtractor(lambda: " ").extract()


def test_ocr_fallback_validates_ocr_text() -> None:
    extractor = ResponseFallbackExtractor(ClipboardExtractor(lambda: "unused"), FakeOcr())
    assert extractor.extract_from_ocr(Path("evidence.png")) == "OCR response"
