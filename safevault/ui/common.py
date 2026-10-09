"""Common reusable UI components and helper utilities for SafeVault."""

from __future__ import annotations

import customtkinter as ctk
from typing import Callable, Optional

from safevault.ui.theme import (
    COLOR_BORDER,
    COLOR_CARD_BG,
    COLOR_ERROR,
    COLOR_PRIMARY_BLUE,
    COLOR_SECONDARY_BLUE,
    COLOR_SUCCESS,
    COLOR_TEXT_MAIN,
    COLOR_TEXT_MUTED,
    COLOR_WARNING,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CARD_TITLE,
    FONT_CARD_VALUE,
    FONT_SMALL,
)


def format_bytes(size_bytes: int) -> str:
    """Format bytes into readable human-friendly units (B, KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class CardFrame(ctk.CTkFrame):
    """Clean white card with subtle border and rounded corners."""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLOR_CARD_BG)
        kwargs.setdefault("border_color", COLOR_BORDER)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("corner_radius", 8)
        super().__init__(master, **kwargs)


class MetricCard(CardFrame):
    """Displays a key dashboard metric with a label, value, and subtitle."""

    def __init__(self, master, title: str, initial_value: str = "0", subtitle: str = "", **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self,
            text=title.upper(),
            font=FONT_CARD_TITLE,
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        self.value_label = ctk.CTkLabel(
            self,
            text=initial_value,
            font=FONT_CARD_VALUE,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        )
        self.value_label.grid(row=1, column=0, padx=16, pady=2, sticky="w")

        self.subtitle_label = ctk.CTkLabel(
            self,
            text=subtitle,
            font=FONT_SMALL,
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        self.subtitle_label.grid(row=2, column=0, padx=16, pady=(2, 14), sticky="w")

    def update_metric(self, value: str, subtitle: Optional[str] = None):
        self.value_label.configure(text=value)
        if subtitle is not None:
            self.subtitle_label.configure(text=subtitle)


class StatusBadge(ctk.CTkFrame):
    """Colored status badge for tables and status displays."""

    def __init__(self, master, status: str, **kwargs):
        bg_color, fg_color = self._get_status_colors(status)
        super().__init__(
            master,
            fg_color=bg_color,
            corner_radius=6,
            height=24,
            **kwargs,
        )
        self.label = ctk.CTkLabel(
            self,
            text=status.upper(),
            font=(FONT_SMALL[0], 9, "bold"),
            text_color=fg_color,
        )
        self.label.pack(padx=8, pady=2)

    def set_status(self, status: str):
        bg_color, fg_color = self._get_status_colors(status)
        self.configure(fg_color=bg_color)
        self.label.configure(text=status.upper(), text_color=fg_color)

    @staticmethod
    def _get_status_colors(status: str) -> tuple[str, str]:
        s = status.upper()
        if s in ("SUCCESS", "VERIFIED", "COMPLETED", "ACTIVE", "READY"):
            return "#E8F5E9", COLOR_SUCCESS
        elif s in ("FAILED", "ERROR", "CORRUPT"):
            return "#FFEBEE", COLOR_ERROR
        elif s in ("CANCELLED", "WARNING", "PARTIAL", "UNVERIFIED"):
            return "#FFF8E1", COLOR_WARNING
        elif s in ("IN_PROGRESS", "RUNNING", "RESTORING", "COPYING"):
            return "#E3F2FD", COLOR_PRIMARY_BLUE
        return "#F1F5F9", COLOR_TEXT_MUTED


class ConfirmDialog(ctk.CTkToplevel):
    """Modal confirmation dialog for destructive or critical actions."""

    def __init__(
        self,
        master,
        title: str,
        message: str,
        details: list[tuple[str, str]] | None = None,
        confirm_text: str = "Confirm",
        cancel_text: str = "Cancel",
        on_confirm: Optional[Callable[[], None]] = None,
        is_danger: bool = False,
    ):
        super().__init__(master)
        self.title(title)
        self.geometry("480x360")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG_MAIN)
        self.transient(master)
        self.grab_set()

        self.on_confirm = on_confirm

        # Card Container
        card = CardFrame(self)
        card.pack(fill="both", expand=True, padx=20, pady=20)
        card.grid_columnconfigure(0, weight=1)

        # Header Title
        title_label = ctk.CTkLabel(
            card,
            text=title,
            font=FONT_BODY_BOLD,
            text_color=COLOR_ERROR if is_danger else COLOR_PRIMARY_BLUE,
            anchor="w",
        )
        title_label.pack(fill="x", padx=20, pady=(16, 6))

        # Message
        msg_label = ctk.CTkLabel(
            card,
            text=message,
            font=FONT_BODY,
            text_color=COLOR_TEXT_MAIN,
            wraplength=400,
            justify="left",
            anchor="w",
        )
        msg_label.pack(fill="x", padx=20, pady=(0, 12))

        # Details list if provided
        if details:
            details_frame = ctk.CTkFrame(card, fg_color="#F8FAFC", corner_radius=6)
            details_frame.pack(fill="x", padx=20, pady=6)
            for k, v in details:
                row = ctk.CTkFrame(details_frame, fg_color="transparent")
                row.pack(fill="x", padx=10, pady=3)
                lbl_k = ctk.CTkLabel(row, text=f"{k}:", font=FONT_SMALL, text_color=COLOR_TEXT_MUTED, width=120, anchor="w")
                lbl_k.pack(side="left")
                lbl_v = ctk.CTkLabel(row, text=str(v), font=FONT_SMALL, text_color=COLOR_TEXT_MAIN, anchor="w")
                lbl_v.pack(side="left", fill="x", expand=True)

        # Buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(16, 14), side="bottom")

        btn_cancel = ctk.CTkButton(
            btn_frame,
            text=cancel_text,
            fg_color="#E2E8F0",
            text_color=COLOR_TEXT_MAIN,
            hover_color="#CBD5E1",
            font=FONT_BODY,
            command=self.destroy,
        )
        btn_cancel.pack(side="right", padx=(8, 0))

        btn_action = ctk.CTkButton(
            btn_frame,
            text=confirm_text,
            fg_color=COLOR_ERROR if is_danger else COLOR_PRIMARY_BLUE,
            text_color="#FFFFFF",
            hover_color="#7F1D1D" if is_danger else "#1B3857",
            font=FONT_BODY_BOLD,
            command=self._handle_confirm,
        )
        btn_action.pack(side="right")

    def _handle_confirm(self):
        self.destroy()
        if self.on_confirm:
            self.on_confirm()
