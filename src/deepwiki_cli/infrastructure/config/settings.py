"""Application settings loaded from environment variables."""

import os
from pathlib import Path
from typing import Any

import structlog
from adalflow import GoogleGenAIClient, OllamaClient
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

from deepwiki_cli.infrastructure.clients.ai.bedrock_client import BedrockClient
from deepwiki_cli.infrastructure.clients.ai.openai_client import OpenAIClient
from deepwiki_cli.infrastructure.clients.ai.openrouter_client import OpenRouterClient

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
                load_dotenv(dotenv_path=normalized, override=True)
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
        aws_access_key_id: AWS access key ID for AWS services.
        aws_secret_access_key: AWS secret access key for AWS services.
        aws_region: AWS region for AWS services.
        aws_role_arn: AWS role ARN for assuming roles.
        github_token: GitHub token for repository access.
        embedder_type: Type of embedder to use (openai, ollama, openrouter).
        config_dir: Optional directory path for configuration files.

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


# Client class mapping
CLIENT_CLASSES = {
    "GoogleGenAIClient": GoogleGenAIClient,
    "OpenAIClient": OpenAIClient,
    "OpenRouterClient": OpenRouterClient,
    "OllamaClient": OllamaClient,
    "BedrockClient": BedrockClient,
}

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


# Use __getattr__ to make EMBEDDER_TYPE read dynamically from _config
# This allows it to pick up changes after module reload
def __getattr__(name: str) -> Any:
    """Dynamic attribute access for backward compatibility."""
    if name == "EMBEDDER_TYPE":
        # Always read from current _config instance
        return _config_instance[0].embedder_type.lower()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
