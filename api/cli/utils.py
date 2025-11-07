"""
Utility functions for DeepWiki CLI.
"""

import os
import re
import logging
import sys
from pathlib import Path
from typing import Optional, Tuple, List
from urllib.parse import urlparse

try:
    from simple_term_menu import TerminalMenu

    SIMPLE_TERM_MENU_AVAILABLE = True
except ImportError:
    SIMPLE_TERM_MENU_AVAILABLE = False

logger = logging.getLogger(__name__)


def validate_github_url(url: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate a GitHub repository URL.

    Args:
        url: URL to validate

    Returns:
        Tuple of (is_valid, owner, repo)
    """
    try:
        parsed = urlparse(url)

        # Check if it's a valid URL
        if not parsed.scheme or not parsed.netloc:
            return False, None, None

        # Check if it's a GitHub-like domain
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) >= 2:
            owner = path_parts[-2]
            repo = path_parts[-1].replace(".git", "")
            return True, owner, repo

        return False, None, None
    except Exception as e:
        logger.error(f"Error validating URL: {e}")
        return False, None, None


def validate_github_shorthand(
    shorthand: str,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate GitHub shorthand format (owner/repo).

    Args:
        shorthand: Shorthand string (e.g., "owner/repo")

    Returns:
        Tuple of (is_valid, owner, repo)
    """
    pattern = r"^[\w\-\.]+/[\w\-\.]+$"
    if re.match(pattern, shorthand):
        parts = shorthand.split("/")
        if len(parts) == 2:
            return True, parts[0], parts[1]
    return False, None, None


def validate_local_path(path: str) -> bool:
    """
    Validate a local file system path.

    Args:
        path: Path to validate

    Returns:
        True if path exists and is a directory
    """
    return os.path.isdir(path)


def parse_repository_input(
    repo_input: str,
) -> Tuple[str, str, Optional[str], Optional[str]]:
    """
    Parse repository input and determine type.

    Args:
        repo_input: User input (URL, shorthand, or local path)

    Returns:
        Tuple of (repo_type, repo_url_or_path, owner, repo_name)
    """
    # Check if it's a local path
    if validate_local_path(repo_input):
        repo_name = os.path.basename(os.path.abspath(repo_input))
        return "local", repo_input, None, repo_name

    # Check if it's a full GitHub URL
    is_valid, owner, repo = validate_github_url(repo_input)
    if is_valid:
        return "github", repo_input, owner, repo

    # Check if it's GitHub shorthand
    is_valid, owner, repo = validate_github_shorthand(repo_input)
    if is_valid:
        url = f"https://github.com/{owner}/{repo}"
        return "github", url, owner, repo

    # Invalid input
    raise ValueError(
        f"Invalid repository input: '{repo_input}'. "
        "Expected a GitHub URL (https://github.com/owner/repo), "
        "shorthand (owner/repo), or local directory path."
    )


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def get_cache_path() -> Path:
    """
    Get the path to the wiki cache directory.

    Returns:
        Path to cache directory
    """
    from adalflow.utils import get_adalflow_default_root_path

    return Path(get_adalflow_default_root_path()) / "wikicache"


def ensure_cache_dir():
    """Ensure the cache directory exists."""
    cache_dir = get_cache_path()
    cache_dir.mkdir(parents=True, exist_ok=True)


def truncate_string(s: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Truncate a string to a maximum length.

    Args:
        s: String to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated string
    """
    if len(s) <= max_length:
        return s
    return s[: max_length - len(suffix)] + suffix


def select_from_list(
    prompt_text: str,
    choices: List[str],
    default: Optional[str] = None,
    allow_custom: bool = False,
) -> str:
    """
    Interactive list selection using arrow keys (simple-term-menu).

    Args:
        prompt_text: The prompt/question to display.
        choices: List of selectable options.
        default: Default choice (will be pre-selected).
        allow_custom: If True, allows typing a custom value not in the list.

    Returns:
        Selected choice string.

    Raises:
        ValueError: If choices list is empty.
        ImportError: If simple-term-menu is not available (falls back to basic input).
    """
    if not choices:
        raise ValueError("No choices provided")

    if not SIMPLE_TERM_MENU_AVAILABLE:
        # Fallback to basic prompt if simple-term-menu is not available
        import click

        click.echo(f"\n{prompt_text}")
        click.echo(f"Available options: {', '.join(choices)}")
        if default:
            click.echo(f"Default: {default}")
        if allow_custom:
            click.echo("(You can also enter a custom value)")

        while True:
            user_input = click.prompt(
                "Select option",
                default=default or "",
                show_default=bool(default),
            )
            if user_input in choices:
                return user_input
            elif allow_custom and user_input:
                return user_input
            else:
                click.echo(
                    f"✗ Invalid selection. Please choose from: {', '.join(choices)}"
                )

    # Handle custom input option
    CUSTOM_OPTION = "(Enter custom value...)"
    display_choices = choices.copy()
    if allow_custom:
        display_choices.append(CUSTOM_OPTION)

    # Find default index
    default_index = 0
    if default and default in choices:
        default_index = choices.index(default)

    try:
        # Create terminal menu - enter is the default accept key
        # Note: simple-term-menu doesn't support "space" as an accept key,
        # but enter works well for confirmation
        terminal_menu = TerminalMenu(
            display_choices,
            title=prompt_text,
            cursor_index=default_index,
            clear_screen=False,
        )

        # Show menu and get selected index
        selected_index = terminal_menu.show()

        # Handle cancellation (None returned on Ctrl+C)
        if selected_index is None:
            import click

            click.echo("\n✗ Selection cancelled.", err=True)
            sys.exit(1)

        # Get selected value
        selected_value = display_choices[selected_index]

        # Handle custom input
        if selected_value == CUSTOM_OPTION:
            import click

            click.echo()  # New line after selection
            custom_value = click.prompt("Enter custom value", type=str)
            if not custom_value:
                raise ValueError("Custom value cannot be empty")
            return custom_value

        return selected_value

    except KeyboardInterrupt:
        # Handle cancellation gracefully
        import click

        click.echo("\n✗ Selection cancelled.", err=True)
        sys.exit(1)
