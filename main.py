#!/usr/bin/env python3
"""SafeVault — Automatic Backup & Restore Desktop Application.

Entry point for the application.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path so modules can be imported directly
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def check_prerequisites():
    """Verify that required dependencies and Python version are satisfied."""
    if sys.version_info < (3, 10):
        print(
            f"Error: SafeVault requires Python 3.10 or newer. "
            f"You are currently running Python {sys.version_info.major}.{sys.version_info.minor}."
        )
        sys.exit(1)

    try:
        import customtkinter
    except ImportError:
        print("=" * 60)
        print("Missing required dependency: customtkinter")
        print("Please install required dependencies by running:")
        print("    pip install -r requirements.txt")
        print("or:")
        print("    py -m pip install customtkinter")
        print("=" * 60)
        sys.exit(1)


def main():
    """Run the SafeVault desktop application."""
    check_prerequisites()

    from safevault.app import SafeVaultApp

    # Use local safevault.db if present beside main.py (dev/portable mode),
    # otherwise defaults to safe per-user local app data directory (%LOCALAPPDATA%/SafeVault)
    local_db = project_root / "safevault.db"
    db_path = local_db if local_db.exists() else None

    app = SafeVaultApp(db_path=db_path)
    app.run()


if __name__ == "__main__":
    main()
