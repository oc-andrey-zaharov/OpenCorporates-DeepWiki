"""High-level helpers for selecting serialization formats."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, MutableMapping, Sequence, TypeVar

from pydantic import BaseModel

from deepwiki_cli.infrastructure.formats.json_compact import to_compact_json
from deepwiki_cli.infrastructure.formats.toon_adapter import ToonAdapter

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class FormatPreference(str, Enum):
    """Available serialization targets."""

    JSON = "json"
    JSON_COMPACT = "json-compact"
    TOON = "toon"


@dataclass(slots=True)
class FormatConversionResult:
    """Result container describing the serialized payload."""

    content: str
    format: FormatPreference


def _model_to_dict(data: BaseModel | Mapping[str, Any] | Sequence[Any] | Any) -> Any:
    """Normalize BaseModel instances to plain dictionaries."""
    if isinstance(data, BaseModel):
        return data.model_dump(mode="json", by_alias=True, exclude_none=True)
    if isinstance(data, MutableMapping):
        return dict(data)
    return data


class FormatConverter:
    """Convert prompt payloads between JSON, compact JSON, and TOON."""

    def __init__(
        self,
        *,
        toon_adapter: ToonAdapter | None = None,
        default_preference: FormatPreference = FormatPreference.JSON_COMPACT,
    ) -> None:
        self._toon_adapter = toon_adapter
        self._default_preference = default_preference

    def serialize(
        self,
        payload: BaseModel | Mapping[str, Any] | Sequence[Any] | Any,
        *,
        preference: FormatPreference | None = None,
    ) -> FormatConversionResult:
        """Serialize data according to the requested preference with fallbacks."""
        pref = preference or self._default_preference
        normalized = _model_to_dict(payload)

        if pref == FormatPreference.TOON and self._toon_adapter:
            result = self._toon_adapter.safe_convert_to_toon(normalized)
            if result:
                return FormatConversionResult(
                    content=result,
                    format=FormatPreference.TOON,
                )
            log.debug(
                "TOON conversion failed, falling back to compact JSON",
                extra={"format_preference": pref},
            )
            pref = FormatPreference.JSON_COMPACT

        if pref == FormatPreference.JSON_COMPACT:
            return FormatConversionResult(
                content=to_compact_json(normalized),
                format=FormatPreference.JSON_COMPACT,
            )

        return FormatConversionResult(
            content=json.dumps(normalized, ensure_ascii=False, indent=2),
            format=FormatPreference.JSON,
        )

    def deserialize(
        self,
        payload: str,
        *,
        schema: type[T],
        input_format: FormatPreference | None = None,
    ) -> T:
        """Deserialize model responses using the configured adapters."""
        fmt = input_format or self._default_preference
        if fmt == FormatPreference.TOON and self._toon_adapter:
            maybe_json = self._toon_adapter.safe_convert_from_toon(payload)
            if maybe_json is not None:
                return schema.model_validate(maybe_json)
            log.debug(
                "TOON payload could not be converted, assuming JSON fallback",
                extra={"format_preference": fmt},
            )

        if fmt == FormatPreference.JSON_COMPACT:
            return schema.model_validate_json(payload)

        # Default: assume well-formatted JSON
        return schema.model_validate_json(payload)
