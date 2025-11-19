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

    # Change CWD to tmp_path to avoid Pydantic reading the real .env
    monkeypatch.chdir(tmp_path)

    original_load_dotenv = importlib.import_module("dotenv").load_dotenv
    
    def mock_load_dotenv(dotenv_path: Path | str | None = None, **kwargs) -> bool:
        # Only allow loading our test files
        if dotenv_path and ("custom.env" in str(dotenv_path) or "deepwiki-config" in str(dotenv_path)):
             return original_load_dotenv(dotenv_path, **kwargs)
        return False

    monkeypatch.setattr("deepwiki_cli.infrastructure.config.settings.load_dotenv", mock_load_dotenv)

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

    # Change CWD to tmp_path to avoid Pydantic reading the real .env
    monkeypatch.chdir(tmp_path)

    # Mock load_dotenv to prevent loading real .env files
    # We only want to test that the logic *attempts* to load the correct file
    # But since _load_env_files calls load_dotenv, we can't easily verify which file it loaded
    # without mocking load_dotenv.
    # However, the Config object reads from os.environ.
    # If we mock load_dotenv to simply set the env var we expect, we can verify the precedence.
    
    # Actually, a better approach is to ensure _load_env_files doesn't mess up our monkeypatch
    # by mocking it out or ensuring it doesn't find the real .env
    
    # Let's mock load_dotenv to do nothing, so it doesn't override our manual setup
    # But wait, the code RELIES on load_dotenv to load the file we just created!
    # So we should NOT mock it to do nothing.
    # The problem is it loads the REAL .env file too.
    
    # We need to prevent it from loading the project root .env
    # We can do this by mocking Path.cwd() or similar, but that's risky.
    # Or we can mock load_dotenv to only load the file we want.
    
    original_load_dotenv = importlib.import_module("dotenv").load_dotenv
    
    def mock_load_dotenv(dotenv_path: Path | str | None = None, **kwargs) -> bool:
        # Only allow loading our test files
        if dotenv_path and ("custom.env" in str(dotenv_path) or "deepwiki-config" in str(dotenv_path)):
             return original_load_dotenv(dotenv_path, **kwargs)
        return False

    monkeypatch.setattr("deepwiki_cli.infrastructure.config.settings.load_dotenv", mock_load_dotenv)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPWIKI_ENV_FILE", raising=False)
    monkeypatch.setenv("DEEPWIKI_CONFIG_DIR", str(config_dir))

    config_module = _reload_config_module()
    cfg = config_module.Config()
    assert cfg.openai_api_key == "config-dir-value"
