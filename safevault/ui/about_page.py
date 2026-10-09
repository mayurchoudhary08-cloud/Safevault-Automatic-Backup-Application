"""About & Operating Systems Learning Section for SafeVault.

Provides comprehensive explanations of OS concepts demonstrated by the application
for college viva examinations, project presentations, and code review.
"""

from __future__ import annotations

import customtkinter as ctk

from safevault import __app_name__, __version__
from safevault.ui.common import CardFrame
from safevault.ui.theme import (
    COLOR_BG_MAIN,
    COLOR_BORDER,
    COLOR_PRIMARY_BLUE,
    COLOR_SECONDARY_BLUE,
    COLOR_SUCCESS,
    COLOR_TEXT_MAIN,
    COLOR_TEXT_MUTED,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_HEADING,
    FONT_MONO,
    FONT_SMALL,
    FONT_SUBHEADING,
)

OS_CONCEPTS = [
    (
        "1. File System Management & Directory Traversal",
        "How it works in SafeVault:\n"
        "The application uses hierarchical directory traversal (via os.walk and pathlib) to discover all files "
        "and subdirectories under the chosen source path. It inspects metadata such as file sizes and timestamps, "
        "re-creates missing directory branches, and ignores symbolic links by default to avoid unintended traversal outside the target tree.",
        "Key OS Concepts: Inodes/Directory entries, Path Resolution, Symbolic vs. Hard Links, Tree Traversal Algorithms.",
    ),
    (
        "2. File Input/Output (I/O) & Chunked Buffers",
        "How it works in SafeVault:\n"
        "Files are copied using 64 KB chunked binary read/write streams rather than reading entire files into RAM at once. "
        "This maintains constant low memory consumption regardless of whether a file is 10 KB or 10 GB. "
        "Simultaneously, chunk-level iteration allows checking cancellation signals mid-stream.",
        "Key OS Concepts: System Calls (read, write), Block I/O, Buffer Caching, Memory Constraints, File Descriptors.",
    ),
    (
        "3. Directory Structures & Relative Path Invariance",
        "How it works in SafeVault:\n"
        "SafeVault calculates relative paths (e.g. 'Notes/OS.txt') with respect to the source root. "
        "During restore, this relative path hierarchy is reconstructed inside an isolated restore root directory. "
        "Empty directories are recorded explicitly in manifest.json so that directory trees can be fully rebuilt.",
        "Key OS Concepts: Hierarchical File Systems, Relative vs. Absolute Paths, Directory Tables, Tree Reconstruction.",
    ),
    (
        "4. Processes, Multithreading & Event Loops",
        "How it works in SafeVault:\n"
        "To prevent GUI thread freezing ('Not Responding' state) during heavy disk I/O, SafeVault spawns independent worker "
        "threads (threading.Thread). Progress reports are passed safely to the main GUI event loop using thread-safe queues "
        "(queue.Queue), preventing race conditions and UI deadlocks.",
        "Key OS Concepts: Multithreading, Concurrency, Race Conditions, Inter-Thread Communication (Queues), Event Loops.",
    ),
    (
        "5. Scheduling & Polling Mechanisms",
        "How it works in SafeVault:\n"
        "SafeVault implements an application-level cooperative scheduler. A background thread polls timing conditions "
        "every minute to detect when a daily or weekly schedule is due. On application startup, a catch-up algorithm checks "
        "whether an enabled run was missed while the system was closed, executing at most one catch-up backup.",
        "Key OS Concepts: Task Scheduling, Polling vs. Interrupts, Persistent State, Catch-up Scheduling Policies.",
    ),
    (
        "6. Cryptographic File Integrity (SHA-256)",
        "How it works in SafeVault:\n"
        "Every copied file is digested through the SHA-256 cryptographic hash function. Hashes and byte sizes are stored in an "
        "immutable manifest.json. During verification or restore, recalculated hashes are matched against the manifest to detect "
        "bit rot, accidental modification, or silent disk corruption.",
        "Key OS Concepts: Cryptographic Checksums, Bit-Rot Detection, Data Integrity, Verification Pipelines.",
    ),
    (
        "7. Defensive Error Handling & Path Traversal Prevention",
        "How it works in SafeVault:\n"
        "The application performs defensive path sanitization: it rejects configurations where source and destination overlap "
        "(preventing infinite recursion loops), blocks directory traversal attacks ('..' path escapes) during restore, and handles "
        "permission denials gracefully using structured try/except blocks.",
        "Key OS Concepts: File Access Control (Permissions), Path Traversal Attacks, Atomic File Operations (rename), Exception Handling.",
    ),
]


class AboutView(ctk.CTkFrame):
    """View presenting project overview, technologies used, and OS viva examination guide."""

    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_MAIN, **kwargs)
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.scroll.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_app_overview_card()
        self._build_os_concepts_cards()

    def _build_header(self):
        title = ctk.CTkLabel(
            self.scroll,
            text=f"About {__app_name__} — Version {__version__}",
            font=FONT_HEADING,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        )
        title.pack(fill="x", pady=(0, 4))

        subtitle = ctk.CTkLabel(
            self.scroll,
            text="A practical Operating Systems desktop application demonstrating real local file operations.",
            font=FONT_BODY,
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        subtitle.pack(fill="x", pady=(0, 16))

    def _build_app_overview_card(self):
        card = CardFrame(self.scroll)
        card.pack(fill="x", pady=(0, 16))

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(16, 6))

        ctk.CTkLabel(top, text="Project Overview & Tech Stack", font=FONT_SUBHEADING, text_color=COLOR_TEXT_MAIN).pack(side="left")

        summary = (
            "SafeVault is built for students and desktop users to protect essential folders with dated snapshot copies. "
            "It emphasizes non-destructive operations: restoration creates new isolated folders, backups reject recursive loops, "
            "and cryptographic SHA-256 hashes guarantee data integrity."
        )
        ctk.CTkLabel(card, text=summary, font=FONT_BODY, text_color=COLOR_TEXT_MAIN, wraplength=640, justify="left", anchor="w").pack(
            fill="x", padx=16, pady=(0, 12)
        )

        tech_f = ctk.CTkFrame(card, fg_color="#F8FAFC", corner_radius=6)
        tech_f.pack(fill="x", padx=16, pady=(0, 16))

        techs = [
            ("Core Language", "Python 3.11+ / Python 3.13"),
            ("Desktop GUI", "CustomTkinter (Light Modern Desktop Theme)"),
            ("Persistent Storage", "SQLite 3 (Foreign keys, parameterized queries)"),
            ("Cryptography", "hashlib (SHA-256 chunked streaming)"),
            ("File Operations", "pathlib & shutil (Chunked streams, copystat metadata)"),
            ("Concurrency", "threading.Thread & queue.Queue (Non-blocking worker)"),
            ("Testing Framework", "unittest (22 automated test cases with isolated fixtures)"),
        ]
        for r, (k, v) in enumerate(techs):
            row = ctk.CTkFrame(tech_f, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(row, text=f"{k}:", font=FONT_SMALL, text_color=COLOR_TEXT_MUTED, width=150, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=v, font=FONT_SMALL, text_color=COLOR_TEXT_MAIN, anchor="w").pack(side="left")

    def _build_os_concepts_cards(self):
        section_lbl = ctk.CTkLabel(
            self.scroll,
            text="Operating Systems Concepts Demonstrated",
            font=FONT_HEADING,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        )
        section_lbl.pack(fill="x", pady=(8, 12))

        for title, explanation, viva_points in OS_CONCEPTS:
            c = CardFrame(self.scroll)
            c.pack(fill="x", pady=(0, 12))

            ctk.CTkLabel(c, text=title, font=FONT_SUBHEADING, text_color=COLOR_PRIMARY_BLUE, anchor="w").pack(
                fill="x", padx=16, pady=(14, 4)
            )

            ctk.CTkLabel(c, text=explanation, font=FONT_BODY, text_color=COLOR_TEXT_MAIN, justify="left", wraplength=640, anchor="w").pack(
                fill="x", padx=16, pady=(0, 8)
            )

            badge_box = ctk.CTkFrame(c, fg_color="#F1F5F9", corner_radius=6)
            badge_box.pack(fill="x", padx=16, pady=(0, 14))

            ctk.CTkLabel(
                badge_box,
                text=f"🎓 Viva Note: {viva_points}",
                font=FONT_SMALL,
                text_color=COLOR_SECONDARY_BLUE,
                justify="left",
                wraplength=620,
                anchor="w",
            ).pack(fill="x", padx=10, pady=6)
