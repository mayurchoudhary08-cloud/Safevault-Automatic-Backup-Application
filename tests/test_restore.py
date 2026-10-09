"""Unit tests for SafeVault restore engine."""

import json
import tempfile
import time
import unittest
from pathlib import Path

from safevault.database import Database
from safevault.integrity import compute_file_sha256
from safevault.restore_manager import RestoreManager


class TestRestoreManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name).resolve()

        self.db_path = self.base_path / "test.db"
        self.db = Database(self.db_path)
        self.restore_mgr = RestoreManager(self.db)

        # Create a valid snapshot
        self.snapshot_dir = self.base_path / "snapshots" / "backup_01"
        self.data_dir = self.snapshot_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # File 1
        self.f1 = self.data_dir / "notes.txt"
        self.f1.write_text("Original Notes", encoding="utf-8")
        h1 = compute_file_sha256(self.f1)

        # File 2 (nested)
        sub_dir = self.data_dir / "project" / "src"
        sub_dir.mkdir(parents=True, exist_ok=True)
        self.f2 = sub_dir / "app.py"
        self.f2.write_text("print('SafeVault')", encoding="utf-8")
        h2 = compute_file_sha256(self.f2)

        # Empty folder
        empty_folder = self.data_dir / "empty_dir"
        empty_folder.mkdir(parents=True, exist_ok=True)

        manifest = {
            "manifest_version": 1,
            "backup_id": "backup_01",
            "total_files": 2,
            "files": [
                {
                    "relative_path": "notes.txt",
                    "size": self.f1.stat().st_size,
                    "sha256": h1,
                },
                {
                    "relative_path": "project/src/app.py",
                    "size": self.f2.stat().st_size,
                    "sha256": h2,
                },
            ],
            "empty_directories": ["empty_dir"],
        }
        with open(self.snapshot_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_restore_success(self):
        target_dir = self.base_path / "Restored_Files"

        done = []
        started, msg = self.restore_mgr.start_restore(
            snapshot_dir=self.snapshot_dir,
            target_restore_dir=target_dir,
            verify_before=True,
            verify_after=True,
            on_complete=lambda ok, m, p: done.append((ok, m, p)),
        )
        self.assertTrue(started)

        while self.restore_mgr.is_running:
            time.sleep(0.05)

        self.assertTrue(len(done) > 0)
        self.assertTrue(done[0][0])

        # Verify files in target_dir
        self.assertTrue((target_dir / "notes.txt").exists())
        self.assertEqual((target_dir / "notes.txt").read_text("utf-8"), "Original Notes")
        self.assertTrue((target_dir / "project" / "src" / "app.py").exists())
        self.assertTrue((target_dir / "empty_dir").exists())

    def test_reject_unsafe_manifest_traversal(self):
        # Tamper manifest with directory traversal attack
        bad_manifest = {
            "manifest_version": 1,
            "backup_id": "bad_backup",
            "files": [
                {
                    "relative_path": "../../escape.txt",
                    "size": 10,
                    "sha256": "fake",
                }
            ],
        }
        with open(self.snapshot_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(bad_manifest, f)

        target_dir = self.base_path / "Restored_Files"
        done = []
        started, _ = self.restore_mgr.start_restore(
            snapshot_dir=self.snapshot_dir,
            target_restore_dir=target_dir,
            on_complete=lambda ok, m, p: done.append((ok, m, p)),
        )

        while self.restore_mgr.is_running:
            time.sleep(0.05)

        self.assertFalse(done[0][0])
        self.assertIn("security violation", done[0][1].lower())


if __name__ == "__main__":
    unittest.main()
