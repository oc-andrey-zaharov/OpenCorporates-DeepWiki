"""LM Studio ModelClient integration.

LM Studio provides a local OpenAI-compatible API server for running models locally.
This client wraps the OpenAI client to connect to LM Studio's local server.
"""

import logging
import os
from typing import Any

from deepwiki_cli.infrastructure.clients.ai.openai_client import OpenAIClient

log = logging.getLogger(__name__)


class LMStudioClient(OpenAIClient):
    """LM Studio ModelClient that uses OpenAI-compatible API.

    LM Studio runs a local server that provides an OpenAI-compatible API endpoint.
    This client connects to that local server for embeddings and chat completions.

    Args:
        base_url: Base URL for LM Studio server. Defaults to http://127.0.0.1:1234/v1
        api_key: API key (not required for LM Studio, but can be set to "lm-studio")
        env_base_url_name: Environment variable name for base URL. Defaults to "LMSTUDIO_BASE_URL"
        env_api_key_name: Environment variable name for API key. Defaults to "LMSTUDIO_API_KEY"

    Example:
        ```python
        from deepwiki_cli.infrastructure.clients.ai.lmstudio_client import LMStudioClient

        client = LMStudioClient()
        embedder = adal.Embedder(
            model_client=client,
            model_kwargs={"model": "nomic-embed-code"}
        )
        ```
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        env_base_url_name: str = "LMSTUDIO_BASE_URL",
        env_api_key_name: str = "LMSTUDIO_API_KEY",
        **kwargs: Any,
    ) -> None:
        """Initialize LM Studio client with default local server URL.

        Args:
            base_url: Base URL for LM Studio server. Defaults to http://127.0.0.1:1234/v1
            api_key: API key (optional, defaults to "lm-studio" if not set)
            env_base_url_name: Environment variable name for base URL
            env_api_key_name: Environment variable name for API key
            **kwargs: Additional arguments passed to OpenAIClient
        """
        # Set default base URL for LM Studio local server
        if base_url is None:
            base_url = os.getenv(env_base_url_name, "http://127.0.0.1:1234/v1")

        # Set default API key if not provided (LM Studio doesn't require auth, but some clients expect it)
        if api_key is None:
            api_key = os.getenv(env_api_key_name, "lm-studio")

        # Ensure base_url ends with /v1 if not already
        if not base_url.endswith("/v1"):
            if base_url.endswith("/"):
                base_url = f"{base_url}v1"
            else:
                base_url = f"{base_url}/v1"

        # Initialize parent OpenAIClient with LM Studio settings
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            env_base_url_name=env_base_url_name,
            env_api_key_name=env_api_key_name,
            **kwargs,
        )

        log.info(
            "LM Studio client initialized",
            base_url=base_url,
            operation="init",
            status="success",
        )
