"""Main application coordinator for SafeVault.

Builds the top-level desktop window, persistent navigation sidebar,
background worker queue listener, and view transitions.
"""

from __future__ import annotations

import os
from queue import Empty, Queue
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Dict, Optional

import customtkinter as ctk

from safevault import __app_name__, __version__
from safevault.backup_manager import BackupManager, BackupProgress
from safevault.database import Database
from safevault.demo_workspace import create_demo_workspace
from safevault.logger import log_event, set_active_database, setup_logger
from safevault.restore_manager import RestoreManager
from safevault.scheduler import BackupScheduler
from safevault.ui.about_page import AboutView
from safevault.ui.activity_page import ActivityLogView
from safevault.ui.backup_page import BackupSetupView
from safevault.ui.common import StatusBadge
from safevault.ui.dashboard import DashboardView
from safevault.ui.history_page import BackupHistoryView
from safevault.ui.restore_page import RestoreCenterView
from safevault.ui.settings_page import SettingsView
from safevault.ui.theme import (
    COLOR_BG_MAIN,
    COLOR_BORDER,
    COLOR_CARD_HOVER,
    COLOR_PRIMARY_BLUE,
    COLOR_SECONDARY_BLUE,
    COLOR_SIDEBAR,
    COLOR_TEXT_MAIN,
    COLOR_TEXT_MUTED,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CARD_TITLE,
    FONT_HEADING,
    FONT_SMALL,
    FONT_SUBHEADING,
)


class SafeVaultApp:
    """The central application class for SafeVault."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        # 1. CustomTkinter global appearance
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # 2. Database & Logging setup
        self.db = Database(db_path)
        set_active_database(self.db)
        setup_logger()

        # 3. Core Engine Managers
        self.backup_mgr = BackupManager(self.db)
        self.restore_mgr = RestoreManager(self.db)
        self.scheduler = BackupScheduler(
            self.db,
            self.backup_mgr,
            on_trigger_callback=self._on_scheduled_backup_triggered,
        )

        # 4. Thread communication queues
        self.backup_progress_queue: Queue = Queue()

        # 5. Build Desktop Window
        self.root = ctk.CTk()
        self.root.title(f"{__app_name__} — Automatic Backup & Restore")
        self.root.geometry("1100x720")
        self.root.minsize(980, 620)
        self.root.configure(fg_color=COLOR_BG_MAIN)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close_window)

        # Main layout: Left sidebar + Right content area
        self.root.grid_columnconfigure(0, weight=0)  # Sidebar width fixed
        self.root.grid_columnconfigure(1, weight=1)  # Content area expands
        self.root.grid_rowconfigure(0, weight=1)

        self._current_page: str = ""
        self.views: Dict[str, ctk.CTkFrame] = {}
        self.nav_buttons: Dict[str, ctk.CTkButton] = {}

        self._build_sidebar()
        self._build_content_area()

        # Start Scheduler & Catch-up check
        self.scheduler.start()
        self.root.after(800, self._check_startup_catchup)

        # Initial view navigation
        self.navigate_to("dashboard")

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self.root,
            width=240,
            fg_color=COLOR_SIDEBAR,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=0,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(8, weight=1)  # Space between nav and bottom utility
        self.sidebar.grid_propagate(False)

        # Logo / Branding
        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=16, pady=(20, 16))

        lbl_logo = ctk.CTkLabel(
            brand_frame,
            text="🛡️ SafeVault",
            font=(FONT_HEADING[0], 18, "bold"),
            text_color=COLOR_PRIMARY_BLUE,
            anchor="w",
        )
        lbl_logo.pack(fill="x")

        lbl_sub = ctk.CTkLabel(
            brand_frame,
            text=f"Desktop Backup & Restore v{__version__}",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        lbl_sub.pack(fill="x", pady=(2, 0))

        # Divider
        div1 = ctk.CTkFrame(self.sidebar, fg_color=COLOR_BORDER, height=1)
        div1.pack(fill="x", padx=16, pady=(0, 12))

        # Navigation Buttons
        nav_items = [
            ("dashboard", "📊  Dashboard"),
            ("setup", "📁  Backup Setup"),
            ("history", "📜  Backup History"),
            ("restore", "🔄  Restore Center"),
            ("activity", "📋  Activity Log"),
            ("settings", "⚙️  Schedule & Settings"),
            ("about", "💡  About & OS Concepts"),
        ]

        self.nav_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_container.pack(fill="x", padx=12)

        for page_id, label in nav_items:
            btn = ctk.CTkButton(
                self.nav_container,
                text=label,
                font=FONT_BODY,
                fg_color="transparent",
                text_color=COLOR_TEXT_MAIN,
                hover_color=COLOR_CARD_HOVER,
                anchor="w",
                height=38,
                corner_radius=6,
                command=lambda p=page_id: self.navigate_to(p),
            )
            btn.pack(fill="x", pady=2)
            self.nav_buttons[page_id] = btn

        # Bottom section: Demo Workspace & Status
        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=12, pady=16)

        btn_demo = ctk.CTkButton(
            bottom_frame,
            text="🧪 Create Demo Workspace",
            font=FONT_SMALL,
            fg_color="#EFF6FF",
            text_color=COLOR_PRIMARY_BLUE,
            hover_color="#DBEAFE",
            height=34,
            corner_radius=6,
            command=self._on_create_demo_workspace,
        )
        btn_demo.pack(fill="x", pady=(0, 8))

        self.sidebar_status = StatusBadge(bottom_frame, status="READY")
        self.sidebar_status.pack(fill="x")

    def _build_content_area(self):
        self.content_container = ctk.CTkFrame(self.root, fg_color=COLOR_BG_MAIN, corner_radius=0)
        self.content_container.grid(row=0, column=1, sticky="nsew")
        self.content_container.grid_columnconfigure(0, weight=1)
        self.content_container.grid_rowconfigure(0, weight=1)

        # Instantiate View Frames
        self.views["dashboard"] = DashboardView(self.content_container, app=self)
        self.views["setup"] = BackupSetupView(self.content_container, app=self)
        self.views["history"] = BackupHistoryView(self.content_container, app=self)
        self.views["restore"] = RestoreCenterView(self.content_container, app=self)
        self.views["activity"] = ActivityLogView(self.content_container, app=self)
        self.views["settings"] = SettingsView(self.content_container, app=self)
        self.views["about"] = AboutView(self.content_container, app=self)

    def navigate_to(self, page_id: str, **kwargs):
        """Switch active view and update button styles."""
        if page_id not in self.views:
            return

        self._current_page = page_id

        # Update button visual states
        for pid, btn in self.nav_buttons.items():
            if pid == page_id:
                btn.configure(
                    fg_color=COLOR_PRIMARY_BLUE,
                    text_color="#FFFFFF",
                    hover_color=COLOR_PRIMARY_BLUE,
                    font=FONT_BODY_BOLD,
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=COLOR_TEXT_MAIN,
                    hover_color=COLOR_CARD_HOVER,
                    font=FONT_BODY,
                )

        # Show target view and hide others
        for pid, view in self.views.items():
            if pid == page_id:
                view.grid(row=0, column=0, sticky="nsew")
            else:
                view.grid_forget()

        # Trigger view-specific refresh
        if page_id == "dashboard":
            self.views["dashboard"].refresh_dashboard()
        elif page_id == "setup":
            self.views["setup"].refresh_setup()
        elif page_id == "history":
            self.views["history"].refresh_history()
        elif page_id == "restore":
            preselect = kwargs.get("preselect_backup_id")
            self.views["restore"].refresh_restore_page(preselect_id=preselect)
        elif page_id == "activity":
            self.views["activity"].refresh_activity_page()
        elif page_id == "settings":
            self.views["settings"].refresh_settings()

    def refresh_all_views(self):
        """Refresh whatever views are relevant."""
        if self._current_page == "dashboard":
            self.views["dashboard"].refresh_dashboard()
        elif self._current_page == "history":
            self.views["history"].refresh_history()
        elif self._current_page == "restore":
            self.views["restore"].refresh_restore_page()

    def trigger_manual_backup(self):
        """Initiate manual backup with progress tracking in UI."""
        settings = self.db.get_all_settings()
        src = settings.get("source_folder", "")
        dst = settings.get("backup_destination", "")
        verify_after = settings.get("verify_after_backup", "1") == "1"

        if not src or not dst:
            messagebox.showwarning(
                "Folder Setup Incomplete",
                "Please configure both your source folder and backup destination in Backup Setup.",
            )
            self.navigate_to("setup")
            return

        # Show progress card in dashboard
        self.views["dashboard"].show_progress_panel()
        self.sidebar_status.set_status("BACKING UP")

        def on_done(success: bool, msg: str):
            # Dispatch UI update on GUI thread
            self.root.after(0, lambda: self._on_backup_finished(success, msg))

        started, b_id = self.backup_mgr.start_backup(
            source_dir=src,
            destination_dir=dst,
            verify_after=verify_after,
            progress_queue=self.backup_progress_queue,
            on_complete=on_done,
        )

        if not started:
            self.views["dashboard"].hide_progress_panel()
            self.sidebar_status.set_status("READY")
            messagebox.showerror("Backup Error", b_id)
            return

        # Start polling queue for GUI updates
        self._poll_backup_progress()

    def _poll_backup_progress(self):
        """Drain progress updates from background worker queue to GUI widgets."""
        while not self.backup_progress_queue.empty():
            try:
                progress: BackupProgress = self.backup_progress_queue.get_nowait()
                self.views["dashboard"].update_progress(progress)
            except Empty:
                break

        if self.backup_mgr.is_running:
            self.root.after(100, self._poll_backup_progress)

    def _on_backup_finished(self, success: bool, msg: str):
        self.views["dashboard"].hide_progress_panel()
        self.sidebar_status.set_status("READY")
        self.refresh_all_views()

        if success:
            messagebox.showinfo("Backup Complete", f"✓ {msg}\n\nYour snapshot has been safely recorded.")
        else:
            if "cancelled" in msg.lower():
                messagebox.showinfo("Backup Cancelled", "The backup operation was stopped by user request.")
            else:
                messagebox.showerror("Backup Failed", f"⚠️ {msg}")

    def _on_scheduled_backup_triggered(self):
        """Called when scheduler triggers an automatic backup."""
        self.root.after(0, lambda: self.views["dashboard"].show_progress_panel())
        self.root.after(0, self._poll_backup_progress)

    def _check_startup_catchup(self):
        """Run catch-up check after window has rendered."""
        if self.scheduler.check_startup_catchup():
            self._poll_backup_progress()

    def _on_create_demo_workspace(self):
        """Prompt user for target directory and create sample demo files."""
        parent_dir = filedialog.askdirectory(title="Choose Location for SafeVault Demo Workspace")
        if not parent_dir:
            return

        success, msg, created_path = create_demo_workspace(parent_dir)
        if success:
            use_as_source = messagebox.askyesno(
                "Demo Workspace Created",
                f"{msg}\n\n"
                f"Would you like to automatically set this demo folder as your Source Folder?",
            )
            if use_as_source:
                self.db.set_setting("source_folder", str(created_path))
                # Also suggest a default destination if none exists
                if not self.db.get_setting("backup_destination"):
                    demo_dest = Path(parent_dir) / "SafeVault_Demo_Backups"
                    self.db.set_setting("backup_destination", str(demo_dest))

                self.navigate_to("setup")
                messagebox.showinfo(
                    "Source Configured",
                    f"Source folder set to:\n{created_path}\n\nYou can now test Back Up Now!",
                )
        else:
            messagebox.showerror("Demo Workspace Failed", msg)

    def _on_close_window(self):
        """Clean shutdown of scheduler and application."""
        if self.backup_mgr.is_running:
            confirm = messagebox.askyesno(
                "Backup In Progress",
                "A backup operation is currently running. Exiting now will cancel it. Are you sure you want to exit?",
            )
            if not confirm:
                return
            self.backup_mgr.cancel_backup()

        self.scheduler.stop()
        self.root.destroy()

    def run(self):
        """Start the Tkinter event loop."""
        self.root.mainloop()


def main():
    """CLI entry point for safevault package."""
    app = SafeVaultApp()
    app.run()
