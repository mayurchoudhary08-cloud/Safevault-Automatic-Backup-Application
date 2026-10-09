"""SQLite database layer for SafeVault.

Provides persistent storage for settings, backup runs, and activity logs.
All database access is thread-safe and uses parameterized queries.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple


DEFAULT_DB_FILENAME = "safevault.db"


class Database:
    """Manages the SQLite database for SafeVault."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            # Check if local safevault.db exists in working directory (portable/dev mode)
            local_db = Path.cwd() / DEFAULT_DB_FILENAME
            if local_db.exists():
                self.db_path = local_db
            else:
                from safevault.paths import get_default_data_dir
                self.db_path = get_default_data_dir() / DEFAULT_DB_FILENAME
        else:
            self.db_path = Path(db_path)

        self._lock = threading.Lock()
        self.init_database()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Create a new SQLite connection with foreign keys and dict-like row access, auto-closing it."""
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON;")
            yield conn
        finally:
            conn.close()

    def init_database(self) -> None:
        """Create required tables and indices if they do not exist."""
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Settings table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

            # 2. Backup runs table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS backup_runs (
                    backup_id TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    snapshot_path TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    completion_time TEXT,
                    status TEXT NOT NULL,
                    file_count INTEGER DEFAULT 0,
                    total_size_bytes INTEGER DEFAULT 0,
                    verification_status TEXT DEFAULT 'UNVERIFIED',
                    error_message TEXT
                );
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_backup_start_time ON backup_runs(start_time DESC);"
            )

            # 3. Activity logs table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    backup_id TEXT
                );
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON activity_logs(timestamp DESC);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_event_type ON activity_logs(event_type);"
            )

            conn.commit()

            # Insert default settings if not present
            defaults = {
                "source_folder": "",
                "backup_destination": "",
                "schedule_enabled": "0",
                "schedule_frequency": "daily",
                "schedule_time": "12:00",
                "schedule_day": "Monday",
                "verify_after_backup": "1",
                "last_scheduled_run": "",
                "last_scheduled_result": "",
            }
            for k, v in defaults.items():
                cursor.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);",
                    (k, v),
                )
            conn.commit()

    # --- Settings Operations ---

    def get_setting(self, key: str, default: str = "") -> str:
        """Retrieve a setting by key."""
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?;", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """Update or insert a setting."""
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value;",
                (key, str(value)),
            )
            conn.commit()

    def get_all_settings(self) -> Dict[str, str]:
        """Retrieve all configuration settings as a dictionary."""
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings;")
            return {row["key"]: row["value"] for row in cursor.fetchall()}

    # --- Backup Runs Operations ---

    def record_backup_run(
        self,
        backup_id: str,
        source_path: str,
        snapshot_path: str,
        start_time: str,
        status: str = "IN_PROGRESS",
        file_count: int = 0,
        total_size_bytes: int = 0,
        verification_status: str = "UNVERIFIED",
        error_message: Optional[str] = None,
    ) -> None:
        """Record the start or existence of a backup run."""
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO backup_runs (
                    backup_id, source_path, snapshot_path, start_time,
                    status, file_count, total_size_bytes, verification_status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    backup_id,
                    source_path,
                    snapshot_path,
                    start_time,
                    status,
                    file_count,
                    total_size_bytes,
                    verification_status,
                    error_message,
                ),
            )
            conn.commit()

    def update_backup_run(
        self,
        backup_id: str,
        *,
        status: Optional[str] = None,
        completion_time: Optional[str] = None,
        file_count: Optional[int] = None,
        total_size_bytes: Optional[int] = None,
        verification_status: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update fields of an existing backup run."""
        updates: List[str] = []
        params: List[Any] = []

        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if completion_time is not None:
            updates.append("completion_time = ?")
            params.append(completion_time)
        if file_count is not None:
            updates.append("file_count = ?")
            params.append(file_count)
        if total_size_bytes is not None:
            updates.append("total_size_bytes = ?")
            params.append(total_size_bytes)
        if verification_status is not None:
            updates.append("verification_status = ?")
            params.append(verification_status)
        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)

        if not updates:
            return

        params.append(backup_id)
        query = f"UPDATE backup_runs SET {', '.join(updates)} WHERE backup_id = ?;"

        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()

    def get_backup_run(self, backup_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single backup record by backup_id."""
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM backup_runs WHERE backup_id = ?;", (backup_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_backup_runs(
        self, order_by: str = "start_time DESC"
    ) -> List[Dict[str, Any]]:
        """Fetch all backup runs."""
        # Sanitize order_by
        safe_orders = {
            "start_time DESC": "ORDER BY start_time DESC",
            "start_time ASC": "ORDER BY start_time ASC",
            "total_size_bytes DESC": "ORDER BY total_size_bytes DESC",
        }
        order_clause = safe_orders.get(order_by, "ORDER BY start_time DESC")

        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM backup_runs {order_clause};")
            return [dict(row) for row in cursor.fetchall()]

    def delete_backup_run(self, backup_id: str) -> None:
        """Remove a backup run entry from the database."""
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM backup_runs WHERE backup_id = ?;", (backup_id,))
            conn.commit()

    # --- Activity Log Operations ---

    def log_activity(
        self,
        event_type: str,
        message: str,
        backup_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        """Insert an event into the activity log."""
        if timestamp is None:
            timestamp = datetime.now().isoformat(timespec="seconds")

        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO activity_logs (timestamp, event_type, message, backup_id)
                VALUES (?, ?, ?, ?);
                """,
                (timestamp, event_type, message, backup_id),
            )
            conn.commit()

    def get_activity_logs(
        self, event_type: Optional[str] = None, limit: int = 300
    ) -> List[Dict[str, Any]]:
        """Fetch activity logs, optionally filtered by event_type."""
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            if event_type and event_type != "ALL":
                cursor.execute(
                    """
                    SELECT * FROM activity_logs
                    WHERE event_type = ?
                    ORDER BY id DESC
                    LIMIT ?;
                    """,
                    (event_type, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM activity_logs
                    ORDER BY id DESC
                    LIMIT ?;
                    """,
                    (limit,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def clear_activity_logs(self) -> None:
        """Clear all activity logs."""
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM activity_logs;")
            conn.commit()

    # --- Dashboard Statistics ---

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Calculate live statistics for the Dashboard."""
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()

            # Successful backups count & total size
            cursor.execute(
                """
                SELECT COUNT(*) as count, COALESCE(SUM(total_size_bytes), 0) as total_size
                FROM backup_runs
                WHERE status = 'SUCCESS';
                """
            )
            row_success = cursor.fetchone()
            success_count = row_success["count"] if row_success else 0
            total_size = row_success["total_size"] if row_success else 0

            # Failed / cancelled count
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM backup_runs
                WHERE status IN ('FAILED', 'CANCELLED');
                """
            )
            row_failed = cursor.fetchone()
            failed_count = row_failed["count"] if row_failed else 0

            # Latest successful backup
            cursor.execute(
                """
                SELECT * FROM backup_runs
                WHERE status = 'SUCCESS'
                ORDER BY start_time DESC
                LIMIT 1;
                """
            )
            latest_success = cursor.fetchone()

            # Latest backup regardless of status
            cursor.execute(
                """
                SELECT * FROM backup_runs
                ORDER BY start_time DESC
                LIMIT 1;
                """
            )
            latest_any = cursor.fetchone()

            return {
                "success_count": success_count,
                "failed_count": failed_count,
                "total_size_bytes": total_size,
                "latest_success": dict(latest_success) if latest_success else None,
                "latest_any": dict(latest_any) if latest_any else None,
            }
