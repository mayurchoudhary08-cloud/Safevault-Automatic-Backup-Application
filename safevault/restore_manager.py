"""Restore Engine for SafeVault.

Handles safe, non-destructive restoration of snapshots into separate,
isolated directories with path traversal protection and post-restore SHA-256 validation.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from queue import Queue
from threading import Event, Lock, Thread
from typing import Any, Callable, Dict, List, Optional, Tuple

from safevault.database import Database
from safevault.integrity import CHUNK_SIZE, compute_file_sha256, verify_snapshot_integrity
from safevault.logger import log_event
from safevault.paths import (
    get_unique_destination_dir,
    is_safe_relative_path,
    normalize_path,
    resolve_safe_subpath,
)


class RestoreCancelledException(Exception):
    """Raised when the user cancels an in-progress restore."""
    pass


@dataclass
class RestoreProgress:
    status: str  # PREPARING, VERIFYING_SNAPSHOT, RESTORING, VERIFYING_RESTORE, COMPLETED, CANCELLED, FAILED
    current_file: str = ""
    files_processed: int = 0
    total_files: int = 0
    bytes_restored: int = 0
    total_bytes: int = 0
    elapsed_seconds: float = 0.0
    error_message: str = ""
    target_dir: str = ""


class RestoreManager:
    """Manages restoration of backups into safe, independent folders."""

    def __init__(self, database: Database) -> None:
        self.db = database
        self._lock = Lock()
        self._is_running = False
        self._cancel_event = Event()
        self._current_thread: Optional[Thread] = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._is_running

    def cancel_restore(self) -> bool:
        """Signal the current restore worker to cancel."""
        with self._lock:
            if not self._is_running:
                return False
            self._cancel_event.set()
            return True

    def prepare_restore_destination(
        self,
        base_restore_dir: str | Path,
        backup_id: str,
    ) -> Path:
        """Compute a unique, safe restore folder name."""
        base_dir = normalize_path(base_restore_dir)
        timestamp_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        candidate_name = f"SafeVault_Restored_{backup_id}_{timestamp_str}"
        return get_unique_destination_dir(base_dir, candidate_name)

    def start_restore(
        self,
        snapshot_dir: str | Path,
        target_restore_dir: str | Path,
        verify_before: bool = True,
        verify_after: bool = True,
        progress_queue: Optional[Queue] = None,
        on_complete: Optional[Callable[[bool, str, str], None]] = None,
    ) -> Tuple[bool, str]:
        """Initiate background restore worker.

        Args:
            snapshot_dir: Path to the snapshot directory (must contain manifest.json and data/)
            target_restore_dir: Directory where restored files will be placed
            verify_before: Whether to verify snapshot SHA-256 before restoring
            verify_after: Whether to verify newly restored files SHA-256 after copy
            progress_queue: Optional queue for UI updates
            on_complete: Callback(success, message, restored_path)

        Returns:
            (started_successfully, message)
        """
        with self._lock:
            if self._is_running:
                return False, "Another restore operation is currently in progress."

            snap_path = normalize_path(snapshot_dir)
            if not snap_path.exists():
                return False, f"Snapshot folder not found: {snap_path}"

            manifest_path = snap_path / "manifest.json"
            if not manifest_path.exists():
                return False, f"Snapshot manifest.json missing in: {snap_path}"

            self._is_running = True
            self._cancel_event.clear()

        thread = Thread(
            target=self._run_restore_worker,
            args=(
                snap_path,
                Path(target_restore_dir),
                verify_before,
                verify_after,
                progress_queue,
                on_complete,
            ),
            name="RestoreWorker",
            daemon=True,
        )
        self._current_thread = thread
        thread.start()

        return True, "Restore process started."

    def _send_progress(
        self,
        queue: Optional[Queue],
        progress: RestoreProgress,
    ) -> None:
        if queue is not None:
            queue.put(progress)

    def _run_restore_worker(
        self,
        snapshot_dir: Path,
        target_dir: Path,
        verify_before: bool,
        verify_after: bool,
        progress_queue: Optional[Queue],
        on_complete: Optional[Callable[[bool, str, str], None]],
    ) -> None:
        start_mono = time.monotonic()
        manifest_path = snapshot_dir / "manifest.json"
        data_dir = snapshot_dir / "data"

        try:
            # 1. Load and validate manifest
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            backup_id = manifest.get("backup_id", snapshot_dir.name)
            files = manifest.get("files", [])
            empty_dirs = manifest.get("empty_directories", [])
            total_files = len(files)
            total_bytes = sum(f.get("size", 0) for f in files)

            # Security check: validate every relative path against directory traversal
            for item in files:
                rel_p = item.get("relative_path", "")
                if not is_safe_relative_path(rel_p):
                    raise ValueError(
                        f"Security violation: unsafe path '{rel_p}' detected in manifest. Restore rejected."
                    )
            for ed in empty_dirs:
                if not is_safe_relative_path(ed):
                    raise ValueError(
                        f"Security violation: unsafe directory path '{ed}' detected in manifest. Restore rejected."
                    )

            # 2. Verify snapshot integrity before restoring if requested
            if verify_before and total_files > 0:
                self._send_progress(
                    progress_queue,
                    RestoreProgress(
                        status="VERIFYING_SNAPSHOT",
                        current_file="Verifying snapshot integrity before restore...",
                        total_files=total_files,
                        elapsed_seconds=round(time.monotonic() - start_mono, 1),
                        target_dir=str(target_dir),
                    ),
                )
                report = verify_snapshot_integrity(snapshot_dir)
                if not report.is_valid:
                    raise RuntimeError(
                        f"Snapshot verification failed before restore: {report.summary_message}"
                    )

            # 3. Create target directory
            target_dir.mkdir(parents=True, exist_ok=True)

            # Create empty directories
            for ed in empty_dirs:
                sub = resolve_safe_subpath(target_dir, ed)
                if sub:
                    sub.mkdir(parents=True, exist_ok=True)

            # 4. Copy files into target directory
            bytes_restored = 0
            for idx, item in enumerate(files, start=1):
                if self._cancel_event.is_set():
                    raise RestoreCancelledException("Restore cancelled by user.")

                rel_p = item["relative_path"]
                expected_sha256 = item.get("sha256", "")
                src_file = data_dir / rel_p
                dst_file = resolve_safe_subpath(target_dir, rel_p)

                if dst_file is None:
                    raise ValueError(f"Unsafe destination path resolved for: {rel_p}")

                self._send_progress(
                    progress_queue,
                    RestoreProgress(
                        status="RESTORING",
                        current_file=rel_p,
                        files_processed=idx - 1,
                        total_files=total_files,
                        bytes_restored=bytes_restored,
                        total_bytes=total_bytes,
                        elapsed_seconds=round(time.monotonic() - start_mono, 1),
                        target_dir=str(target_dir),
                    ),
                )

                if not src_file.exists():
                    raise FileNotFoundError(f"Snapshot data file missing: {src_file}")

                dst_file.parent.mkdir(parents=True, exist_ok=True)

                # Chunked copy to destination
                copied_len = self._copy_file(src_file, dst_file)
                bytes_restored += copied_len

                # Restore modification timestamp if present
                if "modified_time" in item:
                    try:
                        mtime = float(item["modified_time"])
                        os.utime(dst_file, (mtime, mtime))
                    except Exception:
                        pass

            # 5. Verify restored files (post-restore SHA-256 check)
            if verify_after and total_files > 0:
                self._send_progress(
                    progress_queue,
                    RestoreProgress(
                        status="VERIFYING_RESTORE",
                        current_file="Verifying restored files SHA-256 checksums...",
                        files_processed=total_files,
                        total_files=total_files,
                        bytes_restored=bytes_restored,
                        total_bytes=total_bytes,
                        elapsed_seconds=round(time.monotonic() - start_mono, 1),
                        target_dir=str(target_dir),
                    ),
                )
                for item in files:
                    if self._cancel_event.is_set():
                        raise RestoreCancelledException("Restore cancelled during verification.")

                    rel_p = item["relative_path"]
                    expected_hash = item.get("sha256", "")
                    dst_file = resolve_safe_subpath(target_dir, rel_p)

                    if not dst_file or not dst_file.exists():
                        raise FileNotFoundError(f"Restored file missing: {rel_p}")

                    actual_hash = compute_file_sha256(dst_file)
                    if actual_hash.lower() != expected_hash.lower():
                        raise RuntimeError(
                            f"Restored file integrity check failed for {rel_p} (hash mismatch)."
                        )

            # Success!
            msg = f"Restored {total_files} files ({bytes_restored} bytes) to {target_dir}"
            log_event("RESTORE_COMPLETED", msg, backup_id, db=self.db)

            self._send_progress(
                progress_queue,
                RestoreProgress(
                    status="COMPLETED",
                    current_file=f"Restored {total_files} files successfully.",
                    files_processed=total_files,
                    total_files=total_files,
                    bytes_restored=bytes_restored,
                    total_bytes=total_bytes,
                    elapsed_seconds=round(time.monotonic() - start_mono, 1),
                    target_dir=str(target_dir),
                ),
            )

            if on_complete:
                on_complete(True, msg, str(target_dir))

        except RestoreCancelledException:
            log_event("RESTORE_CANCELLED", f"Restore to {target_dir} was cancelled", None, db=self.db)
            self._send_progress(
                progress_queue,
                RestoreProgress(
                    status="CANCELLED",
                    current_file="Restore cancelled by user.",
                    elapsed_seconds=round(time.monotonic() - start_mono, 1),
                    target_dir=str(target_dir),
                ),
            )
            if on_complete:
                on_complete(False, "Restore cancelled by user.", str(target_dir))

        except Exception as e:
            err_msg = str(e)
            log_event("RESTORE_FAILED", f"Restore to {target_dir} failed: {err_msg}", None, db=self.db)
            self._send_progress(
                progress_queue,
                RestoreProgress(
                    status="FAILED",
                    current_file="Restore failed",
                    error_message=err_msg,
                    elapsed_seconds=round(time.monotonic() - start_mono, 1),
                    target_dir=str(target_dir),
                ),
            )
            if on_complete:
                on_complete(False, f"Restore failed: {err_msg}", str(target_dir))

        finally:
            with self._lock:
                self._is_running = False
                self._cancel_event.clear()

    def _copy_file(self, src: Path, dst: Path) -> int:
        """Copy a file in chunks while checking for cancellation."""
        total = 0
        with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
            while True:
                if self._cancel_event.is_set():
                    raise RestoreCancelledException("Cancelled during restore file copy")
                buf = fsrc.read(CHUNK_SIZE)
                if not buf:
                    break
                fdst.write(buf)
                total += len(buf)
        return total
