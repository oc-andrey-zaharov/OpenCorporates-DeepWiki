"""
Configuration management commands.
"""

import click
import json
from api.cli.config import load_config, set_config_value, CONFIG_FILE
from api.utils.mode import (
    is_server_mode,
    get_server_url,
    check_server_health,
    should_fallback,
)


@click.group(name="config")
def config():
    """Manage DeepWiki CLI configuration."""
    pass


@config.command(name="show")
def show_config():
    """Display current configuration."""
    config_data = load_config()

    click.echo("\n" + "=" * 50)
    click.echo("DeepWiki CLI Configuration")
    click.echo("=" * 50)
    click.echo(f"\nConfig file: {CONFIG_FILE}\n")

    # Pretty print the configuration
    click.echo(json.dumps(config_data, indent=2))

    # Show server mode status
    click.echo("\n" + "-" * 50)
    click.echo("Server Mode Status")
    click.echo("-" * 50)
    try:
        if is_server_mode():
            server_url = get_server_url()
            click.echo(f"Mode: Server (URL: {server_url})")
            try:
                if check_server_health(server_url):
                    click.echo("Status: ✓ Server is available")
                else:
                    click.echo("Status: ✗ Server is unavailable")
                    try:
                        if should_fallback():
                            click.echo(
                                "Fallback: ✓ Auto-fallback enabled (will use standalone)"
                            )
                        else:
                            click.echo("Fallback: ✗ Auto-fallback disabled")
                    except Exception as e:
                        click.echo(
                            f"Fallback: ✗ Error checking fallback: {e}", err=True
                        )
            except Exception as e:
                click.echo(f"Status: ✗ Error checking server health: {e}", err=True)
                click.echo(
                    "Note: Server health check failed. Configuration may still be valid."
                )
        else:
            click.echo("Mode: Standalone")
            click.echo("Status: ✓ Ready (no server required)")
    except Exception as e:
        click.echo(f"Error checking server mode: {e}", err=True)
        click.echo("Note: Some configuration details may be unavailable.")

    click.echo("\n" + "=" * 50 + "\n")


@config.command(name="set")
@click.argument("key", shell_complete=complete_config_keys)
@click.argument("value")
def set_config(key: str, value: str):
    """
    Set a configuration value.

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
    except Exception as e:
        click.echo(f"✗ Error updating configuration: {e}", err=True)
        raise click.Abort()
