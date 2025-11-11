"""Delete wiki command.
"""

import click
import requests

from api.cli.config import load_config
from api.cli.utils import confirm_action, get_cache_path, select_wiki_from_list
from api.utils.mode import (
    check_server_health_with_retry,
    get_server_url,
    is_server_mode,
    should_fallback,
)
from api.utils.wiki_cache import parse_cache_filename


@click.command(name="delete")
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
def delete(yes: bool):
    """Delete a cached wiki."""
    cache_dir = get_cache_path()

    if not cache_dir.exists():
        click.echo("No cached wikis found.")
        return

    # Find all cache files
    cache_files = list(cache_dir.glob("deepwiki_cache_*.json"))

    if not cache_files:
        click.echo("No cached wikis found.")
        return

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
        except Exception:
            continue

    if not wikis:
        click.echo("No valid cached wikis found.")
        return

    # Select wiki using menu
    selected_wiki = select_wiki_from_list(wikis, "Select wiki to delete")

    # Confirm deletion
    if not yes:
        display_label = selected_wiki.get("display_name") or selected_wiki["name"]
        if not confirm_action(
            f"\nAre you sure you want to delete '{display_label}' "
            f"({selected_wiki['repo_type']})?",
            default=False,
        ):
            click.echo("Deletion cancelled.")
            return

    # Delete cache based on configuration
    config = load_config()

    if is_server_mode():
        # Server mode: use HTTP DELETE
        server_url = get_server_url()

        # Check server health first
        if not check_server_health_with_retry(server_url, timeout=5):
            if should_fallback():
                click.echo(
                    f"\n⚠️  Server unavailable at {server_url}, "
                    "falling back to standalone mode",
                    err=True,
                )
                _delete_standalone(selected_wiki)
            else:
                click.echo(
                    f"\n✗ Server mode enabled but server unavailable at {server_url}. "
                    "Set 'auto_fallback: true' in config or start the server.",
                    err=True,
                )
                raise click.Abort()
        else:
            try:
                api_url = f"{server_url}/api/wiki_cache"
                params = {
                    "owner": selected_wiki["owner"],
                    "repo": selected_wiki["repo"],
                    "repo_type": selected_wiki["repo_type"],
                    "language": "en",
                    "version": selected_wiki.get("version", 1),
                }

                response = requests.delete(api_url, params=params, timeout=30)

                if response.status_code == 200:
                    result = response.json()
                    click.echo(
                        f"\n✓ {result.get('message', 'Wiki deleted successfully')}",
                    )
                elif response.status_code == 404:
                    click.echo(
                        "\n✗ Wiki cache not found. It may have already been deleted.",
                        err=True,
                    )
                else:
                    error_detail = "Unknown error"
                    try:
                        error_data = response.json()
                        error_detail = error_data.get("detail", error_detail)
                    except (ValueError, requests.exceptions.JSONDecodeError):
                        error_detail = response.text or response.reason

                    click.echo(f"\n✗ Error deleting wiki: {error_detail}", err=True)
                    raise click.Abort()

            except requests.exceptions.ConnectionError:
                if should_fallback():
                    click.echo(
                        "\n⚠️  Could not connect to server, falling back to standalone mode",
                        err=True,
                    )
                    _delete_standalone(selected_wiki)
                else:
                    click.echo(
                        f"\n✗ Could not connect to API server at {server_url}",
                        err=True,
                    )
                    raise click.Abort()
            except requests.exceptions.Timeout:
                click.echo("\n✗ Request timed out. Please try again.", err=True)
                raise click.Abort()
            except Exception as e:
                click.echo(f"\n✗ Unexpected error: {e}", err=True)
                raise click.Abort()
    else:
        # Standalone mode: direct file operations
        _delete_standalone(selected_wiki)


def _delete_standalone(selected_wiki):
    """Standalone cache deletion."""
    cache_path = get_cache_path()
    cache_file = cache_path / selected_wiki["path"].name

    if cache_file.exists():
        cache_file.unlink()
        click.echo("\n✓ Wiki deleted successfully")
    else:
        click.echo("\n✗ Wiki cache not found.", err=True)
