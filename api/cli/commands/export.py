"""Export wiki command.
"""

import json
import os
from datetime import datetime

import click

from api.cli.utils import get_cache_path, select_from_list, select_wiki_from_list
from api.models import WikiPage
from api.utils.export import generate_json_export, generate_markdown_export
from api.utils.wiki_cache import parse_cache_filename


@click.command(name="export")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["markdown", "json"], case_sensitive=False),
    help="Export format (markdown or json)",
)
@click.option("--output", "-o", type=click.Path(), help="Output file path")
def export(format: str, output: str):
    """Export a cached wiki to Markdown or JSON format."""
    cache_dir = get_cache_path()

    if not cache_dir.exists():
        click.echo(
            "No cached wikis found. Generate a wiki first using 'deepwiki generate'.",
        )
        return

    # Find all cache files
    cache_files = list(cache_dir.glob("deepwiki_cache_*.json"))

    if not cache_files:
        click.echo(
            "No cached wikis found. Generate a wiki first using 'deepwiki generate'.",
        )
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
            name = f"{owner}/{repo}" if owner else repo
            display_name = f"{name} (v{meta['version']})"

            wikis.append(
                {
                    "index": i,
                    "name": name,
                    "display_name": display_name,
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
    selected_wiki = select_wiki_from_list(wikis, "Select wiki to export")

    # Prompt for format if not provided
    if not format:
        format = select_from_list(
            "Select export format",
            ["markdown", "json"],
            default="markdown",
        )

    # Load the wiki cache
    try:
        with open(selected_wiki["path"]) as f:
            cache_data = json.load(f)
    except Exception as e:
        click.echo(f"Error loading wiki cache: {e}", err=True)
        return

    # Extract necessary data
    if "wiki_structure" not in cache_data or "generated_pages" not in cache_data:
        click.echo("Invalid wiki cache format.")
        return

    wiki_structure = cache_data["wiki_structure"]
    generated_pages = cache_data["generated_pages"]

    # Get repo URL
    repo_url = ""
    if cache_data.get("repo"):
        repo_info = cache_data["repo"]
        if "repoUrl" in repo_info:
            repo_url = repo_info["repoUrl"]
        elif "owner" in repo_info and "repo" in repo_info:
            repo_url = f"https://github.com/{repo_info['owner']}/{repo_info['repo']}"

    # Prepare pages for export
    pages_to_export = []
    for page_data in wiki_structure.get("pages", []):
        page_id = page_data.get("id")
        if page_id in generated_pages:
            page_content = generated_pages[page_id]
            pages_to_export.append(
                WikiPage(
                    id=page_content.get("id", page_id),
                    title=page_content.get("title", page_data.get("title", "")),
                    content=page_content.get("content", ""),
                    filePaths=page_content.get(
                        "filePaths", page_data.get("filePaths", []),
                    ),
                    importance=page_content.get(
                        "importance", page_data.get("importance", "medium"),
                    ),
                    relatedPages=page_content.get(
                        "relatedPages", page_data.get("relatedPages", []),
                    ),
                ),
            )

    if not pages_to_export:
        click.echo("No pages to export.")
        return

    # Generate output filename if not provided
    if not output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        repo_name = selected_wiki["name"].replace("/", "_")
        if selected_wiki.get("version", 1) > 1:
            repo_name = f"{repo_name}_v{selected_wiki['version']}"
        extension = "md" if format == "markdown" else "json"
        output = f"{repo_name}_wiki_{timestamp}.{extension}"

    # Export based on format
    try:
        if format.lower() == "markdown":
            content = generate_markdown_export(repo_url, pages_to_export)
        else:
            content = generate_json_export(repo_url, pages_to_export)

        # Write to file
        with open(output, "w", encoding="utf-8") as f:
            f.write(content)

        click.echo(f"\n✓ Wiki exported successfully to: {output}")

        # Show file size
        file_size = os.path.getsize(output)
        size_kb = file_size / 1024
        if size_kb > 1024:
            size_str = f"{size_kb / 1024:.2f} MB"
        else:
            size_str = f"{size_kb:.2f} KB"

        click.echo(f"  File size: {size_str}")
        click.echo(f"  Pages exported: {len(pages_to_export)}\n")

    except Exception as e:
        click.echo(f"✗ Error exporting wiki: {e}", err=True)
        raise click.Abort()
