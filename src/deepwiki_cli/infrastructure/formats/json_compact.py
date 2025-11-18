"""Utilities for working with compact JSON payloads.

The functions here intentionally avoid third-party dependencies so they can be
used from both the domain layer (via ``model_dump_json``) and infrastructure
components (model clients, adapters, etc.).
"""

from __future__ import annotations

import json
from typing import Any


def to_compact_json(data: Any, *, sort_keys: bool = False) -> str:
    """Return a minified JSON string using separators without extra whitespace."""
    return json.dumps(
        data,
        separators=(",", ":"),
        sort_keys=sort_keys,
        ensure_ascii=False,
    )


def from_compact_json(payload: str) -> Any:
    """Deserialize compact JSON content back into Python structures."""
    return json.loads(payload)
