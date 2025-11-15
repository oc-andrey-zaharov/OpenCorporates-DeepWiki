"""Utility functions for DeepWiki CLI."""

import inspect
import logging
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

try:
    from simple_term_menu import TerminalMenu

    SIMPLE_TERM_MENU_AVAILABLE = True
except ImportError:
    SIMPLE_TERM_MENU_AVAILABLE = False

if TYPE_CHECKING:
    from deepwiki_cli.infrastructure.storage.workspace import ExportManifest

logger = logging.getLogger(__name__)


def validate_github_url(url: str) -> tuple[bool, str | None, str | None]:
    """Validate a GitHub repository URL.

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
            owner = path_parts[0]
            repo = path_parts[1].replace(".git", "")
            return True, owner, repo

        return False, None, None
    except Exception as e:
        logger.exception(f"Error validating URL: {e}")
        return False, None, None


def validate_github_shorthand(
    shorthand: str,
) -> tuple[bool, str | None, str | None]:
    """Validate GitHub shorthand format (owner/repo).

    Enforces GitHub naming rules:
    - Owner and repo names must start and end with alphanumeric characters
    - Can contain hyphens and dots in the middle
    - Owner length: 1-39 characters
    - Repository length: 1-100 characters

    Args:
        shorthand: Shorthand string (e.g., "owner/repo")

    Returns:
        Tuple of (is_valid, owner, repo)
    """
    # Stricter pattern: ensures owner/repo don't start/end with hyphens or dots
    # Pattern breakdown:
    # - [a-zA-Z0-9] : must start with alphanumeric
    # - ([a-zA-Z0-9\-\.]*[a-zA-Z0-9])? : optional middle part ending with alphanumeric
    # - This allows single char names (e.g., "a/b") and multi-char names
    # The regex guarantees exactly one slash, so no need to check parts length
    pattern = r"^([a-zA-Z0-9](?:[a-zA-Z0-9\-\.]*[a-zA-Z0-9])?)/([a-zA-Z0-9](?:[a-zA-Z0-9\-\.]*[a-zA-Z0-9])?)$"
    match = re.match(pattern, shorthand)
    if match:
        owner, repo = match.groups()
        # Enforce GitHub length limits
        if 1 <= len(owner) <= 39 and 1 <= len(repo) <= 100:
            return True, owner, repo
    return False, None, None


def validate_local_path(path: str) -> bool:
    """Validate a local file system path.

    Args:
        path: Path to validate

    Returns:
        True if path exists and is a directory
    """
    return os.path.isdir(path)


def parse_repository_input(
    repo_input: str,
) -> tuple[str, str, str | None, str | None]:
    """Parse repository input and determine type.

    Args:
        repo_input: User input (URL, shorthand, or local path)

    Returns:
        Tuple of (repo_type, repo_url_or_path, owner, repo_name)
    """
    # Check if it's a full GitHub URL first
    is_valid, owner, repo = validate_github_url(repo_input)
    if is_valid:
        return "github", repo_input, owner, repo

    # Check if it's GitHub shorthand
    is_valid, owner, repo = validate_github_shorthand(repo_input)
    if is_valid:
        url = f"https://github.com/{owner}/{repo}"
        return "github", url, owner, repo

    # Only check local path if URL/shorthand patterns don't match
    if validate_local_path(repo_input):
        repo_name = Path(repo_input).resolve().name
        return "local", repo_input, None, repo_name

    # Invalid input
    raise ValueError(
        f"Invalid repository input: '{repo_input}'. "
        "Expected a GitHub URL (https://github.com/owner/repo), "
        "shorthand (owner/repo), or local directory path.",
    )


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

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
    """Get the path to the wiki cache directory.

    Returns:
        Path to cache directory
    """
    from adalflow.utils import get_adalflow_default_root_path

    return Path(get_adalflow_default_root_path()) / "wikicache"


def ensure_cache_dir() -> None:
    """Ensure the cache directory exists."""
    cache_dir = get_cache_path()
    cache_dir.mkdir(parents=True, exist_ok=True)


def truncate_string(s: str, max_length: int = 50, suffix: str = "...") -> str:
    """Truncate a string to a maximum length.

    Args:
        s: String to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated string (never exceeds max_length)
    """
    # Handle edge case: max_length <= 0
    if max_length <= 0:
        return ""

    # Handle edge case: max_length <= len(suffix)
    # Return a substring of the original string limited to max_length
    if max_length <= len(suffix):
        return s[:max_length]

    # Normal case: truncate and append suffix
    if len(s) <= max_length:
        return s
    return s[: max_length - len(suffix)] + suffix


def select_from_list(
    prompt_text: str,
    choices: list[str],
    default: str | None = None,
    allow_custom: bool = False,
) -> str:
    """Interactive list selection using arrow keys (simple-term-menu).

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
            if user_input in choices or (allow_custom and user_input):
                return user_input
            click.echo(
                f"✗ Invalid selection. Please choose from: {', '.join(choices)}",
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


def select_multiple_from_list(
    prompt_text: str,
    choices: list[str],
) -> list[str]:
    """Interactive helper to pick multiple options."""
    if not choices:
        raise ValueError("No choices provided")

    if not SIMPLE_TERM_MENU_AVAILABLE:
        import click

        click.echo(f"\n{prompt_text}")
        for idx, choice in enumerate(choices, start=1):
            click.echo(f"  {idx}. {choice}")

        while True:
            selection = click.prompt(
                "Enter numbers (comma-separated) or press enter for all",
                default="",
                show_default=False,
            )
            if not selection.strip():
                return choices

            try:
                indexes = {
                    int(item.strip()) for item in selection.split(",") if item.strip()
                }
            except ValueError:
                click.echo("✗ Invalid input. Use comma-separated numbers like 1,3,4")
                continue

            if any(idx < 1 or idx > len(choices) for idx in indexes):
                click.echo(f"✗ Please choose values between 1 and {len(choices)}")
                continue

            return [choices[idx - 1] for idx in sorted(indexes)]

    try:
        term_kwargs = {
            "title": prompt_text,
            "clear_screen": False,
            "multi_select": True,
            "show_multi_select_hint": True,
            "multi_select_select_on_accept": True,
        }

        try:
            sig = inspect.signature(TerminalMenu.__init__)
            supported_kwargs = {
                key: value
                for key, value in term_kwargs.items()
                if key in sig.parameters
            }
        except (ValueError, TypeError):
            supported_kwargs = term_kwargs

        terminal_menu = TerminalMenu(choices, **supported_kwargs)
        result = terminal_menu.show()

        if result is None:
            import click

            click.echo("\n✗ Selection cancelled.", err=True)
            sys.exit(1)

        if isinstance(result, tuple):
            selected_indexes = list(result)
        elif isinstance(result, list):
            selected_indexes = result
        elif isinstance(result, int):
            selected_indexes = [result]
        else:
            selected_indexes = []

        if not selected_indexes:
            return choices

        unique_sorted = sorted({idx for idx in selected_indexes if idx is not None})
        return [choices[idx] for idx in unique_sorted if idx < len(choices)]

    except KeyboardInterrupt:
        import click

        click.echo("\n✗ Selection cancelled.", err=True)
        sys.exit(1)


def confirm_action(
    prompt_text: str,
    default: bool = True,
) -> bool:
    """Interactive yes/no confirmation using arrow keys (simple-term-menu).

    Args:
        prompt_text: The prompt/question to display.
        default: Default choice (True for Yes, False for No).

    Returns:
        True if Yes selected, False if No selected.
    """
    choices = ["Yes", "No"]
    default_index = 0 if default else 1

    if not SIMPLE_TERM_MENU_AVAILABLE:
        # Fallback to basic prompt if simple-term-menu is not available
        import click

        return click.confirm(prompt_text, default=default)

    try:
        terminal_menu = TerminalMenu(
            choices,
            title=prompt_text,
            cursor_index=default_index,
            clear_screen=False,
        )

        selected_index = terminal_menu.show()

        if selected_index is None:
            import click

            click.echo("\n✗ Selection cancelled.", err=True)
            sys.exit(1)

        return selected_index == 0  # 0 = Yes, 1 = No

    except KeyboardInterrupt:
        import click

        click.echo("\n✗ Selection cancelled.", err=True)
        sys.exit(1)


def prompt_text_input(
    prompt_text: str,
    default: str | None = None,
    show_default: bool = True,
) -> str:
    """Prompt for text input with optional menu-based type selection.
    For repository input, shows a menu to select input type first.

    Args:
        prompt_text: The prompt/question to display.
        default: Default value (optional).
        show_default: Whether to show the default value.

    Returns:
        User input string.
    """
    import click

    # For repository input, show input type menu first
    if "repository" in prompt_text.lower() or "repo" in prompt_text.lower():
        input_types = [
            "Local directory path",
            "GitHub URL (https://github.com/owner/repo)",
            "GitHub shorthand (owner/repo)",
        ]

        if not SIMPLE_TERM_MENU_AVAILABLE:
            # Fallback to direct prompt
            return click.prompt(prompt_text, default=default, show_default=show_default)

        try:
            terminal_menu = TerminalMenu(
                input_types,
                title="Select repository input type",
                cursor_index=0,  # Default to local directory path
                clear_screen=False,
            )

            selected_index = terminal_menu.show()

            if selected_index is None:
                click.echo("\n✗ Selection cancelled.", err=True)
                sys.exit(1)

            # Show appropriate hint based on selection
            hints = {
                0: "Enter local directory path (e.g., /path/to/repo)",
                1: "Enter GitHub URL (e.g., https://github.com/owner/repo)",
                2: "Enter GitHub shorthand (e.g., owner/repo)",
            }
            click.echo(f"\n{hints[selected_index]}")

        except KeyboardInterrupt:
            click.echo("\n✗ Selection cancelled.", err=True)
            sys.exit(1)

    # Get text input
    return click.prompt(prompt_text, default=default, show_default=show_default)


def select_wiki_from_list(
    wikis: list[dict],
    prompt_text: str = "Select wiki",
) -> dict:
    """Display wikis in a menu format for selection.

    Args:
        wikis: List of wiki dictionaries, each containing at least 'index' and 'name' keys.
        prompt_text: Prompt text to display.

    Returns:
        Selected wiki dictionary.

    Raises:
        ValueError: If wikis list is empty.
    """
    if not wikis:
        raise ValueError("No wikis provided")

    import click

    # Format wiki display strings
    display_choices = []
    for wiki in wikis:
        index = wiki.get("index", wikis.index(wiki) + 1)
        name = wiki.get("display_name") or wiki.get("name", "Unknown")
        repo_type = wiki.get("repo_type", "")
        display_str = f"{index}. {name}"
        if repo_type:
            display_str += f" ({repo_type})"
        display_choices.append(display_str)

    if not SIMPLE_TERM_MENU_AVAILABLE:
        # Fallback to basic prompt
        click.echo(f"\n{prompt_text}")
        for choice in display_choices:
            click.echo(f"  {choice}")

        while True:
            try:
                selection = click.prompt("\nSelect wiki (enter number)", type=int)
                if 1 <= selection <= len(wikis):
                    return wikis[selection - 1]
                click.echo(f"✗ Invalid selection. Please choose 1-{len(wikis)}")
            except click.Abort:
                raise
            except (ValueError, TypeError):
                click.echo(
                    f"✗ Invalid input. Please enter a number between 1 and {len(wikis)}",
                )

    try:
        terminal_menu = TerminalMenu(
            display_choices,
            title=prompt_text,
            clear_screen=False,
        )

        selected_index = terminal_menu.show()

        if selected_index is None:
            click.echo("\n✗ Selection cancelled.", err=True)
            sys.exit(1)

        return wikis[selected_index]

    except KeyboardInterrupt:
        click.echo("\n✗ Selection cancelled.", err=True)
        sys.exit(1)


def watch_manifest_cli(manifest: "ExportManifest") -> None:
    """Watch an editable workspace for Markdown changes."""
    import click

    from deepwiki_cli.infrastructure.storage.workspace import watch_workspace

    click.echo("\nWatching for edits (press Ctrl+C to stop)...\n")
    try:
        for summary in watch_workspace(manifest):
            updated = summary.get("updated", 0)
            timestamp = summary.get("timestamp") or datetime.now(tz=UTC).isoformat()
            click.echo(f"  ✓ Synced {updated} page(s) at {timestamp}")
    except KeyboardInterrupt:
        click.echo("\nStopped watching workspace.")
    except FileNotFoundError as exc:
        click.echo(f"✗ Cannot watch workspace: {exc}", err=True)
