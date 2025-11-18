"""Tests for format conversion helpers."""

from __future__ import annotations

from deepwiki_cli.domain.schemas import WikiStructurePageSchema, WikiStructureSchema
from deepwiki_cli.infrastructure.formats import (
    FormatConverter,
    FormatPreference,
    ToonAdapter,
    to_compact_json,
)


def test_to_compact_json_minifies_payload() -> None:
    """Whitespace should be removed from compact JSON."""
    payload = {"a": 1, "nested": {"b": 2}}
    compact = to_compact_json(payload)
    assert compact == '{"a":1,"nested":{"b":2}}'


def test_format_converter_serialize_deserialize_roundtrip() -> None:
    """FormatConverter should round-trip structured payloads."""
    converter = FormatConverter(toon_adapter=None)
    schema = WikiStructureSchema(
        title="Demo",
        description="Sample wiki",
        pages=[
            WikiStructurePageSchema(
                page_id="p1",
                title="Intro",
                summary="Summary",
                importance="medium",
                relevant_files=["README.md"],
                related_page_ids=[],
                diagram_suggestions=[],
            ),
        ],
    )

    result = converter.serialize(schema)
    assert result.format == FormatPreference.JSON_COMPACT
    parsed = converter.deserialize(result.content, schema=WikiStructureSchema)
    assert parsed.title == "Demo"


def test_toon_adapter_fallback_parsing() -> None:
    """TOON adapter should fall back to JSON parsing when CLI unavailable."""
    adapter = ToonAdapter(cli_path=None, enabled=False)
    parsed = adapter.safe_convert_from_toon('{"demo": true}')
    assert parsed == {"demo": True}
