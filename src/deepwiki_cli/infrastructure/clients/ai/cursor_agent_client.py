"""Cursor Agent ModelClient integration."""

import json
import logging
import subprocess
from typing import Any, Literal, Self

import backoff
from adalflow.core.model_client import ModelClient
from adalflow.core.types import (
    GeneratorOutput,
    ModelType,
)
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice

log = logging.getLogger(__name__)


class CursorAgentClient(ModelClient):
    __doc__ = r"""A component wrapper for the Cursor Agent CLI.

    This client executes the `cursor-agent` CLI command to generate responses.
    It supports both text and structured output (via prompt engineering).

    Args:
        model (str, optional): The model to use (e.g., 'gpt-4o', 'claude-3.5-sonnet').
            Defaults to None (uses CLI default).
    """

    def __init__(
        self,
        model: str | None = None,
    ) -> None:
        super().__init__()
        self.model = model
        self._api_kwargs: dict[str, Any] = {}

    def _build_command(self, prompt: str, model_kwargs: dict[str, Any]) -> list[str]:
        """Build the cursor-agent command line arguments."""
        cmd = ["cursor-agent", "-p"]  # Always use print mode for headless execution

        # Add model if specified
        model = model_kwargs.get("model", self.model)
        if model:
            cmd.extend(["--model", model])

        # Add force flag if specified (default to False for safety, but can be overridden)
        if model_kwargs.get("force", False):
            cmd.append("--force")

        # Add output format (default to text, but can be json)
        output_format = model_kwargs.get("output_format", "text")
        cmd.extend(["--output-format", output_format])

        # Add other flags as needed
        if model_kwargs.get("approve_mcps", False):
            cmd.append("--approve-mcps")
            
        if model_kwargs.get("browser", False):
            cmd.append("--browser")

        # Add the prompt as the last argument
        cmd.append(prompt)
        return cmd

    def call(
        self,
        api_kwargs: dict | None = None,
        model_type: ModelType = ModelType.UNDEFINED,
    ) -> ChatCompletion | GeneratorOutput:
        """Execute the cursor-agent command."""
        if api_kwargs is None:
            api_kwargs = {}
        self._api_kwargs = api_kwargs

        if model_type != ModelType.LLM:
            raise ValueError(f"CursorAgentClient only supports LLM model type, got {model_type}")

        # Extract messages to build prompt
        messages = api_kwargs.get("messages", [])
        if not messages:
            raise ValueError("No messages provided for CursorAgentClient")

        # Convert messages to a single prompt string
        # Cursor Agent CLI takes a single prompt argument
        # We'll concatenate messages, but ideally the last user message is the prompt
        # and previous messages are context.
        # For now, let's just join them with newlines, or take the last one if it's a simple query.
        # A better approach might be to format them as a chat transcript if the agent supports it,
        # but the CLI help says "Initial prompt for the agent".
        
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
            else:
                prompt_parts.append(f"{role}: {content}")
        
        # If it's just a single user message, use it directly to avoid "User:" prefix confusion
        if len(messages) == 1 and messages[0].get("role") == "user":
            prompt = messages[0].get("content", "")
        else:
            prompt = "\n\n".join(prompt_parts)

        cmd = self._build_command(prompt, api_kwargs)
        log.info(f"Executing cursor-agent command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,  # We'll handle return codes manually
            )

            if result.returncode != 0:
                error_msg = f"Cursor Agent CLI failed with code {result.returncode}: {result.stderr}"
                log.error(error_msg)
                raise RuntimeError(error_msg)

            response_text = result.stdout.strip()
            
            # If output format is JSON, we might need to parse it, but for now we return text
            # The Generator component expects a ChatCompletion object or similar
            
            return ChatCompletion(
                id="cursor-agent-response",
                model=api_kwargs.get("model", "cursor-agent"),
                created=0,
                object="chat.completion",
                choices=[
                    Choice(
                        index=0,
                        finish_reason="stop",
                        message=ChatCompletionMessage(
                            content=response_text,
                            role="assistant",
                        ),
                    ),
                ],
                usage=CompletionUsage(
                    completion_tokens=0, # We don't get usage stats from CLI
                    prompt_tokens=0,
                    total_tokens=0,
                )
            )

        except Exception as e:
            log.exception(f"Error executing cursor-agent: {e}")
            raise

    async def acall(self, api_kwargs: dict | None = None, model_type: ModelType = ModelType.UNDEFINED):
        """Async call - just wraps sync call for now since subprocess is blocking."""
        # In a real async implementation we'd use asyncio.create_subprocess_exec
        return self.call(api_kwargs, model_type)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(model=data.get("model"))

    def to_dict(self) -> dict[str, Any]:
        return {"model": self.model}
