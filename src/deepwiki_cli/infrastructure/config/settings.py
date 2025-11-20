"""Application settings loaded from environment variables."""

import os
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

from deepwiki_cli.infrastructure.clients.ai.cursor_agent_client import CursorAgentClient
from deepwiki_cli.infrastructure.clients.ai.lmstudio_client import LMStudioClient
from deepwiki_cli.infrastructure.clients.ai.openai_client import OpenAIClient
from deepwiki_cli.infrastructure.clients.ai.openrouter_client import OpenRouterClient
from deepwiki_cli.shared.structlog import structlog

logger = structlog.get_logger()

ENV_FILE_ENV_VAR = "DEEPWIKI_ENV_FILE"
CONFIG_DIR_ENV_VAR = "DEEPWIKI_CONFIG_DIR"
DEFAULT_HOME_ENV_FILE = Path.home() / ".deepwiki" / ".env"
_env_files_loaded = [False]


def _normalize_env_path(path: Path) -> Path:
    """Expand user references and resolve the provided path when possible."""
    expanded = path.expanduser()
    try:
        return expanded.resolve()
    except (OSError, RuntimeError):
        return expanded


def _load_env_files() -> None:
    """Load environment variables from supported .env locations once per process."""
    if _env_files_loaded[0]:
        return

    candidate_paths: list[Path] = []
    env_override = os.environ.get(ENV_FILE_ENV_VAR)
    if env_override:
        candidate_paths.append(Path(env_override))

    config_dir_override = os.environ.get(CONFIG_DIR_ENV_VAR)
    if config_dir_override:
        candidate_paths.append(Path(config_dir_override) / ".env")

    candidate_paths.append(DEFAULT_HOME_ENV_FILE)

    try:
        project_root = Path(__file__).resolve().parents[4]
    except IndexError:
        project_root = Path(__file__).resolve().parent
    candidate_paths.append(project_root / ".env")
    candidate_paths.append(Path.cwd() / ".env")

    seen_paths: set[Path] = set()
    loaded_paths: list[str] = []

    for candidate in candidate_paths:
        normalized = _normalize_env_path(candidate)
        if normalized in seen_paths:
            continue
        seen_paths.add(normalized)

        if normalized.is_file():
            try:
                load_dotenv(dotenv_path=normalized, override=False)
                loaded_paths.append(str(normalized))
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning(
                    "Failed to load environment file",
                    operation="load_env",
                    status="warning",
                    env_path=str(normalized),
                    error=str(exc),
                )

    if loaded_paths:
        logger.info(
            "Environment configuration loaded",
            operation="load_env",
            status="success",
            loaded_paths=loaded_paths,
        )
    else:
        logger.info(
            "No environment files detected",
            operation="load_env",
            status="info",
        )

    _env_files_loaded[0] = True


class Config(BaseSettings):
    """Application configuration loaded from environment variables.

    Attributes:
        openai_api_key: OpenAI API key for OpenAI client.
        google_api_key: Google API key for Google client.
        openrouter_api_key: OpenRouter API key for OpenRouter client.
        aws_access_key_id: AWS access key ID for AWS services (e.g., CodeArtifact).
        aws_secret_access_key: AWS secret access key for AWS services (e.g., CodeArtifact).
        aws_region: AWS region for AWS services (e.g., CodeArtifact).
        aws_role_arn: AWS role ARN for assuming roles (optional).
        github_token: GitHub token for repository access.
        embedder_type: Type of embedder to use (openai, lmstudio, openrouter).
        config_dir: Optional directory path for configuration files.
        toon_cli_path: Path to the TOON CLI binary (optional).
        toon_enabled: Whether TOON conversion is enabled.
        use_json_compact: Toggle for compact JSON serialization by default.
        format_preference: Preferred serialization format when multiple are available.

    Example:
        >>> config = Config()
        >>> print(config.embedder_type)
        'openai'
    """

    openai_api_key: str | None = Field(default=None, env="OPENAI_API_KEY")  # type: ignore[call-overload]
    google_api_key: str | None = Field(default=None, env="GOOGLE_API_KEY")  # type: ignore[call-overload]
    openrouter_api_key: str | None = Field(default=None, env="OPENROUTER_API_KEY")  # type: ignore[call-overload]
    aws_access_key_id: str | None = Field(default=None, env="AWS_ACCESS_KEY_ID")  # type: ignore[call-overload]
    aws_secret_access_key: str | None = Field(default=None, env="AWS_SECRET_ACCESS_KEY")  # type: ignore[call-overload]
    aws_region: str | None = Field(default=None, env="AWS_REGION")  # type: ignore[call-overload]
    aws_role_arn: str | None = Field(default=None, env="AWS_ROLE_ARN")  # type: ignore[call-overload]
    github_token: str | None = Field(default=None, env="GITHUB_TOKEN")  # type: ignore[call-overload]
    embedder_type: str = Field(
        default="openai",
        env="DEEPWIKI_EMBEDDER_TYPE",
        validation_alias="DEEPWIKI_EMBEDDER_TYPE",
    )  # type: ignore[call-overload]
    config_dir: str | None = Field(default=None, env="DEEPWIKI_CONFIG_DIR")  # type: ignore[call-overload]
    toon_cli_path: str | None = Field(
        default=None,
        env="TOON_CLI_PATH",
    )  # type: ignore[call-overload]
    toon_enabled: bool = Field(
        default=False,
        env="TOON_ENABLED",
    )  # type: ignore[call-overload]
    use_json_compact: bool = Field(
        default=True,
        env="USE_JSON_COMPACT",
    )  # type: ignore[call-overload]
    format_preference: Literal["json", "json-compact", "toon"] = Field(
        default="json-compact",
        env="FORMAT_PREFERENCE",
    )  # type: ignore[call-overload]
    langfuse_public_key: str | None = Field(
        default=None,
        env="LANGFUSE_PUBLIC_KEY",
    )  # type: ignore[call-overload]
    langfuse_secret_key: str | None = Field(
        default=None,
        env="LANGFUSE_SECRET_KEY",
    )  # type: ignore[call-overload]
    langfuse_base_url: str | None = Field(
        default=None,
        env="LANGFUSE_BASE_URL",
    )  # type: ignore[call-overload]
    langfuse_enabled: bool = Field(
        default=True,
        env="LANGFUSE_ENABLED",
    )  # type: ignore[call-overload]

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        case_sensitive = False
        extra = (
            "ignore"  # Ignore extra environment variables for backward compatibility
        )

    def __init__(self, **kwargs: Any) -> None:
        """Initialize configuration and set environment variables.

        Args:
            **kwargs: Configuration values to override defaults.
        """
        super().__init__(**kwargs)
        # Set keys in environment (in case they're needed elsewhere in the code)
        if self.openai_api_key:
            os.environ["OPENAI_API_KEY"] = self.openai_api_key
        if self.google_api_key:
            os.environ["GOOGLE_API_KEY"] = self.google_api_key
        if self.openrouter_api_key:
            os.environ["OPENROUTER_API_KEY"] = self.openrouter_api_key
        if self.aws_access_key_id:
            os.environ["AWS_ACCESS_KEY_ID"] = self.aws_access_key_id
        if self.aws_secret_access_key:
            os.environ["AWS_SECRET_ACCESS_KEY"] = self.aws_secret_access_key
        if self.aws_region:
            os.environ["AWS_REGION"] = self.aws_region
        if self.aws_role_arn:
            os.environ["AWS_ROLE_ARN"] = self.aws_role_arn
        if self.toon_cli_path:
            os.environ["TOON_CLI_PATH"] = self.toon_cli_path
        if self.langfuse_public_key:
            os.environ["LANGFUSE_PUBLIC_KEY"] = self.langfuse_public_key
        if self.langfuse_secret_key:
            os.environ["LANGFUSE_SECRET_KEY"] = self.langfuse_secret_key
        if self.langfuse_base_url:
            os.environ["LANGFUSE_BASE_URL"] = self.langfuse_base_url


# Client class mapping (lazy-loaded to avoid early adalflow import)
_client_classes_cache: dict[str, Any] | None = None


def get_client_classes() -> dict[str, Any]:
    """Get client class mapping with lazy import of adalflow.

    Returns:
        Dictionary mapping client class names to their actual classes.

    Note:
        GoogleGenAIClient is lazily imported to avoid triggering adalflow's
        MLflow warning before logging filters are configured.
    """
    global _client_classes_cache  # noqa: PLW0603
    if _client_classes_cache is not None:
        return _client_classes_cache

    from adalflow import GoogleGenAIClient

    _client_classes_cache = {
        "GoogleGenAIClient": GoogleGenAIClient,
        "OpenAIClient": OpenAIClient,
        "OpenRouterClient": OpenRouterClient,
        "LMStudioClient": LMStudioClient,
        "CursorAgentClient": CursorAgentClient,
    }
    return _client_classes_cache


# Note: Use get_client_classes() function to access client classes
# This ensures adalflow is only imported after logging is configured
CLIENT_CLASSES: dict[str, Any] = {}  # Populated lazily by get_client_classes()

# Initialize global config instance
# Read embedder_type directly from env to ensure it's current
# This handles module reloads correctly
_load_env_files()
_config_instance = [
    Config(
        embedder_type=os.environ.get("DEEPWIKI_EMBEDDER_TYPE", "openai").lower(),
    )
]


def _refresh_config() -> None:
    """Refresh the global config instance to pick up environment variable changes."""
    _config_instance[0] = Config(
        embedder_type=os.environ.get("DEEPWIKI_EMBEDDER_TYPE", "openai").lower(),
    )


# Backward compatibility: expose as module-level variables
# These will be updated when module is reloaded or _refresh_config() is called
OPENAI_API_KEY = _config_instance[0].openai_api_key
GOOGLE_API_KEY = _config_instance[0].google_api_key
OPENROUTER_API_KEY = _config_instance[0].openrouter_api_key
AWS_ACCESS_KEY_ID = _config_instance[0].aws_access_key_id
AWS_SECRET_ACCESS_KEY = _config_instance[0].aws_secret_access_key
AWS_REGION = _config_instance[0].aws_region
AWS_ROLE_ARN = _config_instance[0].aws_role_arn
GITHUB_TOKEN = _config_instance[0].github_token
# EMBEDDER_TYPE reads dynamically from _config to support module reloads
CONFIG_DIR = _config_instance[0].config_dir
TOON_CLI_PATH = _config_instance[0].toon_cli_path
TOON_ENABLED = _config_instance[0].toon_enabled
USE_JSON_COMPACT = _config_instance[0].use_json_compact
FORMAT_PREFERENCE = _config_instance[0].format_preference
LANGFUSE_PUBLIC_KEY = _config_instance[0].langfuse_public_key
LANGFUSE_SECRET_KEY = _config_instance[0].langfuse_secret_key
LANGFUSE_BASE_URL = _config_instance[0].langfuse_base_url
LANGFUSE_ENABLED = _config_instance[0].langfuse_enabled


# Use __getattr__ to make EMBEDDER_TYPE read dynamically from _config
# This allows it to pick up changes after module reload
def __getattr__(name: str) -> Any:
    """Dynamic attribute access for backward compatibility."""
    if name == "EMBEDDER_TYPE":
        # Always read from current _config instance
        return _config_instance[0].embedder_type.lower()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
