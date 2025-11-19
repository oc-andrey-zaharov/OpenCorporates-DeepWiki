"""Utilities for working with loosely formatted JSON payloads."""

from __future__ import annotations


def strip_markdown_fences(raw_payload: str) -> str:
    """Remove leading/trailing markdown code fences from a payload.

    Args:
        raw_payload: Text that may include ``` fences or ```json annotations.

    Returns:
        Payload without surrounding fences. If no fences are detected, the
        original text (stripped of surrounding whitespace) is returned.
    """
    stripped = raw_payload.strip()
    if not stripped.startswith("```"):
        return stripped

    first_newline = stripped.find("\n")
    if first_newline != -1:
        stripped = stripped[first_newline + 1 :]
    stripped = stripped.strip()
    if stripped.endswith("```"):
        stripped = stripped[: stripped.rfind("```")].strip()
    return stripped


def extract_json_object(raw_payload: str) -> str:
    """Return the most likely JSON object embedded within the payload.

    Args:
        raw_payload: Text that should contain a JSON object but may include
            markdown fences or leading/trailing commentary.

    Returns:
        String slice that looks like a JSON object. If no curly braces are
        detected, the stripped payload is returned unchanged.
    """
    stripped = strip_markdown_fences(raw_payload)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or start > end:
        return stripped
    return stripped[start : end + 1]


__all__ = ["extract_json_object", "strip_markdown_fences"]
