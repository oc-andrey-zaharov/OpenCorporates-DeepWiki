"""Delete wiki command."""

from pathlib import Path

import click

from deepwiki_cli.cli.utils import (
    confirm_action,
    get_cache_path,
    select_multiple_from_list,
)
from deepwiki_cli.infrastructure.storage.cache import parse_cache_filename


def _get_cached_wikis() -> list[dict]:
    """Get list of cached wikis from cache directory.

    Returns:
        List of wiki dictionaries with metadata
    """
    cache_dir = get_cache_path()

    if not cache_dir.exists():
        return []

    # Find all cache files
    cache_files = list(cache_dir.glob("deepwiki_cache_*.json"))
    if not cache_files:
        return []

    # Parse cache files to display options
    wikis = []
    for i, cache_file in enumerate(cache_files, 1):
        try:
            meta = parse_cache_filename(cache_file)
            if not meta:
                continue

            owner = meta["owner"]
            repo = meta["repo"]
            name = repo if owner == "local" else f"{owner}/{repo}"
            display_name = f"{name} (v{meta['version']})"

            wikis.append(
                {
                    "index": i,
                    "name": name,
                    "display_name": display_name,
                    "owner": owner,
                    "repo": repo,
                    "repo_type": meta["repo_type"],
                    "language": meta["language"],
                    "version": meta["version"],
                    "path": cache_file,
                },
            )
        except (OSError, ValueError, KeyError):
            continue

    # Sort by name (repo), then by version (descending)
    wikis.sort(key=lambda x: (x["name"], -int(str(x["version"]))))

    return wikis


def _confirm_deletion(selected_wikis: list[dict], *, yes: bool) -> bool:
    """Confirm deletion with user if not auto-confirmed.

    Args:
        selected_wikis: List of wiki dictionaries to delete
        yes: Whether to skip confirmation

    Returns:
        True if deletion should proceed, False otherwise
    """
    if yes:
        return True

    if len(selected_wikis) == 1:
        wiki = selected_wikis[0]
        display_label = wiki.get("display_name") or wiki["name"]
        return confirm_action(
            f"\nAre you sure you want to delete '{display_label}' "
            f"({wiki['repo_type']})?",
            default=False,
        )
    return confirm_action(
        f"\nAre you sure you want to delete {len(selected_wikis)} wiki(s)?",
        default=False,
    )


@click.command(name="delete")
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
def delete(yes: bool) -> None:
    """Delete a cached wiki."""
    # Get available wikis
    wikis = _get_cached_wikis()

    if not wikis:
        click.echo("No cached wikis found.")
        return

    # Format wiki display strings for multi-select
    display_choices = []
    for wiki in wikis:
        name = wiki.get("display_name") or wiki.get("name", "Unknown")
        repo_type = wiki.get("repo_type", "")
        display_str = f"{name}"
        if repo_type:
            display_str += f" ({repo_type})"
        display_choices.append(display_str)

    # Select wikis using multi-select menu
    selected_labels = select_multiple_from_list(
        "Select wiki(s) to delete (space to toggle, enter to confirm)",
        display_choices,
    )

    if not selected_labels:
        click.echo("No wikis selected. Deletion cancelled.")
        return

    # Map selected labels back to wiki dictionaries
    selected_wikis = []
    for label in selected_labels:
        # Find the wiki that matches this label
        for wiki in wikis:
            name = wiki.get("display_name") or wiki.get("name", "Unknown")
            repo_type = wiki.get("repo_type", "")
            display_str = f"{name}"
            if repo_type:
                display_str += f" ({repo_type})"
            if display_str == label:
                selected_wikis.append(wiki)
                break

    if not selected_wikis:
        click.echo("No valid wikis found. Deletion cancelled.")
        return

    # Confirm deletion
    if not _confirm_deletion(selected_wikis, yes=yes):
        click.echo("Deletion cancelled.")
        return

    cache_path = get_cache_path()
    deleted_count = 0
    failed_count = 0

    for wiki in selected_wikis:
        cache_file = cache_path / wiki["path"].name
        if not cache_file.exists():
            click.echo(f"\n✗ Wiki cache not found: {wiki['display_name']}", err=True)
            failed_count += 1
            continue

        try:
            Path(cache_file).unlink()
            deleted_count += 1
        except OSError as exc:  # pragma: no cover - filesystem edge case
            click.echo(
                f"\n✗ Failed to delete cache '{wiki['display_name']}': {exc}",
                err=True,
            )
            failed_count += 1

    if deleted_count > 0:
        click.echo(f"\n✓ Successfully deleted {deleted_count} wiki(s)")
    if failed_count > 0:
        click.echo(f"✗ Failed to delete {failed_count} wiki(s)", err=True)
        raise click.Abort from None
