"""Tests for JSON sanitization helpers."""

from deepwiki_cli.shared.json_utils import extract_json_object, strip_markdown_fences


def test_strip_markdown_fences_removes_language_hint() -> None:
    """Ensure ```json code fences are stripped."""
    payload = """```json
{
  "foo": "bar"
}
```"""
    assert strip_markdown_fences(payload) == '{\n  "foo": "bar"\n}'


def test_strip_markdown_fences_leaves_plain_text() -> None:
    """Verify plain text is left untouched."""
    payload = "  {\"foo\": \"bar\"}  "
    assert strip_markdown_fences(payload) == payload.strip()


def test_extract_json_object_returns_inner_object() -> None:
    """Extract JSON object from a payload with commentary."""
    payload = "Here you go:\n```json\n{\n  \"foo\": \"bar\"\n}\n```\nThanks!"
    assert extract_json_object(payload) == '{\n  "foo": "bar"\n}'


def test_extract_json_object_handles_strings_without_braces() -> None:
    """If payload lacks braces, the stripped text should be returned."""
    payload = "No JSON present"
    assert extract_json_object(payload) == "No JSON present"
