"""Application logging for SafeVault.

Handles both file-based logging for troubleshooting and database-backed
activity logging for the user-facing Activity Log interface.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from safevault.database import Database

_DB_INSTANCE: Optional[Database] = None
_LOGGER = logging.getLogger("SafeVault")


def setup_logger(log_file_path: Optional[str | Path] = None) -> logging.Logger:
    """Configure standard logging output to file and console."""
    if log_file_path is None:
        local_log = Path.cwd() / "safevault.log"
        if local_log.exists():
            log_file_path = local_log
        else:
            from safevault.paths import get_default_data_dir
            log_file_path = get_default_data_dir() / "safevault.log"
    else:
        log_file_path = Path(log_file_path)

    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    _LOGGER.setLevel(logging.INFO)
    # Clear existing handlers to avoid duplicates on re-initialization
    _LOGGER.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    file_handler = logging.FileHandler(str(log_file_path), encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    _LOGGER.addHandler(file_handler)

    # Console handler for developer convenience
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    _LOGGER.addHandler(console_handler)

    return _LOGGER


def set_active_database(db: Database) -> None:
    """Set the database instance used for activity logs."""
    global _DB_INSTANCE
    _DB_INSTANCE = db


def log_event(
    event_type: str,
    message: str,
    backup_id: Optional[str] = None,
    level: int = logging.INFO,
    db: Optional[Database] = None,
) -> None:
    """Log an event both to standard python logging and database activity table."""
    _LOGGER.log(level, f"[{event_type}] {message} (backup_id={backup_id})")
    target_db = db if db is not None else _DB_INSTANCE
    if target_db is not None:
        try:
            target_db.log_activity(
                event_type=event_type,
                message=message,
                backup_id=backup_id,
            )
        except Exception:
            pass
