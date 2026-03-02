"""
Centralized logging configuration for the CatDataSchema / DataPipeline package.

Environment variables:
- LOG_LEVEL (default: INFO): minimum level (DEBUG, INFO, WARNING, ERROR).
- LOG_FILE (optional): when set, logs are also written to this file with rotation.

Avoids logging sensitive data (e.g. DATABASE_URL is redacted). Configure once at
application entry; modules use getLogger(__name__) and do not add their own handlers.
"""

import logging
import os
import re
from logging.handlers import RotatingFileHandler

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(): pass  # no-op if python-dotenv not installed


# Rotation defaults when LOG_FILE is set
LOG_FILE_MAX_BYTES = 1 * 1024 * 1024  # 1 MB
LOG_FILE_BACKUP_COUNT = 5


def _redact_database_url(url: str) -> str:
    """Return a safe string for logging: hide password, show scheme and host."""
    if not url:
        return "<not set>"
    # Match postgresql://user:password@host:port/db or similar
    m = re.match(r"^([^:]+://)([^:]+):([^@]+)@([^/]+)(/.*)?$", url)
    if m:
        return f"{m.group(1)}{m.group(2)}:***@{m.group(4)}{m.group(5) or ''}"
    return "<redacted>"


def configure_logging(
    log_level_env: str = "LOG_LEVEL",
    default_level: str = "INFO",
    log_file_env: str = "LOG_FILE",
) -> None:
    """
    Configure logging for the process. Safe to call multiple times; only runs once.
    Reads level from environment (e.g. LOG_LEVEL=DEBUG). When LOG_FILE is set,
    adds a rotating file handler (same format and level as stdout).
    """
    load_dotenv()
    root = logging.getLogger()
    if root.handlers:
        return

    level_name = (os.getenv(log_level_env) or default_level).upper()
    level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    root.setLevel(level)
    root.addHandler(stream_handler)

    log_file = os.getenv(log_file_env)
    if log_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=LOG_FILE_MAX_BYTES,
            backupCount=LOG_FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)


def redact_database_url(url: str) -> str:
    """Public helper for logging: redact credentials from DATABASE_URL."""
    return _redact_database_url(url)
