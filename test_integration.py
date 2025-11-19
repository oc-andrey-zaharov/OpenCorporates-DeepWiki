
import sys
import os
import asyncio
from unittest.mock import patch, MagicMock
from typing import AsyncGenerator

# Add src to path
sys.path.append(os.path.abspath("src"))

# Mock langfuse before importing generate_content
sys.modules["langfuse"] = MagicMock()
sys.modules["langfuse.decorators"] = MagicMock()

# Mock observe decorator
mock_observe = MagicMock()
def observe_decorator(*args, **kwargs):
    def wrapper(func):
        return func
    return wrapper
mock_observe.side_effect = observe_decorator
sys.modules["langfuse"].observe = observe_decorator

# Mock returns module
mock_returns = MagicMock()
mock_returns.result = MagicMock()
class MockResult:
    def value_or(self, default):
        return default
mock_returns.result.Result = MockResult
mock_returns.result.Success = lambda x: MagicMock(value_or=lambda d: x, unwrap=lambda: x)
mock_returns.result.Failure = lambda x: MagicMock(value_or=lambda d: d)
sys.modules["returns"] = mock_returns
sys.modules["returns.result"] = mock_returns.result

from deepwiki_cli.application.wiki.generate_content import generate_wiki_content
from deepwiki_cli.infrastructure.clients.ai.cursor_agent_client import CursorAgentClient
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types import CompletionUsage

# Mock RAG to avoid database operations
@patch("deepwiki_cli.application.wiki.generate_content.RAG")
@patch("deepwiki_cli.application.wiki.generate_content.CursorAgentClient")
def test_generate_content_integration(MockCursorAgentClient, MockRAG):
    print("Testing generate_wiki_content with cursor-agent...")
    
    # Setup Mock RAG
    mock_rag_instance = MagicMock()
    MockRAG.return_value = mock_rag_instance
    
    # Setup Mock Client
    mock_client_instance = MagicMock()
    MockCursorAgentClient.return_value = mock_client_instance
    
    # Mock acall response
    async def mock_acall(*args, **kwargs):
        return ChatCompletion(
            id="test-id",
            model="test-model",
            created=0,
            object="chat.completion",
            choices=[
                Choice(
                    index=0,
                    finish_reason="stop",
                    message=ChatCompletionMessage(
                        content="Generated content from cursor-agent",
                        role="assistant",
                    ),
                ),
            ],
            usage=CompletionUsage(completion_tokens=10, prompt_tokens=5, total_tokens=15)
        )
    
    mock_client_instance.acall.side_effect = mock_acall
    
    # Mock call_structured to return None so it falls back to standard call
    # Or we can mock it to raise AttributeError to simulate not having it, 
    # but the code checks hasattr.
    # Since CursorAgentClient inherits from ModelClient, it might have it.
    # Let's just ensure the fallback path is taken by not mocking call_structured 
    # or making it return None if called.
    
    # Run generation
    messages = [{"role": "user", "content": "Test query"}]
    generator = generate_wiki_content(
        repo_url="https://github.com/test/repo",
        messages=messages,
        provider="cursor-agent",
        model="gpt-4o",
        repo_type="github"
    )
    
    # Consume generator
    output = []
    try:
        for chunk in generator:
            print(f"Received chunk: {chunk}")
            output.append(chunk)
    except Exception as e:
        print(f"❌ Error during generation: {e}")
        raise
        
    full_output = "".join(output)
    print(f"Full output: {full_output}")
    
    assert "Generated content from cursor-agent" in full_output
    print("✅ Integration test passed")

if __name__ == "__main__":
    test_generate_content_integration()
