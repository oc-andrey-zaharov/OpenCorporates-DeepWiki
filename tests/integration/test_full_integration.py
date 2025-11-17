#!/usr/bin/env python3
"""Full integration test for Google AI embeddings."""

import logging
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


def test_config_loading() -> bool | None:
    """Test that configurations load properly."""
    try:
        from deepwiki_cli.infrastructure.config import CLIENT_CLASSES, configs

        # Check if Google embedder config exists
        if "embedder_google" in configs:
            configs["embedder_google"]
        else:
            return False

        # Check if GoogleEmbedderClient is in CLIENT_CLASSES
        if "GoogleEmbedderClient" in CLIENT_CLASSES:
            pass
        else:
            return False

        return True

    except Exception:
        import traceback

        traceback.print_exc()
        return False


def test_embedder_selection() -> bool | None:
    """Test embedder selection mechanism."""
    try:
        from deepwiki_cli.infrastructure.config import (
            get_embedder_type,
            is_google_embedder,
        )
        from deepwiki_cli.infrastructure.embedding.embedder import get_embedder

        # Test default embedder type
        get_embedder_type()

        # Test is_google_embedder function
        is_google_embedder()

        # Test get_embedder with google type
        get_embedder(embedder_type="google")

        return True

    except Exception:
        import traceback

        traceback.print_exc()
        return False


def test_google_embedder_with_env() -> bool | None:
    """Test Google embedder with environment variable."""
    # Set environment variable
    original_value = os.environ.get("DEEPWIKI_EMBEDDER_TYPE")
    os.environ["DEEPWIKI_EMBEDDER_TYPE"] = "google"

    try:
        # Reload config module to pick up new env var
        import importlib

        import deepwiki_cli.infrastructure.config

        importlib.reload(deepwiki_cli.infrastructure.config)

        from deepwiki_cli.infrastructure.config import get_embedder_config
        from deepwiki_cli.infrastructure.embedding.embedder import get_embedder

        # Test getting embedder config
        get_embedder_config()

        # Test creating embedder
        get_embedder()

        return True

    except Exception:
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Restore original environment variable
        if original_value is not None:
            os.environ["DEEPWIKI_EMBEDDER_TYPE"] = original_value
        elif "DEEPWIKI_EMBEDDER_TYPE" in os.environ:
            del os.environ["DEEPWIKI_EMBEDDER_TYPE"]


def main() -> bool:
    """Run all integration tests."""
    tests = [
        test_config_loading,
        test_embedder_selection,
        test_google_embedder_with_env,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                pass
        except Exception as e:
            logger.exception("Test failed: %s", e)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
