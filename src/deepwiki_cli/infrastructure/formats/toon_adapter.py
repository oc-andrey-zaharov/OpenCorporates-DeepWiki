"""Wrapper around the optional TOON CLI.

The adapter orchestrates the hand-off between JSON payloads and TOON's compact
tabular encoding. The CLI is not bundled with DeepWiki; instead we detect its
availability and fall back to JSON-compact without raising errors.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from deepwiki_cli.infrastructure.formats.json_compact import to_compact_json

log = logging.getLogger(__name__)


class ToonAdapterError(RuntimeError):
    """Raised when TOON conversions fail after retry/fallback."""


class ToonAdapter:
    """Thin wrapper around the TOON CLI."""

    def __init__(
        self,
        cli_path: str | Path | None,
        *,
        enabled: bool = False,
        timeout: float = 30.0,
    ) -> None:
        self._cli_path = Path(cli_path).expanduser() if cli_path else None
        self._enabled = enabled
        self._timeout = timeout

    @property
    def cli_path(self) -> Path | None:
        """Return the resolved CLI path when configured."""
        return self._cli_path

    def is_available(self) -> bool:
        """Check whether TOON CLI is usable."""
        if not self._enabled or not self._cli_path:
            return False
        return bool(shutil.which(str(self._cli_path)))

    def safe_convert_to_toon(self, payload: dict[str, Any]) -> str | None:
        """Best-effort TOON conversion with JSON fallback."""
        if not self.is_available():
            return None
        try:
            return self._convert(payload, to_toon=True)
        except ToonAdapterError:
            return None

    def safe_convert_from_toon(self, payload: str) -> dict[str, Any] | None:
        """Best-effort conversion from TOON back to JSON."""
        if not self.is_available():
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return None
        try:
            converted = self._convert(payload, to_toon=False)
        except ToonAdapterError:
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return None
        if isinstance(converted, str):
            try:
                return json.loads(converted)
            except json.JSONDecodeError:
                return None
        return converted if isinstance(converted, dict) else None

    def _convert(self, payload: Any, *, to_toon: bool) -> str:
        """Call the CLI in encode (JSON->TOON) or decode (TOON->JSON) mode."""
        if not self._cli_path:
            raise ToonAdapterError("TOON CLI path is not configured")
        command = [str(self._cli_path), "--mode", "encode" if to_toon else "decode"]
        try:
            serialized = (
                to_compact_json(payload) if not isinstance(payload, str) else payload
            )
            proc = subprocess.run(
                command,
                input=serialized.encode(),
                capture_output=True,
                timeout=self._timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover
            raise ToonAdapterError(f"TOON invocation failed: {exc}") from exc

        if proc.returncode != 0:
            log.warning(
                "TOON CLI exited with non-zero status",
                extra={
                    "returncode": proc.returncode,
                    "stdout": proc.stdout.decode(errors="ignore"),
                    "stderr": proc.stderr.decode(errors="ignore"),
                },
            )
            raise ToonAdapterError("TOON CLI reported an error")
        return proc.stdout.decode()
