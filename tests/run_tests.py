#!/usr/bin/env python3
"""Test runner for DeepWiki project.

This script provides a unified way to run all tests or specific test categories.
"""

import argparse
import contextlib
import os
import subprocess
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_test_file(test_file: str) -> bool | None:
    """Run a single test file and return success status."""
    try:
        result = subprocess.run(
            [sys.executable, str(test_file)],
            check=False,
            capture_output=True,
            text=True,
            cwd=project_root,
        )

        if result.returncode == 0:
            if result.stdout:
                pass
            return True
        if result.stderr:
            pass
        if result.stdout:
            pass
        return False
    except Exception:
        return False


def run_tests(test_dirs: list[str]) -> bool:
    """Run all tests in the specified directories."""
    total_tests = 0
    passed_tests = 0
    failed_tests = []

    for test_dir in test_dirs:
        test_path = Path(__file__).parent / test_dir
        if not test_path.exists():
            continue

        test_files = list(test_path.glob("test_*.py"))
        if not test_files:
            continue

        for test_file in sorted(test_files):
            total_tests += 1
            if run_test_file(test_file):
                passed_tests += 1
            else:
                failed_tests.append(str(test_file))

    # Print summary

    if failed_tests:
        for _test in failed_tests:
            pass
        return False
    return True


def check_environment() -> None:
    """Check if required environment variables and dependencies are available."""
    # Check for .env file
    env_file = project_root / ".env"
    if env_file.exists():
        from dotenv import load_dotenv

        load_dotenv(env_file)
    else:
        pass

    # Check for API keys
    api_keys = {
        "GOOGLE_API_KEY": "Google AI embedder tests",
        "OPENAI_API_KEY": "OpenAI integration tests",
    }

    for key, _purpose in api_keys.items():
        if os.getenv(key):
            pass
        else:
            pass

    # Check Python dependencies
    with contextlib.suppress(ImportError):
        pass

    with contextlib.suppress(ImportError):
        pass

    with contextlib.suppress(ImportError):
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DeepWiki tests")
    parser.add_argument("--unit", action="store_true", help="Run only unit tests")
    parser.add_argument(
        "--integration", action="store_true", help="Run only integration tests"
    )
    parser.add_argument("--api", action="store_true", help="Run only API tests")
    parser.add_argument(
        "--check-env", action="store_true", help="Only check environment setup"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Check environment first
    check_environment()

    if args.check_env:
        return

    # Determine which tests to run
    test_dirs = []
    if args.unit:
        test_dirs.append("unit")
    if args.integration:
        test_dirs.append("integration")
    if args.api:
        test_dirs.append("api")

    # If no specific category selected, run all
    if not test_dirs:
        test_dirs = ["unit", "integration", "api"]

    success = run_tests(test_dirs)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
