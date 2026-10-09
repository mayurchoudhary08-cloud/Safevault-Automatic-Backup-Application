"""Demo Workspace generator for SafeVault.

Creates a harmless sample directory structure with representative files
for viva demonstration, testing, and tutorial walkthroughs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

SAMPLE_FILES = {
    "Notes/OS_Practical.txt": (
        "Operating Systems Practical Notes\n"
        "=================================\n"
        "Topic: Process Scheduling and Virtual Memory\n"
        "1. First-Come First-Served (FCFS)\n"
        "2. Shortest Job First (SJF)\n"
        "3. Round Robin (RR)\n"
        "SafeVault demonstrates multithreading and directory tree traversal."
    ),
    "Notes/DSA_Notes.txt": (
        "Data Structures & Algorithms\n"
        "============================\n"
        "Tree Traversals:\n"
        "- In-order (Left, Root, Right)\n"
        "- Pre-order (Root, Left, Right)\n"
        "- Post-order (Left, Right, Root)\n"
        "Used for recursive directory scanning."
    ),
    "Projects/sample_code.py": (
        '#!/usr/bin/env python3\n'
        '"""Sample student python project."""\n\n'
        'def compute_average(scores: list[float]) -> float:\n'
        '    if not scores:\n'
        '        return 0.0\n'
        '    return sum(scores) / len(scores)\n\n'
        'if __name__ == "__main__":\n'
        '    print("Student Project Grade Tracker")\n'
        '    print("Average:", compute_average([90, 85, 95]))\n'
    ),
    "Documents/assignment.txt": (
        "Operating Systems Assignment 1\n"
        "Name: Demo Student\n"
        "Subject: SafeVault Architecture Review\n"
        "Date: October 2026\n\n"
        "Goal: Demonstrate file system management and data integrity preservation."
    ),
}


def create_demo_workspace(target_parent_dir: Path | str) -> Tuple[bool, str, Path]:
    """Create a sample demo workspace inside target_parent_dir.

    Returns:
        (success, message, created_workspace_path)
    """
    parent = Path(target_parent_dir)
    if not parent.exists():
        return False, f"Target directory does not exist: {parent}", parent

    workspace_dir = parent / "SafeVault_Demo_Source"

    try:
        workspace_dir.mkdir(parents=True, exist_ok=True)

        for rel_path, content in SAMPLE_FILES.items():
            dest_file = workspace_dir / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            dest_file.write_text(content, encoding="utf-8")

        return True, f"Demo workspace successfully created at:\n{workspace_dir}", workspace_dir
    except Exception as e:
        return False, f"Failed to create demo workspace: {e}", workspace_dir
