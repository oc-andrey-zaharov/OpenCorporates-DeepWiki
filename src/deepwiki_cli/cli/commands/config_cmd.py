"""Configuration management commands."""

import json
from pathlib import Path

import click

from deepwiki_cli.cli.completion import complete_config_keys
from deepwiki_cli.cli.config import CONFIG_FILE, load_config, set_config_value


@click.group(name="config")
def config() -> None:
    """Manage DeepWiki CLI configuration."""


@config.command(name="show")
def show_config() -> None:
    """Display current configuration."""
    config_data = load_config()

    click.echo("\n" + "=" * 50)
    click.echo("DeepWiki CLI Configuration")
    click.echo("=" * 50)
    click.echo(f"\nConfig file: {CONFIG_FILE}\n")

    # Pretty print the configuration
    click.echo(json.dumps(config_data, indent=2))

    workspace = Path(config_data.get("wiki_workspace", "docs/wiki"))
    click.echo("\n" + "-" * 50)
    click.echo("Local Wiki Workspace")
    click.echo("-" * 50)
    click.echo(f"Path: {workspace}")
    click.echo(
        f"Exists: {'✓' if workspace.exists() else '✗ (will be created on export)'}",
    )
    click.echo(f"Default layout: {config_data.get('export', {}).get('layout', 'single')}")
    click.echo(
        "Auto-watch exports: "
        f"{'enabled' if config_data.get('export', {}).get('watch') else 'disabled'}",
    )

    click.echo("\n" + "=" * 50 + "\n")


@config.command(name="set")
@click.argument("key", shell_complete=complete_config_keys)
@click.argument("value")
def set_config(key: str, value: str) -> None:
    """Set a configuration value.

    KEY: Configuration key (e.g., 'default_provider' or 'file_filters.excluded_dirs')
    VALUE: Value to set (will be parsed as JSON if possible)
    """
    # Try to parse value as JSON for complex types
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        # If not valid JSON, use as string
        parsed_value = value

    try:
        set_config_value(key, parsed_value)
        click.echo(f"✓ Configuration updated: {key} = {parsed_value}")
    except (TypeError, OSError, json.JSONDecodeError) as e:
        click.echo(f"✗ Error updating configuration: {e}", err=True)
        raise click.Abort from None
