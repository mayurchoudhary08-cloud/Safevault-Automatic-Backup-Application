"""Unit tests for SafeVault backup engine."""

import json
import tempfile
import time
import unittest
from pathlib import Path
from queue import Queue

from safevault.backup_manager import BackupManager
from safevault.database import Database


class TestBackupManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name).resolve()

        self.db_path = self.base_path / "test.db"
        self.db = Database(self.db_path)
        self.manager = BackupManager(self.db)

        self.source_dir = self.base_path / "source"
        self.source_dir.mkdir(parents=True, exist_ok=True)

        self.dest_dir = self.base_path / "destination"
        self.dest_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_backup_with_nested_directories_and_empty_dirs(self):
        # Create test files
        (self.source_dir / "file1.txt").write_text("Hello SafeVault", encoding="utf-8")
        sub_dir = self.source_dir / "Notes" / "College"
        sub_dir.mkdir(parents=True, exist_ok=True)
        (sub_dir / "os_notes.txt").write_text("OS practical notes content", encoding="utf-8")

        empty_dir = self.source_dir / "EmptySubfolder"
        empty_dir.mkdir(parents=True, exist_ok=True)

        prog_queue = Queue()
        done = []

        def on_done(success, msg):
            done.append((success, msg))

        started, b_id = self.manager.start_backup(
            source_dir=self.source_dir,
            destination_dir=self.dest_dir,
            verify_after=True,
            progress_queue=prog_queue,
            on_complete=on_done,
        )

        self.assertTrue(started)

        # Wait for thread to finish
        while self.manager.is_running:
            time.sleep(0.05)

        self.assertTrue(len(done) > 0)
        self.assertTrue(done[0][0])

        # Verify snapshot exists
        snapshot_dir = self.dest_dir / "snapshots" / b_id
        self.assertTrue(snapshot_dir.exists())

        # Check data directory
        data_dir = snapshot_dir / "data"
        self.assertTrue((data_dir / "file1.txt").exists())
        self.assertTrue((data_dir / "Notes" / "College" / "os_notes.txt").exists())
        self.assertTrue((data_dir / "EmptySubfolder").exists())

        # Check manifest
        manifest_path = snapshot_dir / "manifest.json"
        self.assertTrue(manifest_path.exists())
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest["backup_id"], b_id)
        self.assertEqual(manifest["total_files"], 2)
        self.assertEqual(manifest["verification_status"], "VERIFIED")
        self.assertIn("EmptySubfolder", manifest["empty_directories"])

        # Check database record
        record = self.db.get_backup_run(b_id)
        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "SUCCESS")
        self.assertEqual(record["file_count"], 2)
        self.assertEqual(record["verification_status"], "VERIFIED")

    def test_backup_empty_folder(self):
        # Source has no files
        done = []
        started, b_id = self.manager.start_backup(
            source_dir=self.source_dir,
            destination_dir=self.dest_dir,
            verify_after=True,
            on_complete=lambda s, m: done.append((s, m)),
        )
        self.assertTrue(started)

        while self.manager.is_running:
            time.sleep(0.05)

        self.assertTrue(done[0][0])
        snapshot_dir = self.dest_dir / "snapshots" / b_id
        manifest_path = snapshot_dir / "manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["total_files"], 0)

    def test_prevent_concurrent_backups(self):
        # Create a dummy run
        (self.source_dir / "big.bin").write_bytes(b"A" * 100000)
        started1, _ = self.manager.start_backup(
            source_dir=self.source_dir,
            destination_dir=self.dest_dir,
        )
        self.assertTrue(started1)

        # Attempt to start second backup while first is running
        started2, msg2 = self.manager.start_backup(
            source_dir=self.source_dir,
            destination_dir=self.dest_dir,
        )
        self.assertFalse(started2)
        self.assertIn("already running", msg2.lower())

        while self.manager.is_running:
            time.sleep(0.05)


if __name__ == "__main__":
    unittest.main()
