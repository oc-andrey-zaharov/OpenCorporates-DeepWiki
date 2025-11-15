"""Sync editable workspaces back to the DeepWiki cache."""

from __future__ import annotations

from pathlib import Path

import click

from deepwiki_cli.cli.config import load_config
from deepwiki_cli.cli.utils import select_from_list, watch_manifest_cli
from deepwiki_cli.utils.wiki_workspace import (
    ExportManifest,
    list_manifests,
    sync_manifest,
)


@click.command(name="sync")
@click.option(
    "--workspace",
    type=click.Path(path_type=Path),
    help="Path to a workspace directory (docs/wiki/...) or its manifest file.",
)
@click.option(
    "--watch/--no-watch",
    "watch_enabled",
    default=False,
    help="Continue watching the workspace after syncing.",
)
def sync(workspace: Path | None, watch_enabled: bool) -> None:
    """Sync markdown edits from docs/wiki back to the cache."""
    config = load_config()
    workspace_base = Path(config.get("wiki_workspace", "docs/wiki"))
    manifest = _resolve_manifest(workspace_base, workspace)
    summary = sync_manifest(manifest)
    click.echo(
        f"\n✓ Synced {summary.get('updated', 0)} page(s) at {summary.get('timestamp')}\n",
    )
    if watch_enabled:
        watch_manifest_cli(manifest)


def _resolve_manifest(base_dir: Path, provided: Path | None) -> ExportManifest:
    if provided:
        manifest_path = (
            provided
            if provided.name == ".deepwiki-manifest.json"
            else provided / ".deepwiki-manifest.json"
        )
        manifest_path = manifest_path.resolve()
        if not manifest_path.exists():
            raise click.BadParameter(
                f"No manifest found at {manifest_path}. Run 'deepwiki export' first.",
            )
        return ExportManifest.from_path(manifest_path)

    manifests = list_manifests(base_dir)
    if not manifests:
        raise click.ClickException(
            f"No editable workspaces found under {base_dir}. Run 'deepwiki export' to create one.",
        )

    choices = [
        f"{idx + 1}. {manifest.repo_display} (v{manifest.version}, {manifest.layout}) -> {manifest.root_dir}"
        for idx, manifest in enumerate(manifests)
    ]
    selected = select_from_list("Select workspace to sync", choices, default=choices[0])
    index = choices.index(selected)
    return manifests[index]
