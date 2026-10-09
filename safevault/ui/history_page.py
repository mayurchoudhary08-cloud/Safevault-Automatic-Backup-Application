"""Backup History Page for SafeVault.

Presents a comprehensive table of all previous backups with filtering,
snapshot manifest inspection, SHA-256 integrity re-verification, and restore triggers.
"""

from __future__ import annotations

import json
import customtkinter as ctk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from safevault.integrity import verify_snapshot_integrity
from safevault.logger import log_event
from safevault.ui.common import CardFrame, StatusBadge, format_bytes
from safevault.ui.theme import (
    COLOR_BG_MAIN,
    COLOR_BORDER,
    COLOR_ERROR,
    COLOR_HOVER_BLUE,
    COLOR_PRIMARY_BLUE,
    COLOR_SECONDARY_BLUE,
    COLOR_SUCCESS,
    COLOR_TEXT_MAIN,
    COLOR_TEXT_MUTED,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CARD_TITLE,
    FONT_HEADING,
    FONT_MONO,
    FONT_SMALL,
    FONT_SUBHEADING,
)

if TYPE_CHECKING:
    from safevault.app import SafeVaultApp


class BackupDetailsDialog(ctk.CTkToplevel):
    """Modal dialog displaying manifest details, file list, and cryptographic hashes."""

    def __init__(self, master, backup_run: Dict[str, Any]):
        super().__init__(master)
        b_id = backup_run["backup_id"]
        self.title(f"Backup Details — {b_id}")
        self.geometry("720x560")
        self.minsize(600, 400)
        self.configure(fg_color=COLOR_BG_MAIN)
        self.transient(master)

        container = CardFrame(self)
        container.pack(fill="both", expand=True, padx=20, pady=20)
        container.grid_columnconfigure(0, weight=1)

        # Header
        top_f = ctk.CTkFrame(container, fg_color="transparent")
        top_f.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(top_f, text=f"Snapshot: {b_id}", font=FONT_SUBHEADING, text_color=COLOR_TEXT_MAIN).pack(side="left")
        StatusBadge(top_f, status=backup_run.get("status", "UNKNOWN")).pack(side="right")

        # Metadata grid
        meta_f = ctk.CTkFrame(container, fg_color="#F8FAFC", corner_radius=6)
        meta_f.pack(fill="x", padx=16, pady=6)
        meta_f.grid_columnconfigure(1, weight=1)

        rows = [
            ("Start Time", backup_run.get("start_time", "-")),
            ("Completion Time", backup_run.get("completion_time", "-")),
            ("Source Path", backup_run.get("source_path", "-")),
            ("Snapshot Path", backup_run.get("snapshot_path", "-")),
            ("Total Size", format_bytes(backup_run.get("total_size_bytes", 0))),
            ("File Count", str(backup_run.get("file_count", 0))),
            ("Integrity", backup_run.get("verification_status", "UNVERIFIED")),
        ]
        for r_idx, (k, v) in enumerate(rows):
            ctk.CTkLabel(meta_f, text=f"{k}:", font=FONT_SMALL, text_color=COLOR_TEXT_MUTED, width=120, anchor="w").grid(
                row=r_idx, column=0, padx=10, pady=2, sticky="w"
            )
            ctk.CTkLabel(meta_f, text=str(v), font=FONT_SMALL, text_color=COLOR_TEXT_MAIN, anchor="w").grid(
                row=r_idx, column=1, padx=10, pady=2, sticky="w"
            )

        # File List from Manifest
        ctk.CTkLabel(
            container, text="Manifest Included Files & SHA-256 Hashes", font=FONT_BODY_BOLD, text_color=COLOR_TEXT_MAIN, anchor="w"
        ).pack(fill="x", padx=16, pady=(12, 4))

        snap_path = Path(backup_run.get("snapshot_path", ""))
        manifest_file = snap_path / "manifest.json"

        file_scroll = ctk.CTkScrollableFrame(container, fg_color="#FFFFFF", border_color=COLOR_BORDER, border_width=1)
        file_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        file_scroll.grid_columnconfigure(0, weight=1)

        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                files = manifest_data.get("files", [])
                if not files:
                    ctk.CTkLabel(file_scroll, text="No files recorded in manifest.", font=FONT_SMALL, text_color=COLOR_TEXT_MUTED).pack(pady=10)
                else:
                    for f_item in files:
                        item_f = ctk.CTkFrame(file_scroll, fg_color="#F8FAFC", corner_radius=4)
                        item_f.pack(fill="x", pady=2, padx=4)

                        rel_p = f_item.get("relative_path", "")
                        sz = format_bytes(f_item.get("size", 0))
                        sha = f_item.get("sha256", "")[:24] + "..."

                        ctk.CTkLabel(item_f, text=rel_p, font=FONT_SMALL, text_color=COLOR_TEXT_MAIN, anchor="w").pack(side="left", padx=8, pady=4)
                        ctk.CTkLabel(item_f, text=f"[{sz}]", font=FONT_SMALL, text_color=COLOR_TEXT_MUTED).pack(side="left", padx=4)
                        ctk.CTkLabel(item_f, text=f"SHA: {sha}", font=FONT_MONO, text_color=COLOR_SECONDARY_BLUE).pack(side="right", padx=8)
            except Exception as e:
                ctk.CTkLabel(file_scroll, text=f"Error reading manifest.json: {e}", font=FONT_SMALL, text_color=COLOR_ERROR).pack(pady=10)
        else:
            ctk.CTkLabel(file_scroll, text=f"manifest.json not found at:\n{manifest_file}", font=FONT_SMALL, text_color=COLOR_ERROR).pack(pady=10)

        # Close button
        btn_close = ctk.CTkButton(
            container,
            text="Close",
            font=FONT_BODY,
            fg_color="#E2E8F0",
            text_color=COLOR_TEXT_MAIN,
            hover_color="#CBD5E1",
            command=self.destroy,
            width=100,
        )
        btn_close.pack(side="bottom", padx=16, pady=(4, 16), anchor="e")


class BackupHistoryView(ctk.CTkFrame):
    """View to search, inspect, verify, and restore backups from SQLite records."""

    def __init__(self, master, app: "SafeVaultApp", **kwargs):
        super().__init__(master, fg_color=COLOR_BG_MAIN, **kwargs)
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.scroll.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_search_filter_bar()
        self._build_table_container()

    def _build_header(self):
        title = ctk.CTkLabel(
            self.scroll,
            text="Backup History",
            font=FONT_HEADING,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        )
        title.pack(fill="x", pady=(0, 4))

        subtitle = ctk.CTkLabel(
            self.scroll,
            text="Inspect previous dated snapshot versions, verify SHA-256 integrity, or restore files.",
            font=FONT_BODY,
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        subtitle.pack(fill="x", pady=(0, 16))

    def _build_search_filter_bar(self):
        filter_card = CardFrame(self.scroll)
        filter_card.pack(fill="x", pady=(0, 16))

        bar = ctk.CTkFrame(filter_card, fg_color="transparent")
        bar.pack(fill="x", padx=16, pady=12)
        bar.grid_columnconfigure(0, weight=1)

        self.entry_search = ctk.CTkEntry(
            bar,
            placeholder_text="🔍 Search backups by ID or folder path...",
            font=FONT_BODY,
            height=36,
        )
        self.entry_search.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self.entry_search.bind("<KeyRelease>", lambda e: self.filter_history())

        btn_refresh = ctk.CTkButton(
            bar,
            text="🔄 Refresh",
            font=FONT_BODY,
            fg_color="#F1F5F9",
            text_color=COLOR_TEXT_MAIN,
            hover_color="#E2E8F0",
            height=36,
            width=100,
            command=self.refresh_history,
        )
        btn_refresh.grid(row=0, column=1)

    def _build_table_container(self):
        self.table_card = CardFrame(self.scroll)
        self.table_card.pack(fill="x", pady=(0, 16))
        self.table_card.grid_columnconfigure(0, weight=1)

        # Table header row
        t_header = ctk.CTkFrame(self.table_card, fg_color="#F8FAFC", corner_radius=6)
        t_header.pack(fill="x", padx=12, pady=(12, 6))

        headers = [
            ("Date & Time", 140),
            ("Backup ID", 160),
            ("Files", 70),
            ("Size", 90),
            ("Status", 100),
            ("Integrity", 110),
            ("Actions", 200),
        ]
        for title, w in headers:
            ctk.CTkLabel(
                t_header,
                text=title,
                font=FONT_CARD_TITLE,
                text_color=COLOR_TEXT_MUTED,
                width=w,
                anchor="w",
            ).pack(side="left", padx=4, pady=8)

        self.rows_frame = ctk.CTkFrame(self.table_card, fg_color="transparent")
        self.rows_frame.pack(fill="x", padx=12, pady=(0, 12))

    def refresh_history(self):
        """Fetch all backup records from SQLite and display them."""
        self._all_records = self.app.db.get_all_backup_runs(order_by="start_time DESC")
        self.filter_history()

    def filter_history(self):
        """Filter cached records by search string and populate table rows."""
        query = self.entry_search.get().strip().lower()

        # Clear existing rows
        for child in self.rows_frame.winfo_children():
            child.destroy()

        if not hasattr(self, "_all_records") or not self._all_records:
            empty_frame = ctk.CTkFrame(self.rows_frame, fg_color="transparent")
            empty_frame.pack(fill="x", pady=24)
            ctk.CTkLabel(
                empty_frame,
                text="No backups yet. Choose a folder to protect and create your first backup.",
                font=FONT_BODY,
                text_color=COLOR_TEXT_MUTED,
            ).pack(pady=4)
            btn_create = ctk.CTkButton(
                empty_frame,
                text="Create First Backup",
                font=FONT_BODY_BOLD,
                fg_color=COLOR_PRIMARY_BLUE,
                hover_color="#1B3857",
                command=lambda: self.app.navigate_to("setup"),
            )
            btn_create.pack(pady=8)
            return

        filtered = [
            r for r in self._all_records
            if query in r.get("backup_id", "").lower() or query in r.get("source_path", "").lower()
        ]

        if not filtered:
            ctk.CTkLabel(
                self.rows_frame,
                text=f"No backup records match '{query}'.",
                font=FONT_BODY,
                text_color=COLOR_TEXT_MUTED,
            ).pack(pady=16)
            return

        for record in filtered:
            self._render_row(record)

    def _render_row(self, record: Dict[str, Any]):
        row_f = ctk.CTkFrame(self.rows_frame, fg_color="#FFFFFF", border_color=COLOR_BORDER, border_width=1, corner_radius=6)
        row_f.pack(fill="x", pady=3)

        b_id = record.get("backup_id", "")
        start_time = record.get("start_time", "")
        try:
            dt = datetime.fromisoformat(start_time)
            display_dt = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            display_dt = start_time

        file_cnt = str(record.get("file_count", 0))
        sz_str = format_bytes(record.get("total_size_bytes", 0))
        status = record.get("status", "UNKNOWN")
        integ_status = record.get("verification_status", "UNVERIFIED")

        # Date & Time
        ctk.CTkLabel(row_f, text=display_dt, font=FONT_SMALL, text_color=COLOR_TEXT_MAIN, width=140, anchor="w").pack(side="left", padx=4, pady=8)

        # Backup ID
        ctk.CTkLabel(row_f, text=b_id, font=FONT_MONO, text_color=COLOR_TEXT_MAIN, width=160, anchor="w").pack(side="left", padx=4, pady=8)

        # Files
        ctk.CTkLabel(row_f, text=file_cnt, font=FONT_SMALL, text_color=COLOR_TEXT_MUTED, width=70, anchor="w").pack(side="left", padx=4, pady=8)

        # Size
        ctk.CTkLabel(row_f, text=sz_str, font=FONT_SMALL, text_color=COLOR_TEXT_MAIN, width=90, anchor="w").pack(side="left", padx=4, pady=8)

        # Status
        badge_status = StatusBadge(row_f, status=status)
        badge_status.pack(side="left", padx=4, pady=6)

        # Integrity
        badge_integ = StatusBadge(row_f, status=integ_status)
        badge_integ.pack(side="left", padx=12, pady=6)

        # Action Buttons
        btn_box = ctk.CTkFrame(row_f, fg_color="transparent")
        btn_box.pack(side="right", padx=8, pady=6)

        btn_details = ctk.CTkButton(
            btn_box,
            text="Inspect",
            font=FONT_SMALL,
            fg_color="#F1F5F9",
            text_color=COLOR_TEXT_MAIN,
            hover_color="#E2E8F0",
            width=65,
            height=28,
            command=lambda r=record: self._open_details(r),
        )
        btn_details.pack(side="left", padx=2)

        btn_verify = ctk.CTkButton(
            btn_box,
            text="Verify",
            font=FONT_SMALL,
            fg_color="#F1F5F9",
            text_color=COLOR_PRIMARY_BLUE,
            hover_color="#E2E8F0",
            width=65,
            height=28,
            command=lambda r=record: self._verify_record(r),
        )
        btn_verify.pack(side="left", padx=2)

        btn_restore = ctk.CTkButton(
            btn_box,
            text="Restore",
            font=FONT_SMALL,
            fg_color=COLOR_PRIMARY_BLUE,
            hover_color="#1B3857",
            width=65,
            height=28,
            command=lambda r=record: self._restore_record(r),
        )
        btn_restore.pack(side="left", padx=2)

    def _open_details(self, record: Dict[str, Any]):
        BackupDetailsDialog(self, record)

    def _verify_record(self, record: Dict[str, Any]):
        snap_path = Path(record.get("snapshot_path", ""))
        b_id = record.get("backup_id", "")

        if not snap_path.exists():
            messagebox.showerror("Verification Error", f"Snapshot folder not found:\n{snap_path}")
            return

        report = verify_snapshot_integrity(snap_path)
        new_status = "VERIFIED" if report.is_valid else "FAILED"

        # Update SQLite record
        self.app.db.update_backup_run(b_id, verification_status=new_status)
        log_event(
            "INTEGRITY_PASSED" if report.is_valid else "INTEGRITY_FAILED",
            f"Manual verification of {b_id}: {report.summary_message}",
            b_id,
        )

        if report.is_valid:
            messagebox.showinfo(
                "Integrity Verification Passed",
                f"✓ Snapshot {b_id} is 100% Intact!\n\n"
                f"{report.summary_message}\n"
                f"All cryptographic hashes matched the manifest.",
            )
        else:
            err_details = "\n".join([f"- {f.relative_path}: {f.error_message}" for f in report.file_results if f.status != "OK"][:5])
            messagebox.showwarning(
                "Integrity Verification Failed",
                f"⚠️ Integrity Check Failed for {b_id}!\n\n"
                f"{report.summary_message}\n\n"
                f"Issues detected:\n{err_details}",
            )

        self.refresh_history()

    def _restore_record(self, record: Dict[str, Any]):
        b_id = record.get("backup_id", "")
        self.app.navigate_to("restore", preselect_backup_id=b_id)
