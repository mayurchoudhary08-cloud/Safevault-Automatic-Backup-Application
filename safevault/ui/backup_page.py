"""Backup Setup Page for SafeVault.

Allows users to configure and validate source and destination folders
with real-time path safety checks (preventing recursive backups and loops).
"""

from __future__ import annotations

import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

from safevault.paths import validate_backup_paths
from safevault.ui.common import CardFrame
from safevault.ui.theme import (
    COLOR_BG_MAIN,
    COLOR_BORDER,
    COLOR_ERROR,
    COLOR_PRIMARY_BLUE,
    COLOR_SUCCESS,
    COLOR_TEXT_MAIN,
    COLOR_TEXT_MUTED,
    COLOR_WARNING,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_HEADING,
    FONT_SMALL,
    FONT_SUBHEADING,
)

if TYPE_CHECKING:
    from safevault.app import SafeVaultApp


class BackupSetupView(ctk.CTkFrame):
    """View to select, inspect, and validate source and backup destination paths."""

    def __init__(self, master, app: "SafeVaultApp", **kwargs):
        super().__init__(master, fg_color=COLOR_BG_MAIN, **kwargs)
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.scroll.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_folder_selectors()
        self._build_validation_card()
        self._build_guidance_card()

    def _build_header(self):
        title = ctk.CTkLabel(
            self.scroll,
            text="Backup Setup & Folders",
            font=FONT_HEADING,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        )
        title.pack(fill="x", pady=(0, 4))

        subtitle = ctk.CTkLabel(
            self.scroll,
            text="Configure which folder to protect and where your dated backup snapshots will be kept.",
            font=FONT_BODY,
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        subtitle.pack(fill="x", pady=(0, 16))

    def _build_folder_selectors(self):
        card = CardFrame(self.scroll)
        card.pack(fill="x", pady=(0, 16))

        # --- Source Folder Section ---
        f_src = ctk.CTkFrame(card, fg_color="transparent")
        f_src.pack(fill="x", padx=16, pady=(16, 12))

        lbl_src_title = ctk.CTkLabel(
            f_src,
            text="1. Source Folder (Files to Protect)",
            font=FONT_SUBHEADING,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        )
        lbl_src_title.pack(fill="x", pady=(0, 4))

        lbl_src_hint = ctk.CTkLabel(
            f_src,
            text="Select your project directory, documents, or assignments folder.",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        lbl_src_hint.pack(fill="x", pady=(0, 6))

        row_src = ctk.CTkFrame(f_src, fg_color="transparent")
        row_src.pack(fill="x")
        row_src.grid_columnconfigure(0, weight=1)

        self.entry_source = ctk.CTkEntry(
            row_src,
            placeholder_text="e.g. C:/Users/Student/Documents/College_Projects",
            font=FONT_BODY,
            height=38,
        )
        self.entry_source.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        btn_browse_src = ctk.CTkButton(
            row_src,
            text="📁 Browse Source...",
            font=FONT_BODY_BOLD,
            fg_color=COLOR_PRIMARY_BLUE,
            hover_color="#1B3857",
            height=38,
            width=150,
            command=self._on_browse_source,
        )
        btn_browse_src.grid(row=0, column=1)

        # Divider
        div = ctk.CTkFrame(card, fg_color=COLOR_BORDER, height=1)
        div.pack(fill="x", padx=16, pady=6)

        # --- Destination Folder Section ---
        f_dst = ctk.CTkFrame(card, fg_color="transparent")
        f_dst.pack(fill="x", padx=16, pady=(12, 16))

        lbl_dst_title = ctk.CTkLabel(
            f_dst,
            text="2. Backup Destination (Snapshot Storage)",
            font=FONT_SUBHEADING,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        )
        lbl_dst_title.pack(fill="x", pady=(0, 4))

        lbl_dst_hint = ctk.CTkLabel(
            f_dst,
            text="Select a separate folder or external drive where snapshots will be placed.",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        lbl_dst_hint.pack(fill="x", pady=(0, 6))

        row_dst = ctk.CTkFrame(f_dst, fg_color="transparent")
        row_dst.pack(fill="x")
        row_dst.grid_columnconfigure(0, weight=1)

        self.entry_dest = ctk.CTkEntry(
            row_dst,
            placeholder_text="e.g. D:/SafeVault_Backups",
            font=FONT_BODY,
            height=38,
        )
        self.entry_dest.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        btn_browse_dst = ctk.CTkButton(
            row_dst,
            text="📁 Browse Dest...",
            font=FONT_BODY_BOLD,
            fg_color=COLOR_PRIMARY_BLUE,
            hover_color="#1B3857",
            height=38,
            width=150,
            command=self._on_browse_dest,
        )
        btn_browse_dst.grid(row=0, column=1)

        # Action buttons row
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(6, 16))

        self.btn_save_config = ctk.CTkButton(
            btn_row,
            text="Save Folder Settings",
            font=FONT_BODY_BOLD,
            fg_color=COLOR_PRIMARY_BLUE,
            hover_color="#1B3857",
            height=40,
            command=self._on_save_clicked,
            width=180,
        )
        self.btn_save_config.pack(side="left")

        self.btn_test_validate = ctk.CTkButton(
            btn_row,
            text="Verify Path Safety",
            font=FONT_BODY,
            fg_color="#F1F5F9",
            text_color=COLOR_TEXT_MAIN,
            hover_color="#E2E8F0",
            height=40,
            command=self._validate_current_paths,
            width=150,
        )
        self.btn_test_validate.pack(side="left", padx=8)

    def _build_validation_card(self):
        self.card_validation = CardFrame(self.scroll, fg_color="#F8FAFC")
        self.card_validation.pack(fill="x", pady=(0, 16))

        self.lbl_valid_title = ctk.CTkLabel(
            self.card_validation,
            text="Path Safety Status",
            font=FONT_BODY_BOLD,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        )
        self.lbl_valid_title.pack(fill="x", padx=16, pady=(12, 4))

        self.lbl_valid_message = ctk.CTkLabel(
            self.card_validation,
            text="Select source and destination folders above to test configuration.",
            font=FONT_BODY,
            text_color=COLOR_TEXT_MUTED,
            justify="left",
            wraplength=600,
            anchor="w",
        )
        self.lbl_valid_message.pack(fill="x", padx=16, pady=(0, 12))

    def _build_guidance_card(self):
        guide = CardFrame(self.scroll)
        guide.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            guide,
            text="🛡️ Operating Systems Concept: Recursive Backup Prevention",
            font=FONT_SUBHEADING,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 6))

        explanation = (
            "Why must destination never be inside source?\n"
            "If your backup destination was placed inside the source folder being backed up, each subsequent "
            "backup operation would recursively scan and back up previous snapshots! This causes an exponential "
            "directory explosion and quickly consumes available disk space.\n\n"
            "SafeVault strictly validates both paths with Path.resolve() to prevent infinite recursive loops "
            "before any file operations begin."
        )
        ctk.CTkLabel(
            guide,
            text=explanation,
            font=FONT_BODY,
            text_color=COLOR_TEXT_MUTED,
            justify="left",
            wraplength=640,
            anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 14))

    def refresh_setup(self):
        """Load saved paths from settings into entries."""
        settings = self.app.db.get_all_settings()
        src = settings.get("source_folder", "")
        dst = settings.get("backup_destination", "")

        self.entry_source.delete(0, "end")
        self.entry_source.insert(0, src)

        self.entry_dest.delete(0, "end")
        self.entry_dest.insert(0, dst)

        self._validate_current_paths()

    def _on_browse_source(self):
        selected = filedialog.askdirectory(title="Select Source Folder to Protect")
        if selected:
            self.entry_source.delete(0, "end")
            self.entry_source.insert(0, selected)
            self._validate_current_paths()

    def _on_browse_dest(self):
        selected = filedialog.askdirectory(title="Select Destination Folder for Backups")
        if selected:
            self.entry_dest.delete(0, "end")
            self.entry_dest.insert(0, selected)
            self._validate_current_paths()

    def _validate_current_paths(self) -> bool:
        src = self.entry_source.get().strip()
        dst = self.entry_dest.get().strip()

        if not src or not dst:
            self.card_validation.configure(fg_color="#F8FAFC", border_color=COLOR_BORDER)
            self.lbl_valid_title.configure(text="Path Status: Incomplete", text_color=COLOR_TEXT_MUTED)
            self.lbl_valid_message.configure(
                text="Please select both a source folder and a destination folder to validate.",
                text_color=COLOR_TEXT_MUTED,
            )
            return False

        valid, err_msg = validate_backup_paths(src, dst)
        if valid:
            self.card_validation.configure(fg_color="#F0FDF4", border_color="#BBF7D0")
            self.lbl_valid_title.configure(text="✓ Paths Valid & Safe", text_color=COLOR_SUCCESS)
            self.lbl_valid_message.configure(
                text="The selected folders are distinct, non-overlapping, and ready for backup operations.",
                text_color=COLOR_SUCCESS,
            )
            return True
        else:
            self.card_validation.configure(fg_color="#FEF2F2", border_color="#FECACA")
            self.lbl_valid_title.configure(text="⚠️ Configuration Rejected", text_color=COLOR_ERROR)
            self.lbl_valid_message.configure(text=err_msg, text_color=COLOR_ERROR)
            return False

    def _on_save_clicked(self):
        src = self.entry_source.get().strip()
        dst = self.entry_dest.get().strip()

        valid, err_msg = validate_backup_paths(src, dst)
        if not valid:
            messagebox.showerror("Invalid Folder Configuration", err_msg)
            self._validate_current_paths()
            return

        self.app.db.set_setting("source_folder", src)
        self.app.db.set_setting("backup_destination", dst)
        messagebox.showinfo("Configuration Saved", "Source and backup destination folders have been successfully saved!")
        self.app.refresh_all_views()
