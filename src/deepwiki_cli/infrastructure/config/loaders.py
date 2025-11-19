"""JSON configuration file loaders."""

import json
import os
import re
from pathlib import Path
from typing import Any

from returns.result import Failure, Result, Success

# Import client classes for mapping
from deepwiki_cli.infrastructure.clients.ai.bedrock_client import BedrockClient
from deepwiki_cli.infrastructure.clients.ai.lmstudio_client import LMStudioClient
from deepwiki_cli.infrastructure.clients.ai.openai_client import OpenAIClient
from deepwiki_cli.infrastructure.clients.ai.openrouter_client import OpenRouterClient
from deepwiki_cli.infrastructure.config.settings import (
    CONFIG_DIR,
    get_client_classes,
    logger,
)


def replace_env_placeholders(
    config: dict[str, Any] | list[Any] | str | Any,
) -> dict[str, Any] | list[Any] | str | Any:
    """Recursively replace placeholders like "${ENV_VAR}" in string values.

    Replaces placeholders within a nested configuration structure (dicts, lists, strings)
    with environment variable values. Logs a warning if a placeholder is not found.

    Args:
        config: Configuration structure that may contain placeholders.

    Returns:
        Configuration structure with placeholders replaced by environment variable values.

    Example:
        >>> os.environ["TEST_VAR"] = "test_value"
        >>> replace_env_placeholders({"key": "${TEST_VAR}"})
        {'key': 'test_value'}
    """
    pattern = re.compile(r"\$\{([A-Z0-9_]+)\}")

    def replacer(match: re.Match[str]) -> str:
        env_var_name = match.group(1)
        original_placeholder = match.group(0)
        env_var_value = os.environ.get(env_var_name)
        if env_var_value is None:
            logger.warning(
                "Environment variable placeholder not found",
                operation="replace_env_placeholders",
                status="warning",
                placeholder=original_placeholder,
                env_var_name=env_var_name,
            )
            return original_placeholder
        return env_var_value

    if isinstance(config, dict):
        return {k: replace_env_placeholders(v) for k, v in config.items()}
    if isinstance(config, list):
        return [replace_env_placeholders(item) for item in config]
    if isinstance(config, str):
        return pattern.sub(replacer, config)
    # Handles numbers, booleans, None, etc.
    return config


def load_json_config(filename: str) -> Result[dict[str, Any], str]:
    """Load JSON configuration file with environment variable placeholder replacement.

    Args:
        filename: Name of the JSON configuration file to load.

    Returns:
        Result containing dictionary with loaded configuration on success,
        or error message on failure.

    Example:
        >>> result = load_json_config("generator.json")
        >>> config = result.unwrap() if result.is_successful() else {}
        >>> isinstance(config, dict)
        True
    """
    try:
        # If environment variable is set, use the directory specified by it
        if CONFIG_DIR:
            config_path = Path(CONFIG_DIR) / filename
        else:
            # Otherwise use default directory
            config_path = Path(__file__).parent / "files" / filename

        logger.info(
            "Loading configuration",
            operation="load_json_config",
            status="started",
            config_path=str(config_path),
        )

        if not config_path.exists():
            logger.warning(
                "Configuration file does not exist",
                operation="load_json_config",
                status="warning",
                config_path=str(config_path),
            )
            return Success({})

        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
            result = replace_env_placeholders(config)
            # Ensure result is a dict for the Success type
            if not isinstance(result, dict):
                result = {}
            logger.info(
                "Configuration loaded successfully",
                operation="load_json_config",
                status="success",
                config_path=str(config_path),
            )
            return Success(result)
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in configuration file {filename}: {e}"
        logger.exception(
            "Error loading configuration file",
            operation="load_json_config",
            status="error",
            filename=filename,
            error=error_msg,
        )
        return Failure(error_msg)
    except Exception as e:
        error_msg = f"Error loading configuration file {filename}: {e}"
        logger.exception(
            "Error loading configuration file",
            operation="load_json_config",
            status="error",
            filename=filename,
            error=error_msg,
        )
        return Failure(error_msg)


def load_generator_config() -> dict[str, Any]:
    """Load generator model configuration from JSON file.

    Returns:
        Dictionary containing generator configuration with model_client resolved
        for each provider. Returns empty dict on error.

    Example:
        >>> config = load_generator_config()
        >>> "providers" in config
        True
    """
    result = load_json_config("generator.json")
    generator_config = result.value_or({})

    # Add client classes to each provider
    if "providers" in generator_config:
        for provider_id, provider_config in generator_config["providers"].items():
            # Get client classes lazily
            client_classes = get_client_classes()

            # Try to set client class from client_class
            if provider_config.get("client_class") in client_classes:
                provider_config["model_client"] = client_classes[
                    provider_config["client_class"]
                ]
            # Fall back to default mapping based on provider_id
            elif provider_id in [
                "google",
                "openai",
                "openrouter",
                "lmstudio",
                "bedrock",
            ]:
                default_map = {
                    "google": client_classes.get("GoogleGenAIClient"),
                    "openai": OpenAIClient,
                    "openrouter": OpenRouterClient,
                    "lmstudio": LMStudioClient,
                    "bedrock": BedrockClient,
                }
                provider_config["model_client"] = default_map[provider_id]
            else:
                logger.warning(
                    "Unknown provider or client class",
                    operation="load_generator_config",
                    status="warning",
                    provider_id=provider_id,
                )

    return generator_config


def load_embedder_config() -> dict[str, Any]:
    """Load embedder configuration from JSON file.

    Returns:
        Dictionary containing embedder configuration with model_client resolved
        for each embedder type. Returns empty dict on error.

    Example:
        >>> config = load_embedder_config()
        >>> "embedder" in config or "embedder_lmstudio" in config
        True
    """
    result = load_json_config("embedder.json")
    embedder_config = result.value_or({})

    # Process client classes
    # Get client classes lazily
    client_classes = get_client_classes()

    for key in [
        "embedder_openai",
        "embedder_lmstudio",
        "embedder_openrouter",
    ]:
        if key in embedder_config and "client_class" in embedder_config[key]:
            class_name = embedder_config[key]["client_class"]
            if class_name in client_classes:
                embedder_config[key]["model_client"] = client_classes[class_name]

    return embedder_config


def load_repo_config() -> dict[str, Any]:
    """Load repository and file filters configuration from JSON file.

    Returns:
        Dictionary containing repository configuration including file filters.
        Returns empty dict on error.

    Example:
        >>> config = load_repo_config()
        >>> isinstance(config, dict)
        True
    """
    result = load_json_config("repo.json")
    return result.value_or({})
