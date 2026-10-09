"""Dashboard Page for SafeVault.

Shows quick system overview, live statistics, folder configurations,
and primary actions (Back Up Now, View History, Restore Files).
"""

from __future__ import annotations

import customtkinter as ctk
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from safevault.scheduler import calculate_next_run_time
from safevault.ui.common import CardFrame, MetricCard, StatusBadge, format_bytes
from safevault.ui.theme import (
    COLOR_BG_MAIN,
    COLOR_BORDER,
    COLOR_ERROR,
    COLOR_PRIMARY_BLUE,
    COLOR_SECONDARY_BLUE,
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


class DashboardView(ctk.CTkFrame):
    """The central dashboard view showing metrics, status, and quick actions."""

    def __init__(self, master, app: "SafeVaultApp", **kwargs):
        super().__init__(master, fg_color=COLOR_BG_MAIN, **kwargs)
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Scrollable container for dashboard
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.scroll.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_setup_banner()
        self._build_active_progress_card()
        self._build_metrics_grid()
        self._build_actions_section()
        self._build_folder_summary_card()
        self._build_recent_activity_card()

    def _build_header(self):
        header_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 16))

        title = ctk.CTkLabel(
            header_frame,
            text="System Overview",
            font=FONT_HEADING,
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        )
        title.pack(side="left")

        self.status_badge = StatusBadge(header_frame, status="READY")
        self.status_badge.pack(side="right")

    def _build_setup_banner(self):
        self.setup_banner = CardFrame(self.scroll, fg_color="#FFFBEB", border_color="#FDE68A")
        self.setup_banner.grid_columnconfigure(0, weight=1)

        lbl = ctk.CTkLabel(
            self.setup_banner,
            text="⚠️ Folders Not Fully Configured\nPlease select your source folder and backup destination in Backup Setup before creating backups.",
            font=FONT_BODY,
            text_color="#92400E",
            justify="left",
            anchor="w",
        )
        lbl.pack(side="left", padx=16, pady=12, fill="x", expand=True)

        btn = ctk.CTkButton(
            self.setup_banner,
            text="Configure Folders Now",
            font=FONT_BODY_BOLD,
            fg_color=COLOR_PRIMARY_BLUE,
            text_color="#FFFFFF",
            command=lambda: self.app.navigate_to("setup"),
            width=160,
        )
        btn.pack(side="right", padx=16, pady=12)

    def _build_active_progress_card(self):
        self.progress_card = CardFrame(self.scroll, fg_color="#F0F9FF", border_color="#BAE6FD")
        self.progress_card.grid_columnconfigure(0, weight=1)

        p_header = ctk.CTkFrame(self.progress_card, fg_color="transparent")
        p_header.pack(fill="x", padx=16, pady=(12, 6))

        self.p_title_label = ctk.CTkLabel(
            p_header,
            text="🔄 Backup in Progress...",
            font=FONT_SUBHEADING,
            text_color=COLOR_PRIMARY_BLUE,
            anchor="w",
        )
        self.p_title_label.pack(side="left")

        self.btn_cancel_backup = ctk.CTkButton(
            p_header,
            text="Cancel Backup",
            font=FONT_SMALL,
            fg_color=COLOR_ERROR,
            hover_color="#991B1B",
            width=100,
            command=self._on_cancel_backup_clicked,
        )
        self.btn_cancel_backup.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(
            self.progress_card,
            fg_color="#E0F2FE",
            progress_color=COLOR_PRIMARY_BLUE,
            height=10,
        )
        self.progress_bar.pack(fill="x", padx=16, pady=4)
        self.progress_bar.set(0)

        p_details = ctk.CTkFrame(self.progress_card, fg_color="transparent")
        p_details.pack(fill="x", padx=16, pady=(4, 12))

        self.p_file_label = ctk.CTkLabel(
            p_details,
            text="Preparing...",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        self.p_file_label.pack(side="left", fill="x", expand=True)

        self.p_stats_label = ctk.CTkLabel(
            p_details,
            text="0 / 0 files",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_MAIN,
            anchor="e",
        )
        self.p_stats_label.pack(side="right")

        # Initially hidden until backup is running
        self.progress_card.pack_forget()

    def _build_metrics_grid(self):
        self.metrics_container = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.metrics_container.pack(fill="x", pady=(0, 16))
        for col in range(4):
            self.metrics_container.grid_columnconfigure(col, weight=1, uniform="metric")

        self.card_total_backups = MetricCard(
            self.metrics_container, title="Successful Backups", initial_value="0", subtitle="0 failed attempts"
        )
        self.card_total_backups.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        self.card_last_backup = MetricCard(
            self.metrics_container, title="Latest Backup", initial_value="None", subtitle="No backups completed"
        )
        self.card_last_backup.grid(row=0, column=1, padx=4, sticky="nsew")

        self.card_storage_used = MetricCard(
            self.metrics_container, title="Storage Used", initial_value="0 B", subtitle="Total snapshot size"
        )
        self.card_storage_used.grid(row=0, column=2, padx=4, sticky="nsew")

        self.card_next_schedule = MetricCard(
            self.metrics_container, title="Next Scheduled", initial_value="Disabled", subtitle="Check schedule settings"
        )
        self.card_next_schedule.grid(row=0, column=3, padx=(8, 0), sticky="nsew")

    def _build_actions_section(self):
        actions_card = CardFrame(self.scroll)
        actions_card.pack(fill="x", pady=(0, 16))

        top_f = ctk.CTkFrame(actions_card, fg_color="transparent")
        top_f.pack(fill="x", padx=16, pady=(14, 6))

        title = ctk.CTkLabel(top_f, text="Quick Actions", font=FONT_SUBHEADING, text_color=COLOR_TEXT_MAIN)
        title.pack(side="left")

        btn_row = ctk.CTkFrame(actions_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(4, 16))
        btn_row.grid_columnconfigure(0, weight=2)
        btn_row.grid_columnconfigure(1, weight=1)
        btn_row.grid_columnconfigure(2, weight=1)

        self.btn_backup_now = ctk.CTkButton(
            btn_row,
            text="🛡️  BACK UP NOW",
            font=(FONT_BODY_BOLD[0], 13, "bold"),
            fg_color=COLOR_PRIMARY_BLUE,
            hover_color="#1B3857",
            height=44,
            command=self._on_backup_now_clicked,
        )
        self.btn_backup_now.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        self.btn_view_history = ctk.CTkButton(
            btn_row,
            text="📜  View History",
            font=FONT_BODY_BOLD,
            fg_color="#FFFFFF",
            text_color=COLOR_PRIMARY_BLUE,
            border_color=COLOR_PRIMARY_BLUE,
            border_width=1,
            hover_color="#F1F5F9",
            height=44,
            command=lambda: self.app.navigate_to("history"),
        )
        self.btn_view_history.grid(row=0, column=1, padx=4, sticky="nsew")

        self.btn_restore = ctk.CTkButton(
            btn_row,
            text="🔄  Restore Files",
            font=FONT_BODY_BOLD,
            fg_color="#FFFFFF",
            text_color=COLOR_SECONDARY_BLUE,
            border_color=COLOR_SECONDARY_BLUE,
            border_width=1,
            hover_color="#F1F5F9",
            height=44,
            command=lambda: self.app.navigate_to("restore"),
        )
        self.btn_restore.grid(row=0, column=2, padx=(8, 0), sticky="nsew")

    def _build_folder_summary_card(self):
        card = CardFrame(self.scroll)
        card.pack(fill="x", pady=(0, 16))
        card.grid_columnconfigure(1, weight=1)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(header, text="Configured Directories", font=FONT_SUBHEADING, text_color=COLOR_TEXT_MAIN).pack(side="left")

        btn_edit = ctk.CTkButton(
            header,
            text="Change Folders",
            font=FONT_SMALL,
            fg_color="transparent",
            text_color=COLOR_PRIMARY_BLUE,
            hover_color="#E2E8F0",
            width=110,
            command=lambda: self.app.navigate_to("setup"),
        )
        btn_edit.pack(side="right")

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="x", padx=16, pady=(0, 14))

        # Source row
        row_src = ctk.CTkFrame(content, fg_color="transparent")
        row_src.pack(fill="x", pady=3)
        ctk.CTkLabel(row_src, text="Source Folder:", font=FONT_BODY_BOLD, text_color=COLOR_TEXT_MUTED, width=140, anchor="w").pack(side="left")
        self.lbl_src_path = ctk.CTkLabel(row_src, text="Not configured", font=FONT_BODY, text_color=COLOR_TEXT_MAIN, anchor="w")
        self.lbl_src_path.pack(side="left", fill="x", expand=True)

        # Dest row
        row_dst = ctk.CTkFrame(content, fg_color="transparent")
        row_dst.pack(fill="x", pady=3)
        ctk.CTkLabel(row_dst, text="Backup Destination:", font=FONT_BODY_BOLD, text_color=COLOR_TEXT_MUTED, width=140, anchor="w").pack(side="left")
        self.lbl_dst_path = ctk.CTkLabel(row_dst, text="Not configured", font=FONT_BODY, text_color=COLOR_TEXT_MAIN, anchor="w")
        self.lbl_dst_path.pack(side="left", fill="x", expand=True)

    def _build_recent_activity_card(self):
        self.card_recent = CardFrame(self.scroll)
        self.card_recent.pack(fill="x", pady=(0, 16))

        header = ctk.CTkFrame(self.card_recent, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(header, text="Recent Activity", font=FONT_SUBHEADING, text_color=COLOR_TEXT_MAIN).pack(side="left")

        btn_all = ctk.CTkButton(
            header,
            text="View Full Log",
            font=FONT_SMALL,
            fg_color="transparent",
            text_color=COLOR_PRIMARY_BLUE,
            hover_color="#E2E8F0",
            width=100,
            command=lambda: self.app.navigate_to("activity"),
        )
        btn_all.pack(side="right")

        self.recent_logs_frame = ctk.CTkFrame(self.card_recent, fg_color="transparent")
        self.recent_logs_frame.pack(fill="x", padx=16, pady=(0, 14))

    def refresh_dashboard(self):
        """Reload all metrics and configuration status from database."""
        db = self.app.db
        stats = db.get_dashboard_stats()
        settings = db.get_all_settings()

        src = settings.get("source_folder", "")
        dst = settings.get("backup_destination", "")

        # 1. Update Folders
        self.lbl_src_path.configure(text=src if src else "Not configured (choose folder to protect)")
        self.lbl_dst_path.configure(text=dst if dst else "Not configured (choose storage folder)")

        # 2. Show/hide Setup Banner
        if not src or not dst:
            self.setup_banner.pack(fill="x", pady=(0, 16), before=self.metrics_container)
        else:
            self.setup_banner.pack_forget()

        # 3. Update Metrics
        success_cnt = stats["success_count"]
        failed_cnt = stats["failed_count"]
        self.card_total_backups.update_metric(
            str(success_cnt),
            subtitle=f"{failed_cnt} failed or cancelled" if failed_cnt else "All operations healthy",
        )

        latest_success = stats["latest_success"]
        if latest_success:
            time_str = latest_success.get("start_time", "")
            try:
                dt = datetime.fromisoformat(time_str)
                display_time = dt.strftime("%b %d, %H:%M")
            except Exception:
                display_time = time_str
            file_count = latest_success.get("file_count", 0)
            self.card_last_backup.update_metric(display_time, subtitle=f"{file_count} files preserved")
        else:
            self.card_last_backup.update_metric("None", subtitle="No backups created yet")

        total_bytes = stats["total_size_bytes"]
        self.card_storage_used.update_metric(format_bytes(total_bytes), subtitle="Total snapshots data")

        # Schedule calculation
        sched_enabled = settings.get("schedule_enabled") == "1"
        if sched_enabled:
            freq = settings.get("schedule_frequency", "daily")
            t_str = settings.get("schedule_time", "12:00")
            d_str = settings.get("schedule_day", "Monday")
            try:
                next_dt = calculate_next_run_time(freq, t_str, d_str)
                self.card_next_schedule.update_metric(
                    next_dt.strftime("%b %d, %H:%M"),
                    subtitle=f"{freq.capitalize()} backup",
                )
            except Exception:
                self.card_next_schedule.update_metric("Active", subtitle=f"{freq.capitalize()} at {t_str}")
        else:
            self.card_next_schedule.update_metric("Disabled", subtitle="Set in Schedule & Settings")

        # 4. Status Badge
        if self.app.backup_mgr.is_running:
            self.status_badge.set_status("BACKING UP")
        elif not src or not dst:
            self.status_badge.set_status("SETUP NEEDED")
        else:
            self.status_badge.set_status("READY")

        # 5. Refresh Recent Activity
        for child in self.recent_logs_frame.winfo_children():
            child.destroy()

        logs = db.get_activity_logs(limit=4)
        if not logs:
            lbl_empty = ctk.CTkLabel(
                self.recent_logs_frame,
                text="No recorded activity yet. Backups and restoration events will appear here.",
                font=FONT_SMALL,
                text_color=COLOR_TEXT_MUTED,
                anchor="w",
            )
            lbl_empty.pack(fill="x", pady=4)
        else:
            for log_entry in logs:
                row = ctk.CTkFrame(self.recent_logs_frame, fg_color="#F8FAFC", corner_radius=6)
                row.pack(fill="x", pady=2)
                t_lbl = ctk.CTkLabel(row, text=log_entry["timestamp"][-8:], font=FONT_SMALL, text_color=COLOR_TEXT_MUTED, width=65, anchor="w")
                t_lbl.pack(side="left", padx=(8, 4), pady=4)

                badge = StatusBadge(row, status=log_entry["event_type"])
                badge.pack(side="left", padx=4, pady=4)

                m_lbl = ctk.CTkLabel(row, text=log_entry["message"], font=FONT_SMALL, text_color=COLOR_TEXT_MAIN, anchor="w")
                m_lbl.pack(side="left", padx=8, pady=4, fill="x", expand=True)

    def show_progress_panel(self):
        self.progress_card.pack(fill="x", pady=(0, 16), before=self.metrics_container)
        self.btn_backup_now.configure(state="disabled", text="⏳ Backup Running...")
        self.status_badge.set_status("BACKING UP")

    def hide_progress_panel(self):
        self.progress_card.pack_forget()
        self.btn_backup_now.configure(state="normal", text="🛡️  BACK UP NOW")
        self.refresh_dashboard()

    def update_progress(self, progress):
        if progress.total_files > 0:
            frac = min(1.0, max(0.0, progress.files_processed / progress.total_files))
            self.progress_bar.set(frac)
            self.p_stats_label.configure(
                text=f"{progress.files_processed} / {progress.total_files} files ({format_bytes(progress.bytes_copied)})"
            )
        else:
            self.progress_bar.set(0)
            self.p_stats_label.configure(text=format_bytes(progress.bytes_copied))

        self.p_title_label.configure(text=f"🔄 Status: {progress.status} ({progress.elapsed_seconds}s)")
        self.p_file_label.configure(text=progress.current_file or progress.error_message or "Processing...")

    def _on_backup_now_clicked(self):
        self.app.trigger_manual_backup()

    def _on_cancel_backup_clicked(self):
        self.app.backup_mgr.cancel_backup()
        self.btn_cancel_backup.configure(state="disabled", text="Cancelling...")
