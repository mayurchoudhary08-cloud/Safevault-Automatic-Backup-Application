"""Activity Log Page for SafeVault.

Provides an audit trail of all backup, restoration, verification,
and scheduler events with event type filtering and search.
"""

from __future__ import annotations

import customtkinter as ctk
from datetime import datetime
from tkinter import messagebox
from typing import TYPE_CHECKING, Any, Dict, List

from safevault.ui.common import CardFrame, ConfirmDialog, StatusBadge
from safevault.ui.theme import (
    COLOR_BG_MAIN,
    COLOR_BORDER,
    COLOR_ERROR,
    COLOR_PRIMARY_BLUE,
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

EVENT_FILTERS = [
    "ALL",
    "BACKUP_STARTED",
    "BACKUP_COMPLETED",
    "BACKUP_FAILED",
    "BACKUP_CANCELLED",
    "INTEGRITY_PASSED",
    "INTEGRITY_FAILED",
    "RESTORE_COMPLETED",
    "RESTORE_FAILED",
    "SCHEDULE_TRIGGERED",
]


class ActivityLogView(ctk.CTkFrame):
    """View to review, filter, and audit chronological application operations."""

    def __init__(self, master, app: "SafeVaultApp", **kwargs):
        super().__init__(master, fg_color=COLOR_BG_MAIN, **kwargs)
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.scroll.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_controls()
        self._build_log_table()

    def _build_header(self):
        title = ctk.CTkLabel(
            self.scroll,
            text="Activity Logs & Audit Trail",
            font=FONT_HEADING,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        )
        title.pack(fill="x", pady=(0, 4))

        subtitle = ctk.CTkLabel(
            self.scroll,
            text="Chronological record of all backup runs, SHA-256 checks, restore procedures, and scheduled events.",
            font=FONT_BODY,
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        subtitle.pack(fill="x", pady=(0, 16))

    def _build_controls(self):
        filter_card = CardFrame(self.scroll)
        filter_card.pack(fill="x", pady=(0, 16))

        bar = ctk.CTkFrame(filter_card, fg_color="transparent")
        bar.pack(fill="x", padx=16, pady=12)
        bar.grid_columnconfigure(1, weight=1)

        # Dropdown filter
        ctk.CTkLabel(bar, text="Filter Event:", font=FONT_BODY_BOLD, text_color=COLOR_TEXT_MUTED).grid(
            row=0, column=0, padx=(0, 8), sticky="w"
        )

        self.combo_filter = ctk.CTkComboBox(
            bar,
            values=EVENT_FILTERS,
            font=FONT_BODY,
            height=36,
            width=180,
            command=lambda v: self.filter_logs(),
        )
        self.combo_filter.set("ALL")
        self.combo_filter.grid(row=0, column=1, padx=(0, 12), sticky="w")

        # Search box
        self.entry_search = ctk.CTkEntry(
            bar,
            placeholder_text="Search message or backup ID...",
            font=FONT_BODY,
            height=36,
            width=240,
        )
        self.entry_search.grid(row=0, column=2, padx=(0, 8), sticky="e")
        self.entry_search.bind("<KeyRelease>", lambda e: self.filter_logs())

        btn_refresh = ctk.CTkButton(
            bar,
            text="🔄 Refresh",
            font=FONT_BODY,
            fg_color="#F1F5F9",
            text_color=COLOR_TEXT_MAIN,
            hover_color="#E2E8F0",
            height=36,
            width=90,
            command=self.refresh_activity_page,
        )
        btn_refresh.grid(row=0, column=3, padx=(0, 8))

        btn_clear = ctk.CTkButton(
            bar,
            text="Clear Logs",
            font=FONT_SMALL,
            fg_color="#FEF2F2",
            text_color=COLOR_ERROR,
            hover_color="#FEE2E2",
            height=36,
            width=90,
            command=self._on_clear_logs,
        )
        btn_clear.grid(row=0, column=4)

    def _build_log_table(self):
        self.card_table = CardFrame(self.scroll)
        self.card_table.pack(fill="x", pady=(0, 16))
        self.card_table.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.card_table, fg_color="#F8FAFC", corner_radius=6)
        header.pack(fill="x", padx=12, pady=(12, 6))

        ctk.CTkLabel(header, text="Timestamp", font=FONT_CARD_TITLE, text_color=COLOR_TEXT_MUTED, width=140, anchor="w").pack(side="left", padx=4, pady=8)
        ctk.CTkLabel(header, text="Event Type", font=FONT_CARD_TITLE, text_color=COLOR_TEXT_MUTED, width=150, anchor="w").pack(side="left", padx=4, pady=8)
        ctk.CTkLabel(header, text="Backup ID", font=FONT_CARD_TITLE, text_color=COLOR_TEXT_MUTED, width=160, anchor="w").pack(side="left", padx=4, pady=8)
        ctk.CTkLabel(header, text="Details & Message", font=FONT_CARD_TITLE, text_color=COLOR_TEXT_MUTED, anchor="w").pack(side="left", padx=8, pady=8, fill="x", expand=True)

        self.rows_frame = ctk.CTkFrame(self.card_table, fg_color="transparent")
        self.rows_frame.pack(fill="x", padx=12, pady=(0, 12))

    def refresh_activity_page(self):
        """Fetch latest activity logs from SQLite."""
        self._all_logs = self.app.db.get_activity_logs(limit=250)
        self.filter_logs()

    def filter_logs(self):
        """Filter cached logs by event type and search query."""
        selected_filter = self.combo_filter.get()
        query = self.entry_search.get().strip().lower()

        for child in self.rows_frame.winfo_children():
            child.destroy()

        if not hasattr(self, "_all_logs") or not self._all_logs:
            ctk.CTkLabel(
                self.rows_frame,
                text="No activity logs recorded yet.",
                font=FONT_BODY,
                text_color=COLOR_TEXT_MUTED,
            ).pack(pady=20)
            return

        filtered = self._all_logs
        if selected_filter != "ALL":
            filtered = [log for log in filtered if log.get("event_type") == selected_filter]

        if query:
            filtered = [
                log for log in filtered
                if query in log.get("message", "").lower() or query in str(log.get("backup_id", "")).lower()
            ]

        if not filtered:
            ctk.CTkLabel(
                self.rows_frame,
                text="No logs match the current filter criteria.",
                font=FONT_BODY,
                text_color=COLOR_TEXT_MUTED,
            ).pack(pady=16)
            return

        for entry in filtered:
            self._render_log_row(entry)

    def _render_log_row(self, entry: Dict[str, Any]):
        row_f = ctk.CTkFrame(self.rows_frame, fg_color="#FFFFFF", border_color=COLOR_BORDER, border_width=1, corner_radius=6)
        row_f.pack(fill="x", pady=2)

        ts = entry.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts)
            display_ts = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            display_ts = ts

        event_t = entry.get("event_type", "INFO")
        b_id = entry.get("backup_id") or "-"
        msg = entry.get("message", "")

        # Timestamp
        ctk.CTkLabel(row_f, text=display_ts, font=FONT_SMALL, text_color=COLOR_TEXT_MUTED, width=140, anchor="w").pack(side="left", padx=4, pady=6)

        # Event Badge
        badge = StatusBadge(row_f, status=event_t)
        badge.pack(side="left", padx=4, pady=6)

        # Backup ID
        ctk.CTkLabel(row_f, text=b_id, font=FONT_MONO, text_color=COLOR_SECONDARY_BLUE, width=160, anchor="w").pack(side="left", padx=8, pady=6)

        # Message
        ctk.CTkLabel(row_f, text=msg, font=FONT_SMALL, text_color=COLOR_TEXT_MAIN, anchor="w", wraplength=480, justify="left").pack(
            side="left", padx=8, pady=6, fill="x", expand=True
        )

    def _on_clear_logs(self):
        def clear_confirmed():
            self.app.db.clear_activity_logs()
            self.refresh_activity_page()

        ConfirmDialog(
            master=self,
            title="Clear Activity Logs",
            message="Are you sure you want to clear all recorded activity logs? This does not delete any backups.",
            confirm_text="Clear All Logs",
            is_danger=True,
            on_confirm=clear_confirmed,
        )
