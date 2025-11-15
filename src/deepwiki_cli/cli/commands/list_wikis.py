"""List cached wikis command."""

import json
import logging
from datetime import UTC, datetime

import click

from deepwiki_cli.cli.utils import format_file_size, get_cache_path
from deepwiki_cli.utils.wiki_cache import parse_cache_filename

logger = logging.getLogger(__name__)


@click.command(name="list")
def list_wikis() -> None:
    """List all cached wikis."""
    cache_dir = get_cache_path()

    if not cache_dir.exists():
        click.echo("No cached wikis found.")
        return

    # Find all cache files
    cache_files = list(cache_dir.glob("deepwiki_cache_*.json"))

    if not cache_files:
        click.echo("No cached wikis found.")
        return

    click.echo("\n" + "=" * 80)
    click.echo("Cached Wikis")
    click.echo("=" * 80 + "\n")

    # Parse and display each cache file
    wikis = []
    for cache_file in cache_files:
        try:
            meta = parse_cache_filename(cache_file)
            if not meta:
                continue

            repo_type = meta["repo_type"]
            owner = meta["owner"]
            repo = meta["repo"]
            version = meta["version"]

            # Get file stats
            stats = cache_file.stat()
            size = format_file_size(stats.st_size)
            modified = datetime.fromtimestamp(stats.st_mtime, tz=UTC)

            # Try to load the cache to get more info
            wiki_type = "-"
            page_count = 0
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                    if "wiki_structure" in data and "pages" in data["wiki_structure"]:
                        page_count = len(data["wiki_structure"]["pages"])
                    comprehensive_flag = data.get("comprehensive")
                    if comprehensive_flag is True:
                        wiki_type = "comprehensive"
                    elif comprehensive_flag is False:
                        wiki_type = "concise"
                    else:
                        detected = data.get("wiki_type")
                    if isinstance(detected, str) and detected.strip():
                        wiki_type = detected.strip()
            except Exception as e:
                logger.debug("Failed to load cache metadata from %s: %s", cache_file, e)

            wikis.append(
                {
                    "repo_type": repo_type,
                    "owner": owner,
                    "repo": repo,
                    "version": version,
                    "name": f"{owner}/{repo}" if owner else repo,
                    "wiki_type": wiki_type,
                    "page_count": page_count,
                    "size": size,
                    "modified": modified,
                    "path": str(cache_file),
                },
            )
        except Exception as e:
            click.echo(f"Warning: Could not parse {cache_file.name}: {e}", err=True)

    # Sort by modification time (most recent first)
    wikis.sort(key=lambda x: x["modified"], reverse=True)

    # Display wikis
    for i, wiki in enumerate(wikis, 1):
        click.echo(f"{i}. {wiki['name']} (v{wiki['version']})")
        click.echo(
            f"   Type: {wiki['repo_type']} | Wiki Type: {wiki['wiki_type']}",
        )
        click.echo(f"   Pages: {wiki['page_count']} | Size: {wiki['size']}")
        click.echo(f"   Modified: {wiki['modified'].strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"   Path: {wiki['path']}")
        click.echo()

    click.echo(f"Total: {len(wikis)} cached wiki(s)")
    click.echo("=" * 80 + "\n")
