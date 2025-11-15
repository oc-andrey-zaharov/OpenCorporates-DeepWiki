"""Tests for DeepWiki environment file discovery logic."""

from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

MODULE_NAME = "deepwiki_cli.infrastructure.config.settings"


@pytest.fixture(autouse=True)
def reset_config_module() -> Generator[None]:
    """Ensure each test works with a clean config module state."""
    if MODULE_NAME in sys.modules:
        del sys.modules[MODULE_NAME]
    try:
        yield
    finally:
        if MODULE_NAME in sys.modules:
            del sys.modules[MODULE_NAME]


def _reload_config_module() -> object:
    """Reload the config module so that env discovery logic runs again."""
    return importlib.import_module(MODULE_NAME)


def test_env_file_variable_takes_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure DEEPWIKI_ENV_FILE is honored even when CWD lacks .env."""
    env_file = tmp_path / "custom.env"
    env_file.write_text("OPENAI_API_KEY=test-from-env\n", encoding="utf-8")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DEEPWIKI_ENV_FILE", str(env_file))
    config_module = _reload_config_module()

    cfg = config_module.Config()
    assert cfg.openai_api_key == "test-from-env"


def test_config_dir_env_supports_dotenv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify DEEPWIKI_CONFIG_DIR/.env is loaded before falling back to defaults."""
    config_dir = tmp_path / "deepwiki-config"
    config_dir.mkdir()
    (config_dir / ".env").write_text(
        "OPENAI_API_KEY=config-dir-value\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPWIKI_ENV_FILE", raising=False)
    monkeypatch.setenv("DEEPWIKI_CONFIG_DIR", str(config_dir))

    config_module = _reload_config_module()
    cfg = config_module.Config()
    assert cfg.openai_api_key == "config-dir-value"
