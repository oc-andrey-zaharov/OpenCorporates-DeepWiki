"""Tests for the OpenRouterClient batching safeguards."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from unittest.mock import MagicMock

import pytest
from adalflow.core.types import ModelType
from requests import Response
from requests.exceptions import RequestException

from deepwiki_cli.infrastructure.clients.ai.openrouter_client import OpenRouterClient


def _build_response(payload_size: int) -> Response:
    """Create a mock response payload with predictable embedding data."""
    response = MagicMock(spec=Response)
    response.json.return_value = {
        "data": [
            {"embedding": [float(idx)], "index": idx} for idx in range(payload_size)
        ],
        "model": "mistralai/codestral-embed-2505",
        "usage": {"prompt_tokens": payload_size, "total_tokens": payload_size},
    }
    return response


def test_openrouter_client_chunks_large_batches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure large batches get split before calling the API."""
    client = OpenRouterClient()
    client.max_embed_batch_size = 2
    seen_inputs: list[Sequence[str]] = []

    def fake_call(api_kwargs: dict) -> Response:
        seen_inputs.append(tuple(api_kwargs["input"]))
        return _build_response(len(api_kwargs["input"]))

    monkeypatch.setattr(client, "_call_embeddings", fake_call)

    api_kwargs = {
        "input": ["first", "second", "third"],
        "model": "mistralai/codestral-embed-2505",
    }
    response = client.call(api_kwargs, ModelType.EMBEDDER)

    assert seen_inputs == [("first", "second"), ("third",)]
    assert isinstance(response, dict)
    assert len(response["data"]) == 3


def test_openrouter_client_sequential_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify provider errors trigger sequential retries."""
    client = OpenRouterClient()
    client.max_embed_batch_size = 5
    successful_calls: list[list[str]] = []

    def failing_call(api_kwargs: dict) -> Response:
        inputs = api_kwargs["input"]
        if len(inputs) > 1:
            raise RequestException("Provider error: No successful provider responses.")
        successful_calls.append(list(inputs))
        return _build_response(1)

    monkeypatch.setattr(client, "_call_embeddings", failing_call)

    api_kwargs = {
        "input": ["alpha", "beta"],
        "model": "mistralai/codestral-embed-2505",
    }
    response = client.call(api_kwargs, ModelType.EMBEDDER)

    assert successful_calls == [["alpha"], ["beta"]]
    assert isinstance(response, dict)
    assert len(response["data"]) == 2
