"""
Configuration management for DeepWiki CLI.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Default configuration directory
CONFIG_DIR = Path.home() / ".deepwiki"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Default configuration values
DEFAULT_CONFIG = {
    "default_provider": "google",
    "default_model": "gemini-2.0-flash-exp",
    "wiki_type": "comprehensive",
    "file_filters": {"excluded_dirs": [], "excluded_files": []},
}


def ensure_config_dir():
    """Ensure the configuration directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> Dict[str, Any]:
    """
    Load configuration from file.

    Returns:
        Dictionary with configuration values, or defaults if file doesn't exist.
    """
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            # Merge with defaults to ensure all keys exist
            merged = DEFAULT_CONFIG.copy()
            merged.update(config)
            return merged
    except Exception as e:
        logger.warning(f"Error loading config file: {e}. Using defaults.")
        return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]):
    """
    Save configuration to file.

    Args:
        config: Configuration dictionary to save.
    """
    ensure_config_dir()

    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        logger.info(f"Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Error saving config file: {e}")
        raise


def get_config_value(key: str, default: Any = None) -> Any:
    """
    Get a configuration value by key.

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


def set_config_value(key: str, value: Any):
    """
    Set a configuration value.

    Args:
        key: Configuration key (supports nested keys with dots)
        value: Value to set
    """
    config = load_config()

    # Support nested keys
    keys = key.split(".")
    target = config
    for k in keys[:-1]:
        if k not in target:
            target[k] = {}
        target = target[k]

    target[keys[-1]] = value
    save_config(config)


def get_provider_models() -> Dict[str, list]:
    """
    Get available models for each provider from api.config.

    Returns:
        Dictionary mapping provider names to lists of available models.
    """
    from api.config import configs

    provider_models = {}
    if "providers" in configs:
        for provider_id, provider_config in configs["providers"].items():
            if "models" in provider_config:
                provider_models[provider_id] = list(provider_config["models"].keys())

    return provider_models
