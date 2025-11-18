"""Tests for wiki structure generation retry behaviour."""

from __future__ import annotations

import pytest

from deepwiki_cli.cli.commands.generate import generate_wiki_structure


class StubContext:
    """Minimal WikiGenerationContext stub yielding predefined payloads."""

    def __init__(self, payloads: list[list[str]]) -> None:
        self.payloads = payloads
        self.calls = 0

    def stream_completion(self, *args, **kwargs):  # noqa: ANN003, D401 - test stub
        index = min(self.calls, len(self.payloads) - 1)
        payload = self.payloads[index]
        self.calls += 1

        def _generator():
            for chunk in payload:
                if chunk == "__RAISE__":
                    raise RuntimeError("simulated streaming failure")
                yield chunk

        return _generator()


VALID_XML = """
<wiki_structure>
  <title>Test Wiki</title>
  <description>Example description</description>
  <pages>
    <page id="page-1">
      <title>Overview</title>
      <importance>high</importance>
      <relevant_files>
        <file_path>README.md</file_path>
      </relevant_files>
      <related_pages />
    </page>
  </pages>
</wiki_structure>
""".strip()


def _run_generate_structure(context: StubContext) -> object | None:
    return generate_wiki_structure(
        repo_url="file:///tmp/repo",
        repo_type="local",
        file_tree="README.md\nsrc/main.py",
        readme="# Example",
        provider="google",
        model="gemini-test",
        is_comprehensive=False,
        generation_context=context,
    )


def test_generate_structure_retries_after_stream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI should retry when the provider aborts mid-stream."""
    context = StubContext(
        [
            ["<wiki_structure>", "__RAISE__"],
            [VALID_XML],
        ],
    )
    monkeypatch.setattr(
        "deepwiki_cli.cli.commands.generate.time.sleep",
        lambda *_args, **_kwargs: None,
    )
    structure = _run_generate_structure(context)
    assert structure is not None
    assert structure.title == "Test Wiki"
    assert context.calls == 2


def test_generate_structure_returns_none_after_exhausting_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """After repeated failures the function should give up gracefully."""
    context = StubContext([["plain text"], ["still bad"], ["no xml here"]])
    monkeypatch.setattr(
        "deepwiki_cli.cli.commands.generate.time.sleep",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "deepwiki_cli.cli.commands.generate._dump_failed_structure_response",
        lambda _payload: None,
    )
    structure = _run_generate_structure(context)
    assert structure is None
    assert context.calls == 3
