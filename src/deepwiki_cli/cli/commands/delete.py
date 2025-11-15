"""Delete wiki command."""

from pathlib import Path

import click

from deepwiki_cli.cli.utils import confirm_action, get_cache_path, select_wiki_from_list
from deepwiki_cli.utils.wiki_cache import parse_cache_filename


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

    return wikis


def _confirm_deletion(selected_wiki: dict, *, yes: bool) -> bool:
    """Confirm deletion with user if not auto-confirmed.

    Args:
        selected_wiki: The wiki dictionary to delete
        yes: Whether to skip confirmation

    Returns:
        True if deletion should proceed, False otherwise
    """
    if yes:
        return True

    display_label = selected_wiki.get("display_name") or selected_wiki["name"]
    return confirm_action(
        f"\nAre you sure you want to delete '{display_label}' "
        f"({selected_wiki['repo_type']})?",
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

    # Select wiki using menu
    selected_wiki = select_wiki_from_list(wikis, "Select wiki to delete")

    # Confirm deletion
    if not _confirm_deletion(selected_wiki, yes=yes):
        click.echo("Deletion cancelled.")
        return

    cache_path = get_cache_path()
    cache_file = cache_path / selected_wiki["path"].name
    if not cache_file.exists():
        click.echo("\n✗ Wiki cache not found.", err=True)
        raise click.Abort from None

    try:
        Path(cache_file).unlink()
        click.echo("\n✓ Wiki deleted successfully")
    except OSError as exc:  # pragma: no cover - filesystem edge case
        click.echo(f"\n✗ Failed to delete cache: {exc}", err=True)
        raise click.Abort from None
