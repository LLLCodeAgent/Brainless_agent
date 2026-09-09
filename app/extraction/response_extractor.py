"""Provider-independent response validation before persistence."""
from __future__ import annotations


class ResponseValidationError(ValueError):
    pass


def validate_response(response: str) -> str:
    normalized = response.strip()
    if not normalized:
        raise ResponseValidationError("Provider returned an empty response")
    errors = ("something went wrong", "an error occurred", "try again later")
    if normalized.lower() in errors:
        raise ResponseValidationError("Provider returned an error message instead of a response")
    return normalized
