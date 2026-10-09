"""Unit tests for SafeVault SHA-256 integrity verification."""

import json
import tempfile
import unittest
from pathlib import Path

from safevault.integrity import compute_file_sha256, verify_snapshot_integrity


class TestIntegrity(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name).resolve()

        self.snapshot_dir = self.base_path / "snapshots" / "test_backup"
        self.data_dir = self.snapshot_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Create sample files
        self.file1 = self.data_dir / "file1.txt"
        self.file1.write_text("Hello World", encoding="utf-8")
        self.hash1 = compute_file_sha256(self.file1)

        self.file2 = self.data_dir / "sub" / "file2.txt"
        self.file2.parent.mkdir(parents=True, exist_ok=True)
        self.file2.write_text("College OS Assignment", encoding="utf-8")
        self.hash2 = compute_file_sha256(self.file2)

        # Write manifest
        self.manifest_data = {
            "manifest_version": 1,
            "backup_id": "test_backup",
            "total_files": 2,
            "files": [
                {
                    "relative_path": "file1.txt",
                    "size": self.file1.stat().st_size,
                    "sha256": self.hash1,
                },
                {
                    "relative_path": "sub/file2.txt",
                    "size": self.file2.stat().st_size,
                    "sha256": self.hash2,
                },
            ],
        }
        with open(self.snapshot_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(self.manifest_data, f)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_verify_intact_snapshot(self):
        report = verify_snapshot_integrity(self.snapshot_dir)
        self.assertTrue(report.is_valid)
        self.assertEqual(report.passed_count, 2)
        self.assertEqual(report.failed_count, 0)
        self.assertIn("verified", report.summary_message.lower())

    def test_detect_tampered_file(self):
        # Tamper with file1
        self.file1.write_text("Altered Malicious Content", encoding="utf-8")
        report = verify_snapshot_integrity(self.snapshot_dir)
        self.assertFalse(report.is_valid)
        self.assertEqual(report.failed_count, 1)

        failed_entry = report.file_results[0]
        self.assertIn(failed_entry.status, ["HASH_MISMATCH", "SIZE_MISMATCH"])

    def test_detect_missing_file(self):
        self.file2.unlink()
        report = verify_snapshot_integrity(self.snapshot_dir)
        self.assertFalse(report.is_valid)
        self.assertEqual(report.failed_count, 1)

        failed_entry = [f for f in report.file_results if f.relative_path == "sub/file2.txt"][0]
        self.assertEqual(failed_entry.status, "MISSING")

    def test_missing_manifest(self):
        (self.snapshot_dir / "manifest.json").unlink()
        report = verify_snapshot_integrity(self.snapshot_dir)
        self.assertFalse(report.is_valid)
        self.assertIn("missing", report.summary_message.lower())


if __name__ == "__main__":
    unittest.main()
