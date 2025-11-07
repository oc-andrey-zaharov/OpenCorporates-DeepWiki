"""
Delete wiki command.
"""

import click
import requests
from api.cli.utils import get_cache_path, select_wiki_from_list, confirm_action


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
            filename = cache_file.stem
            parts = filename.replace("deepwiki_cache_", "").split("_")

            if len(parts) >= 4:
                repo_type = parts[0]
                owner = parts[1]
                language = parts[-1]
                repo = "_".join(parts[2:-1])
                # For local repos, owner is 'local', so show just the repo name
                name = repo if owner == "local" else f"{owner}/{repo}"

                wikis.append(
                    {
                        "index": i,
                        "name": name,
                        "owner": owner,
                        "repo": repo,
                        "repo_type": repo_type,
                        "language": language,
                        "path": cache_file,
                    }
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
        if not confirm_action(
            f"\nAre you sure you want to delete '{selected_wiki['name']}' "
            f"({selected_wiki['repo_type']})?",
            default=False,
        ):
            click.echo("Deletion cancelled.")
            return

    # Call API endpoint to delete
    try:
        api_url = "http://localhost:8001/api/wiki_cache"
        params = {
            "owner": selected_wiki["owner"],
            "repo": selected_wiki["repo"],
            "repo_type": selected_wiki["repo_type"],
            "language": selected_wiki["language"],
        }

        response = requests.delete(api_url, params=params, timeout=30)

        if response.status_code == 200:
            result = response.json()
            click.echo(f"\n✓ {result.get('message', 'Wiki deleted successfully')}")
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
            except:
                error_detail = response.text or response.reason

            click.echo(f"\n✗ Error deleting wiki: {error_detail}", err=True)
            raise click.Abort()

    except requests.exceptions.ConnectionError:
        click.echo(
            "\n✗ Could not connect to API server. "
            "Make sure the server is running on http://localhost:8001",
            err=True,
        )
        raise click.Abort()
    except requests.exceptions.Timeout:
        click.echo("\n✗ Request timed out. Please try again.", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"\n✗ Unexpected error: {e}", err=True)
        raise click.Abort()
