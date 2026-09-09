"""Optional local OCR fallback for screenshots when DOM extraction is unavailable."""
from __future__ import annotations

from pathlib import Path


class OcrUnavailable(RuntimeError):
    pass


class OcrReader:
    def read(self, image_path: Path) -> str:
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        try:
            import pytesseract
            from PIL import Image
        except ImportError as error:
            raise OcrUnavailable("Install pytesseract and Pillow to enable OCR fallback") from error
        try:
            return pytesseract.image_to_string(Image.open(image_path)).strip()
        except pytesseract.TesseractNotFoundError as error:
            raise OcrUnavailable("Install the local Tesseract executable to enable OCR fallback") from error
