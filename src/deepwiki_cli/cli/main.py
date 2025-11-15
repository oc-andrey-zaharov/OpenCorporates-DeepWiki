"""Main CLI entry point for DeepWiki."""

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
from dotenv import load_dotenv

from deepwiki_cli import __version__

if TYPE_CHECKING:
    from click import Context
else:
    from typing import Any

    Context = Any  # type: ignore[assignment,misc]

# Add the project root to the path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
root_dir_str = str(ROOT_DIR)
if root_dir_str not in sys.path:
    sys.path.insert(0, root_dir_str)

# Load environment variables from .env file in project root
env_path = ROOT_DIR / ".env"
if env_path.exists():
    load_dotenv(str(env_path), override=True)

# Setup logging with default WARNING level (will be adjusted based on verbose flag)
# Set default log level to WARNING for CLI (less verbose)
import os

from deepwiki_cli.infrastructure.logging.setup import setup_logging

os.environ["LOG_LEVEL"] = os.environ.get("LOG_LEVEL", "WARNING")
setup_logging()
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__, prog_name="deepwiki")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output (INFO level logging)",
)
@click.pass_context
def cli(ctx: "Context", verbose: bool) -> None:
    """DeepWiki CLI - Generate comprehensive wikis from code repositories.

    Interactive tool for creating, managing, and exporting documentation
    from GitHub repositories and local codebases.
    """
    # Store verbose flag in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    # Adjust logging level based on verbose flag
    log_level = logging.INFO if verbose else logging.WARNING

    # Update root logger and all handlers
    logging.root.setLevel(log_level)
    for handler in logging.root.handlers:
        handler.setLevel(log_level)

    # Update all existing loggers
    for logger_name in logging.Logger.manager.loggerDict:
        logger_obj = logging.getLogger(logger_name)
        logger_obj.setLevel(log_level)
        # Also update handlers for each logger
        for handler in logger_obj.handlers:
            handler.setLevel(log_level)

    if verbose:
        logger.info("Verbose mode enabled")


# Import commands after the CLI group is defined
from deepwiki_cli.cli.commands import (
    config_cmd,
    delete,
    export,
    generate,
    list_wikis,
    sync,
)

cli.add_command(generate.generate)
cli.add_command(list_wikis.list_wikis)
cli.add_command(export.export)
cli.add_command(config_cmd.config)
cli.add_command(delete.delete)
cli.add_command(sync.sync)


def main() -> None:
    """Main entry point with custom error handling."""
    # Check if first non-option argument is a valid command
    args = sys.argv[1:]
    global_options = ["--help", "-h", "--version", "--verbose", "-v"]

    # Find the first non-option argument (potential command)
    command_name = None
    for arg in args:
        if arg not in global_options and not arg.startswith("-"):
            command_name = arg
            break

    # If we found a potential command, check if it's valid
    if command_name and command_name not in cli.commands:
        # Invalid command - show error and help
        click.echo(f"Error: No such command '{command_name}'.", err=True)
        click.echo()
        # Show help
        try:
            ctx = click.Context(cli, info_name="deepwiki")
            click.echo(ctx.get_help())
        except Exception:
            # Fallback if context creation fails - show commands manually
            click.echo("Usage: deepwiki [OPTIONS] COMMAND [ARGS]...")
            click.echo("\nCommands:")
            for cmd_name, cmd in cli.commands.items():
                help_str = cmd.get_short_help_str() or cmd.help or ""
                click.echo(f"  {cmd_name:10}  {help_str}")
        sys.exit(2)

    # Use Click's normal invocation
    try:
        cli()
    except click.exceptions.ClickException as e:
        # Handle Click exceptions
        e.show()
        sys.exit(e.exit_code)
    except SystemExit:
        # Re-raise SystemExit (used by Click for normal exits)
        raise
    except Exception as e:
        # Handle unexpected errors
        click.echo(f"Unexpected error: {e}", err=True)
        if logger.isEnabledFor(logging.INFO):
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
