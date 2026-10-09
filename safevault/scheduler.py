"""Automatic backup scheduler for SafeVault.

Provides daily and weekly scheduling while the application is running,
along with a startup catch-up check for missed backups.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from threading import Event, Lock, Thread
from typing import Callable, Optional

from safevault.backup_manager import BackupManager
from safevault.database import Database
from safevault.logger import log_event


DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def calculate_next_run_time(
    frequency: str,
    time_str: str,
    day_str: str = "Monday",
    from_time: Optional[datetime] = None,
) -> datetime:
    """Calculate the next scheduled run timestamp.

    Args:
        frequency: "daily" or "weekly"
        time_str: "HH:MM" (24-hour format)
        day_str: "Monday" through "Sunday" (for weekly frequency)
        from_time: Base reference time (defaults to datetime.now())
    """
    if from_time is None:
        from_time = datetime.now()

    # Parse HH:MM
    try:
        parts = time_str.strip().split(":")
        target_hour = int(parts[0])
        target_minute = int(parts[1]) if len(parts) > 1 else 0
    except Exception:
        target_hour, target_minute = 12, 0

    if frequency.lower() == "weekly":
        # Target day index: 0=Monday, 6=Sunday
        try:
            target_weekday = DAY_NAMES.index(day_str.capitalize())
        except ValueError:
            target_weekday = 0

        # Start from today's target time
        candidate = from_time.replace(
            hour=target_hour, minute=target_minute, second=0, microsecond=0
        )
        days_ahead = (target_weekday - candidate.weekday()) % 7
        candidate = candidate + timedelta(days=days_ahead)

        # If it's today but already passed, advance by 7 days
        if candidate <= from_time:
            candidate += timedelta(days=7)
        return candidate
    else:
        # Daily
        candidate = from_time.replace(
            hour=target_hour, minute=target_minute, second=0, microsecond=0
        )
        if candidate <= from_time:
            candidate += timedelta(days=1)
        return candidate


class BackupScheduler:
    """Background scheduler that evaluates schedule conditions while SafeVault is active."""

    def __init__(
        self,
        database: Database,
        backup_manager: BackupManager,
        on_trigger_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self.db = database
        self.backup_mgr = backup_manager
        self.on_trigger_callback = on_trigger_callback

        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self._lock = Lock()

    def start(self) -> None:
        """Start the background scheduler thread."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = Thread(target=self._scheduler_loop, name="SchedulerThread", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop the background scheduler thread."""
        with self._lock:
            self._stop_event.set()

    def check_startup_catchup(self) -> bool:
        """Check if an enabled scheduled backup was missed while the app was closed.

        Runs at most one catch-up backup.
        """
        enabled = self.db.get_setting("schedule_enabled") == "1"
        if not enabled:
            return False

        src = self.db.get_setting("source_folder")
        dst = self.db.get_setting("backup_destination")
        if not src or not dst:
            return False

        last_run_str = self.db.get_setting("last_scheduled_run", "")
        freq = self.db.get_setting("schedule_frequency", "daily")
        time_str = self.db.get_setting("schedule_time", "12:00")
        day_str = self.db.get_setting("schedule_day", "Monday")

        now = datetime.now()

        # If never run, check if today's scheduled time has already passed
        if not last_run_str:
            # Check if scheduled time passed today
            scheduled_today = calculate_next_run_time(
                freq, time_str, day_str, from_time=now - timedelta(days=1)
            )
            if scheduled_today <= now:
                log_event("SCHEDULE_TRIGGERED", "Running startup catch-up backup (first run missed)", db=self.db)
                self._trigger_scheduled_backup(is_catchup=True)
                return True
            return False

        try:
            last_run = datetime.fromisoformat(last_run_str)
            # Find next expected run after the last run
            expected_run = calculate_next_run_time(freq, time_str, day_str, from_time=last_run)
            if expected_run <= now:
                log_event("SCHEDULE_TRIGGERED", f"Running startup catch-up backup (missed scheduled run at {expected_run.isoformat()})", db=self.db)
                self._trigger_scheduled_backup(is_catchup=True)
                return True
        except Exception as e:
            log_event("WARNING", f"Error parsing last scheduled run time: {e}", db=self.db)

        return False

    def _scheduler_loop(self) -> None:
        """Periodic loop that checks if a backup is due."""
        while not self._stop_event.is_set():
            try:
                self._evaluate_schedule()
            except Exception as e:
                log_event("ERROR", f"Scheduler loop error: {e}", db=self.db)

            # Sleep in small slices to allow quick shutdown
            for _ in range(30):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    def _evaluate_schedule(self) -> None:
        enabled = self.db.get_setting("schedule_enabled") == "1"
        if not enabled:
            return

        if self.backup_mgr.is_running:
            return

        src = self.db.get_setting("source_folder")
        dst = self.db.get_setting("backup_destination")
        if not src or not dst:
            return

        last_run_str = self.db.get_setting("last_scheduled_run", "")
        freq = self.db.get_setting("schedule_frequency", "daily")
        time_str = self.db.get_setting("schedule_time", "12:00")
        day_str = self.db.get_setting("schedule_day", "Monday")

        now = datetime.now()

        # If last run was already today / in this schedule interval, don't re-run
        if last_run_str:
            try:
                last_run = datetime.fromisoformat(last_run_str)
                # Next run should be after last_run
                next_expected = calculate_next_run_time(freq, time_str, day_str, from_time=last_run)
                if now < next_expected:
                    return
            except Exception:
                pass

        # Check if current time matches scheduled time (within a 5-minute window)
        parts = time_str.split(":")
        th, tm = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0

        is_due = False
        if freq.lower() == "weekly":
            try:
                weekday_idx = DAY_NAMES.index(day_str.capitalize())
            except ValueError:
                weekday_idx = 0
            if now.weekday() == weekday_idx and now.hour == th and now.minute == tm:
                is_due = True
        else:
            if now.hour == th and now.minute == tm:
                is_due = True

        if is_due:
            log_event("SCHEDULE_TRIGGERED", f"Automatic backup triggered on schedule ({freq} at {time_str})")
            self._trigger_scheduled_backup(is_catchup=False)

    def _trigger_scheduled_backup(self, is_catchup: bool = False) -> None:
        src = self.db.get_setting("source_folder")
        dst = self.db.get_setting("backup_destination")
        verify_after = self.db.get_setting("verify_after_backup", "1") == "1"

        now_iso = datetime.now().isoformat(timespec="seconds")
        self.db.set_setting("last_scheduled_run", now_iso)

        if self.on_trigger_callback:
            self.on_trigger_callback()

        def on_done(success: bool, msg: str):
            res = "SUCCESS" if success else "FAILED"
            self.db.set_setting("last_scheduled_result", f"{res}: {msg}")

        success, msg = self.backup_mgr.start_backup(
            source_dir=src,
            destination_dir=dst,
            verify_after=verify_after,
            on_complete=on_done,
        )
        if not success:
            self.db.set_setting("last_scheduled_result", f"FAILED: {msg}")
