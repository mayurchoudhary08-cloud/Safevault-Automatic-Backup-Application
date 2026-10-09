"""SHA-256 File integrity verification for SafeVault.

Calculates cryptographic hashes using chunked I/O to support files of any size
without excessive memory consumption, and verifies snapshot files against
their recorded manifest.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CHUNK_SIZE = 64 * 1024  # 64 KB chunks for efficient I/O


@dataclass
class FileCheckResult:
    relative_path: str
    status: str  # "OK", "MISSING", "HASH_MISMATCH", "SIZE_MISMATCH", "ERROR"
    expected_hash: str = ""
    actual_hash: str = ""
    expected_size: int = 0
    actual_size: int = 0
    error_message: str = ""


@dataclass
class IntegrityReport:
    backup_id: str
    is_valid: bool
    total_files_checked: int = 0
    passed_count: int = 0
    failed_count: int = 0
    file_results: List[FileCheckResult] = field(default_factory=list)
    summary_message: str = ""


def compute_file_sha256(file_path: Path | str) -> str:
    """Calculate the SHA-256 checksum of a file using chunked streaming.

    Raises:
        FileNotFoundError, PermissionError, OSError on read failure.
    """
    hasher = hashlib.sha256()
    path = Path(file_path)

    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)

    return hasher.hexdigest()


def verify_snapshot_integrity(
    snapshot_dir: Path | str,
    progress_callback: Optional[callable] = None,
) -> IntegrityReport:
    """Verify all files in a snapshot against its manifest.json.

    Args:
        snapshot_dir: The snapshot folder containing manifest.json and data/
        progress_callback: Optional callback(current_file_idx, total_files, filename)

    Returns:
        IntegrityReport containing detailed verification results.
    """
    snap_path = Path(snapshot_dir)
    manifest_path = snap_path / "manifest.json"
    data_dir = snap_path / "data"

    if not manifest_path.exists():
        return IntegrityReport(
            backup_id=snap_path.name,
            is_valid=False,
            summary_message=f"Manifest file missing: {manifest_path}",
        )

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        return IntegrityReport(
            backup_id=snap_path.name,
            is_valid=False,
            summary_message=f"Corrupt or unreadable manifest.json: {e}",
        )

    backup_id = manifest.get("backup_id", snap_path.name)
    files = manifest.get("files", [])
    total_files = len(files)

    report = IntegrityReport(
        backup_id=backup_id,
        is_valid=True,
        total_files_checked=total_files,
    )

    for idx, item in enumerate(files, start=1):
        rel_path = item.get("relative_path", "")
        expected_hash = item.get("sha256", "")
        expected_size = item.get("size", 0)

        if progress_callback:
            progress_callback(idx, total_files, rel_path)

        target_file = data_dir / rel_path

        if not target_file.exists():
            report.is_valid = False
            report.failed_count += 1
            report.file_results.append(
                FileCheckResult(
                    relative_path=rel_path,
                    status="MISSING",
                    expected_hash=expected_hash,
                    expected_size=expected_size,
                    error_message="File is missing from snapshot data directory",
                )
            )
            continue

        try:
            actual_size = target_file.stat().st_size
            if actual_size != expected_size:
                report.is_valid = False
                report.failed_count += 1
                report.file_results.append(
                    FileCheckResult(
                        relative_path=rel_path,
                        status="SIZE_MISMATCH",
                        expected_hash=expected_hash,
                        expected_size=expected_size,
                        actual_size=actual_size,
                        error_message=f"File size differs: expected {expected_size} bytes, found {actual_size} bytes",
                    )
                )
                continue

            actual_hash = compute_file_sha256(target_file)
            if actual_hash.lower() != expected_hash.lower():
                report.is_valid = False
                report.failed_count += 1
                report.file_results.append(
                    FileCheckResult(
                        relative_path=rel_path,
                        status="HASH_MISMATCH",
                        expected_hash=expected_hash,
                        actual_hash=actual_hash,
                        expected_size=expected_size,
                        actual_size=actual_size,
                        error_message="SHA-256 hash mismatch: file content has been altered or corrupted",
                    )
                )
                continue

            # Verified successfully
            report.passed_count += 1
            report.file_results.append(
                FileCheckResult(
                    relative_path=rel_path,
                    status="OK",
                    expected_hash=expected_hash,
                    actual_hash=actual_hash,
                    expected_size=expected_size,
                    actual_size=actual_size,
                )
            )

        except Exception as e:
            report.is_valid = False
            report.failed_count += 1
            report.file_results.append(
                FileCheckResult(
                    relative_path=rel_path,
                    status="ERROR",
                    expected_hash=expected_hash,
                    expected_size=expected_size,
                    error_message=f"Error reading file: {e}",
                )
            )

    if report.is_valid:
        report.summary_message = (
            f"Backup verified: {report.passed_count} files checked. All file checksums match."
        )
    else:
        report.summary_message = (
            f"Verification failed: {report.failed_count} file(s) failed out of {total_files} total files."
        )

    return report
