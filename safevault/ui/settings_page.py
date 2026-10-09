"""Schedule & Settings Page for SafeVault.

Configures automatic backup frequencies, preferred times, post-backup verification,
and displays calculated upcoming backup runs.
"""

from __future__ import annotations

import customtkinter as ctk
from datetime import datetime
from tkinter import messagebox
from typing import TYPE_CHECKING

from safevault.scheduler import DAY_NAMES, calculate_next_run_time
from safevault.ui.common import CardFrame
from safevault.ui.theme import (
    COLOR_BG_MAIN,
    COLOR_BORDER,
    COLOR_PRIMARY_BLUE,
    COLOR_SUCCESS,
    COLOR_TEXT_MAIN,
    COLOR_TEXT_MUTED,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CARD_TITLE,
    FONT_HEADING,
    FONT_SMALL,
    FONT_SUBHEADING,
)

if TYPE_CHECKING:
    from safevault.app import SafeVaultApp


class SettingsView(ctk.CTkFrame):
    """View to configure background backup scheduling and application options."""

    def __init__(self, master, app: "SafeVaultApp", **kwargs):
        super().__init__(master, fg_color=COLOR_BG_MAIN, **kwargs)
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.scroll.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_schedule_card()
        self._build_verification_card()
        self._build_action_button()

    def _build_header(self):
        title = ctk.CTkLabel(
            self.scroll,
            text="Schedule & Settings",
            font=FONT_HEADING,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        )
        title.pack(fill="x", pady=(0, 4))

        subtitle = ctk.CTkLabel(
            self.scroll,
            text="Configure automated background backups and snapshot verification policies.",
            font=FONT_BODY,
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        subtitle.pack(fill="x", pady=(0, 16))

    def _build_schedule_card(self):
        card = CardFrame(self.scroll)
        card.pack(fill="x", pady=(0, 16))

        top_f = ctk.CTkFrame(card, fg_color="transparent")
        top_f.pack(fill="x", padx=16, pady=(16, 6))

        ctk.CTkLabel(
            top_f,
            text="Automatic Backup Schedule",
            font=FONT_SUBHEADING,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        ).pack(side="left")

        self.switch_schedule = ctk.CTkSwitch(
            top_f,
            text="Enable Schedule",
            font=FONT_BODY_BOLD,
            command=self._on_schedule_toggle,
        )
        self.switch_schedule.pack(side="right")

        # Scope and explanation note
        note_f = ctk.CTkFrame(card, fg_color="#F8FAFC", corner_radius=6)
        note_f.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(
            note_f,
            text=(
                "ℹ️ SafeVault Schedule Operation:\n"
                "• Scheduled backups run automatically in the background while SafeVault is open.\n"
                "• If a scheduled backup was missed while SafeVault was closed, a single catch-up backup "
                "will automatically run when you next open the application.\n"
                "• To ensure zero background interference, SafeVault does not install persistent Windows system services."
            ),
            font=FONT_SMALL,
            text_color=COLOR_TEXT_MUTED,
            justify="left",
            wraplength=640,
            anchor="w",
        ).pack(padx=12, pady=10, fill="x")

        # Frequency & Time controls
        form_f = ctk.CTkFrame(card, fg_color="transparent")
        form_f.pack(fill="x", padx=16, pady=(8, 14))
        form_f.grid_columnconfigure(1, weight=1)

        # Frequency
        ctk.CTkLabel(form_f, text="Backup Frequency:", font=FONT_BODY_BOLD, text_color=COLOR_TEXT_MAIN, width=150, anchor="w").grid(
            row=0, column=0, pady=6, sticky="w"
        )
        self.seg_frequency = ctk.CTkSegmentedButton(
            form_f,
            values=["Daily", "Weekly"],
            font=FONT_BODY,
            command=self._on_frequency_change,
        )
        self.seg_frequency.set("Daily")
        self.seg_frequency.grid(row=0, column=1, pady=6, sticky="w")

        # Preferred Time
        ctk.CTkLabel(form_f, text="Preferred Time (HH:MM):", font=FONT_BODY_BOLD, text_color=COLOR_TEXT_MAIN, width=150, anchor="w").grid(
            row=1, column=0, pady=6, sticky="w"
        )
        self.entry_time = ctk.CTkEntry(form_f, placeholder_text="12:00", font=FONT_BODY, width=120)
        self.entry_time.grid(row=1, column=1, pady=6, sticky="w")
        self.entry_time.bind("<KeyRelease>", lambda e: self._update_next_run_preview())

        # Preferred Day (for Weekly)
        self.lbl_day = ctk.CTkLabel(form_f, text="Day of the Week:", font=FONT_BODY_BOLD, text_color=COLOR_TEXT_MAIN, width=150, anchor="w")
        self.lbl_day.grid(row=2, column=0, pady=6, sticky="w")
        self.combo_day = ctk.CTkComboBox(form_f, values=DAY_NAMES, font=FONT_BODY, width=160, command=lambda v: self._update_next_run_preview())
        self.combo_day.set("Monday")
        self.combo_day.grid(row=2, column=1, pady=6, sticky="w")

        # Next Run live calculation card
        self.preview_box = ctk.CTkFrame(card, fg_color="#F0FDF4", border_color="#BBF7D0", border_width=1, corner_radius=6)
        self.preview_box.pack(fill="x", padx=16, pady=(4, 16))

        self.lbl_next_run = ctk.CTkLabel(
            self.preview_box,
            text="Next Expected Backup: -",
            font=FONT_BODY_BOLD,
            text_color=COLOR_SUCCESS,
            anchor="w",
        )
        self.lbl_next_run.pack(padx=12, pady=10, fill="x")

    def _build_verification_card(self):
        card = CardFrame(self.scroll)
        card.pack(fill="x", pady=(0, 16))

        top_f = ctk.CTkFrame(card, fg_color="transparent")
        top_f.pack(fill="x", padx=16, pady=(16, 6))

        ctk.CTkLabel(
            top_f,
            text="Snapshot Integrity Policy",
            font=FONT_SUBHEADING,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        ).pack(side="left")

        self.switch_verify = ctk.CTkSwitch(
            top_f,
            text="Auto-Verify Backups",
            font=FONT_BODY_BOLD,
        )
        self.switch_verify.pack(side="right")

        desc = (
            "When enabled, SafeVault recalculates the SHA-256 checksum of every copied file immediately "
            "after a backup finishes, guaranteeing that no byte-level disk errors occurred during copying."
        )
        ctk.CTkLabel(
            card,
            text=desc,
            font=FONT_SMALL,
            text_color=COLOR_TEXT_MUTED,
            justify="left",
            wraplength=640,
            anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 16))

    def _build_action_button(self):
        btn_save = ctk.CTkButton(
            self.scroll,
            text="Save Schedule & Settings",
            font=FONT_BODY_BOLD,
            fg_color=COLOR_PRIMARY_BLUE,
            hover_color="#1B3857",
            height=44,
            command=self._on_save_settings,
        )
        btn_save.pack(fill="x", pady=(0, 20))

    def refresh_settings(self):
        """Load current settings from SQLite into UI controls."""
        settings = self.app.db.get_all_settings()

        enabled = settings.get("schedule_enabled", "0") == "1"
        if enabled:
            self.switch_schedule.select()
        else:
            self.switch_schedule.deselect()

        freq = settings.get("schedule_frequency", "daily").capitalize()
        self.seg_frequency.set(freq if freq in ["Daily", "Weekly"] else "Daily")

        time_str = settings.get("schedule_time", "12:00")
        self.entry_time.delete(0, "end")
        self.entry_time.insert(0, time_str)

        day_str = settings.get("schedule_day", "Monday")
        self.combo_day.set(day_str if day_str in DAY_NAMES else "Monday")

        verify = settings.get("verify_after_backup", "1") == "1"
        if verify:
            self.switch_verify.select()
        else:
            self.switch_verify.deselect()

        self._on_schedule_toggle()
        self._on_frequency_change(self.seg_frequency.get())
        self._update_next_run_preview()

    def _on_schedule_toggle(self):
        is_on = self.switch_schedule.get() == 1
        state = "normal" if is_on else "disabled"
        self.seg_frequency.configure(state=state)
        self.entry_time.configure(state=state)
        self.combo_day.configure(state=state)
        self._update_next_run_preview()

    def _on_frequency_change(self, value: str):
        if value.lower() == "weekly":
            self.lbl_day.grid()
            self.combo_day.grid()
        else:
            self.lbl_day.grid_remove()
            self.combo_day.grid_remove()
        self._update_next_run_preview()

    def _update_next_run_preview(self):
        is_on = self.switch_schedule.get() == 1
        if not is_on:
            self.preview_box.configure(fg_color="#F8FAFC", border_color=COLOR_BORDER)
            self.lbl_next_run.configure(text="Schedule is currently disabled.", text_color=COLOR_TEXT_MUTED)
            return

        freq = self.seg_frequency.get().lower()
        t_str = self.entry_time.get().strip() or "12:00"
        d_str = self.combo_day.get()

        try:
            next_run = calculate_next_run_time(freq, t_str, d_str)
            self.preview_box.configure(fg_color="#F0FDF4", border_color="#BBF7D0")
            self.lbl_next_run.configure(
                text=f"Next Expected Backup: {next_run.strftime('%A, %B %d, %Y at %H:%M')}",
                text_color=COLOR_SUCCESS,
            )
        except Exception:
            self.preview_box.configure(fg_color="#FEF2F2", border_color="#FECACA")
            self.lbl_next_run.configure(text="Invalid time format. Please use HH:MM (e.g. 14:30).", text_color=COLOR_ERROR)

    def _on_save_settings(self):
        # Validate time format
        t_str = self.entry_time.get().strip()
        try:
            parts = t_str.split(":")
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError()
        except Exception:
            messagebox.showerror("Invalid Time", "Please enter a valid 24-hour time in HH:MM format (e.g. 14:00).")
            return

        enabled_val = "1" if self.switch_schedule.get() == 1 else "0"
        freq_val = self.seg_frequency.get().lower()
        day_val = self.combo_day.get()
        verify_val = "1" if self.switch_verify.get() == 1 else "0"

        db = self.app.db
        db.set_setting("schedule_enabled", enabled_val)
        db.set_setting("schedule_frequency", freq_val)
        db.set_setting("schedule_time", t_str)
        db.set_setting("schedule_day", day_val)
        db.set_setting("verify_after_backup", verify_val)

        messagebox.showinfo("Settings Saved", "Your schedule and verification settings have been saved successfully!")
        self.app.refresh_all_views()
