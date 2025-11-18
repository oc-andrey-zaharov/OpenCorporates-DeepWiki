"""LM Studio-specific utilities and document processing.

LM Studio uses an OpenAI-compatible API, so it supports batch embeddings.
This module provides utilities for checking model availability and optional
document processing if needed.
"""

import logging
import os
from collections.abc import Sequence
from copy import deepcopy

import adalflow as adal
import requests
from adalflow.core.component import DataComponent
from adalflow.core.types import Document
from adalflow.utils.registry import EntityMapping
from tqdm import tqdm

# Configure logging
from deepwiki_cli.infrastructure.logging.setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


class LMStudioModelNotFoundError(Exception):
    """Custom exception for when LM Studio model is not found."""


def check_lmstudio_model_exists(
    model_name: str,
    lmstudio_host: str | None = None,
) -> bool:
    """Check if an LM Studio model is available.

    Args:
        model_name: Name of the model to check (e.g., "nomic-embed-code")
        lmstudio_host: LM Studio host URL, defaults to http://127.0.0.1:1234

    Returns:
        bool: True if model is available, False otherwise
    """
    if lmstudio_host is None:
        lmstudio_host = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234")

    try:
        # Ensure URL doesn't have /v1 suffix for model check
        base_url = lmstudio_host.rstrip("/v1").rstrip("/")

        # Check if server is running by trying to list models
        # LM Studio uses OpenAI-compatible API
        response = requests.get(
            f"{base_url}/v1/models",
            headers={"Authorization": "Bearer lm-studio"},
            timeout=5,
        )
        if response.status_code == 200:
            models_data = response.json()
            available_models = [
                model.get("id", "") for model in models_data.get("data", [])
            ]

            is_available = model_name in available_models
            if is_available:
                logger.info(f"LM Studio model '{model_name}' is available")
            else:
                logger.warning(
                    f"LM Studio model '{model_name}' is not available. "
                    f"Available models: {available_models}",
                )
            return is_available
        logger.warning(
            f"Could not check LM Studio models, status code: {response.status_code}",
        )
        return False
    except requests.exceptions.RequestException as e:
        logger.warning(f"Could not connect to LM Studio to check models: {e}")
        return False
    except Exception as e:
        logger.warning(f"Error checking LM Studio model availability: {e}")
        return False


class LMStudioDocumentProcessor(DataComponent):
    """Process documents for LM Studio embeddings.

    LM Studio uses OpenAI-compatible API which supports batch embeddings,
    but this processor can be used if individual document processing is needed
    for consistency checking or error handling.
    """

    def __init__(self, embedder: adal.Embedder) -> None:
        super().__init__()
        self.embedder = embedder

    def __call__(self, documents: Sequence[Document]) -> Sequence[Document]:
        output = deepcopy(documents)
        logger.info(
            f"Processing {len(output)} documents for LM Studio embeddings",
        )

        successful_docs = []
        expected_embedding_size = None

        for i, doc in enumerate(
            tqdm(output, desc="Processing documents for LM Studio embeddings"),
        ):
            try:
                # Get embedding for a single document
                result = self.embedder(input=doc.text)
                if result.data and len(result.data) > 0:
                    embedding = result.data[0].embedding

                    # Validate embedding size consistency
                    if expected_embedding_size is None:
                        expected_embedding_size = len(embedding)
                        logger.info(
                            f"Expected embedding size set to: {expected_embedding_size}",
                        )
                    elif len(embedding) != expected_embedding_size:
                        file_path = getattr(doc, "meta_data", {}).get(
                            "file_path",
                            f"document_{i}",
                        )
                        logger.warning(
                            f"Document '{file_path}' has inconsistent embedding size "
                            f"{len(embedding)} != {expected_embedding_size}, skipping",
                        )
                        continue

                    # Assign the embedding to the document
                    output[i].vector = embedding
                    successful_docs.append(output[i])
                else:
                    file_path = getattr(doc, "meta_data", {}).get(
                        "file_path",
                        f"document_{i}",
                    )
                    logger.warning(
                        f"Failed to get embedding for document '{file_path}', skipping",
                    )
            except Exception as e:
                file_path = getattr(doc, "meta_data", {}).get(
                    "file_path",
                    f"document_{i}",
                )
                logger.exception(
                    f"Error processing document '{file_path}': {e}, skipping",
                )

        logger.info(
            f"Successfully processed {len(successful_docs)}/{len(output)} "
            "documents with consistent embeddings",
        )
        return successful_docs


# Ensure the processor can be restored from pickled LocalDB instances
EntityMapping.register("LMStudioDocumentProcessor", LMStudioDocumentProcessor)
