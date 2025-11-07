"""
List cached wikis command.
"""

import json
import click
from datetime import datetime
from api.cli.utils import get_cache_path, format_file_size


@click.command(name="list")
def list_wikis():
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
            # Parse filename: deepwiki_cache_{repo_type}_{owner}_{repo}_{language}.json
            filename = cache_file.stem
            parts = filename.replace("deepwiki_cache_", "").split("_")

            if len(parts) >= 4:
                repo_type = parts[0]
                owner = parts[1]
                language = parts[-1]
                repo = "_".join(parts[2:-1])

                # Get file stats
                stats = cache_file.stat()
                size = format_file_size(stats.st_size)
                modified = datetime.fromtimestamp(stats.st_mtime)

                # Try to load the cache to get more info
                wiki_type = "unknown"
                page_count = 0
                try:
                    with open(cache_file, "r") as f:
                        data = json.load(f)
                        if (
                            "wiki_structure" in data
                            and "pages" in data["wiki_structure"]
                        ):
                            page_count = len(data["wiki_structure"]["pages"])
                        # Try to determine wiki type from comprehensive flag if available
                        if "comprehensive" in data:
                            wiki_type = (
                                "comprehensive" if data["comprehensive"] else "concise"
                            )
                except:
                    pass

                wikis.append(
                    {
                        "repo_type": repo_type,
                        "owner": owner,
                        "repo": repo,
                        "name": f"{owner}/{repo}" if owner else repo,
                        "language": language,
                        "wiki_type": wiki_type,
                        "page_count": page_count,
                        "size": size,
                        "modified": modified,
                        "path": str(cache_file),
                    }
                )
        except Exception as e:
            click.echo(f"Warning: Could not parse {cache_file.name}: {e}", err=True)

    # Sort by modification time (most recent first)
    wikis.sort(key=lambda x: x["modified"], reverse=True)

    # Display wikis
    for i, wiki in enumerate(wikis, 1):
        click.echo(f"{i}. {wiki['name']}")
        click.echo(f"   Type: {wiki['repo_type']} | Wiki Type: {wiki['wiki_type']}")
        click.echo(f"   Pages: {wiki['page_count']} | Size: {wiki['size']}")
        click.echo(f"   Modified: {wiki['modified'].strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"   Path: {wiki['path']}")
        click.echo()

    click.echo(f"Total: {len(wikis)} cached wiki(s)")
    click.echo("=" * 80 + "\n")
