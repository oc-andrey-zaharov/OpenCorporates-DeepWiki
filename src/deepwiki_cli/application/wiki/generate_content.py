"""Wiki content generation with RAG support.

This module provides synchronous text generation with streaming support
for wiki structure and page content generation. It uses RAG (Retrieval-Augmented Generation)
to provide context-aware content generation.
"""

import asyncio
import logging
import os
import time
from collections.abc import AsyncGenerator, Generator
from typing import Any

import google.generativeai as genai
from adalflow.core.types import ModelType
from google.api_core import exceptions as google_exceptions
from langfuse import observe
from pydantic import BaseModel

from deepwiki_cli.infrastructure.clients.ai.bedrock_client import BedrockClient
from deepwiki_cli.infrastructure.clients.ai.cursor_agent_client import CursorAgentClient
from deepwiki_cli.infrastructure.clients.ai.openai_client import OpenAIClient
from deepwiki_cli.infrastructure.clients.ai.openrouter_client import OpenRouterClient
from deepwiki_cli.infrastructure.config import (
    get_model_config,
)
from deepwiki_cli.infrastructure.observability import (
    get_langfuse_client,
    is_langfuse_enabled,
)
from deepwiki_cli.infrastructure.prompts import SIMPLE_CHAT_SYSTEM_PROMPT
from deepwiki_cli.services.data_pipeline import count_tokens, get_file_content
from deepwiki_cli.services.rag import RAG

logger = logging.getLogger(__name__)


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.lower() in {"1", "true", "yes", "on"}


OPENAI_STREAMING_ENABLED = _is_truthy(os.environ.get("OPENAI_STREAMING_ENABLED"))


def _read_int_env(var_name: str, default: int) -> int:
    value = os.environ.get(var_name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning(
            "Invalid integer value for %s: %s. Using default %s.",
            var_name,
            value,
            default,
        )
        return default


def _read_float_env(var_name: str, default: float) -> float:
    value = os.environ.get(var_name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning(
            "Invalid float value for %s: %s. Using default %s.",
            var_name,
            value,
            default,
        )
        return default


GOOGLE_STREAM_MAX_RETRIES = _read_int_env("DEEPWIKI_GOOGLE_STREAM_RETRIES", 3)
GOOGLE_STREAM_RETRY_DELAY = _read_float_env("DEEPWIKI_GOOGLE_STREAM_RETRY_DELAY", 3.0)


def _extract_completion_text(completion: Any) -> str | None:
    from typing import cast

    try:
        choices = getattr(completion, "choices", [])
        if choices:
            first_choice = choices[0]
            message = getattr(first_choice, "message", None)
            if message and hasattr(message, "content"):
                return cast("str | None", message.content)
            delta = getattr(first_choice, "delta", None)
            if delta and hasattr(delta, "content"):
                return cast("str | None", delta.content)
        return cast("str | None", getattr(completion, "content", None))
    except Exception as exc:
        logger.warning(f"Failed to extract text from completion: {exc}")
        return None


def _async_to_sync_generator(
    async_gen: AsyncGenerator[str],
) -> Generator[str]:
    """Convert an async generator to a sync generator.
    Uses a new event loop and runs the async generator in a background task.
    """
    import queue
    import threading

    q: queue.Queue[tuple[str, Any]] = queue.Queue()
    exception = None

    def run_async() -> None:
        nonlocal exception
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:

            async def consume() -> None:
                try:
                    async for item in async_gen:
                        q.put(("item", item))
                except Exception as e:
                    q.put(("error", e))
                finally:
                    q.put(("done", None))

            loop.run_until_complete(consume())
        except Exception as e:
            exception = e
            q.put(("error", e))
        finally:
            loop.close()

    thread = threading.Thread(target=run_async, daemon=True)
    thread.start()

    while True:
        try:
            item = q.get(timeout=1.0)  # Increased timeout to 1 second
            msg_type, value = item
            if msg_type == "item":
                yield value
            elif msg_type == "error":
                raise value
            elif msg_type == "done":
                break
        except queue.Empty:
            if not thread.is_alive():
                if exception:
                    raise exception
                # Thread died without sending done signal - might be an issue
                logger.warning("Async generator thread ended without completion signal")
                break
            continue


@observe(name="wiki-generation", capture_input=False)
def generate_wiki_content(
    repo_url: str,
    messages: list[dict[str, str]],
    provider: str,
    model: str,
    repo_type: str = "github",
    structured_schema: type[BaseModel] | None = None,
    token: str | None = None,
    excluded_dirs: list[str] | None = None,
    excluded_files: list[str] | None = None,
    included_dirs: list[str] | None = None,
    included_files: list[str] | None = None,
    additional_context: str | None = None,
    file_path: str | None = None,
    prepared_rag: RAG | None = None,
) -> Generator[str]:
    """Generate wiki content using RAG with streaming support.

    This function generates wiki structure and page content using LLM models
    with RAG (Retrieval-Augmented Generation) for context-aware generation.
    It can be used by both CLI (standalone mode) and server.

    Args:
        repo_url: Repository URL
        messages: List of message dicts with 'role' and 'content' keys
        provider: Model provider (google, openai, openrouter, bedrock)
        model: Model name
        repo_type: Repository type (default: "github")
        structured_schema: Optional Pydantic schema for structured responses
        token: Optional access token for private repositories
        excluded_dirs: Optional list of directories to exclude
        excluded_files: Optional list of file patterns to exclude
        included_dirs: Optional list of directories to include exclusively
        included_files: Optional list of file patterns to include exclusively
        additional_context: Optional additional text context to inject into the prompt
        file_path: Optional path to a file in the repository to include in the prompt
        prepared_rag: Optional pre-initialized RAG instance for reuse

    Yields:
        str: Text chunks as they arrive from the model

    Raises:
        ValueError: If RAG preparation fails
        Exception: For other errors during processing
    """
    # Initialize Langfuse client for inner spans if enabled
    langfuse = get_langfuse_client() if is_langfuse_enabled() else None

    # Check if request contains very large input
    input_too_large = False
    if messages and len(messages) > 0:
        last_message = messages[-1]
        if isinstance(last_message, dict) and last_message.get("content"):
            # Map provider to embedder_type for token counting
            embedder_type = "lmstudio" if provider == "lmstudio" else None
            tokens = count_tokens(last_message["content"], embedder_type=embedder_type)
            logger.info(f"Request size: {tokens} tokens")
            if tokens > 8000:
                logger.warning(
                    f"Request exceeds recommended token limit ({tokens} > 8000)",
                )
                input_too_large = True

    # Create or reuse a RAG instance for this request
    if prepared_rag is not None:
        request_rag = prepared_rag
    else:
        try:
            request_rag = RAG(provider=provider, model=model)

            # Prepare RAG retriever
            request_rag.prepare_retriever(
                repo_url,
                repo_type,
                token,
                excluded_dirs,
                excluded_files,
                included_dirs,
                included_files,
            )
            logger.info(f"Retriever prepared for {repo_url}")
        except ValueError as e:
            if "No valid documents with embeddings found" in str(e):
                logger.exception(f"No valid embeddings found: {e!s}")
                raise ValueError(
                    "No valid document embeddings found. This may be due to embedding size inconsistencies or API errors during document processing. Please try again or check your repository content.",
                )
            else:
                logger.exception(f"ValueError preparing retriever: {e!s}")
                raise ValueError(f"Error preparing retriever: {e!s}")
        except Exception as e:
            logger.exception(f"Error preparing retriever: {e!s}")
            # Check for specific embedding-related errors
            if "All embeddings should be of the same size" in str(e):
                raise ValueError(
                    "Inconsistent embedding sizes detected. Some documents may have failed to embed properly. Please try again.",
                )
            else:
                raise ValueError(f"Error preparing retriever: {e!s}")

    # Validate request
    if not messages or len(messages) == 0:
        raise ValueError("No messages provided")

    last_message = messages[-1]
    if isinstance(last_message, dict) and last_message.get("role") != "user":
        raise ValueError("Last message must be from the user")

    # Get the query from the last message
    query = (
        last_message.get("content", "")
        if isinstance(last_message, dict)
        else str(last_message)
    )

    # Only retrieve documents if input is not too large
    context_text = ""
    context_json_payload: str | None = None
    retrieved_documents = None

    if not input_too_large:
        try:
            # If file_path exists, modify the query for RAG to focus on the file
            rag_query = query
            if file_path:
                # Use the file path to get relevant context about the file
                rag_query = f"Contexts related to {file_path}"
                logger.info(f"Modified RAG query to focus on file: {file_path}")

            # Try to perform RAG retrieval
            try:
                # Start RAG retrieval span for Langfuse (v3 API)
                rag_start_time = time.time()
                # Use context manager for RAG span
                rag_ctx = (
                    langfuse.start_as_current_observation(
                        as_type="retriever",
                        name="rag-retrieval",
                        input={"query": rag_query},
                        metadata={"file_path": file_path},
                    )
                    if langfuse
                    else None
                )

                # We need to manually enter/exit if we want to capture the span object for updates
                # But since we just want to wrap the call, we can use a try/finally or just use the context manager
                # However, the original code updated the span with results.

                if rag_ctx:
                    rag_span = rag_ctx.__enter__()
                else:
                    rag_span = None

                try:
                    # This will use the actual RAG implementation
                    retrieved_documents = request_rag(rag_query)

                    rag_duration = time.time() - rag_start_time

                    if retrieved_documents and retrieved_documents[0].documents:
                        # Format context for the prompt in a more structured way
                        documents = retrieved_documents[0].documents
                        logger.info(f"Retrieved {len(documents)} documents")
                        context_json_payload = getattr(
                            retrieved_documents[0],
                            "context_json",
                            None,
                        )

                        # Update RAG span with results (v3 API)
                        if rag_span:
                            try:
                                rag_span.update(
                                    output={
                                        "document_count": len(documents),
                                        "has_context_json": context_json_payload
                                        is not None,
                                    },
                                    metadata={
                                        "retrieval_duration_seconds": rag_duration,
                                        "documents_retrieved": len(documents),
                                    },
                                )
                            except Exception as e:
                                logger.debug(f"Failed to update RAG span: {e!s}")

                        # Group documents by file path
                        docs_by_file: dict[str, list[Any]] = {}
                        for doc in documents:
                            doc_file_path = doc.meta_data.get("file_path", "unknown")
                            if doc_file_path not in docs_by_file:
                                docs_by_file[doc_file_path] = []
                            docs_by_file[doc_file_path].append(doc)

                        # Format context text with file path grouping
                        context_parts = []
                        for doc_file_path, docs in docs_by_file.items():
                            # Add file header with metadata
                            header = f"## File Path: {doc_file_path}\n\n"
                            # Add document content
                            content = "\n\n".join([doc.text for doc in docs])

                            context_parts.append(f"{header}{content}")

                        # Join all parts with clear separation
                        separator = "\n\n" + "-" * 10 + "\n\n"
                        context_text = separator.join(context_parts)
                    else:
                        logger.warning("No documents retrieved from RAG")
                        if rag_span:
                            try:
                                rag_span.update(
                                    output={"document_count": 0},
                                    metadata={
                                        "retrieval_duration_seconds": rag_duration
                                    },
                                )
                            except Exception as e:
                                logger.debug(f"Failed to update RAG span: {e!s}")
                finally:
                    if rag_ctx:
                        rag_ctx.__exit__(None, None, None)

            except Exception as e:
                logger.exception(f"Error in RAG retrieval: {e!s}")
                # Continue without RAG if there's an error

        except Exception as e:
            logger.exception(f"Error retrieving documents: {e!s}")
            context_text = ""

    # Get repository information
    repo_name = repo_url.split("/")[-1] if "/" in repo_url else repo_url

    # Create system prompt for wiki generation
    system_prompt = SIMPLE_CHAT_SYSTEM_PROMPT.format(
        repo_type=repo_type,
        repo_url=repo_url,
        repo_name=repo_name,
    )

    # Fetch file content if provided
    file_content = ""
    if file_path:
        try:
            file_content = get_file_content(repo_url, file_path, repo_type, token)
            logger.info(f"Successfully retrieved content for file: {file_path}")
        except Exception as e:
            logger.exception(f"Error retrieving file content: {e!s}")
            # Continue without file content if there's an error

    # Create the prompt with context
    prompt = f"/no_think {system_prompt}\n\n"

    # Check if file_path is provided and fetch file content if it exists
    if file_content:
        # Add file content to the prompt
        prompt += f'<currentFileContent path="{file_path}">\n{file_content}\n</currentFileContent>\n\n'

    if context_json_payload:
        prompt += "RAG_CONTEXT_JSON:\n"
        prompt += f"{context_json_payload}\n\n"
    elif context_text.strip():
        prompt += "RAG_CONTEXT_MARKDOWN:\n"
        prompt += f"{context_text}\n\n"
    else:
        logger.info("No context available from RAG")
        prompt += "RAG_CONTEXT_JSON: []\n\n"

    prompt += f"<query>\n{query}\n</query>\n\n"

    if additional_context:
        prompt += f"<additional_context>\n{additional_context}\n</additional_context>\n\n"

    prompt += "Assistant: "

    model_config = get_model_config(provider, model)["model_kwargs"]

    # Start generation span for Langfuse (v3 API)
    generation_start_time = time.time()
    generation_ctx = None
    generation_span = None

    if langfuse:
        try:
            generation_ctx = langfuse.start_as_current_observation(
                as_type="generation",
                name="llm-generation",
                model=model,
                model_parameters={
                    "temperature": model_config.get("temperature"),
                    "top_p": model_config.get("top_p"),
                    "top_k": model_config.get("top_k"),
                },
                input=messages,
                metadata={
                    "provider": provider,
                    "repo_url": repo_url,
                    "has_rag_context": bool(context_text or context_json_payload),
                    "has_file_content": bool(file_content),
                    "structured_schema": structured_schema.__name__
                    if structured_schema
                    else None,
                },
            )
            generation_span = generation_ctx.__enter__()
        except Exception as e:
            logger.debug(f"Failed to create generation span: {e!s}")

    # Create async generator function for streaming/structured responses
    async def _async_stream() -> AsyncGenerator[str]:
        async def _maybe_structured_completion(
            model_client: Any,
            model_kwargs: dict[str, Any],
        ) -> str | None:
            """Attempt structured completion when supported."""
            if structured_schema is None:
                return None
            if not hasattr(model_client, "call_structured"):
                return None
            try:
                schema_obj = await asyncio.to_thread(
                    model_client.call_structured,
                    schema=structured_schema,
                    messages=[{"role": "user", "content": prompt}],
                    model_kwargs=model_kwargs,
                )
                result = schema_obj.model_dump_json()
                return result if isinstance(result, str) else None
            except Exception as exc:  # pragma: no cover - fallback only
                logger.warning(
                    "Structured completion failed; falling back to standard generation",
                    extra={"error": str(exc)},
                )
                return None

        try:
            if provider == "openrouter":
                try:
                    logger.info(f"Using OpenRouter with model: {model}")
                    model_client = OpenRouterClient()
                    model_kwargs = {
                        "model": model,
                        "stream": True,
                        "temperature": model_config["temperature"],
                    }
                    if "top_p" in model_config:
                        model_kwargs["top_p"] = model_config["top_p"]
                    structured_payload = await _maybe_structured_completion(
                        model_client,
                        {**model_kwargs, "stream": False},
                    )
                    if structured_payload is not None:
                        yield structured_payload
                        return
                    api_kwargs = model_client.convert_inputs_to_api_kwargs(
                        input=prompt,
                        model_kwargs=model_kwargs,
                        model_type=ModelType.LLM,
                    )
                    logger.info("Making OpenRouter API call")
                    response = await model_client.acall(
                        api_kwargs=api_kwargs,
                        model_type=ModelType.LLM,
                    )
                    async for chunk in response:
                        yield chunk
                except Exception as e_openrouter:
                    logger.exception(f"Error with OpenRouter API: {e_openrouter!s}")
                    yield f"\nError with OpenRouter API: {e_openrouter!s}\n\nPlease check that you have set the OPENROUTER_API_KEY environment variable with a valid API key."
            elif provider == "openai":
                try:
                    logger.info(f"Using Openai protocol with model: {model}")
                    model_client = OpenAIClient()
                    stream_requested = OPENAI_STREAMING_ENABLED
                    model_kwargs = {
                        "model": model,
                        "stream": stream_requested,
                        "temperature": model_config["temperature"],
                    }
                    if "top_p" in model_config:
                        model_kwargs["top_p"] = model_config["top_p"]
                    structured_payload = await _maybe_structured_completion(
                        model_client,
                        {**model_kwargs, "stream": False},
                    )
                    if structured_payload is not None:
                        yield structured_payload
                        return
                    api_kwargs = model_client.convert_inputs_to_api_kwargs(
                        input=prompt,
                        model_kwargs=model_kwargs,
                        model_type=ModelType.LLM,
                    )
                    logger.info("Making Openai API call")
                    response = await model_client.acall(
                        api_kwargs=api_kwargs,
                        model_type=ModelType.LLM,
                    )
                    if model_kwargs.get("stream", True):
                        async for chunk in response:
                            choices = getattr(chunk, "choices", [])
                            if len(choices) > 0:
                                delta = getattr(choices[0], "delta", None)
                                if delta is not None:
                                    text = getattr(delta, "content", None)
                                    if text is not None:
                                        yield text
                    else:
                        completion_text = _extract_completion_text(response)
                        if completion_text:
                            logger.debug(
                                "OpenAI non-stream response (first 200 chars): %s",
                                completion_text[:200],
                            )
                            yield completion_text
                        else:
                            logger.warning(
                                "OpenAI non-stream response empty; yielding raw completion",
                            )
                            yield str(response)
                except Exception as e_openai:
                    error_text = str(e_openai)
                    streaming_attempted = model_kwargs.get("stream", True)
                    if (
                        streaming_attempted
                        and "unsupported_value" in error_text
                        and "stream" in error_text
                    ):
                        logger.warning(
                            "OpenAI streaming not permitted for this model; retrying without stream",
                        )
                        try:
                            non_stream_model_kwargs = {
                                **model_kwargs,
                                "stream": False,
                            }
                            fallback_api_kwargs = (
                                model_client.convert_inputs_to_api_kwargs(
                                    input=prompt,
                                    model_kwargs=non_stream_model_kwargs,
                                    model_type=ModelType.LLM,
                                )
                            )
                            completion = await model_client.acall(
                                api_kwargs=fallback_api_kwargs,
                                model_type=ModelType.LLM,
                            )
                            completion_text = _extract_completion_text(completion)
                            if completion_text:
                                logger.debug(
                                    "OpenAI fallback non-stream response (first 200 chars): %s",
                                    completion_text[:200],
                                )
                                yield completion_text
                                return
                            logger.warning(
                                "OpenAI fallback non-stream response empty; yielding raw completion",
                            )
                            yield str(completion)
                            return
                        except Exception as fallback_error:
                            logger.exception(
                                f"Error with Openai API non-stream fallback: {fallback_error!s}",
                            )
                            yield (
                                f"\nError with Openai API fallback: {fallback_error!s}\n\n"
                                "Please check that you have set the OPENAI_API_KEY environment variable with a valid API key."
                            )
                            return
                    logger.exception(f"Error with Openai API: {error_text}")
                    yield f"\nError with Openai API: {error_text}\n\nPlease check that you have set the OPENAI_API_KEY environment variable with a valid API key."
            elif provider == "bedrock":
                try:
                    logger.info(f"Using AWS Bedrock with model: {model}")
                    model_client = BedrockClient()
                    model_kwargs = {
                        "model": model,
                        "temperature": model_config["temperature"],
                        "top_p": model_config["top_p"],
                    }
                    structured_payload = await _maybe_structured_completion(
                        model_client,
                        model_kwargs.copy(),
                    )
                    if structured_payload is not None:
                        yield structured_payload
                        return
                    api_kwargs = model_client.convert_inputs_to_api_kwargs(
                        input=prompt,
                        model_kwargs=model_kwargs,
                        model_type=ModelType.LLM,
                    )
                    logger.info("Making AWS Bedrock API call")
                    response = await model_client.acall(
                        api_kwargs=api_kwargs,
                        model_type=ModelType.LLM,
                    )
                    if isinstance(response, str):
                        yield response
                    else:
                        yield str(response)
                except Exception as e_bedrock:
                    logger.exception(f"Error with AWS Bedrock API: {e_bedrock!s}")
                    yield f"\nError with AWS Bedrock API: {e_bedrock!s}\n\nPlease check that you have set the AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables with valid credentials."
            elif provider == "cursor":
                try:
                    logger.info(f"Using Cursor Agent with model: {model}")
                    model_client = CursorAgentClient(model=model)
                    model_kwargs = {
                        "model": model,
                    }
                    
                    # Try structured first if schema exists
                    structured_payload = await _maybe_structured_completion(
                        model_client,
                        model_kwargs,
                    )
                    if structured_payload is not None:
                        yield structured_payload
                        return

                    # Fallback to standard call
                    api_kwargs = {
                        "messages": [{"role": "user", "content": prompt}],
                        **model_kwargs
                    }
                    
                    logger.info("Making Cursor Agent CLI call")
                    response = await model_client.acall(
                        api_kwargs=api_kwargs,
                        model_type=ModelType.LLM,
                    )
                    
                    completion_text = _extract_completion_text(response)
                    if completion_text:
                        yield completion_text
                    else:
                        yield str(response)

                except Exception as e_cursor:
                     logger.exception(f"Error with Cursor Agent: {e_cursor!s}")
                     yield f"\nError with Cursor Agent: {e_cursor!s}"
            else:
                # Google Generative AI with retry for overloads
                attempt = 0
                while attempt < GOOGLE_STREAM_MAX_RETRIES:
                    attempt += 1
                    try:
                        google_model = genai.GenerativeModel(
                            model_name=model_config["model"],
                            generation_config={  # type: ignore[arg-type]
                                "temperature": model_config["temperature"],
                                "top_p": model_config["top_p"],
                                "top_k": model_config["top_k"],
                            },
                        )
                        response = google_model.generate_content(prompt, stream=True)
                        for chunk in response:
                            if hasattr(chunk, "text"):
                                yield chunk.text
                        break
                    except google_exceptions.ServiceUnavailable as svc_error:
                        logger.warning(
                            "Google Generative AI overloaded (attempt %s/%s): %s",
                            attempt,
                            GOOGLE_STREAM_MAX_RETRIES,
                            svc_error,
                        )
                        if attempt >= GOOGLE_STREAM_MAX_RETRIES:
                            raise
                        await asyncio.sleep(GOOGLE_STREAM_RETRY_DELAY * attempt)

        except Exception as e_outer:
            logger.exception(f"Error in streaming response: {e_outer!s}")
            error_message = str(e_outer)

            # Check for token limit errors
            if (
                "maximum context length" in error_message
                or "token limit" in error_message
                or "too many tokens" in error_message
            ):
                # If we hit a token limit error, try again without context
                logger.warning("Token limit exceeded, retrying without context")
                try:
                    # Create a simplified prompt without context
                    simplified_prompt = f"/no_think {system_prompt}\n\n"

                    # Include file content in the fallback prompt if it was retrieved
                    if file_path and file_content:
                        simplified_prompt += f'<currentFileContent path="{file_path}">\n{file_content}\n</currentFileContent>\n\n'

                    simplified_prompt += "<note>Answering without retrieval augmentation due to input size constraints.</note>\n\n"
                    simplified_prompt += f"<query>\n{query}\n</query>\n\nAssistant: "

                    # Handle fallback for each provider (simplified version)
                    if provider == "google":
                        fallback_model = genai.GenerativeModel(
                            model_name=model_config["model"],
                            generation_config={  # type: ignore[arg-type]
                                "temperature": model_config.get("temperature", 0.7),
                                "top_p": model_config.get("top_p", 0.8),
                                "top_k": model_config.get("top_k", 40),
                            },
                        )
                        fallback_response = fallback_model.generate_content(
                            simplified_prompt,
                            stream=True,
                        )
                        for chunk in fallback_response:
                            if hasattr(chunk, "text"):
                                yield chunk.text
                    else:
                        yield "\nI apologize, but your request is too large for me to process. Please try a shorter query or break it into smaller parts."
                except Exception as e2:
                    logger.exception(f"Error in fallback streaming response: {e2!s}")
                    yield "\nI apologize, but your request is too large for me to process. Please try a shorter query or break it into smaller parts."
            else:
                # For other errors, return the error message
                yield f"\nError: {error_message}"

    # Convert async generator to sync generator
    # @observe will automatically capture the output from the generator

    input_tokens = count_tokens(prompt, embedder_type=None)
    output_tokens = 0
    collected_output = []

    try:
        for chunk in _async_to_sync_generator(_async_stream()):
            collected_output.append(chunk)
            yield chunk

        # Update generation span with usage details if possible
        if generation_span:
            try:
                full_output = "".join(collected_output)
                output_tokens = count_tokens(full_output, embedder_type=None)

                generation_span.update(
                    usage_details={
                        "prompt_tokens": input_tokens,
                        "completion_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                    }
                )
            except Exception as e:
                logger.debug(f"Failed to update generation stats: {e}")

    except Exception as e:
        logger.exception(f"Error during wiki generation: {e!s}")
        raise
    finally:
        # End generation span
        if generation_ctx:
            generation_ctx.__exit__(None, None, None)

        # Flush Langfuse events
        if langfuse:
            try:
                langfuse.flush()
            except Exception as e:
                logger.debug(f"Failed to flush Langfuse: {e!s}")
