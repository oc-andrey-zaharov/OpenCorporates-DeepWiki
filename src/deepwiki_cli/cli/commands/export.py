"""Export wiki command with editable workspace support."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import click

from deepwiki_cli.cli.completion import complete_wiki_names
from deepwiki_cli.cli.config import load_config
from deepwiki_cli.cli.utils import (
    confirm_action,
    get_cache_path,
    select_from_list,
    select_multiple_from_list,
    select_wiki_from_list,
    watch_manifest_cli,
)
from deepwiki_cli.models import WikiPage, WikiStructureModel
from deepwiki_cli.utils.export import generate_json_export
from deepwiki_cli.utils.wiki_cache import parse_cache_filename
from deepwiki_cli.utils.wiki_workspace import (
    ExportManifest,
    export_markdown_workspace,
    watch_workspace,
    workspace_name,
)

KB_SIZE = 1024
MARKDOWN_LAYOUTS = ("single", "multi")


@click.command(name="export")
@click.option(
    "--wiki",
    "wiki_name",
    help="Repository identifier (owner/repo or local name).",
    shell_complete=complete_wiki_names,
)
@click.option(
    "--format",
    "-f",
    "export_format",
    type=click.Choice(["markdown", "json"], case_sensitive=False),
    help="Export format (markdown or json). Defaults to markdown.",
)
@click.option(
    "--layout",
    type=click.Choice(list(MARKDOWN_LAYOUTS), case_sensitive=False),
    help="Markdown layout (single file or multi-file workspace).",
)
@click.option(
    "--pages",
    "pages_arg",
    help="Comma-separated page IDs or titles (default: interactive multi-select/all).",
)
@click.option(
    "--docs-dir",
    type=click.Path(path_type=Path),
    help="Override editable workspace directory (default from config).",
)
@click.option(
    "--watch/--no-watch",
    "watch_enabled",
    default=None,
    help="Watch exported markdown for edits and sync automatically.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output path (applies to JSON exports).",
)
def export(
    wiki_name: str | None,
    export_format: str | None,
    layout: str | None,
    pages_arg: str | None,
    docs_dir: Path | None,
    watch_enabled: bool | None,
    output: str | None,
) -> None:
    """Export a cached wiki to Markdown or JSON format."""
    config = load_config()
    cache_dir = get_cache_path()
    if not cache_dir.exists():
        click.echo("No cached wikis found. Run 'deepwiki generate' first.")
        return

    cached_wikis = _discover_cached_wikis(cache_dir)
    if not cached_wikis:
        click.echo("No valid cached wikis found.")
        return

    selected_wiki = _select_wiki(cached_wikis, wiki_name)

    export_format = export_format or select_from_list(
        "Select export format",
        ["markdown", "json"],
        default="markdown",
    )

    cache_data = _load_cache(selected_wiki["path"])
    if export_format.lower() == "json":
        _export_json(cache_data, selected_wiki, output)
        return

    layout_choice = (layout or config.get("export", {}).get("layout", "single")).lower()
    if layout_choice not in MARKDOWN_LAYOUTS:
        raise click.BadParameter(
            f"Unsupported layout '{layout_choice}'. Valid options: {', '.join(MARKDOWN_LAYOUTS)}",
        )

    workspace_base = docs_dir or Path(config.get("wiki_workspace", "docs/wiki"))
    workspace_base.mkdir(parents=True, exist_ok=True)

    structure = WikiStructureModel(**cache_data["wiki_structure"])
    available_pages = _build_pages(structure, cache_data["generated_pages"])
    pages_to_export = _filter_pages(available_pages, pages_arg)

    if not pages_to_export:
        click.echo("No matching pages to export.", err=True)
        raise click.Abort()

    repo_url = _resolve_repo_url(cache_data)
    workspace_dir = workspace_base / workspace_name(
        selected_wiki.get("owner"),
        selected_wiki["repo"],
        selected_wiki["version"],
    )
    artifact_path = (
        workspace_dir / "wiki.md" if layout_choice == "single" else workspace_dir
    )

    manifest = ExportManifest(
        owner=selected_wiki.get("owner"),
        repo=selected_wiki["repo"],
        repo_type=selected_wiki["repo_type"],
        version=selected_wiki["version"],
        cache_file=str(selected_wiki["path"].resolve()),
        layout=layout_choice,
        format="markdown",
        root_dir=str(workspace_dir),
        artifact=str(artifact_path),
        repo_url=repo_url,
    )
    export_markdown_workspace(
        pages=pages_to_export,
        structure=structure,
        manifest=manifest,
    )

    click.echo(
        f"\n✓ Exported {len(pages_to_export)} page(s) to workspace: {manifest.root_dir}",
    )

    if watch_enabled is not None:
        enable_watch = watch_enabled
    else:
        default_watch = bool(config.get("export", {}).get("watch", False))
        enable_watch = confirm_action(
            "Watch this workspace for edits and sync automatically?",
            default=default_watch,
        )

    if enable_watch:
        watch_manifest_cli(manifest)
    else:
        click.echo(
            "Tip: run 'deepwiki sync' later to apply manual edits back to the cache.",
        )


def _discover_cached_wikis(cache_dir: Path) -> list[dict]:
    cache_files = list(cache_dir.glob("deepwiki_cache_*.json"))
    wikis = []
    for index, cache_file in enumerate(cache_files, start=1):
        try:
            meta = parse_cache_filename(cache_file)
            if not meta:
                continue
            owner = meta.get("owner")
            repo = meta["repo"]
            name = repo if owner == "local" else f"{owner}/{repo}"
            wikis.append(
                {
                    "index": index,
                    "name": name,
                    "display_name": f"{name} (v{meta['version']})",
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


def _select_wiki(wikis: list[dict], identifier: str | None) -> dict:
    if identifier:
        for wiki in wikis:
            if wiki["name"].lower() == identifier.lower():
                return wiki
        raise click.BadParameter(
            f"Unknown wiki '{identifier}'. Run without --wiki to see options.",
        )
    return select_wiki_from_list(wikis, "Select wiki to export")


def _load_cache(cache_file: Path) -> dict:
    try:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise click.ClickException(f"Failed to load cache {cache_file}: {exc}") from exc


def _build_pages(
    structure: WikiStructureModel,
    generated_pages: dict,
) -> list[WikiPage]:
    pages: list[WikiPage] = []
    generated_lookup = generated_pages or {}
    for page in structure.pages:
        source = {**page.model_dump(), **generated_lookup.get(page.id, {})}
        pages.append(WikiPage(**source))
    return pages


def _filter_pages(
    available: list[WikiPage],
    pages_arg: str | None,
) -> list[WikiPage]:
    if pages_arg:
        tokens = {
            token.strip() for token in pages_arg.split(",") if token.strip()
        }
        if not tokens or "all" in {token.lower() for token in tokens}:
            return available

        id_lookup = {page.id: page for page in available}
        title_lookup = {page.title.lower(): page for page in available}
        selected: list[WikiPage] = []
        for token in tokens:
            if token in id_lookup:
                selected.append(id_lookup[token])
                continue
            lowered = token.lower()
            if lowered in title_lookup:
                selected.append(title_lookup[lowered])
                continue
            raise click.BadParameter(f"Unknown page identifier '{token}'")
        return selected

    choices = [f"{page.title} [{page.id}]" for page in available]
    selection = select_multiple_from_list(
        "Select pages to export (press enter for all)",
        choices,
    )
    if len(selection) == len(choices):
        return available

    choice_map = {label: page for label, page in zip(choices, available)}
    return [choice_map[label] for label in selection]


def _resolve_repo_url(cache_data: dict) -> str | None:
    repo_info = cache_data.get("repo")
    if not repo_info:
        return None
    if repo_info.get("repoUrl"):
        return repo_info["repoUrl"]
    if repo_info.get("owner") and repo_info.get("repo"):
        return f"https://github.com/{repo_info['owner']}/{repo_info['repo']}"
    return None


def _export_json(cache_data: dict, wiki_meta: dict, output: str | None) -> None:
    pages = _build_pages(
        WikiStructureModel(**cache_data["wiki_structure"]),
        cache_data["generated_pages"],
    )
    repo_url = _resolve_repo_url(cache_data) or wiki_meta["name"]
    payload = generate_json_export(repo_url, pages)

    if not output:
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
        repo_slug = wiki_meta["name"].replace("/", "_")
        if wiki_meta.get("version", 1) > 1:
            repo_slug = f"{repo_slug}_v{wiki_meta['version']}"
        output = f"{repo_slug}_wiki_{timestamp}.json"

    output_path = Path(output)
    output_path.write_text(payload, encoding="utf-8")

    file_size = output_path.stat().st_size
    size_kb = file_size / KB_SIZE
    size_str = (
        f"{size_kb / KB_SIZE:.2f} MB" if size_kb > KB_SIZE else f"{size_kb:.2f} KB"
    )

    click.echo(f"\n✓ Wiki exported successfully to: {output_path}")
    click.echo(f"  File size: {size_str}")
    click.echo(f"  Pages exported: {len(pages)}\n")

