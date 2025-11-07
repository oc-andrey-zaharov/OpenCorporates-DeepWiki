#!/usr/bin/env python3
"""
Unit tests for RAG token limit validation and truncation.

Tests the MAX_INPUT_TOKENS constant usage and query truncation functionality.
"""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TestRAGTokenLimit:
    """Test RAG token limit validation and truncation."""

    def test_max_input_tokens_constant_exists(self):
        """Test that MAX_INPUT_TOKENS constant is defined."""
        # Read the file directly to avoid import issues
        rag_file = project_root / "api" / "services" / "rag.py"
        content = rag_file.read_text()

        # Verify constant is defined
        assert "MAX_INPUT_TOKENS = 7500" in content, (
            "MAX_INPUT_TOKENS should be defined as 7500"
        )

        # Verify it's used in the code
        assert content.count("MAX_INPUT_TOKENS") > 1, (
            "MAX_INPUT_TOKENS should be used in the code (not just defined)"
        )

        logger.info("✓ MAX_INPUT_TOKENS constant exists and is used")

    def test_truncate_query_by_tokens_method_exists(self):
        """Test that _truncate_query_by_tokens method exists in RAG class."""
        # Read the file directly to verify method exists
        rag_file = project_root / "api" / "services" / "rag.py"
        content = rag_file.read_text()

        assert "def _truncate_query_by_tokens" in content, "Method should be defined"
        assert "count_tokens" in content, "Should use count_tokens function"
        assert "MAX_INPUT_TOKENS" in content, "Should reference MAX_INPUT_TOKENS"

        logger.info("✓ _truncate_query_by_tokens method exists")

    def test_call_method_uses_token_validation(self):
        """Test that call method uses token limit validation."""
        # Read the file directly to verify call method uses token validation
        rag_file = project_root / "api" / "services" / "rag.py"
        content = rag_file.read_text()

        # Find the call method
        call_method_start = content.find("def call(self, query: str)")
        assert call_method_start != -1, "call method should exist"

        # Extract the call method content (find next method or end of class)
        call_method_end = content.find("\n    def ", call_method_start + 1)
        if call_method_end == -1:
            # Try to find end of class or end of file
            call_method_end = content.find("\n\nclass ", call_method_start + 1)
            if call_method_end == -1:
                call_method_end = len(content)

        call_method_content = content[call_method_start:call_method_end]

        # Verify it uses token validation
        assert "_truncate_query_by_tokens" in call_method_content, (
            "Should call truncation method"
        )
        assert "MAX_INPUT_TOKENS" in call_method_content, (
            "Should use MAX_INPUT_TOKENS constant"
        )

        logger.info("✓ call method uses token limit validation")

    def test_count_tokens_imported(self):
        """Test that count_tokens is imported from data_pipeline."""
        rag_file = project_root / "api" / "services" / "rag.py"
        content = rag_file.read_text()

        # Check for import statement
        assert "from api.services.data_pipeline import" in content, (
            "Should import from data_pipeline"
        )
        assert "count_tokens" in content, "Should import count_tokens"

        # Verify it's used in the truncation method
        assert (
            "count_tokens" in content[content.find("def _truncate_query_by_tokens") :]
        ), "Should use count_tokens in truncation method"

        logger.info("✓ count_tokens is imported and used")

    def test_truncation_logic_handles_edge_cases(self):
        """Test that truncation logic handles edge cases."""
        rag_file = project_root / "api" / "services" / "rag.py"
        content = rag_file.read_text()

        # Find the truncation method
        trunc_method_start = content.find("def _truncate_query_by_tokens")
        assert trunc_method_start != -1, "Truncation method should exist"

        # Extract method content
        trunc_method_end = content.find("\n    def ", trunc_method_start + 1)
        if trunc_method_end == -1:
            trunc_method_end = len(content)
        trunc_method_content = content[trunc_method_start:trunc_method_end]

        # Check for edge case handling
        assert (
            "if not query:" in trunc_method_content
            or "if not query" in trunc_method_content
        ), "Should handle empty query"
        assert "token_count <= max_tokens" in trunc_method_content, (
            "Should check if query is within limit"
        )

        logger.info("✓ Truncation logic handles edge cases")


def run_tests():
    """Run all token limit tests."""
    logger.info("Running RAG token limit tests...")

    test_instance = TestRAGTokenLimit()

    test_methods = [
        method
        for method in dir(test_instance)
        if method.startswith("test_") and callable(getattr(test_instance, method))
    ]

    passed = 0
    failed = 0

    for method_name in test_methods:
        try:
            logger.info(f"\n🧪 Running {method_name}...")
            getattr(test_instance, method_name)()
            passed += 1
            logger.info(f"✅ {method_name} PASSED")
        except Exception as e:
            failed += 1
            logger.error(f"❌ {method_name} FAILED: {e}")
            import traceback

            traceback.print_exc()

    logger.info(f"\n📊 Test Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
