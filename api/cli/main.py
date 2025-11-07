"""
Main CLI entry point for DeepWiki.
"""

import os
import sys
import logging
import click
from dotenv import load_dotenv

# Add the project root to the path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Load environment variables from .env file in project root
env_path = os.path.join(ROOT_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)

# Setup logging with default WARNING level (will be adjusted based on verbose flag)
from api.logging_config import setup_logging

# Set default log level to WARNING for CLI (less verbose)
os.environ["LOG_LEVEL"] = os.environ.get("LOG_LEVEL", "WARNING")
setup_logging()
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="1.0.0", prog_name="deepwiki")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output (INFO level logging)",
)
@click.pass_context
def cli(ctx, verbose):
    """
    DeepWiki CLI - Generate comprehensive wikis from code repositories.

    Interactive tool for creating, managing, and exporting documentation
    from GitHub repositories and local codebases.
    """
    # Store verbose flag in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    # Adjust logging level based on verbose flag
    if verbose:
        # Set to INFO level for verbose mode
        log_level = logging.INFO
    else:
        # Keep at WARNING level for normal mode (less verbose)
        log_level = logging.WARNING

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
from api.cli.commands import generate, list_wikis, export, config_cmd, delete

cli.add_command(generate.generate)
cli.add_command(list_wikis.list_wikis)
cli.add_command(export.export)
cli.add_command(config_cmd.config)
cli.add_command(delete.delete)


if __name__ == "__main__":
    cli()
