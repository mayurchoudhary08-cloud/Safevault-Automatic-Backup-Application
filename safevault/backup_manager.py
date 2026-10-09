"""Backup Engine for SafeVault.

Performs robust local file backups with relative directory preservation,
chunked streaming copies, cancellation support, SHA-256 manifest generation,
and atomic snapshot publication.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from queue import Queue
from threading import Event, Lock, Thread
from typing import Any, Callable, Dict, List, Optional, Tuple

from safevault.database import Database
from safevault.integrity import CHUNK_SIZE, verify_snapshot_integrity
from safevault.logger import log_event
from safevault.paths import validate_backup_paths, normalize_path


class BackupCancelledException(Exception):
    """Raised when the user cancels an in-progress backup."""
    pass


@dataclass
class BackupProgress:
    status: str  # SCANNING, COPYING, VERIFYING, FINALIZING, COMPLETED, CANCELLED, FAILED
    current_file: str = ""
    files_processed: int = 0
    total_files: int = 0
    bytes_copied: int = 0
    total_bytes: int = 0
    elapsed_seconds: float = 0.0
    error_message: str = ""
    backup_id: str = ""


class BackupManager:
    """Orchestrates backup operations in background threads with thread-safe cancellation."""

    def __init__(self, database: Database) -> None:
        self.db = database
        self._lock = Lock()
        self._is_running = False
        self._cancel_event = Event()
        self._current_thread: Optional[Thread] = None
        self._current_backup_id: str = ""

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._is_running

    def cancel_backup(self) -> bool:
        """Signal the current backup worker to cancel."""
        with self._lock:
            if not self._is_running:
                return False
            self._cancel_event.set()
            return True

    def start_backup(
        self,
        source_dir: str | Path,
        destination_dir: str | Path,
        verify_after: bool = True,
        progress_queue: Optional[Queue] = None,
        on_complete: Optional[Callable[[bool, str], None]] = None,
    ) -> Tuple[bool, str]:
        """Start a backup operation on a background worker thread.

        Returns:
            (started_successfully, message)
        """
        with self._lock:
            if self._is_running:
                return False, "A backup operation is already running."

            # Path validation before launching worker
            valid, err_msg = validate_backup_paths(source_dir, destination_dir)
            if not valid:
                return False, err_msg

            self._is_running = True
            self._cancel_event.clear()

        # Generate unique backup ID
        src_path = normalize_path(source_dir)
        dest_path = normalize_path(destination_dir)
        backup_id = self._generate_unique_backup_id(dest_path)
        self._current_backup_id = backup_id

        # Launch worker thread
        thread = Thread(
            target=self._run_backup_worker,
            args=(src_path, dest_path, backup_id, verify_after, progress_queue, on_complete),
            name=f"BackupWorker-{backup_id}",
            daemon=True,
        )
        self._current_thread = thread
        thread.start()

        return True, backup_id

    def _generate_unique_backup_id(self, dest_path: Path) -> str:
        """Generate a unique timestamp-based snapshot folder name."""
        base_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        snapshots_dir = dest_path / "snapshots"
        candidate = base_id
        counter = 1

        while (snapshots_dir / candidate).exists() or (snapshots_dir / f".partial_{candidate}").exists():
            candidate = f"{base_id}_{counter}"
            counter += 1

        return candidate

    def _send_progress(
        self,
        queue: Optional[Queue],
        progress: BackupProgress,
    ) -> None:
        if queue is not None:
            queue.put(progress)

    def _run_backup_worker(
        self,
        source_path: Path,
        dest_path: Path,
        backup_id: str,
        verify_after: bool,
        progress_queue: Optional[Queue],
        on_complete: Optional[Callable[[bool, str], None]],
    ) -> None:
        start_time = datetime.now().isoformat(timespec="seconds")
        start_mono = time.monotonic()
        snapshots_dir = dest_path / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)

        partial_dir = snapshots_dir / f".partial_{backup_id}"
        partial_data_dir = partial_dir / "data"
        final_dir = snapshots_dir / backup_id

        # Record initial run in database
        self.db.record_backup_run(
            backup_id=backup_id,
            source_path=str(source_path),
            snapshot_path=str(final_dir),
            start_time=start_time,
            status="IN_PROGRESS",
        )
        log_event("BACKUP_STARTED", f"Backup {backup_id} initiated for {source_path}", backup_id, db=self.db)

        try:
            # 1. Scanning Phase
            self._send_progress(
                progress_queue,
                BackupProgress(
                    status="SCANNING",
                    current_file="Scanning directory contents...",
                    elapsed_seconds=round(time.monotonic() - start_mono, 1),
                    backup_id=backup_id,
                ),
            )

            file_list, empty_dirs, warnings, total_bytes = self._scan_source_directory(source_path)

            total_files = len(file_list)
            bytes_copied = 0

            # 2. Preparation of temporary working directory
            if partial_dir.exists():
                shutil.rmtree(partial_dir, ignore_errors=True)
            partial_data_dir.mkdir(parents=True, exist_ok=True)

            # Recreate empty directory structures inside data/
            for ed in empty_dirs:
                (partial_data_dir / ed).mkdir(parents=True, exist_ok=True)

            manifest_files: List[Dict[str, Any]] = []

            # 3. Copying Phase
            for idx, rel_file in enumerate(file_list, start=1):
                if self._cancel_event.is_set():
                    raise BackupCancelledException("Backup cancelled by user.")

                src_file_path = source_path / rel_file
                dst_file_path = partial_data_dir / rel_file

                # Send progress update before copying file
                self._send_progress(
                    progress_queue,
                    BackupProgress(
                        status="COPYING",
                        current_file=rel_file,
                        files_processed=idx - 1,
                        total_files=total_files,
                        bytes_copied=bytes_copied,
                        total_bytes=total_bytes,
                        elapsed_seconds=round(time.monotonic() - start_mono, 1),
                        backup_id=backup_id,
                    ),
                )

                # Ensure parent directory for destination exists
                dst_file_path.parent.mkdir(parents=True, exist_ok=True)

                # Chunked copy + simultaneous SHA-256 calculation
                file_size, file_mtime, file_sha256, copied_chunk_bytes = self._copy_file_with_hash(
                    src_file_path, dst_file_path
                )
                bytes_copied += copied_chunk_bytes

                manifest_files.append({
                    "relative_path": rel_file.replace("\\", "/"),
                    "size": file_size,
                    "modified_time": file_mtime,
                    "sha256": file_sha256,
                })

            # Finished file copying
            self._send_progress(
                progress_queue,
                BackupProgress(
                    status="COPYING",
                    current_file="All files copied",
                    files_processed=total_files,
                    total_files=total_files,
                    bytes_copied=bytes_copied,
                    total_bytes=total_bytes,
                    elapsed_seconds=round(time.monotonic() - start_mono, 1),
                    backup_id=backup_id,
                ),
            )

            # 4. Generate Manifest
            manifest_data = {
                "manifest_version": 1,
                "backup_id": backup_id,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "source_path": str(source_path),
                "total_files": total_files,
                "total_size_bytes": bytes_copied,
                "files": manifest_files,
                "empty_directories": [ed.replace("\\", "/") for ed in empty_dirs],
                "warnings": warnings,
                "verification_status": "UNVERIFIED",
            }

            temp_manifest = partial_dir / "manifest.json.tmp"
            final_manifest = partial_dir / "manifest.json"
            with open(temp_manifest, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2)
            temp_manifest.replace(final_manifest)

            # 5. Verification Phase (if requested)
            verification_status = "UNVERIFIED"
            if verify_after and total_files > 0:
                self._send_progress(
                    progress_queue,
                    BackupProgress(
                        status="VERIFYING",
                        current_file="Verifying snapshot SHA-256 integrity...",
                        files_processed=total_files,
                        total_files=total_files,
                        bytes_copied=bytes_copied,
                        total_bytes=total_bytes,
                        elapsed_seconds=round(time.monotonic() - start_mono, 1),
                        backup_id=backup_id,
                    ),
                )

                report = verify_snapshot_integrity(partial_dir)
                if report.is_valid:
                    verification_status = "VERIFIED"
                    manifest_data["verification_status"] = "VERIFIED"
                    with open(final_manifest, "w", encoding="utf-8") as f:
                        json.dump(manifest_data, f, indent=2)
                    log_event("INTEGRITY_PASSED", f"Post-backup verification passed: {report.summary_message}", backup_id, db=self.db)
                else:
                    verification_status = "FAILED"
                    manifest_data["verification_status"] = "FAILED"
                    with open(final_manifest, "w", encoding="utf-8") as f:
                        json.dump(manifest_data, f, indent=2)
                    log_event("INTEGRITY_FAILED", f"Post-backup verification failed: {report.summary_message}", backup_id, db=self.db)

            # 6. Finalizing Phase (Atomic Rename)
            self._send_progress(
                progress_queue,
                BackupProgress(
                    status="FINALIZING",
                    current_file="Finalizing snapshot...",
                    files_processed=total_files,
                    total_files=total_files,
                    bytes_copied=bytes_copied,
                    total_bytes=total_bytes,
                    elapsed_seconds=round(time.monotonic() - start_mono, 1),
                    backup_id=backup_id,
                ),
            )

            if partial_dir.exists():
                partial_dir.rename(final_dir)

            end_time = datetime.now().isoformat(timespec="seconds")
            self.db.update_backup_run(
                backup_id,
                status="SUCCESS",
                completion_time=end_time,
                file_count=total_files,
                total_size_bytes=bytes_copied,
                verification_status=verification_status,
            )
            log_event(
                "BACKUP_COMPLETED",
                f"Backup {backup_id} completed successfully ({total_files} files, {bytes_copied} bytes)",
                backup_id,
                db=self.db,
            )

            self._send_progress(
                progress_queue,
                BackupProgress(
                    status="COMPLETED",
                    current_file=f"Backup successfully created ({total_files} files)",
                    files_processed=total_files,
                    total_files=total_files,
                    bytes_copied=bytes_copied,
                    total_bytes=total_bytes,
                    elapsed_seconds=round(time.monotonic() - start_mono, 1),
                    backup_id=backup_id,
                ),
            )

            if on_complete:
                on_complete(True, f"Backup {backup_id} created successfully.")

        except BackupCancelledException:
            # Clean up partial directory
            if partial_dir.exists():
                shutil.rmtree(partial_dir, ignore_errors=True)

            end_time = datetime.now().isoformat(timespec="seconds")
            self.db.update_backup_run(
                backup_id,
                status="CANCELLED",
                completion_time=end_time,
                error_message="User cancelled the backup operation.",
            )
            log_event("BACKUP_CANCELLED", f"Backup {backup_id} was cancelled by the user", backup_id, db=self.db)

            self._send_progress(
                progress_queue,
                BackupProgress(
                    status="CANCELLED",
                    current_file="Backup cancelled by user.",
                    elapsed_seconds=round(time.monotonic() - start_mono, 1),
                    backup_id=backup_id,
                ),
            )

            if on_complete:
                on_complete(False, "Backup operation was cancelled.")

        except Exception as e:
            # Clean up partial directory
            if partial_dir.exists():
                shutil.rmtree(partial_dir, ignore_errors=True)

            end_time = datetime.now().isoformat(timespec="seconds")
            err_msg = str(e)
            self.db.update_backup_run(
                backup_id,
                status="FAILED",
                completion_time=end_time,
                error_message=err_msg,
            )
            log_event("BACKUP_FAILED", f"Backup {backup_id} failed: {err_msg}", backup_id, db=self.db)

            self._send_progress(
                progress_queue,
                BackupProgress(
                    status="FAILED",
                    current_file="Backup failed",
                    error_message=err_msg,
                    elapsed_seconds=round(time.monotonic() - start_mono, 1),
                    backup_id=backup_id,
                ),
            )

            if on_complete:
                on_complete(False, f"Backup failed: {err_msg}")

        finally:
            with self._lock:
                self._is_running = False
                self._cancel_event.clear()
                self._current_backup_id = ""

    def _scan_source_directory(
        self, source_path: Path
    ) -> Tuple[List[str], List[str], List[str], int]:
        """Scan source folder returning (files_rel, empty_dirs_rel, warnings, total_bytes)."""
        file_list: List[str] = []
        empty_dirs: List[str] = []
        warnings: List[str] = []
        total_bytes = 0

        for root, dirs, files in os.walk(source_path, topdown=True, followlinks=False):
            root_path = Path(root)

            # Detect empty directories
            if not dirs and not files:
                try:
                    rel_dir = str(root_path.relative_to(source_path))
                    if rel_dir != ".":
                        empty_dirs.append(rel_dir)
                except ValueError:
                    pass

            # Filter out and warn about symlinks in subdirectories
            for d in list(dirs):
                dir_full = root_path / d
                if dir_full.is_symlink():
                    warnings.append(f"Skipped directory symlink: {dir_full}")
                    dirs.remove(d)

            for f in files:
                file_full = root_path / f
                if file_full.is_symlink():
                    warnings.append(f"Skipped file symlink: {file_full}")
                    continue

                try:
                    rel_path = str(file_full.relative_to(source_path))
                    stat = file_full.stat()
                    total_bytes += stat.st_size
                    file_list.append(rel_path)
                except Exception as e:
                    warnings.append(f"Cannot access {file_full}: {e}")

        return file_list, empty_dirs, warnings, total_bytes

    def _copy_file_with_hash(
        self, src: Path, dst: Path
    ) -> Tuple[int, float, str, int]:
        """Copy a file in chunks while calculating SHA-256, preserving timestamps."""
        import hashlib

        hasher = hashlib.sha256()
        total_copied = 0

        with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
            while True:
                if self._cancel_event.is_set():
                    raise BackupCancelledException("Cancelled during file copy")
                buf = fsrc.read(CHUNK_SIZE)
                if not buf:
                    break
                fdst.write(buf)
                hasher.update(buf)
                total_copied += len(buf)

        # Preserve modification and access timestamps
        try:
            shutil.copystat(src, dst)
        except Exception:
            # Fallback if filesystem permissions prevent full copystat
            pass

        stat = src.stat()
        return stat.st_size, stat.st_mtime, hasher.hexdigest(), total_copied
