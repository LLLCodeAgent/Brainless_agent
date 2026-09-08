"""Clipboard read fallback; never reads or stores passwords."""
from __future__ import annotations

def read_text() -> str:
    import pyperclip
    return str(pyperclip.paste())
