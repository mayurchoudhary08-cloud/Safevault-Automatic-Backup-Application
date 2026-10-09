"""End-to-end integration test simulating a college viva demonstration.

Scenario:
1. Generate demo workspace with sample files.
2. Back up the workspace (Snapshot 1).
3. Verify snapshot integrity.
4. Modify a sample file in the source directory.
5. Back up again (Snapshot 2).
6. Restore Snapshot 1 into a new directory.
7. Confirm restored file matches original content prior to modification.
8. Confirm source directory was not altered or overwritten by restore.
9. Tamper with Snapshot 2 and verify that integrity verification detects modification.
"""

import tempfile
import time
import unittest
from pathlib import Path

from safevault.backup_manager import BackupManager
from safevault.database import Database
from safevault.demo_workspace import create_demo_workspace
from safevault.integrity import verify_snapshot_integrity
from safevault.paths import validate_backup_paths
from safevault.restore_manager import RestoreManager


class TestEndToEndWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name).resolve()

        self.db = Database(self.base_dir / "safevault_e2e.db")
        self.backup_mgr = BackupManager(self.db)
        self.restore_mgr = RestoreManager(self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_complete_viva_workflow(self):
        # 1. Create Demo Workspace
        ok, msg, demo_source = create_demo_workspace(self.base_dir)
        self.assertTrue(ok)
        self.assertTrue(demo_source.exists())

        demo_dest = self.base_dir / "SafeVault_Backups"
        demo_dest.mkdir(parents=True, exist_ok=True)

        # 2. Path Safety Validation
        valid, err = validate_backup_paths(demo_source, demo_dest)
        self.assertTrue(valid)
        self.assertEqual(err, "")

        # 3. Create Backup 1 (Snapshot 1)
        done1 = []
        started1, b_id1 = self.backup_mgr.start_backup(
            source_dir=demo_source,
            destination_dir=demo_dest,
            verify_after=True,
            on_complete=lambda s, m: done1.append((s, m)),
        )
        self.assertTrue(started1)
        while self.backup_mgr.is_running:
            time.sleep(0.05)
        self.assertTrue(done1[0][0])

        # Verify Snapshot 1 integrity
        snap1_path = demo_dest / "snapshots" / b_id1
        rep1 = verify_snapshot_integrity(snap1_path)
        self.assertTrue(rep1.is_valid)
        self.assertEqual(rep1.failed_count, 0)

        # Record original assignment text
        assignment_file = demo_source / "Documents" / "assignment.txt"
        original_text = assignment_file.read_text("utf-8")

        # 4. Student modifies assignment file (simulating accidental overwrite / edits)
        time.sleep(1.0)  # Ensure unique timestamp for snapshot 2
        modified_text = "MODIFIED: This was edited on Tuesday and contains errors."
        assignment_file.write_text(modified_text, encoding="utf-8")

        # 5. Create Backup 2 (Snapshot 2)
        done2 = []
        started2, b_id2 = self.backup_mgr.start_backup(
            source_dir=demo_source,
            destination_dir=demo_dest,
            verify_after=True,
            on_complete=lambda s, m: done2.append((s, m)),
        )
        self.assertTrue(started2)
        while self.backup_mgr.is_running:
            time.sleep(0.05)
        self.assertTrue(done2[0][0])
        self.assertNotEqual(b_id1, b_id2)

        # 6. Check Database History
        history = self.db.get_all_backup_runs()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["status"], "SUCCESS")
        self.assertEqual(history[1]["status"], "SUCCESS")

        # 7. Restore Snapshot 1 into a safe, new directory
        restore_parent = self.base_dir / "Restored_Output"
        restore_parent.mkdir(parents=True, exist_ok=True)
        target_restore_dir = self.restore_mgr.prepare_restore_destination(restore_parent, b_id1)

        done_restore = []
        started_r, _ = self.restore_mgr.start_restore(
            snapshot_dir=snap1_path,
            target_restore_dir=target_restore_dir,
            verify_before=True,
            verify_after=True,
            on_complete=lambda s, m, p: done_restore.append((s, m, p)),
        )
        self.assertTrue(started_r)
        while self.restore_mgr.is_running:
            time.sleep(0.05)
        self.assertTrue(done_restore[0][0])

        # 8. Verify Restored File matches Original Monday Version
        restored_assignment = target_restore_dir / "Documents" / "assignment.txt"
        self.assertTrue(restored_assignment.exists())
        self.assertEqual(restored_assignment.read_text("utf-8"), original_text)

        # Confirm source file still has its Tuesday content (not overwritten)
        self.assertEqual(assignment_file.read_text("utf-8"), modified_text)

        # 9. Tamper test: Alter file in snapshot 2 and verify detection
        snap2_file = demo_dest / "snapshots" / b_id2 / "data" / "Documents" / "assignment.txt"
        snap2_file.write_text("CORRUPTED BY BIT ROT", encoding="utf-8")

        rep2 = verify_snapshot_integrity(demo_dest / "snapshots" / b_id2)
        self.assertFalse(rep2.is_valid)
        self.assertEqual(rep2.failed_count, 1)


if __name__ == "__main__":
    unittest.main()
