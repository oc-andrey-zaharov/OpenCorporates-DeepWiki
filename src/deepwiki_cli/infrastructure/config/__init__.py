"""Configuration management for DeepWiki CLI.

This module provides a unified interface for accessing configuration from
environment variables and JSON files.
"""

from typing import Any

from deepwiki_cli.infrastructure.config.defaults import (
    DEFAULT_EXCLUDED_DIRS,
    DEFAULT_EXCLUDED_FILES,
)
from deepwiki_cli.infrastructure.config.loaders import (
    load_embedder_config,
    load_generator_config,
    load_json_config,
    load_repo_config,
)
from deepwiki_cli.infrastructure.config.settings import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_ROLE_ARN,
    AWS_SECRET_ACCESS_KEY,
    CLIENT_CLASSES,
    CONFIG_DIR,
    GITHUB_TOKEN,
    GOOGLE_API_KEY,
    OPENAI_API_KEY,
    OPENROUTER_API_KEY,
    Config,
    _config_instance,
    _refresh_config,
)

# Initialize empty configuration
configs: dict[str, Any] = {}

# Load all configuration files
generator_config = load_generator_config()
embedder_config = load_embedder_config()
repo_config = load_repo_config()

# Update configuration
if generator_config:
    configs["default_provider"] = generator_config.get("default_provider", "google")
    configs["providers"] = generator_config.get("providers", {})

# Update embedder configuration
if embedder_config:
    for key in [
        "embedder_openai",
        "embedder_lmstudio",
        "embedder_openrouter",
        "retriever",
        "text_splitter",
    ]:
        if key in embedder_config:
            configs[key] = embedder_config[key]
    # Backward compatibility: map embedder_openai to embedder
    if "embedder_openai" in embedder_config:
        configs["embedder"] = embedder_config["embedder_openai"]

# Update repository configuration
if repo_config:
    for key in ["file_filters", "repository"]:
        if key in repo_config:
            configs[key] = repo_config[key]

# Language is hardcoded to English
configs["lang_config"] = {"supported_languages": {"en": "English"}, "default": "en"}


def get_embedder_config() -> dict[str, Any]:
    """Get the current embedder configuration based on DEEPWIKI_EMBEDDER_TYPE.

    Returns:
        Dictionary containing the embedder configuration with model_client resolved.

    Example:
        >>> config = get_embedder_config()
        >>> isinstance(config, dict)
        True
    """
    from typing import cast

    # Read from config instance to get current value (supports module reload)
    embedder_type = _config_instance[0].embedder_type.lower()
    if embedder_type == "lmstudio" and "embedder_lmstudio" in configs:
        return cast("dict[str, Any]", configs.get("embedder_lmstudio", {}))
    if embedder_type == "openrouter" and "embedder_openrouter" in configs:
        return cast("dict[str, Any]", configs.get("embedder_openrouter", {}))
    if embedder_type == "openai" and "embedder_openai" in configs:
        return cast("dict[str, Any]", configs.get("embedder_openai", {}))
    return cast("dict[str, Any]", configs.get("embedder", {}))


def is_lmstudio_embedder() -> bool:
    """Check if the current embedder configuration uses LMStudioClient.

    Returns:
        bool: True if using LMStudioClient, False otherwise
    """
    embedder_config = get_embedder_config()
    if not embedder_config:
        return False

    # First check client_class string (more reliable)
    client_class = embedder_config.get("client_class", "")
    if client_class == "LMStudioClient":
        return True

    # Fallback: check if model_client is LMStudioClient
    model_client = embedder_config.get("model_client")
    if model_client:
        # Safely access __name__ attribute (handles MagicMock and other cases)
        client_name = getattr(model_client, "__name__", None)
        return client_name == "LMStudioClient"

    return False


def is_openrouter_embedder() -> bool:
    """Check if the current embedder configuration uses OpenRouterClient.

    Returns:
        bool: True if using OpenRouterClient, False otherwise.
    """
    embedder_config = get_embedder_config()
    if not embedder_config:
        return False

    client_class = embedder_config.get("client_class", "")
    if client_class == "OpenRouterClient":
        return True

    model_client = embedder_config.get("model_client")
    if model_client:
        client_name = getattr(model_client, "__name__", None)
        return client_name == "OpenRouterClient"

    return False


def get_embedder_type() -> str:
    """Get the current embedder type based on configuration.

    Returns:
        str: 'lmstudio', 'openrouter', or 'openai' (default)
    """
    # Read from config instance to get current value (supports module reload)
    current_type = _config_instance[0].embedder_type.lower()
    # Prioritize the explicit embedder_type from config over embedder detection
    if current_type == "lmstudio":
        return "lmstudio"
    if current_type == "openai":
        return "openai"
    if current_type == "openrouter":
        return "openrouter"
    # Fallback to embedder detection if type is not explicitly set
    if is_lmstudio_embedder():
        return "lmstudio"
    if is_openrouter_embedder():
        return "openrouter"
    return "openai"


def get_model_config(
    provider: str = "google",
    model: str | None = None,
) -> dict[str, Any]:
    """Get configuration for the specified provider and model.

    Args:
        provider: Model provider ('google', 'openai', 'openrouter', 'lmstudio', 'bedrock').
        model: Model name, or None to use default model.

    Returns:
        Dictionary containing model_client, model and other parameters.

    Raises:
        ValueError: If provider configuration is not loaded, provider not found,
            model client not specified, or no default model specified.

    Example:
        >>> config = get_model_config("google", "gemini-pro")
        >>> "model_client" in config
        True
        >>> "model_kwargs" in config
        True
    """
    # Get provider configuration
    if "providers" not in configs:
        raise ValueError("Provider configuration not loaded")

    provider_config = configs["providers"].get(provider)
    if not provider_config:
        raise ValueError(f"Configuration for provider '{provider}' not found")

    model_client = provider_config.get("model_client")
    if not model_client:
        raise ValueError(f"Model client not specified for provider '{provider}'")

    # If model not provided, use default model for the provider
    if not model:
        model = provider_config.get("default_model")
        if not model:
            raise ValueError(f"No default model specified for provider '{provider}'")

    # Get model parameters (if present)
    model_params = {}
    if model in provider_config.get("models", {}):
        model_params = provider_config["models"][model]
    else:
        default_model = provider_config.get("default_model")
        model_params = provider_config["models"][default_model]

    # Prepare base configuration
    result = {
        "model_client": model_client,
    }

    # Provider-specific adjustments
    if provider == "lmstudio":
        # LM Studio uses standard OpenAI-compatible parameter structure
        result["model_kwargs"] = {"model": model, **model_params}
    else:
        # Standard structure for other providers
        result["model_kwargs"] = {"model": model, **model_params}

    return result


# Export EMBEDDER_TYPE for backward compatibility
# Access via __getattr__ in settings module
def __getattr__(name: str) -> Any:
    """Dynamic attribute access for backward compatibility."""
    if name == "EMBEDDER_TYPE":
        from deepwiki_cli.infrastructure.config.settings import _config_instance

        return _config_instance[0].embedder_type.lower()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


# Export everything for backward compatibility
__all__ = [
    "AWS_ACCESS_KEY_ID",
    "AWS_REGION",
    "AWS_ROLE_ARN",
    "AWS_SECRET_ACCESS_KEY",
    "CLIENT_CLASSES",
    "CONFIG_DIR",
    # Defaults
    "DEFAULT_EXCLUDED_DIRS",
    "DEFAULT_EXCLUDED_FILES",
    "EMBEDDER_TYPE",
    "GITHUB_TOKEN",
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    # Settings
    "Config",
    # Internal
    "_config",
    "_refresh_config",
    # Config accessors
    "configs",
    "get_embedder_config",
    "get_embedder_type",
    "get_model_config",
    "is_lmstudio_embedder",
    "is_openrouter_embedder",
    "load_embedder_config",
    "load_generator_config",
    # Loaders
    "load_json_config",
    "load_repo_config",
]
