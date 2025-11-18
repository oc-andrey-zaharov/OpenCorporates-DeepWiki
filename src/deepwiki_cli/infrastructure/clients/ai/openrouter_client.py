"""OpenRouter ModelClient integration."""

import json
import logging
import os
from collections.abc import AsyncGenerator, Generator, Sequence
from typing import Any

import aiohttp
import backoff
import requests
from adalflow.core.model_client import ModelClient
from adalflow.core.types import (
    CompletionUsage,
    EmbedderOutput,
    Embedding,
    GeneratorOutput,
    ModelType,
    Usage,
)
from requests.exceptions import RequestException

log = logging.getLogger(__name__)


class OpenRouterClient(ModelClient):
    __doc__ = r"""A component wrapper for the OpenRouter API client.

    OpenRouter provides a unified API that gives access to hundreds of AI models through a single endpoint.
    The API is compatible with OpenAI's API format with a few small differences.

    Visit https://openrouter.ai/docs for more details.

    Example:
        ```python
        from deepwiki_cli.infrastructure.clients.ai.openrouter_client import OpenRouterClient

        client = OpenRouterClient()
        generator = adal.Generator(
            model_client=client,
            model_kwargs={"model": "openai/gpt-4o"}
        )
        ```
    """

    DEFAULT_MAX_EMBED_BATCH_SIZE = 8
    PROVIDER_ERROR_RETRY = "No successful provider responses"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the OpenRouter client."""
        super().__init__(*args, **kwargs)
        self.sync_client = self.init_sync_client()
        self.async_client = None  # Initialize async client only when needed
        self.max_embed_batch_size = self._resolve_max_embed_batch_size()

    def init_sync_client(self):
        """Initialize the synchronous OpenRouter client."""
        from deepwiki_cli.infrastructure.config.settings import OPENROUTER_API_KEY

        api_key = OPENROUTER_API_KEY
        if not api_key:
            log.warning("OPENROUTER_API_KEY not configured")

        # OpenRouter doesn't have a dedicated client library, so we'll use requests directly
        return {"api_key": api_key, "base_url": "https://openrouter.ai/api/v1"}

    def init_async_client(self):
        """Initialize the asynchronous OpenRouter client."""
        from deepwiki_cli.infrastructure.config.settings import OPENROUTER_API_KEY

        api_key = OPENROUTER_API_KEY
        if not api_key:
            log.warning("OPENROUTER_API_KEY not configured")

        # For async, we'll use aiohttp
        return {"api_key": api_key, "base_url": "https://openrouter.ai/api/v1"}

    def convert_inputs_to_api_kwargs(
        self,
        input: Any,
        model_kwargs: dict | None = None,
        model_type: ModelType = None,
    ) -> dict:
        """Convert AdalFlow inputs to OpenRouter API format."""
        model_kwargs = model_kwargs or {}

        if model_type == ModelType.LLM:
            # Handle LLM generation
            messages = []

            # Convert input to messages format if it's a string
            if isinstance(input, str):
                messages = [{"role": "user", "content": input}]
            elif isinstance(input, list) and all(
                isinstance(msg, dict) for msg in input
            ):
                messages = input
            else:
                raise ValueError(
                    f"Unsupported input format for OpenRouter: {type(input)}",
                )

            if log.isEnabledFor(logging.DEBUG):
                preview = ""
                if messages:
                    last_message = messages[-1]
                    content = last_message.get("content")
                    if isinstance(content, str):
                        preview = content[:200]
                log.debug(
                    "Prepared %d messages for OpenRouter. Preview: %s",
                    len(messages),
                    preview,
                )

            api_kwargs = {"messages": messages, **model_kwargs}

            # Ensure model is specified
            if "model" not in api_kwargs:
                api_kwargs["model"] = "openai/gpt-3.5-turbo"

            return api_kwargs

        if model_type == ModelType.EMBEDDER:
            if isinstance(input, str):
                inputs: list[str] = [input]
            elif isinstance(input, Sequence):
                inputs = list(input)
            else:
                raise TypeError(
                    f"Unsupported embedding input format for OpenRouter: {type(input)}",
                )

            api_kwargs = {"input": inputs, **model_kwargs}
            if "model" not in api_kwargs:
                api_kwargs["model"] = "mistralai/codestral-embed-2505"

            return api_kwargs

        raise ValueError(f"Unsupported model type: {model_type}")

    def call(
        self,
        api_kwargs: dict | None = None,
        model_type: ModelType = ModelType.UNDEFINED,
    ):
        """Make a synchronous call to the OpenRouter API."""
        if api_kwargs is None:
            api_kwargs = {}

        if model_type == ModelType.EMBEDDER:
            inputs = api_kwargs.get("input")
            return self._call_embeddings_with_chunking(api_kwargs, inputs)

        raise ValueError(
            f"Synchronous call not supported for model type: {model_type}",
        )

    @backoff.on_exception(
        backoff.expo,
        (RequestException,),
        max_tries=3,
        max_time=30,
    )
    def _call_embeddings(self, api_kwargs: dict) -> requests.Response:
        """Execute a synchronous embeddings request with retry logic."""
        if not self.sync_client:
            self.sync_client = self.init_sync_client()

        if not self.sync_client.get("api_key"):
            raise ValueError(
                "OPENROUTER_API_KEY not configured. Please set it to use OpenRouter embeddings.",
            )

        inputs = api_kwargs.get("input")
        if inputs is None:
            raise ValueError("OpenRouter embeddings require 'input' data.")

        # Filter out empty inputs
        if isinstance(inputs, list):
            filtered_inputs = [
                inp for inp in inputs if inp and isinstance(inp, str) and inp.strip()
            ]
            if not filtered_inputs:
                log.warning("All inputs were empty after filtering")
                raise ValueError("All inputs are empty or invalid")
            if len(filtered_inputs) != len(inputs):
                log.warning(
                    f"Filtered out {len(inputs) - len(filtered_inputs)} empty inputs",
                    extra={
                        "original_count": len(inputs),
                        "filtered_count": len(filtered_inputs),
                    },
                )
            inputs = filtered_inputs
        elif isinstance(inputs, str):
            if not inputs.strip():
                raise ValueError("Input string is empty")
        else:
            raise TypeError(
                f"Input must be a string or list of strings, got {type(inputs)}"
            )

        headers = {
            "Authorization": f"Bearer {self.sync_client['api_key']}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/AsyncFuncAI/deepwiki-open",
            "X-Title": "DeepWiki",
        }

        payload = {
            "model": api_kwargs.get("model", "mistralai/codestral-embed-2505"),
            "input": inputs,
        }

        if "encoding_format" in api_kwargs:
            payload["encoding_format"] = api_kwargs["encoding_format"]

        log.info(
            "Calling OpenRouter embeddings API",
            extra={
                "model": payload["model"],
                "input_count": (
                    len(payload["input"]) if isinstance(payload["input"], list) else 1
                ),
            },
        )

        try:
            response = requests.post(
                f"{self.sync_client['base_url']}/embeddings",
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()

            # Check for provider errors in successful HTTP responses
            try:
                response_data = response.json()
                if "error" in response_data:
                    error_msg = response_data["error"]
                    if isinstance(error_msg, dict):
                        error_msg = error_msg.get("message", str(error_msg))
                    # Retry on provider errors like "No successful provider responses"
                    if (
                        "No successful provider responses" in str(error_msg)
                        or "provider" in str(error_msg).lower()
                    ):
                        log.warning(f"Provider error detected, will retry: {error_msg}")
                        raise RequestException(f"Provider error: {error_msg}")
            except (json.JSONDecodeError, ValueError):
                # If response isn't JSON or doesn't have error, continue
                pass

            return response
        except RequestException as exc:
            log.warning(f"OpenRouter embeddings API call failed (will retry): {exc!s}")
            raise

    def _call_embeddings_with_chunking(
        self,
        api_kwargs: dict,
        inputs: Sequence[str] | str | None,
    ) -> Any:
        """Chunk large batches and gracefully retry on provider failures."""
        if isinstance(inputs, list) and len(inputs) > self.max_embed_batch_size:
            log.debug(
                "Splitting OpenRouter embedding batch",
                extra={
                    "original_count": len(inputs),
                    "batch_size": self.max_embed_batch_size,
                },
            )
            payloads: list[dict[str, Any]] = []
            for chunk in self._chunk_inputs(inputs, self.max_embed_batch_size):
                chunk_kwargs = {**api_kwargs, "input": chunk}
                response = self._call_embeddings_with_chunking(
                    chunk_kwargs,
                    chunk,
                )
                payloads.append(self._ensure_payload_dict(response))
            return self._combine_embedding_payloads(payloads, api_kwargs.get("model"))

        try:
            return self._call_embeddings(api_kwargs)
        except RequestException as exc:
            if (
                isinstance(inputs, list)
                and len(inputs) > 1
                and self.PROVIDER_ERROR_RETRY in str(exc)
            ):
                log.info(
                    "Provider rejected batched embeddings, retrying sequentially",
                    extra={"input_count": len(inputs)},
                )
                payloads = []
                for chunk in self._chunk_inputs(inputs, 1):
                    chunk_kwargs = {**api_kwargs, "input": chunk}
                    response = self._call_embeddings_with_chunking(
                        chunk_kwargs,
                        chunk,
                    )
                    payloads.append(self._ensure_payload_dict(response))
                return self._combine_embedding_payloads(
                    payloads,
                    api_kwargs.get("model"),
                )
            raise
    def _ensure_payload_dict(self, response: Any) -> dict[str, Any]:
        """Normalize various response types to a dictionary."""
        if isinstance(response, requests.Response):
            return response.json()
        if isinstance(response, (str, bytes)):
            return json.loads(response)
        if isinstance(response, dict):
            return response
        raise TypeError(f"Unsupported response type: {type(response)}")

    def _combine_embedding_payloads(
        self,
        payloads: list[dict[str, Any]],
        default_model: str | None,
    ) -> dict[str, Any]:
        """Combine multiple embedding payloads into a single response."""
        combined_data: list[dict[str, Any]] = []
        prompt_tokens = 0
        total_tokens = 0
        model = default_model

        for payload in payloads:
            combined_data.extend(payload.get("data", []))
            model = payload.get("model", model)
            usage = payload.get("usage")
            if isinstance(usage, dict):
                prompt_tokens += int(usage.get("prompt_tokens") or 0)
                total_tokens += int(usage.get("total_tokens") or 0)

        result: dict[str, Any] = {"data": combined_data}
        if model:
            result["model"] = model
        if prompt_tokens or total_tokens:
            result["usage"] = {
                "prompt_tokens": prompt_tokens,
                "total_tokens": total_tokens or prompt_tokens,
            }
        return result

    @staticmethod
    def _chunk_inputs(
        inputs: Sequence[str],
        chunk_size: int,
    ) -> Generator[list[str], None, None]:
        """Yield list chunks without modifying the original input list."""
        for start in range(0, len(inputs), chunk_size):
            yield list(inputs[start : start + chunk_size])

    def _resolve_max_embed_batch_size(self) -> int:
        """Determine the maximum embed batch size from environment overrides."""
        env_value = os.environ.get("OPENROUTER_EMBED_BATCH_SIZE")
        if not env_value:
            return self.DEFAULT_MAX_EMBED_BATCH_SIZE
        try:
            parsed = int(env_value)
        except (TypeError, ValueError):
            log.warning(
                "Invalid OPENROUTER_EMBED_BATCH_SIZE value: %s. Using default.",
                env_value,
            )
            return self.DEFAULT_MAX_EMBED_BATCH_SIZE
        return parsed if parsed > 0 else self.DEFAULT_MAX_EMBED_BATCH_SIZE

    def parse_embedding_response(self, response: Any) -> EmbedderOutput:
        """Parse the OpenRouter embeddings API response."""
        try:
            if hasattr(response, "json"):
                payload = response.json()
            elif isinstance(response, (str, bytes)):
                payload = json.loads(response)
            elif isinstance(response, dict):
                payload = response
            else:
                raise TypeError(
                    f"Unsupported response type for embeddings: {type(response)}",
                )

            # Check for API errors in the response
            if "error" in payload:
                error_msg = payload["error"]
                if isinstance(error_msg, dict):
                    error_msg = error_msg.get("message", str(error_msg))
                log.error(
                    f"OpenRouter API error in response: {error_msg}",
                    extra={"payload": payload},
                )
                return EmbedderOutput(
                    data=[],
                    error=f"OpenRouter API error: {error_msg}",
                    raw_response=payload,
                )

            usage = None
            usage_payload = payload.get("usage")
            if isinstance(usage_payload, dict):
                prompt_tokens = usage_payload.get("prompt_tokens")
                total_tokens = usage_payload.get("total_tokens")
                if prompt_tokens is not None and total_tokens is not None:
                    usage = Usage(
                        prompt_tokens=prompt_tokens,
                        total_tokens=total_tokens,
                    )

            embeddings: list[Embedding] = []
            data_items = payload.get("data", [])

            if not data_items:
                log.warning(
                    "OpenRouter API returned empty data array",
                    extra={"payload_keys": list(payload.keys())},
                )
                return EmbedderOutput(
                    data=[],
                    error="OpenRouter API returned empty data array",
                    raw_response=payload,
                )

            for idx, item in enumerate(data_items):
                vector = item.get("embedding")
                if vector is None:
                    log.warning(
                        f"Missing embedding vector at index {idx}",
                        extra={
                            "item_keys": list(item.keys())
                            if isinstance(item, dict)
                            else None
                        },
                    )
                    continue
                embeddings.append(
                    Embedding(
                        embedding=vector,
                        index=item.get("index", idx),
                    ),
                )

            if not embeddings:
                log.error(
                    "No valid embeddings found in OpenRouter response",
                    extra={"data_items_count": len(data_items), "payload": payload},
                )
                return EmbedderOutput(
                    data=[],
                    error="No valid embeddings found in OpenRouter response",
                    raw_response=payload,
                )

            return EmbedderOutput(
                data=embeddings,
                model=payload.get("model"),
                usage=usage,
                raw_response=payload,
            )
        except Exception as exc:
            log.exception(f"Failed to parse OpenRouter embedding response: {exc!s}")
            return EmbedderOutput(
                data=[],
                error=str(exc),
                raw_response=response,
            )

    async def acall(  # noqa: PLR0911
        self,
        api_kwargs: dict | None = None,
        model_type: ModelType = None,
    ) -> Any:
        """Make an asynchronous call to the OpenRouter API."""
        if not self.async_client:
            self.async_client = self.init_async_client()

        # Check if API key is set
        if self.async_client is None or not self.async_client.get("api_key"):  # type: ignore[unreachable]
            error_msg = "OPENROUTER_API_KEY not configured. Please set this environment variable to use OpenRouter."
            log.error(error_msg)

            # Instead of raising an exception, return a generator that yields the error message
            # This allows the error to be displayed to the user in the streaming response
            async def error_generator() -> AsyncGenerator[str]:
                yield error_msg

            return error_generator()

        api_kwargs = api_kwargs or {}  # type: ignore[unreachable]

        if model_type == ModelType.LLM:
            # Prepare headers
            # At this point, self.async_client is guaranteed to be not None
            assert self.async_client is not None  # noqa: S101
            headers = {
                "Authorization": f"Bearer {self.async_client['api_key']}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/AsyncFuncAI/deepwiki-open",  # Optional
                "X-Title": "DeepWiki",  # Optional
            }

            # Always use non-streaming mode for OpenRouter
            api_kwargs["stream"] = False

            # Make the API call
            try:
                log.info(
                    "Calling OpenRouter chat completions API at %s",
                    f"{self.async_client['base_url']}/chat/completions",
                )
                log.debug("OpenRouter request headers: %s", headers)
                if log.isEnabledFor(logging.DEBUG):
                    debug_payload = api_kwargs.copy()
                    if "messages" in debug_payload:
                        debug_payload = debug_payload.copy()
                        formatted_messages = []
                        for msg in debug_payload["messages"]:
                            if isinstance(msg, dict):
                                content = msg.get("content")
                                preview_content = (
                                    content[:200]
                                    if isinstance(content, str)
                                    else content
                                )
                                formatted_messages.append(
                                    {**msg, "content": preview_content},
                                )
                            else:
                                formatted_messages.append(msg)
                        debug_payload["messages"] = formatted_messages
                    log.debug("OpenRouter request payload: %s", debug_payload)

                async with aiohttp.ClientSession() as session:
                    from aiohttp import ClientTimeout

                    async with session.post(
                        f"{self.async_client['base_url']}/chat/completions",
                        headers=headers,
                        json=api_kwargs,
                        timeout=ClientTimeout(total=60),
                    ) as response:
                        if response.status != 200:
                            # Handle error response
                            error_text = await response.text()
                            log.error(
                                f"OpenRouter API error ({response.status}): {error_text}",
                            )

                            # Return a generator that yields the error message
                            async def error_response_generator() -> AsyncGenerator[str]:
                                yield f"OpenRouter API error ({response.status}): {error_text}"

                            return error_response_generator()
                        # Get the full response
                        data = await response.json()
                        log.info(f"Received response from OpenRouter: {data}")

                        # Create a generator that yields the content

                    async def content_generator() -> AsyncGenerator[str]:
                        if "choices" in data and len(data["choices"]) > 0:
                            choice = data["choices"][0]
                            if "message" in choice and "content" in choice["message"]:
                                content = choice["message"]["content"]
                                log.info("Successfully retrieved response")

                                # Check if the content is XML and ensure it's properly formatted
                                if content.strip().startswith("<") and ">" in content:
                                    # It's likely XML, let's make sure it's properly formatted
                                    try:
                                        # Extract the XML content
                                        xml_content = content

                                        # Check if it's a wiki_structure XML
                                        if "<wiki_structure>" in xml_content:
                                            log.info(
                                                "Found wiki_structure XML, ensuring proper format",
                                            )

                                            # Extract just the wiki_structure XML
                                            import re

                                            wiki_match = re.search(
                                                r"<wiki_structure>[\s\S]*?<\/wiki_structure>",
                                                xml_content,
                                            )
                                            if wiki_match:
                                                # Get the raw XML
                                                raw_xml = wiki_match.group(0)

                                                # Clean the XML by removing any leading/trailing whitespace
                                                # and ensuring it's properly formatted
                                                clean_xml = raw_xml.strip()

                                                # Try to fix common XML issues
                                                try:
                                                    # Replace problematic characters in XML
                                                    fixed_xml = clean_xml

                                                    # Replace & with &amp; if not already part of an entity
                                                    fixed_xml = re.sub(
                                                        r"&(?!amp;|lt;|gt;|apos;|quot;)",
                                                        "&amp;",
                                                        fixed_xml,
                                                    )

                                                    # Fix other common XML issues
                                                    fixed_xml = fixed_xml.replace(
                                                        "</",
                                                        "</",
                                                    ).replace("  >", ">")

                                                    # Try to parse the fixed XML
                                                    from xml.dom.minidom import (
                                                        parseString,
                                                    )

                                                    dom = parseString(fixed_xml)

                                                    # Get the pretty-printed XML with proper indentation
                                                    pretty_xml = dom.toprettyxml()

                                                    # Remove XML declaration
                                                    if pretty_xml.startswith(
                                                        "<?xml",
                                                    ):
                                                        pretty_xml = pretty_xml[
                                                            pretty_xml.find(
                                                                "?>",
                                                            )
                                                            + 2 :
                                                        ].strip()

                                                    log.info(
                                                        f"Extracted and validated XML: {pretty_xml[:100]}...",
                                                    )
                                                    yield pretty_xml
                                                except Exception as xml_parse_error:
                                                    log.warning(
                                                        f"XML validation failed: {xml_parse_error!s}, using raw XML",
                                                    )

                                                    # If XML validation fails, try a more aggressive approach
                                                    try:
                                                        # Use regex to extract just the structure without any problematic characters
                                                        import re

                                                        # Extract the basic structure
                                                        structure_match = re.search(
                                                            r"<wiki_structure>(.*?)</wiki_structure>",
                                                            clean_xml,
                                                            re.DOTALL,
                                                        )
                                                        if structure_match:
                                                            structure = (
                                                                structure_match.group(
                                                                    1,
                                                                ).strip()
                                                            )

                                                            # Rebuild a clean XML structure
                                                            clean_structure = (
                                                                "<wiki_structure>\n"
                                                            )

                                                            # Extract title
                                                            title_match = re.search(
                                                                r"<title>(.*?)</title>",
                                                                structure,
                                                                re.DOTALL,
                                                            )
                                                            if title_match:
                                                                title = (
                                                                    title_match.group(
                                                                        1,
                                                                    ).strip()
                                                                )
                                                                clean_structure += f"  <title>{title}</title>\n"

                                                            # Extract description
                                                            desc_match = re.search(
                                                                r"<description>(.*?)</description>",
                                                                structure,
                                                                re.DOTALL,
                                                            )
                                                            if desc_match:
                                                                desc = desc_match.group(
                                                                    1,
                                                                ).strip()
                                                                clean_structure += f"  <description>{desc}</description>\n"

                                                            # Add pages section
                                                            clean_structure += (
                                                                "  <pages>\n"
                                                            )

                                                            # Extract pages
                                                            pages = re.findall(
                                                                r'<page id="(.*?)">(.*?)</page>',
                                                                structure,
                                                                re.DOTALL,
                                                            )
                                                            for (
                                                                page_id,
                                                                page_content,
                                                            ) in pages:
                                                                clean_structure += f'    <page id="{page_id}">\n'

                                                                # Extract page title
                                                                page_title_match = re.search(
                                                                    r"<title>(.*?)</title>",
                                                                    page_content,
                                                                    re.DOTALL,
                                                                )
                                                                if page_title_match:
                                                                    page_title = page_title_match.group(
                                                                        1,
                                                                    ).strip()
                                                                    clean_structure += f"      <title>{page_title}</title>\n"

                                                                # Extract page description
                                                                page_desc_match = re.search(
                                                                    r"<description>(.*?)</description>",
                                                                    page_content,
                                                                    re.DOTALL,
                                                                )
                                                                if page_desc_match:
                                                                    page_desc = page_desc_match.group(
                                                                        1,
                                                                    ).strip()
                                                                    clean_structure += f"      <description>{page_desc}</description>\n"

                                                                # Extract importance
                                                                importance_match = re.search(
                                                                    r"<importance>(.*?)</importance>",
                                                                    page_content,
                                                                    re.DOTALL,
                                                                )
                                                                if importance_match:
                                                                    importance = importance_match.group(
                                                                        1,
                                                                    ).strip()
                                                                    clean_structure += f"      <importance>{importance}</importance>\n"

                                                                # Extract relevant files
                                                                clean_structure += "      <relevant_files>\n"
                                                                file_paths = re.findall(
                                                                    r"<file_path>(.*?)</file_path>",
                                                                    page_content,
                                                                    re.DOTALL,
                                                                )
                                                                for (
                                                                    file_path
                                                                ) in file_paths:
                                                                    clean_structure += f"        <file_path>{file_path.strip()}</file_path>\n"
                                                                clean_structure += "      </relevant_files>\n"

                                                                # Extract related pages
                                                                clean_structure += "      <related_pages>\n"
                                                                related_pages = re.findall(
                                                                    r"<related>(.*?)</related>",
                                                                    page_content,
                                                                    re.DOTALL,
                                                                )
                                                                for (
                                                                    related
                                                                ) in related_pages:
                                                                    clean_structure += f"        <related>{related.strip()}</related>\n"
                                                                clean_structure += "      </related_pages>\n"

                                                                clean_structure += (
                                                                    "    </page>\n"
                                                                )

                                                            clean_structure += "  </pages>\n</wiki_structure>"

                                                            log.info(
                                                                "Successfully rebuilt clean XML structure",
                                                            )
                                                            yield clean_structure
                                                        else:
                                                            log.warning(
                                                                "Could not extract wiki structure, using raw XML",
                                                            )
                                                            yield clean_xml
                                                    except Exception as rebuild_error:
                                                        log.warning(
                                                            f"Failed to rebuild XML: {rebuild_error!s}, using raw XML",
                                                        )
                                                        yield clean_xml
                                            else:
                                                # If we can't extract it, just yield the original content
                                                log.warning(
                                                    "Could not extract wiki_structure XML, yielding original content",
                                                )
                                                yield xml_content
                                        else:
                                            # For other XML content, just yield it as is
                                            yield content
                                    except Exception as xml_error:
                                        log.exception(
                                            f"Error processing XML content: {xml_error!s}",
                                        )
                                        yield content
                                else:
                                    # Not XML, just yield the content
                                    yield content
                            else:
                                log.error(f"Unexpected response format: {data}")
                                yield "Error: Unexpected response format from OpenRouter API"
                        else:
                            log.error(f"No choices in response: {data}")
                            yield "Error: No response content from OpenRouter API"

                    return content_generator()
            except aiohttp.ClientError as e:
                e_client = e
                log.exception(
                    f"Connection error with OpenRouter API: {e_client!s}",
                )

                # Return a generator that yields the error message
                async def connection_error_generator() -> AsyncGenerator[str]:
                    yield f"Connection error with OpenRouter API: {e_client!s}. Please check your internet connection and that the OpenRouter API is accessible."

                return connection_error_generator()
            except RequestException as e:
                e_req = e
                log.exception(f"Error calling OpenRouter API asynchronously: {e_req!s}")

                # Return a generator that yields the error message
                async def request_error_generator() -> AsyncGenerator[str]:
                    yield f"Error calling OpenRouter API: {e_req!s}"

                return request_error_generator()
            except Exception as e:
                e_unexp = e
                log.exception(
                    f"Unexpected error calling OpenRouter API asynchronously: {e_unexp!s}",
                )

                # Return a generator that yields the error message
                async def unexpected_error_generator() -> AsyncGenerator[str]:
                    yield f"Unexpected error calling OpenRouter API: {e_unexp!s}"

                return unexpected_error_generator()
        else:
            error_msg = f"Unsupported model type: {model_type}"
            log.error(error_msg)

            # Return a generator that yields the error message
            async def model_type_error_generator() -> AsyncGenerator[str]:
                yield error_msg

            return model_type_error_generator()

    def _process_completion_response(self, data: dict) -> GeneratorOutput:
        """Process a non-streaming completion response from OpenRouter."""
        try:
            # Extract the completion text from the response
            if not data.get("choices"):

                def _raise_value_error() -> None:
                    raise ValueError(f"No choices in OpenRouter response: {data}")  # noqa: TRY301

                _raise_value_error()

            choice = data["choices"][0]

            if "message" in choice:
                content = choice["message"].get("content", "")
            elif "text" in choice:
                content = choice.get("text", "")
            else:

                def _raise_value_error() -> None:
                    raise ValueError(  # noqa: TRY301
                        f"Unexpected response format from OpenRouter: {choice}",
                    )

                _raise_value_error()

            # Extract usage information if available
            usage = None
            if "usage" in data:
                usage = CompletionUsage(
                    prompt_tokens=data["usage"].get("prompt_tokens", 0),
                    completion_tokens=data["usage"].get("completion_tokens", 0),
                    total_tokens=data["usage"].get("total_tokens", 0),
                )

            # Create and return the GeneratorOutput
            return GeneratorOutput(data=content, usage=usage, raw_response=data)

        except Exception as e_proc:
            log.exception(
                f"Error processing OpenRouter completion response: {e_proc!s}",
            )
            raise

    def _process_streaming_response(self, response: Any) -> Generator[str]:
        """Process a streaming response from OpenRouter."""
        try:
            log.info("Starting to process streaming response from OpenRouter")
            buffer = ""

            for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
                try:
                    # Add chunk to buffer
                    buffer += chunk

                    # Process complete lines in the buffer
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()

                        if not line:
                            continue

                        log.debug(f"Processing line: {line}")

                        # Skip SSE comments (lines starting with :)
                        if line.startswith(":"):
                            log.debug(f"Skipping SSE comment: {line}")
                            continue

                        if line.startswith("data: "):
                            data = line[6:]  # Remove "data: " prefix

                            # Check for stream end
                            if data == "[DONE]":
                                log.info("Received [DONE] marker")
                                break

                            try:
                                data_obj = json.loads(data)
                                log.debug(f"Parsed JSON data: {data_obj}")

                                # Extract content from delta
                                if (
                                    "choices" in data_obj
                                    and len(data_obj["choices"]) > 0
                                ):
                                    choice = data_obj["choices"][0]

                                    if (
                                        "delta" in choice
                                        and "content" in choice["delta"]
                                        and choice["delta"]["content"]
                                    ):
                                        content = choice["delta"]["content"]
                                        log.debug(f"Yielding delta content: {content}")
                                        yield content
                                    elif "text" in choice:
                                        log.debug(
                                            f"Yielding text content: {choice['text']}",
                                        )
                                        yield choice["text"]
                                    else:
                                        log.debug(
                                            f"No content found in choice: {choice}",
                                        )
                                else:
                                    log.debug(f"No choices found in data: {data_obj}")

                            except json.JSONDecodeError:
                                log.warning(f"Failed to parse SSE data: {data}")
                                continue
                except Exception as e_chunk:
                    log.exception(f"Error processing streaming chunk: {e_chunk!s}")
                    yield f"Error processing response chunk: {e_chunk!s}"
        except Exception as e_stream:
            log.exception(f"Error in streaming response: {e_stream!s}")
            yield f"Error in streaming response: {e_stream!s}"

    async def _process_async_streaming_response(
        self,
        response: Any,
    ) -> AsyncGenerator[str]:
        """Process an asynchronous streaming response from OpenRouter."""
        buffer = ""
        try:
            log.info("Starting to process async streaming response from OpenRouter")
            async for chunk in response.content:
                try:
                    # Convert bytes to string and add to buffer
                    if isinstance(chunk, bytes):
                        chunk_str = chunk.decode("utf-8")
                    else:
                        chunk_str = str(chunk)

                    buffer += chunk_str

                    # Process complete lines in the buffer
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()

                        if not line:
                            continue

                        log.debug(f"Processing line: {line}")

                        # Skip SSE comments (lines starting with :)
                        if line.startswith(":"):
                            log.debug(f"Skipping SSE comment: {line}")
                            continue

                        if line.startswith("data: "):
                            data = line[6:]  # Remove "data: " prefix

                            # Check for stream end
                            if data == "[DONE]":
                                log.info("Received [DONE] marker")
                                break

                            try:
                                data_obj = json.loads(data)
                                log.debug(f"Parsed JSON data: {data_obj}")

                                # Extract content from delta
                                if (
                                    "choices" in data_obj
                                    and len(data_obj["choices"]) > 0
                                ):
                                    choice = data_obj["choices"][0]

                                    if (
                                        "delta" in choice
                                        and "content" in choice["delta"]
                                        and choice["delta"]["content"]
                                    ):
                                        content = choice["delta"]["content"]
                                        log.debug(f"Yielding delta content: {content}")
                                        yield content
                                    elif "text" in choice:
                                        log.debug(
                                            f"Yielding text content: {choice['text']}",
                                        )
                                        yield choice["text"]
                                    else:
                                        log.debug(
                                            f"No content found in choice: {choice}",
                                        )
                                else:
                                    log.debug(f"No choices found in data: {data_obj}")

                            except json.JSONDecodeError:
                                log.warning(f"Failed to parse SSE data: {data}")
                                continue
                except Exception as e_chunk:
                    log.exception(f"Error processing streaming chunk: {e_chunk!s}")
                    yield f"Error processing response chunk: {e_chunk!s}"
        except Exception as e_stream:
            log.exception(f"Error in async streaming response: {e_stream!s}")
            yield f"Error in streaming response: {e_stream!s}"
