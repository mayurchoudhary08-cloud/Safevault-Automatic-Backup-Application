"""Path validation and safety utilities for SafeVault.

Ensures that backup and restore operations do not perform recursive backups,
overwrite source folders, or escape target directories through path traversal.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple, Optional


def normalize_path(path: str | Path) -> Path:
    """Normalize and resolve a path to an absolute path, resolving symlinks."""
    return Path(path).expanduser().resolve()


def validate_backup_paths(
    source: str | Path,
    destination: str | Path
) -> Tuple[bool, str]:
    """Validate source and destination paths for a backup operation.

    Rules enforced:
    1. Source must not be empty.
    2. Destination must not be empty.
    3. Source must exist.
    4. Source must be a directory (not a regular file).
    5. Destination must be creatable or existing.
    6. Source and Destination must not be the exact same directory.
    7. Destination must not be inside the Source directory (prevents infinite recursive backup).
    8. Source must not be inside the Destination directory (prevents backing up previous snapshots).
    9. Source must be readable.

    Returns:
        (is_valid, error_message)
    """
    if not source or not str(source).strip():
        return False, "Source folder has not been selected."

    if not destination or not str(destination).strip():
        return False, "Backup destination folder has not been selected."

    try:
        src_path = normalize_path(source)
    except Exception as e:
        return False, f"Invalid source path: {e}"

    try:
        dest_path = normalize_path(destination)
    except Exception as e:
        return False, f"Invalid destination path: {e}"

    # 1. Source existence check
    if not src_path.exists():
        return False, f"Source folder does not exist:\n{src_path}"

    if not src_path.is_dir():
        return False, f"Source path is a file, not a directory:\n{src_path}"

    # 2. Same directory check
    if src_path == dest_path:
        return False, (
            "Source and destination point to the exact same folder.\n"
            "Choose a separate destination folder to store your backups."
        )

    # 3. Destination inside source (Recursive loop prevention)
    try:
        if dest_path.is_relative_to(src_path):
            return False, (
                "The backup destination is inside your source folder.\n"
                "Choose a separate destination to prevent recursive backups."
            )
    except AttributeError:
        # Fallback for Python < 3.9 if ever needed
        if src_path in dest_path.parents or src_path == dest_path:
            return False, (
                "The backup destination is inside your source folder.\n"
                "Choose a separate destination to prevent recursive backups."
            )

    # 4. Source inside destination check
    try:
        if src_path.is_relative_to(dest_path):
            return False, (
                "The source folder is inside your backup destination.\n"
                "Choose a separate destination to avoid backing up existing snapshots."
            )
    except AttributeError:
        if dest_path in src_path.parents or dest_path == src_path:
            return False, (
                "The source folder is inside your backup destination.\n"
                "Choose a separate destination to avoid backing up existing snapshots."
            )

    # 5. Destination creatable / writable check
    try:
        if not dest_path.exists():
            # Check if closest existing parent is writable
            parent = dest_path.parent
            while not parent.exists() and parent != parent.parent:
                parent = parent.parent
            if not os.access(parent, os.W_OK):
                return False, f"Destination folder cannot be created (permission denied on parent {parent})."
        else:
            if not dest_path.is_dir():
                return False, f"Destination path exists and is a file, not a directory:\n{dest_path}"
            if not os.access(dest_path, os.W_OK):
                return False, f"Destination folder is not writable (permission denied):\n{dest_path}"
    except Exception as e:
        return False, f"Cannot access destination directory: {e}"

    # 6. Source readability check
    try:
        if not os.access(src_path, os.R_OK):
            return False, f"Source folder is not readable (permission denied):\n{src_path}"
    except Exception as e:
        return False, f"Cannot verify source folder readability: {e}"

    return True, ""


def is_safe_relative_path(rel_path_str: str) -> bool:
    """Verify that a relative path from a manifest does not escape its root.

    Prevents directory traversal attacks via '..' segments, absolute paths,
    or Windows drive qualifiers.
    """
    if not rel_path_str or not rel_path_str.strip():
        return False

    # Check for leading slashes/backslashes (root-relative on Windows or absolute on POSIX)
    if rel_path_str.startswith(("/", "\\")):
        return False

    if os.path.isabs(rel_path_str):
        return False

    import re

    # Check for drive specification (e.g. C: or C:/) across all platforms (POSIX & Windows)
    if re.match(r"^[a-zA-Z]:", rel_path_str):
        return False

    # Check for drive specification via Path object
    path_obj = Path(rel_path_str)
    if path_obj.is_absolute() or path_obj.drive:
        return False

    parts = path_obj.parts
    # Reject any '..' in parts
    if ".." in parts:
        return False

    # Normalize separators
    normalized = os.path.normpath(rel_path_str)
    if normalized.startswith("..") or normalized == "." or os.path.isabs(normalized):
        return False

    return True


def resolve_safe_subpath(base_dir: Path, rel_path_str: str) -> Optional[Path]:
    """Safely resolve a relative path inside base_dir, returning None if unsafe."""
    if not is_safe_relative_path(rel_path_str):
        return None

    try:
        resolved_base = normalize_path(base_dir)
        target = (resolved_base / rel_path_str).resolve()
        if target.is_relative_to(resolved_base):
            return target
        return None
    except Exception:
        return None


def get_unique_destination_dir(parent_dir: Path, base_name: str) -> Path:
    """Generate a unique directory path by appending numeric suffixes if name exists."""
    target = parent_dir / base_name
    if not target.exists():
        return target

    counter = 1
    while True:
        candidate = parent_dir / f"{base_name}_{counter}"
        if not candidate.exists():
            return candidate
        counter += 1


def get_default_data_dir() -> Path:
    """Return a safe, writable per-user application data directory for SafeVault.

    On Windows: %LOCALAPPDATA%/SafeVault (e.g. C:/Users/<User>/AppData/Local/SafeVault)
    On POSIX/Linux: ~/.safevault

    Ensures that packaged executables run safely from any directory without permission errors.
    """
    if os.name == "nt":
        base_env = os.environ.get("LOCALAPPDATA")
        if base_env:
            data_dir = Path(base_env) / "SafeVault"
        else:
            data_dir = Path.home() / "AppData" / "Local" / "SafeVault"
    else:
        data_dir = Path.home() / ".safevault"

    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Fallback to current user's home directory
        data_dir = Path.home() / ".safevault"
        data_dir.mkdir(parents=True, exist_ok=True)

    return data_dir
