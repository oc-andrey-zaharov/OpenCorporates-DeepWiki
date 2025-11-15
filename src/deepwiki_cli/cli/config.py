"""Configuration management for DeepWiki CLI."""

import copy
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default configuration directory
CONFIG_DIR = Path.home() / ".deepwiki"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Default configuration values
DEFAULT_CONFIG = {
    "default_provider": "google",
    "default_model": "gemini-2.0-flash-exp",
    "wiki_type": "comprehensive",
    "file_filters": {
        "excluded_dirs": [],
        "excluded_files": [],
        "included_dirs": [],
        "included_files": [],
    },
    "wiki_workspace": "docs/wiki",
    "export": {
        "layout": "single",  # or "multi"
        "watch": False,
    },
}


def ensure_config_dir() -> None:
    """Ensure the configuration directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries recursively.

    Args:
        base: Base dictionary (defaults)
        override: Dictionary with values to override

    Returns:
        New dictionary with merged values. Nested dicts are merged recursively.
    """
    result = copy.deepcopy(base)

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Both are dicts, merge recursively
            result[key] = _deep_merge(result[key], value)
        else:
            # Override with new value
            result[key] = value

    return result


def load_config() -> dict[str, Any]:
    """Load configuration from file.

    Returns:
        Dictionary with configuration values, or defaults if file doesn't exist.
    """
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
            # Deep merge with defaults to ensure all keys exist
            return _deep_merge(DEFAULT_CONFIG, config)
    except Exception as e:
        logger.warning(f"Error loading config file: {e}. Using defaults.")
        return DEFAULT_CONFIG.copy()


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to file.

    Args:
        config: Configuration dictionary to save.
    """
    ensure_config_dir()

    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        logger.info(f"Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        logger.exception(f"Error saving config file: {e}")
        raise


def get_config_value(key: str, default: Any = None) -> Any:
    """Get a configuration value by key.

    Args:
        key: Configuration key (supports nested keys with dots, e.g., 'file_filters.excluded_dirs')
        default: Default value if key doesn't exist

    Returns:
        Configuration value or default.
    """
    config = load_config()

    # Support nested keys
    keys = key.split(".")
    value = config
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default

    return value


def set_config_value(key: str, value: Any) -> None:
    """Set a configuration value.

    Args:
        key: Configuration key (supports nested keys with dots)
        value: Value to set

    Raises:
        TypeError: If an intermediate key exists but is not a dict
    """
    config = load_config()

    # Support nested keys
    keys = key.split(".")
    target = config
    path_parts = []

    for k in keys[:-1]:
        path_parts.append(k)
        if k not in target:
            # Create empty dict for missing intermediate key
            target[k] = {}
        elif not isinstance(target[k], dict):
            # Intermediate key exists but is not a dict - config is malformed
            path = ".".join(path_parts)
            raise TypeError(
                f"Configuration key '{path}' exists but is not a dictionary. "
                f"Cannot set nested key '{key}'. Current value type: {type(target[k]).__name__}",
            )
        target = target[k]

    target[keys[-1]] = value
    save_config(config)


def get_provider_models() -> dict[str, list]:
    """Get available models for each provider from deepwiki_cli.config.

    Returns:
        Dictionary mapping provider names to lists of available models.
    """
    from deepwiki_cli.config import configs

    provider_models = {}
    if "providers" in configs:
        for provider_id, provider_config in configs["providers"].items():
            if "models" in provider_config:
                provider_models[provider_id] = list(provider_config["models"].keys())

    return provider_models
