"""Performance tests for critical operations.

These tests verify that operations complete within acceptable time limits.
"""

import time

import pytest

from deepwiki_cli.services.data_pipeline import count_tokens, count_tokens_batch


@pytest.mark.performance
class TestTokenCountingPerformance:
    """Performance tests for token counting operations."""

    def test_count_tokens_small_text(self) -> None:
        """Test token counting performance on small text."""
        text = "This is a test string with some words."
        start_time = time.time()
        result = count_tokens(text)
        elapsed = time.time() - start_time

        assert isinstance(result, int)
        assert result > 0
        # Should complete in under 100ms
        assert elapsed < 0.1, f"Token counting took {elapsed}s, expected < 0.1s"

    def test_count_tokens_large_text(self) -> None:
        """Test token counting performance on large text."""
        text = "word " * 10000  # ~50k characters
        start_time = time.time()
        result = count_tokens(text)
        elapsed = time.time() - start_time

        assert isinstance(result, int)
        assert result > 0
        # Should complete in under 1 second
        assert elapsed < 1.0, f"Token counting took {elapsed}s, expected < 1.0s"

    def test_count_tokens_batch_performance(self) -> None:
        """Test batch token counting performance."""
        texts = [f"Text number {i} with some content." for i in range(100)]
        start_time = time.time()
        results = count_tokens_batch(texts)
        elapsed = time.time() - start_time

        assert len(results) == len(texts)
        assert all(isinstance(r, int) for r in results)
        # Batch should be faster than sequential (rough heuristic)
        assert elapsed < 2.0, f"Batch counting took {elapsed}s, expected < 2.0s"
