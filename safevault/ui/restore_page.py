"""Restore Center Page for SafeVault.

Provides non-destructive restoration of snapshots into new, isolated
directories with confirmation, integrity checks, and progress tracking.
"""

from __future__ import annotations

import json
import os
import subprocess
import customtkinter as ctk
from datetime import datetime
from pathlib import Path
from queue import Queue
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from safevault.restore_manager import RestoreProgress
from safevault.ui.common import CardFrame, ConfirmDialog, StatusBadge, format_bytes
from safevault.ui.theme import (
    COLOR_BG_MAIN,
    COLOR_BORDER,
    COLOR_ERROR,
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


class RestoreCenterView(ctk.CTkFrame):
    """View to select a snapshot, inspect contents, configure safe restore location, and restore."""

    def __init__(self, master, app: "SafeVaultApp", **kwargs):
        super().__init__(master, fg_color=COLOR_BG_MAIN, **kwargs)
        self.app = app
        self._selected_backup: Optional[Dict[str, Any]] = None
        self._restore_queue: Optional[Queue] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.scroll.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_progress_card()
        self._build_selection_card()
        self._build_overview_card()
        self._build_destination_card()
        self._build_file_list_preview_card()

    def _build_header(self):
        title = ctk.CTkLabel(
            self.scroll,
            text="Restore Center",
            font=FONT_HEADING,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        )
        title.pack(fill="x", pady=(0, 4))

        subtitle = ctk.CTkLabel(
            self.scroll,
            text="Safely retrieve earlier versions of your files into a separate, isolated folder.",
            font=FONT_BODY,
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        subtitle.pack(fill="x", pady=(0, 16))

    def _build_progress_card(self):
        self.progress_card = CardFrame(self.scroll, fg_color="#F0FDF4", border_color="#BBF7D0")
        self.progress_card.grid_columnconfigure(0, weight=1)

        p_header = ctk.CTkFrame(self.progress_card, fg_color="transparent")
        p_header.pack(fill="x", padx=16, pady=(12, 6))

        self.p_title_label = ctk.CTkLabel(
            p_header,
            text="🔄 Restoring Snapshot...",
            font=FONT_SUBHEADING,
            text_color=COLOR_SUCCESS,
            anchor="w",
        )
        self.p_title_label.pack(side="left")

        self.btn_cancel_restore = ctk.CTkButton(
            p_header,
            text="Cancel Restore",
            font=FONT_SMALL,
            fg_color=COLOR_ERROR,
            hover_color="#991B1B",
            width=100,
            command=self._on_cancel_restore_clicked,
        )
        self.btn_cancel_restore.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(
            self.progress_card,
            fg_color="#DCFCE7",
            progress_color=COLOR_SUCCESS,
            height=10,
        )
        self.progress_bar.pack(fill="x", padx=16, pady=4)
        self.progress_bar.set(0)

        p_details = ctk.CTkFrame(self.progress_card, fg_color="transparent")
        p_details.pack(fill="x", padx=16, pady=(4, 12))

        self.p_file_label = ctk.CTkLabel(
            p_details,
            text="Preparing restoration...",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        self.p_file_label.pack(side="left", fill="x", expand=True)

        self.p_stats_label = ctk.CTkLabel(
            p_details,
            text="",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_MAIN,
            anchor="e",
        )
        self.p_stats_label.pack(side="right")

        # Initially hidden
        self.progress_card.pack_forget()

    def _build_selection_card(self):
        card = CardFrame(self.scroll)
        card.pack(fill="x", pady=(0, 16))

        top_f = ctk.CTkFrame(card, fg_color="transparent")
        top_f.pack(fill="x", padx=16, pady=(14, 6))

        ctk.CTkLabel(
            top_f,
            text="1. Select Backup Snapshot Version",
            font=FONT_SUBHEADING,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        ).pack(side="left")

        select_f = ctk.CTkFrame(card, fg_color="transparent")
        select_f.pack(fill="x", padx=16, pady=(0, 14))
        select_f.grid_columnconfigure(0, weight=1)

        self.combo_backups = ctk.CTkComboBox(
            select_f,
            values=["No backups available"],
            font=FONT_BODY,
            height=38,
            command=self._on_backup_selected,
        )
        self.combo_backups.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        btn_refresh = ctk.CTkButton(
            select_f,
            text="🔄 Refresh",
            font=FONT_BODY,
            fg_color="#F1F5F9",
            text_color=COLOR_TEXT_MAIN,
            hover_color="#E2E8F0",
            height=38,
            width=90,
            command=self.refresh_restore_page,
        )
        btn_refresh.grid(row=0, column=1)

    def _build_overview_card(self):
        self.card_overview = CardFrame(self.scroll)
        self.card_overview.pack(fill="x", pady=(0, 16))

        header = ctk.CTkFrame(self.card_overview, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 6))

        ctk.CTkLabel(header, text="2. Snapshot Information", font=FONT_SUBHEADING, text_color=COLOR_TEXT_MAIN).pack(side="left")
        self.badge_integ = StatusBadge(header, status="UNVERIFIED")
        self.badge_integ.pack(side="right")

        grid = ctk.CTkFrame(self.card_overview, fg_color="#F8FAFC", corner_radius=6)
        grid.pack(fill="x", padx=16, pady=(0, 14))
        grid.grid_columnconfigure(1, weight=1)

        fields = [
            ("Created Timestamp", "lbl_created"),
            ("File Count", "lbl_file_count"),
            ("Total Size", "lbl_total_size"),
            ("Snapshot Directory", "lbl_snap_path"),
        ]
        self.info_labels = {}
        for r, (title, key) in enumerate(fields):
            ctk.CTkLabel(grid, text=f"{title}:", font=FONT_SMALL, text_color=COLOR_TEXT_MUTED, width=140, anchor="w").grid(
                row=r, column=0, padx=12, pady=3, sticky="w"
            )
            lbl = ctk.CTkLabel(grid, text="-", font=FONT_SMALL, text_color=COLOR_TEXT_MAIN, anchor="w")
            lbl.grid(row=r, column=1, padx=12, pady=3, sticky="w")
            self.info_labels[key] = lbl

    def _build_destination_card(self):
        card = CardFrame(self.scroll)
        card.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            card,
            text="3. Safe Restore Destination",
            font=FONT_SUBHEADING,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 4))

        explanation = (
            "Safety Guarantee: SafeVault will create a new, separate folder for the restored files.\n"
            "This ensures your existing documents and current project code are never silently overwritten."
        )
        ctk.CTkLabel(
            card,
            text=explanation,
            font=FONT_SMALL,
            text_color=COLOR_SUCCESS,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 8))

        row_dest = ctk.CTkFrame(card, fg_color="transparent")
        row_dest.pack(fill="x", padx=16, pady=(0, 8))
        row_dest.grid_columnconfigure(0, weight=1)

        self.entry_restore_parent = ctk.CTkEntry(
            row_dest,
            placeholder_text="Select destination folder for restored files...",
            font=FONT_BODY,
            height=38,
        )
        self.entry_restore_parent.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        btn_browse = ctk.CTkButton(
            row_dest,
            text="📁 Browse Destination...",
            font=FONT_BODY_BOLD,
            fg_color=COLOR_PRIMARY_BLUE,
            hover_color="#1B3857",
            height=38,
            width=160,
            command=self._on_browse_restore_dest,
        )
        btn_browse.grid(row=0, column=1)

        # Verification toggle checkbox
        self.check_verify = ctk.CTkCheckBox(
            card,
            text="Verify SHA-256 checksums before & after restoration",
            font=FONT_BODY,
            checkbox_height=20,
            checkbox_width=20,
        )
        self.check_verify.pack(padx=16, pady=(4, 12), anchor="w")
        self.check_verify.select()

        # Primary Restore Action
        self.btn_execute_restore = ctk.CTkButton(
            card,
            text="🚀  RESTORE THIS BACKUP",
            font=(FONT_BODY_BOLD[0], 13, "bold"),
            fg_color=COLOR_PRIMARY_BLUE,
            hover_color="#1B3857",
            height=44,
            command=self._on_restore_clicked,
        )
        self.btn_execute_restore.pack(fill="x", padx=16, pady=(4, 16))

    def _build_file_list_preview_card(self):
        self.card_files = CardFrame(self.scroll)
        self.card_files.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            self.card_files,
            text="4. Included Files Preview",
            font=FONT_SUBHEADING,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 6))

        self.scroll_files = ctk.CTkScrollableFrame(self.card_files, fg_color="#FFFFFF", border_color=COLOR_BORDER, border_width=1, height=180)
        self.scroll_files.pack(fill="x", padx=16, pady=(0, 14))
        self.scroll_files.grid_columnconfigure(0, weight=1)

    def refresh_restore_page(self, preselect_id: Optional[str] = None):
        """Populate backup options from SQLite."""
        runs = self.app.db.get_all_backup_runs(order_by="start_time DESC")
        # Filter for SUCCESS runs
        success_runs = [r for r in runs if r.get("status") == "SUCCESS"]

        self._available_runs = {r["backup_id"]: r for r in success_runs}

        if not success_runs:
            self.combo_backups.configure(values=["No successful backups found"])
            self.combo_backups.set("No successful backups found")
            self._clear_snapshot_details()
            self.btn_execute_restore.configure(state="disabled")
            return

        self.btn_execute_restore.configure(state="normal")
        display_values = [f"{r['backup_id']}  ({r['start_time'][:16].replace('T', ' ')})" for r in success_runs]
        self.combo_backups.configure(values=display_values)

        # Select target ID or newest
        target_run = None
        if preselect_id and preselect_id in self._available_runs:
            target_run = self._available_runs[preselect_id]
        else:
            target_run = success_runs[0]

        for disp in display_values:
            if disp.startswith(target_run["backup_id"]):
                self.combo_backups.set(disp)
                break

        self._load_snapshot_details(target_run)

    def _on_backup_selected(self, choice: str):
        b_id = choice.split()[0]
        if hasattr(self, "_available_runs") and b_id in self._available_runs:
            self._load_snapshot_details(self._available_runs[b_id])

    def _load_snapshot_details(self, run: Dict[str, Any]):
        self._selected_backup = run
        self.info_labels["lbl_created"].configure(text=run.get("start_time", "-"))
        self.info_labels["lbl_file_count"].configure(text=str(run.get("file_count", 0)))
        self.info_labels["lbl_total_size"].configure(text=format_bytes(run.get("total_size_bytes", 0)))
        self.info_labels["lbl_snap_path"].configure(text=run.get("snapshot_path", "-"))
        self.badge_integ.set_status(run.get("verification_status", "UNVERIFIED"))

        # Default restore parent: desktop or user documents or source parent
        src_p = Path(run.get("source_path", ""))
        default_parent = src_p.parent if src_p.exists() else Path.home() / "Documents"
        self.entry_restore_parent.delete(0, "end")
        self.entry_restore_parent.insert(0, str(default_parent))

        # Populate file preview from manifest
        for child in self.scroll_files.winfo_children():
            child.destroy()

        snap_path = Path(run.get("snapshot_path", ""))
        manifest_file = snap_path / "manifest.json"

        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                files = data.get("files", [])
                for f_item in files:
                    row = ctk.CTkFrame(self.scroll_files, fg_color="#F8FAFC", corner_radius=4)
                    row.pack(fill="x", pady=2, padx=4)
                    rel = f_item.get("relative_path", "")
                    sz = format_bytes(f_item.get("size", 0))
                    ctk.CTkLabel(row, text=rel, font=FONT_SMALL, text_color=COLOR_TEXT_MAIN, anchor="w").pack(side="left", padx=8, pady=3)
                    ctk.CTkLabel(row, text=sz, font=FONT_SMALL, text_color=COLOR_TEXT_MUTED).pack(side="right", padx=8)
            except Exception as e:
                ctk.CTkLabel(self.scroll_files, text=f"Error reading manifest: {e}", font=FONT_SMALL, text_color=COLOR_ERROR).pack(pady=6)
        else:
            ctk.CTkLabel(self.scroll_files, text="Manifest not found on disk.", font=FONT_SMALL, text_color=COLOR_ERROR).pack(pady=6)

    def _clear_snapshot_details(self):
        self._selected_backup = None
        for lbl in self.info_labels.values():
            lbl.configure(text="-")
        self.badge_integ.set_status("UNVERIFIED")
        for child in self.scroll_files.winfo_children():
            child.destroy()

    def _on_browse_restore_dest(self):
        selected = filedialog.askdirectory(title="Select Folder to Receive Restored Backup")
        if selected:
            self.entry_restore_parent.delete(0, "end")
            self.entry_restore_parent.insert(0, selected)

    def _on_restore_clicked(self):
        if not self._selected_backup:
            messagebox.showwarning("No Snapshot Selected", "Please select a backup snapshot first.")
            return

        parent_dir = self.entry_restore_parent.get().strip()
        if not parent_dir:
            messagebox.showwarning("Missing Destination", "Please choose a destination folder.")
            return

        if not Path(parent_dir).exists():
            messagebox.showerror("Invalid Destination", f"The destination folder does not exist:\n{parent_dir}")
            return

        b_id = self._selected_backup["backup_id"]
        target_restore_dir = self.app.restore_mgr.prepare_restore_destination(parent_dir, b_id)

        # Show Confirmation Dialog with full safety details
        details = [
            ("Backup Date", self._selected_backup.get("start_time", "")),
            ("Files to Restore", str(self._selected_backup.get("file_count", 0))),
            ("Total Data Size", format_bytes(self._selected_backup.get("total_size_bytes", 0))),
            ("Exact New Folder", str(target_restore_dir)),
            ("Integrity Status", self._selected_backup.get("verification_status", "UNVERIFIED")),
        ]

        def proceed():
            self._start_restore_process(target_restore_dir)

        ConfirmDialog(
            master=self,
            title="Confirm Safe File Restoration",
            message=(
                "SafeVault will restore the selected snapshot into a brand new folder. "
                "No existing files will be overwritten or deleted."
            ),
            details=details,
            confirm_text="Restore Files Now",
            cancel_text="Cancel",
            on_confirm=proceed,
            is_danger=False,
        )

    def _start_restore_process(self, target_dir: Path):
        snap_path = Path(self._selected_backup.get("snapshot_path", ""))
        do_verify = self.check_verify.get() == 1

        self._restore_queue = Queue()
        self.progress_card.pack(fill="x", pady=(0, 16), before=self.card_selection)
        self.btn_execute_restore.configure(state="disabled", text="⏳ Restoration in Progress...")

        def on_done(success: bool, msg: str, restored_path: str):
            self.app.root.after(0, lambda: self._on_restore_completed(success, msg, restored_path))

        started, err = self.app.restore_mgr.start_restore(
            snapshot_dir=snap_path,
            target_restore_dir=target_dir,
            verify_before=do_verify,
            verify_after=do_verify,
            progress_queue=self._restore_queue,
            on_complete=on_done,
        )

        if not started:
            self.progress_card.pack_forget()
            self.btn_execute_restore.configure(state="normal", text="🚀  RESTORE THIS BACKUP")
            messagebox.showerror("Restore Error", err)
            return

        self._poll_restore_progress()

    def _poll_restore_progress(self):
        if self._restore_queue is not None:
            while not self._restore_queue.empty():
                try:
                    p: RestoreProgress = self._restore_queue.get_nowait()
                    if p.total_files > 0:
                        frac = min(1.0, max(0.0, p.files_processed / p.total_files))
                        self.progress_bar.set(frac)
                        self.p_stats_label.configure(
                            text=f"{p.files_processed} / {p.total_files} files ({format_bytes(p.bytes_restored)})"
                        )
                    self.p_title_label.configure(text=f"🔄 Status: {p.status} ({p.elapsed_seconds}s)")
                    self.p_file_label.configure(text=p.current_file or p.error_message or "Restoring...")
                except Exception:
                    break

        if self.app.restore_mgr.is_running:
            self.after(100, self._poll_restore_progress)

    def _on_cancel_restore_clicked(self):
        self.app.restore_mgr.cancel_restore()
        self.btn_cancel_restore.configure(state="disabled", text="Cancelling...")

    def _on_restore_completed(self, success: bool, msg: str, restored_path: str):
        self.progress_card.pack_forget()
        self.btn_execute_restore.configure(state="normal", text="🚀  RESTORE THIS BACKUP")
        self.btn_cancel_restore.configure(state="normal", text="Cancel Restore")

        if success:
            open_folder = messagebox.askyesno(
                "Restoration Completed Successfully",
                f"✓ Restoration Complete!\n\n"
                f"{msg}\n\n"
                f"Would you like to open the restored folder in Windows Explorer now?",
            )
            if open_folder and Path(restored_path).exists():
                try:
                    os.startfile(restored_path)
                except Exception:
                    pass
        else:
            messagebox.showerror("Restoration Failed", f"Restore could not be completed:\n\n{msg}")

        self.app.refresh_all_views()
