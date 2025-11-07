import logging
import os
from typing import List, Optional
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


# Configure logging
from api.logging_config import setup_logging
from api.core.chat import generate_chat_completion_core

setup_logging()
logger = logging.getLogger(__name__)


def _is_truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.lower() in {"1", "true", "yes", "on"}


OPENAI_STREAMING_ENABLED = _is_truthy(os.environ.get("OPENAI_STREAMING_ENABLED"))


def _extract_chat_completion_text(completion) -> Optional[str]:
    try:
        choices = getattr(completion, "choices", [])
        if choices:
            first_choice = choices[0]
            message = getattr(first_choice, "message", None)
            if message and hasattr(message, "content"):
                return message.content
            delta = getattr(first_choice, "delta", None)
            if delta and hasattr(delta, "content"):
                return delta.content
        return getattr(completion, "content", None)
    except Exception as exc:
        logger.warning(f"Failed to extract text from completion: {exc}")
        return None


# Initialize FastAPI app
app = FastAPI(
    title="Simple Chat API", description="Simplified API for streaming chat completions"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


# Models for the API
class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str


class ChatCompletionRequest(BaseModel):
    """
    Model for requesting a chat completion.
    """

    repo_url: str = Field(..., description="URL of the repository to query")
    messages: List[ChatMessage] = Field(..., description="List of chat messages")
    filePath: Optional[str] = Field(
        None,
        description="Optional path to a file in the repository to include in the prompt",
    )
    token: Optional[str] = Field(
        None, description="Personal access token for private repositories"
    )
    type: Optional[str] = Field("github", description="Type of repository (GitHub)")

    # model parameters
    provider: str = Field(
        "google",
        description="Model provider (google, openai, openrouter, ollama, bedrock, azure)",
    )
    model: Optional[str] = Field(
        None, description="Model name for the specified provider"
    )

    language: Optional[str] = Field(
        "en", description="Language for content generation (e.g., 'en')"
    )
    excluded_dirs: Optional[str] = Field(
        None,
        description="Comma-separated list of directories to exclude from processing",
    )
    excluded_files: Optional[str] = Field(
        None,
        description="Comma-separated list of file patterns to exclude from processing",
    )
    included_dirs: Optional[str] = Field(
        None, description="Comma-separated list of directories to include exclusively"
    )
    included_files: Optional[str] = Field(
        None, description="Comma-separated list of file patterns to include exclusively"
    )


@app.post("/chat/completions/stream")
async def chat_completions_stream(request: ChatCompletionRequest):
    """Stream a chat completion response using core chat completion logic."""
    try:
        # Convert Pydantic models to dict format for core function
        messages = [
            {"role": msg.role, "content": msg.content} for msg in request.messages
        ]

        # Extract custom file filter parameters if provided
        excluded_dirs = None
        excluded_files = None
        included_dirs = None
        included_files = None

        if request.excluded_dirs:
            excluded_dirs = [
                unquote(dir_path)
                for dir_path in request.excluded_dirs.split("\n")
                if dir_path.strip()
            ]
            logger.info(f"Using custom excluded directories: {excluded_dirs}")
        if request.excluded_files:
            excluded_files = [
                unquote(file_pattern)
                for file_pattern in request.excluded_files.split("\n")
                if file_pattern.strip()
            ]
            logger.info(f"Using custom excluded files: {excluded_files}")
        if request.included_dirs:
            included_dirs = [
                unquote(dir_path)
                for dir_path in request.included_dirs.split("\n")
                if dir_path.strip()
            ]
            logger.info(f"Using custom included directories: {included_dirs}")
        if request.included_files:
            included_files = [
                unquote(file_pattern)
                for file_pattern in request.included_files.split("\n")
                if file_pattern.strip()
            ]
            logger.info(f"Using custom included files: {included_files}")

        # Call core function to get sync generator
        sync_gen = generate_chat_completion_core(
            repo_url=request.repo_url,
            messages=messages,
            provider=request.provider,
            model=request.model or "",
            repo_type=request.type or "github",
            token=request.token,
            excluded_dirs=excluded_dirs,
            excluded_files=excluded_files,
            included_dirs=included_dirs,
            included_files=included_files,
            file_path=request.filePath,
        )

        # Convert sync generator to async generator for FastAPI StreamingResponse
        async def async_stream():
            for chunk in sync_gen:
                yield chunk

        # Return streaming response
        return StreamingResponse(async_stream(), media_type="text/event-stream")

    except ValueError as e:
        error_msg = str(e)
        if "No valid documents with embeddings found" in error_msg:
            raise HTTPException(
                status_code=500,
                detail="No valid document embeddings found. This may be due to embedding size inconsistencies or API errors during document processing. Please try again or check your repository content.",
            )
        elif "Inconsistent embedding sizes" in error_msg:
            raise HTTPException(
                status_code=500,
                detail="Inconsistent embedding sizes detected. Some documents may have failed to embed properly. Please try again.",
            )
        elif "No messages provided" in error_msg:
            raise HTTPException(status_code=400, detail=error_msg)
        elif "Last message must be from the user" in error_msg:
            raise HTTPException(status_code=400, detail=error_msg)
        else:
            raise HTTPException(status_code=500, detail=error_msg)
    except HTTPException:
        raise
    except Exception as e_handler:
        error_msg = f"Error in streaming chat completion: {str(e_handler)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/")
async def root():
    """Root endpoint to check if the API is running"""
    return {
        "status": "API is running",
        "message": "Navigate to /docs for API documentation",
    }
