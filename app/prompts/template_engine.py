"""Strict prompt-template rendering with useful errors for missing variables."""
from __future__ import annotations


def render_template(template: str, variables: dict[str, str]) -> str:
    try:
        return template.format(**variables)
    except KeyError as error:
        raise ValueError(f"Missing prompt template variable: {error.args[0]}") from error
