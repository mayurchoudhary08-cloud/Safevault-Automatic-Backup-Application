"""Unit tests for SafeVault SQLite database operations."""

import tempfile
import unittest
from pathlib import Path

from safevault.database import Database


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_safevault.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_settings_crud(self):
        # Default settings exist
        self.assertEqual(self.db.get_setting("schedule_enabled"), "0")
        self.assertEqual(self.db.get_setting("schedule_frequency"), "daily")

        # Set and retrieve setting
        self.db.set_setting("source_folder", "C:/Users/Student/Docs")
        self.assertEqual(self.db.get_setting("source_folder"), "C:/Users/Student/Docs")

        # Update setting
        self.db.set_setting("source_folder", "C:/Users/Student/NewDocs")
        self.assertEqual(self.db.get_setting("source_folder"), "C:/Users/Student/NewDocs")

    def test_backup_run_lifecycle(self):
        backup_id = "2026-10-09_120000"
        self.db.record_backup_run(
            backup_id=backup_id,
            source_path="C:/Data/Source",
            snapshot_path="C:/Backups/Snapshots/2026-10-09_120000",
            start_time="2026-10-09T12:00:00",
            status="IN_PROGRESS",
        )

        record = self.db.get_backup_run(backup_id)
        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "IN_PROGRESS")

        # Update to SUCCESS
        self.db.update_backup_run(
            backup_id,
            status="SUCCESS",
            completion_time="2026-10-09T12:01:00",
            file_count=15,
            total_size_bytes=1048576,
            verification_status="VERIFIED",
        )

        updated = self.db.get_backup_run(backup_id)
        self.assertEqual(updated["status"], "SUCCESS")
        self.assertEqual(updated["file_count"], 15)
        self.assertEqual(updated["total_size_bytes"], 1048576)
        self.assertEqual(updated["verification_status"], "VERIFIED")

    def test_activity_logging(self):
        self.db.log_activity("BACKUP_STARTED", "Backup test started", "B001")
        self.db.log_activity("BACKUP_COMPLETED", "Backup test finished", "B001")
        self.db.log_activity("INFO", "General note")

        all_logs = self.db.get_activity_logs()
        self.assertEqual(len(all_logs), 3)

        backup_logs = self.db.get_activity_logs(event_type="BACKUP_STARTED")
        self.assertEqual(len(backup_logs), 1)
        self.assertEqual(backup_logs[0]["message"], "Backup test started")

    def test_dashboard_stats(self):
        # Initially empty
        stats = self.db.get_dashboard_stats()
        self.assertEqual(stats["success_count"], 0)
        self.assertEqual(stats["failed_count"], 0)
        self.assertIsNone(stats["latest_success"])

        # Add a success and a failure
        self.db.record_backup_run(
            backup_id="B1",
            source_path="/s",
            snapshot_path="/d",
            start_time="2026-10-09T10:00:00",
            status="SUCCESS",
            file_count=5,
            total_size_bytes=5000,
            verification_status="VERIFIED",
        )
        self.db.record_backup_run(
            backup_id="B2",
            source_path="/s",
            snapshot_path="/d",
            start_time="2026-10-09T11:00:00",
            status="FAILED",
            error_message="Disk full",
        )

        new_stats = self.db.get_dashboard_stats()
        self.assertEqual(new_stats["success_count"], 1)
        self.assertEqual(new_stats["failed_count"], 1)
        self.assertEqual(new_stats["total_size_bytes"], 5000)
        self.assertIsNotNone(new_stats["latest_success"])
        self.assertEqual(new_stats["latest_success"]["backup_id"], "B1")


if __name__ == "__main__":
    unittest.main()
