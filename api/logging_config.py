import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler


class IgnoreLogChangeDetectedFilter(logging.Filter):
    def filter(self, record: logging.LogRecord):
        return "Detected file change in" not in record.getMessage()


class IgnoreMLflowWarningFilter(logging.Filter):
    """Filter to suppress MLflow availability warnings from adalflow."""

    def filter(self, record: logging.LogRecord):
        # Suppress warnings about MLflow not being available
        if record.name == "adalflow.tracing.mlflow_integration":
            if "MLflow not available" in record.getMessage():
                return False
        return True


def setup_logging(format: str = None):
    """
    Configure logging for the application with log rotation.

    Environment variables:
        LOG_LEVEL: Log level (default: INFO)
        LOG_FILE_PATH: Path to log file (default: logs/application.log)
        LOG_MAX_SIZE: Max size in MB before rotating (default: 10MB)
        LOG_BACKUP_COUNT: Number of backup files to keep (default: 5)

    Ensures log directory exists, prevents path traversal, and configures
    both rotating file and console handlers.
    """
    # Determine log directory and default file path
    base_dir = Path(__file__).parent
    log_dir = base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    default_log_file = log_dir / "application.log"

    # Get log level from environment
    log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Get log file path
    log_file_path = Path(os.environ.get("LOG_FILE_PATH", str(default_log_file)))

    # Secure path check: must be inside logs/ directory
    log_dir_resolved = log_dir.resolve()
    resolved_path = log_file_path.resolve()
    if not str(resolved_path).startswith(str(log_dir_resolved) + os.sep):
        raise ValueError(
            f"LOG_FILE_PATH '{log_file_path}' is outside the trusted log directory '{log_dir_resolved}'"
        )

    # Ensure parent directories exist
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    # Get max log file size (default: 10MB)
    try:
        max_mb = int(os.environ.get("LOG_MAX_SIZE", 10))  # 10MB default
        max_bytes = max_mb * 1024 * 1024
    except (TypeError, ValueError):
        max_bytes = 10 * 1024 * 1024  # fallback to 10MB on error

    # Get backup count (default: 5)
    try:
        backup_count = int(os.environ.get("LOG_BACKUP_COUNT", 5))
    except ValueError:
        backup_count = 5

    # Configure format
    log_format = (
        format
        or "%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s"
    )

    # Create handlers
    file_handler = RotatingFileHandler(
        resolved_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    console_handler = logging.StreamHandler()

    # Set format for both handlers
    formatter = logging.Formatter(log_format)
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add filters to suppress unwanted messages
    file_handler.addFilter(IgnoreLogChangeDetectedFilter())
    console_handler.addFilter(IgnoreLogChangeDetectedFilter())
    file_handler.addFilter(IgnoreMLflowWarningFilter())
    console_handler.addFilter(IgnoreMLflowWarningFilter())

    # Also suppress MLflow warnings at the logger level
    mlflow_logger = logging.getLogger("adalflow.tracing.mlflow_integration")
    mlflow_logger.setLevel(logging.ERROR)  # Only show ERROR and above, suppress WARNING

    # Apply logging configuration
    logging.basicConfig(
        level=log_level, handlers=[file_handler, console_handler], force=True
    )

    # Log configuration info
    logger = logging.getLogger(__name__)
    logger.debug(
        f"Logging configured: level={log_level_str}, "
        f"file={resolved_path}, max_size={max_bytes} bytes, "
        f"backup_count={backup_count}"
    )
