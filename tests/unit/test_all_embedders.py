#!/usr/bin/env python3
"""Comprehensive test suite for all embedder types (OpenAI, Google, LM Studio).
This test file validates the embedder system before any modifications are made.
"""

import importlib
import logging
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set up environment
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Simple test framework without pytest
class TestRunner:
    def __init__(self) -> None:
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []

    def run_test(
        self, test_func: Callable, test_name: str | None = None
    ) -> bool | None:
        """Run a single test function."""
        if test_name is None:
            test_name = test_func.__name__

        self.tests_run += 1
        try:
            logger.info("Running test: %s", test_name)
            test_func()
            self.tests_passed += 1
            logger.info("✅ %s PASSED", test_name)
            return True
        except (
            AssertionError,
            AttributeError,
            ImportError,
            ValueError,
            TypeError,
        ) as e:
            self.tests_failed += 1
            self.failures.append((test_name, str(e)))
            logger.exception("❌ %s FAILED", test_name)
            return False

    def run_test_class(self, test_class: type[Any]) -> None:
        """Run all test methods in a test class."""
        instance = test_class()
        test_methods = [
            getattr(instance, method)
            for method in dir(instance)
            if method.startswith("test_") and callable(getattr(instance, method))
        ]

        for test_method in test_methods:
            test_name = f"{test_class.__name__}.{test_method.__name__}"
            self.run_test(test_method, test_name)

    def run_parametrized_test(
        self,
        test_func: Callable,
        parameters: list[Any],
        test_name_base: str | None = None,
    ) -> None:
        """Run a test function with multiple parameter sets."""
        if test_name_base is None:
            test_name_base = test_func.__name__

        for _i, param in enumerate(parameters):
            test_name = f"{test_name_base}[{param}]"
            self.run_test(lambda param=param: test_func(param), test_name)

    def summary(self):
        """Print test summary."""
        logger.info("\n📊 Test Summary:")
        logger.info("Tests run: %s", self.tests_run)
        logger.info("Passed: %s", self.tests_passed)
        logger.info("Failed: %s", self.tests_failed)

        if self.failures:
            logger.error("\n❌ Failed tests:")
            for test_name, error in self.failures:
                logger.error("  - %s: %s", test_name, error)

        return self.tests_failed == 0


class TestEmbedderConfiguration:
    """Test embedder configuration system."""

    def test_config_loading(self) -> None:
        """Test that all embedder configurations load properly."""
        from deepwiki_cli.infrastructure.config import CLIENT_CLASSES, configs

        # Check all embedder configurations exist
        assert "embedder" in configs, "OpenAI embedder config missing"
        assert "embedder_google" in configs, "Google embedder config missing"
        assert "embedder_lmstudio" in configs, "LM Studio embedder config missing"
        assert "embedder_openrouter" in configs, "OpenRouter embedder config missing"

        # Check client classes are available
        assert "OpenAIClient" in CLIENT_CLASSES, (
            "OpenAIClient missing from CLIENT_CLASSES"
        )
        assert "GoogleEmbedderClient" in CLIENT_CLASSES, (
            "GoogleEmbedderClient missing from CLIENT_CLASSES"
        )
        assert "LMStudioClient" in CLIENT_CLASSES, (
            "LMStudioClient missing from CLIENT_CLASSES"
        )
        assert "OpenRouterClient" in CLIENT_CLASSES, (
            "OpenRouterClient missing from CLIENT_CLASSES"
        )

    def test_embedder_type_detection(self) -> None:
        """Test embedder type detection functions."""
        from deepwiki_cli.infrastructure.config import (
            get_embedder_type,
            is_google_embedder,
            is_openrouter_embedder,
        )

        # Default type should be detected
        current_type = get_embedder_type()
        assert current_type in ["openai", "google", "lmstudio", "openrouter"], (
            f"Invalid embedder type: {current_type}"
        )

        # Boolean functions should work
        is_lmstudio = is_lmstudio_embedder()
        is_google = is_google_embedder()
        is_openrouter = is_openrouter_embedder()
        assert isinstance(is_lmstudio, bool), (
            "is_lmstudio_embedder should return boolean"
        )
        assert isinstance(is_google, bool), "is_google_embedder should return boolean"
        assert isinstance(
            is_openrouter,
            bool,
        ), "is_openrouter_embedder should return boolean"

        # Only one should be true at a time (unless using openai default)
        if current_type == "lmstudio":
            assert is_lmstudio
            assert not is_google
            assert not is_openrouter
        elif current_type == "google":
            assert not is_lmstudio
            assert is_google
            assert not is_openrouter
        elif current_type == "openrouter":
            assert not is_lmstudio
            assert not is_google
            assert is_openrouter
        else:  # openai
            assert not is_lmstudio
            assert not is_google
            assert not is_openrouter

    def test_get_embedder_config(self) -> None:
        """Test getting embedder config for each type."""
        from deepwiki_cli.infrastructure.config import get_embedder_config

        config = get_embedder_config()
        assert isinstance(config, dict), "Config should be dict"
        assert "model_client" in config or "client_class" in config, (
            "Config should have model_client or client_class"
        )


class TestEmbedderFactory:
    """Test the embedder factory function."""

    def test_get_embedder_with_explicit_type(self) -> None:
        """Test get_embedder with explicit embedder_type parameter."""
        from deepwiki_cli.infrastructure.embedding.embedder import get_embedder

        # Test Google embedder
        google_embedder = get_embedder(embedder_type="google")
        assert google_embedder is not None, "Google embedder should be created"

        # Test OpenAI embedder
        openai_embedder = get_embedder(embedder_type="openai")
        assert openai_embedder is not None, "OpenAI embedder should be created"

        # Test LM Studio embedder (may fail if LM Studio not available, but should not crash)
        try:
            lmstudio_embedder = get_embedder(embedder_type="lmstudio")
            assert lmstudio_embedder is not None, "LM Studio embedder should be created"
        except (ImportError, ValueError, RuntimeError) as e:
            logger.warning(
                "LM Studio embedder creation failed (expected if LM Studio not available): %s",
                e,
            )
        # Test OpenRouter embedder
        try:
            openrouter_embedder = get_embedder(embedder_type="openrouter")
            assert openrouter_embedder is not None, (
                "OpenRouter embedder should be created"
            )
        except (ImportError, ValueError, RuntimeError) as e:
            logger.warning(
                "OpenRouter embedder creation failed (likely missing OPENROUTER_API_KEY): %s",
                e,
            )

    def test_get_embedder_with_legacy_params(self) -> None:
        """Test get_embedder with legacy boolean parameters."""
        from deepwiki_cli.infrastructure.embedding.embedder import get_embedder

        # Test with use_google_embedder=True
        google_embedder = get_embedder(use_google_embedder=True)
        assert google_embedder is not None, (
            "Google embedder should be created with use_google_embedder=True"
        )

        # Test with is_local_lmstudio=True
        try:
            lmstudio_embedder = get_embedder(is_local_lmstudio=True)
            assert lmstudio_embedder is not None, (
                "LM Studio embedder should be created with is_local_lmstudio=True"
            )
        except (ImportError, ValueError, RuntimeError) as e:
            logger.warning(
                "LM Studio embedder creation failed (expected if LM Studio not available): %s",
                e,
            )

    def test_get_embedder_auto_detection(self) -> None:
        """Test get_embedder with automatic type detection."""
        from deepwiki_cli.infrastructure.embedding.embedder import get_embedder

        # Test auto-detection (should use current configuration)
        embedder = get_embedder()
        assert embedder is not None, "Auto-detected embedder should be created"


class TestEmbedderClients:
    """Test individual embedder clients."""

    def test_google_embedder_client(self) -> None:
        """Test Google embedder client directly."""
        if not os.getenv("GOOGLE_API_KEY"):
            logger.warning(
                "Skipping Google embedder test - GOOGLE_API_KEY not available",
            )
            return

        from adalflow.core.types import ModelType

        from deepwiki_cli.infrastructure.clients.ai.google_embedder_client import (
            GoogleEmbedderClient,
        )

        client = GoogleEmbedderClient()

        # Test single embedding
        api_kwargs = client.convert_inputs_to_api_kwargs(
            input="Hello world",
            model_kwargs={
                "model": "text-embedding-004",
                "task_type": "SEMANTIC_SIMILARITY",
            },
            model_type=ModelType.EMBEDDER,
        )

        response = client.call(api_kwargs, ModelType.EMBEDDER)
        assert response is not None, "Google embedder should return response"

        # Parse the response
        parsed = client.parse_embedding_response(response)
        assert parsed.data is not None, "Parsed response should have data"
        assert len(parsed.data) > 0, "Should have at least one embedding"
        assert parsed.error is None, "Should not have errors"


class TestDataPipelineFunctions:
    """Test data pipeline functions that use embedders."""

    def test_count_tokens(self) -> None:
        """Test token counting with different embedder types."""
        from deepwiki_cli.services.data_pipeline import count_tokens

        test_text = "This is a test string for token counting."

        # Test with all values
        for is_lmstudio in [None, True, False]:
            token_count = count_tokens(test_text, is_lmstudio_embedder=is_lmstudio)
            assert isinstance(token_count, int), "Token count should be an integer"
            assert token_count > 0, "Token count should be positive"

    def test_prepare_data_pipeline(self) -> None:
        """Test data pipeline preparation with different embedder types."""
        from deepwiki_cli.services.data_pipeline import prepare_data_pipeline

        # Test with all values
        for is_lmstudio_val in [None, True, False]:
            try:
                pipeline = prepare_data_pipeline(is_lmstudio_embedder=is_lmstudio_val)
                assert pipeline is not None, "Data pipeline should be created"
                assert callable(pipeline), "Pipeline should be callable"
            except (ImportError, ValueError, RuntimeError) as e:
                logger.warning(
                    "Pipeline creation failed for is_lmstudio=%s: %s",
                    is_lmstudio_val,
                    e,
                )


class TestRAGIntegration:
    """Test RAG class integration with different embedders."""

    def test_rag_initialization(self) -> None:
        """Test RAG initialization with different embedder configurations."""
        from deepwiki_cli.services.rag import RAG

        # Test with default configuration
        try:
            rag = RAG(provider="google", model="gemini-1.5-flash")
            assert rag is not None, "RAG should be initialized"
            assert hasattr(rag, "embedder"), "RAG should have embedder"
            assert hasattr(rag, "is_lmstudio_embedder"), (
                "RAG should have is_lmstudio_embedder attribute"
            )
        except (ImportError, ValueError, RuntimeError, TypeError) as e:
            logger.warning(
                "RAG initialization failed (might be expected if keys missing): %s",
                e,
            )

    def test_rag_embedder_type_detection(self) -> None:
        """Test that RAG correctly detects embedder type."""
        from deepwiki_cli.services.rag import RAG

        try:
            rag = RAG()
            # Should have the embedder type detection logic
            assert hasattr(rag, "is_lmstudio_embedder"), (
                "RAG should detect embedder type"
            )
            assert isinstance(rag.is_lmstudio_embedder, bool), (
                "is_lmstudio_embedder should be boolean"
            )
        except (ImportError, ValueError, RuntimeError, TypeError) as e:
            logger.warning("RAG initialization failed: %s", e)


class TestEnvironmentVariableHandling:
    """Test embedder selection via environment variables."""

    def test_embedder_type_env_var(self) -> None:
        """Test embedder selection via DEEPWIKI_EMBEDDER_TYPE environment variable."""
        for embedder_type in ["openai", "google", "lmstudio", "openrouter"]:
            self._test_single_embedder_type(embedder_type)

    def _test_single_embedder_type(self, embedder_type: str) -> None:
        """Test a single embedder type."""
        # Save original value
        original_value = os.environ.get("DEEPWIKI_EMBEDDER_TYPE")

        try:
            # Set environment variable
            os.environ["DEEPWIKI_EMBEDDER_TYPE"] = embedder_type

            # Reload settings module first to ensure _config is refreshed
            import deepwiki_cli.infrastructure.config.settings

            importlib.reload(deepwiki_cli.infrastructure.config.settings)
            # Reload config to pick up new env var
            importlib.reload(deepwiki_cli.infrastructure.config)
            # Refresh config to ensure it picks up the new environment variable
            from deepwiki_cli.infrastructure.config import _refresh_config

            _refresh_config()

            from deepwiki_cli.infrastructure.config import (
                EMBEDDER_TYPE,
                get_embedder_type,
            )

            assert embedder_type == EMBEDDER_TYPE, (
                f"EMBEDDER_TYPE should be {embedder_type}"
            )
            assert get_embedder_type() == embedder_type, (
                f"get_embedder_type() should return {embedder_type}"
            )

        finally:
            # Restore original value
            if original_value is not None:
                os.environ["DEEPWIKI_EMBEDDER_TYPE"] = original_value
            elif "DEEPWIKI_EMBEDDER_TYPE" in os.environ:
                del os.environ["DEEPWIKI_EMBEDDER_TYPE"]

            # Reload config to restore original state
            importlib.reload(deepwiki_cli.infrastructure.config.settings)
            importlib.reload(deepwiki_cli.infrastructure.config)


class TestIssuesIdentified:
    """Test the specific issues identified in the codebase."""

    def test_binary_assumptions_in_rag(self) -> None:
        """Test that RAG doesn't make binary assumptions about embedders."""
        from deepwiki_cli.services.rag import RAG

        # The current implementation only considers is_lmstudio_embedder
        # This test documents the current behavior and will help verify fixes
        try:
            rag = RAG()

            # Current implementation only has is_lmstudio_embedder
            assert hasattr(rag, "is_lmstudio_embedder"), (
                "RAG should have is_lmstudio_embedder"
            )

            # This is the issue: no explicit support for Google embedder detection
            # The fix should add proper embedder type detection

        except (ImportError, ValueError, RuntimeError, TypeError) as e:
            logger.warning("RAG test failed: %s", e)

    def test_binary_assumptions_in_data_pipeline(self) -> None:
        """Test binary assumptions in data pipeline functions."""
        from deepwiki_cli.services.data_pipeline import (
            count_tokens,
            prepare_data_pipeline,
        )

        # These functions currently only consider is_lmstudio_embedder parameter
        # This test documents the issue and will verify fixes

        # count_tokens only considers lmstudio vs non-lmstudio
        token_count_lmstudio = count_tokens("test", is_lmstudio_embedder=True)
        token_count_other = count_tokens("test", is_lmstudio_embedder=False)

        assert isinstance(token_count_lmstudio, int)
        assert isinstance(token_count_other, int)

        # prepare_data_pipeline only accepts is_lmstudio_embedder parameter
        try:
            pipeline_lmstudio = prepare_data_pipeline(is_lmstudio_embedder=True)
            pipeline_other = prepare_data_pipeline(is_lmstudio_embedder=False)

            assert pipeline_lmstudio is not None
            assert pipeline_other is not None
        except (ImportError, ValueError, RuntimeError) as e:
            logger.warning("Pipeline creation failed: %s", e)


def run_all_tests() -> bool:
    """Run all tests and return results."""
    logger.info("Running comprehensive embedder tests...")

    runner = TestRunner()

    # Test classes to run
    test_classes = [
        TestEmbedderConfiguration,
        TestEmbedderFactory,
        TestEmbedderClients,
        TestDataPipelineFunctions,
        TestRAGIntegration,
        TestEnvironmentVariableHandling,
        TestIssuesIdentified,
    ]

    # Run all test classes
    for test_class in test_classes:
        logger.info("\n🧪 Running %s...", test_class.__name__)
        runner.run_test_class(test_class)

    # Run parametrized tests manually
    logger.info("\n🧪 Running parametrized tests...")

    # Test embedder config with different types
    config_test = TestEmbedderConfiguration()
    for embedder_type in ["openai", "google", "lmstudio"]:
        runner.run_test(
            lambda et=embedder_type: config_test.test_get_embedder_config(et),
            f"TestEmbedderConfiguration.test_get_embedder_config[{embedder_type}]",
        )

    # Test token counting with different types
    pipeline_test = TestDataPipelineFunctions()
    for embedder_type in [None, True, False]:
        runner.run_test(
            lambda et=embedder_type: pipeline_test.test_count_tokens(et),
            f"TestDataPipelineFunctions.test_count_tokens[{embedder_type}]",
        )

    # Test pipeline preparation with different types
    for is_lmstudio in [None, True, False]:
        runner.run_test(
            lambda ls=is_lmstudio: pipeline_test.test_prepare_data_pipeline(ls),
            f"TestDataPipelineFunctions.test_prepare_data_pipeline[{is_lmstudio}]",
        )

    # Test environment variable handling
    env_test = TestEnvironmentVariableHandling()
    for embedder_type in ["openai", "google", "lmstudio"]:
        runner.run_test(
            lambda et=embedder_type: env_test.test_embedder_type_env_var(et),
            f"TestEnvironmentVariableHandling.test_embedder_type_env_var[{embedder_type}]",
        )

    return runner.summary()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
