#!/usr/bin/env python3
"""Unit tests for the truncate_string function.

Run this script to test the truncate_string functionality.
Usage: python test_truncate_string.py
Or use pytest: pytest tests/unit/test_truncate_string.py
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Mock problematic imports before importing utils
sys.modules["simple_term_menu"] = MagicMock()
sys.modules["adalflow"] = MagicMock()
sys.modules["adalflow.utils"] = MagicMock()
sys.modules["click"] = MagicMock()

# Add the parent directory to the path
test_file_path = Path(__file__)
project_root = test_file_path.parent.parent.parent
sys.path.insert(0, str(project_root))

# Import utils module directly without going through package __init__
utils_path = project_root / "src" / "deepwiki_cli" / "cli" / "utils.py"
spec = importlib.util.spec_from_file_location("deepwiki_cli.cli.utils", utils_path)
utils_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utils_module)
truncate_string = utils_module.truncate_string


class TestTruncateString:
    """Comprehensive tests for the truncate_string function."""

    def test_normal_truncation(self) -> None:
        """Test normal truncation behavior."""
        # String longer than max_length
        result = truncate_string("hello world", max_length=5, suffix="...")
        assert result == "he..."
        assert len(result) == 5

        # String exactly max_length
        result = truncate_string("hello", max_length=5, suffix="...")
        assert result == "hello"
        assert len(result) == 5

        # String shorter than max_length
        result = truncate_string("hi", max_length=5, suffix="...")
        assert result == "hi"
        assert len(result) == 2

    def test_max_length_zero(self) -> None:
        """Test edge case: max_length = 0."""
        result = truncate_string("hello world", max_length=0, suffix="...")
        assert result == ""
        assert len(result) == 0

        result = truncate_string("", max_length=0, suffix="...")
        assert result == ""
        assert len(result) == 0

    def test_max_length_negative(self) -> None:
        """Test edge case: max_length < 0."""
        result = truncate_string("hello world", max_length=-1, suffix="...")
        assert result == ""
        assert len(result) == 0

        result = truncate_string("hello world", max_length=-10, suffix="...")
        assert result == ""
        assert len(result) == 0

    def test_max_length_equals_suffix_length(self) -> None:
        """Test edge case: max_length = len(suffix)."""
        suffix = "..."
        result = truncate_string("hello world", max_length=len(suffix), suffix=suffix)
        # When max_length equals suffix length, return substring of original (not suffix)
        assert result == "hel"
        assert len(result) == 3
        assert len(result) <= len(suffix)

        # Test with longer suffix
        suffix = "....."
        result = truncate_string("hello world", max_length=len(suffix), suffix=suffix)
        assert result == "hello"
        assert len(result) == 5
        assert len(result) <= len(suffix)

    def test_max_length_smaller_than_suffix_length(self) -> None:
        """Test edge case: max_length < len(suffix)."""
        suffix = "..."

        # max_length = 1
        result = truncate_string("hello world", max_length=1, suffix=suffix)
        assert result == "h"
        assert len(result) == 1
        assert len(result) <= 1

        # max_length = 2
        result = truncate_string("hello world", max_length=2, suffix=suffix)
        assert result == "he"
        assert len(result) == 2
        assert len(result) <= 2

        # max_length = 0 (already tested, but ensure consistency)
        result = truncate_string("hello world", max_length=0, suffix=suffix)
        assert result == ""
        assert len(result) == 0

        # Test with longer suffix
        suffix = "....."
        result = truncate_string("hello world", max_length=3, suffix=suffix)
        assert result == "hel"
        assert len(result) == 3
        assert len(result) <= 3

    def test_small_positive_max_length(self) -> None:
        """Test small positive max_length values."""
        suffix = "..."

        # max_length = 1
        result = truncate_string("hello", max_length=1, suffix=suffix)
        assert result == "h"
        assert len(result) == 1

        # max_length = 2
        result = truncate_string("hello", max_length=2, suffix=suffix)
        assert result == "he"
        assert len(result) == 2

        # max_length = 3 (equals suffix length)
        result = truncate_string("hello", max_length=3, suffix=suffix)
        assert result == "hel"
        assert len(result) == 3

        # max_length = 4 (one more than suffix length)
        result = truncate_string("hello", max_length=4, suffix=suffix)
        assert result == "h..."
        assert len(result) == 4

        # max_length = 5
        result = truncate_string("hello", max_length=5, suffix=suffix)
        assert result == "hello"
        assert len(result) == 5

    def test_empty_string(self) -> None:
        """Test with empty input string."""
        result = truncate_string("", max_length=5, suffix="...")
        assert result == ""
        assert len(result) == 0

        result = truncate_string("", max_length=0, suffix="...")
        assert result == ""
        assert len(result) == 0

        result = truncate_string("", max_length=2, suffix="...")
        assert result == ""
        assert len(result) == 0

    def test_custom_suffix(self) -> None:
        """Test with custom suffix."""
        # Custom suffix shorter than default
        result = truncate_string("hello world", max_length=5, suffix=".")
        assert result == "hell."
        assert len(result) == 5

        # Custom suffix longer than default
        result = truncate_string("hello world", max_length=10, suffix="[...]")
        assert result == "hello[...]"
        assert len(result) == 10

        # Empty suffix
        result = truncate_string("hello world", max_length=5, suffix="")
        assert result == "hello"
        assert len(result) == 5

    def test_never_exceeds_max_length(self) -> None:
        """Test that result never exceeds max_length."""
        suffix = "..."
        test_string = "a" * 100  # Long string

        for max_len in range(10):
            result = truncate_string(test_string, max_length=max_len, suffix=suffix)
            assert len(result) <= max_len, (
                f"Result length {len(result)} exceeds max_length {max_len}"
            )

        # Test with various suffix lengths
        for suffix_len in [1, 2, 3, 5, 10]:
            suffix = "." * suffix_len
            for max_len in range(15):
                result = truncate_string(test_string, max_length=max_len, suffix=suffix)
                assert len(result) <= max_len, (
                    f"Result length {len(result)} exceeds max_length {max_len} "
                    f"with suffix length {suffix_len}"
                )


def run_tests() -> None:
    """Run all tests."""
    test_instance = TestTruncateString()

    test_instance.test_normal_truncation()
    test_instance.test_max_length_zero()
    test_instance.test_max_length_negative()
    test_instance.test_max_length_equals_suffix_length()
    test_instance.test_max_length_smaller_than_suffix_length()
    test_instance.test_small_positive_max_length()
    test_instance.test_empty_string()
    test_instance.test_custom_suffix()
    test_instance.test_never_exceeds_max_length()


if __name__ == "__main__":
    run_tests()
