"""Fallback wrapper for structlog.

This module attempts to import the real ``structlog`` package. If it is not
available (common in constrained CI environments), we provide a very small
shim that exposes the attributes used within DeepWiki so modules can still be
imported and tests can run.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

try:
    import structlog as _structlog
    from structlog.contextvars import bind_contextvars, clear_contextvars
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal envs

    def bind_contextvars(**_kwargs):
        return None

    def clear_contextvars():
        return None

    def _event_passthrough(_logger=None, _name=None, event_dict=None):
        return event_dict or {}

    processors = SimpleNamespace(
        add_log_level=_event_passthrough,
        TimeStamper=lambda **_kwargs: _event_passthrough,
        StackInfoRenderer=lambda: _event_passthrough,
        format_exc_info=_event_passthrough,
        JSONRenderer=lambda: _event_passthrough,
    )

    stdlib = SimpleNamespace(
        LoggerFactory=lambda: logging.getLogger,
        BoundLogger=logging.Logger,
    )

    class _StructLogShim:
        contextvars = SimpleNamespace(merge_contextvars=_event_passthrough)
        processors = processors
        stdlib = stdlib

        def get_logger(self, name: str | None = None):
            return logging.getLogger(name or "deepwiki")

        def configure(self, **_kwargs):
            return None

    structlog = _StructLogShim()
else:  # pragma: no cover - exercised when structlog is installed
    structlog = _structlog

__all__ = ["structlog", "bind_contextvars", "clear_contextvars"]
