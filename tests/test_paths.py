"""Unit tests for SafeVault path validation and safety utilities."""

import os
import tempfile
import unittest
from pathlib import Path

from safevault.paths import (
    validate_backup_paths,
    is_safe_relative_path,
    resolve_safe_subpath,
    get_unique_destination_dir,
)


class TestPathValidation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name).resolve()

        self.source_dir = self.base_path / "source_folder"
        self.source_dir.mkdir(parents=True, exist_ok=True)

        self.dest_dir = self.base_path / "backup_dest"
        self.dest_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_valid_separate_paths(self):
        valid, msg = validate_backup_paths(self.source_dir, self.dest_dir)
        self.assertTrue(valid)
        self.assertEqual(msg, "")

    def test_nonexistent_source(self):
        bad_source = self.base_path / "does_not_exist"
        valid, msg = validate_backup_paths(bad_source, self.dest_dir)
        self.assertFalse(valid)
        self.assertIn("does not exist", msg.lower())

    def test_source_is_file(self):
        file_path = self.base_path / "file.txt"
        file_path.write_text("hello", encoding="utf-8")
        valid, msg = validate_backup_paths(file_path, self.dest_dir)
        self.assertFalse(valid)
        self.assertIn("is a file", msg.lower())

    def test_same_directory(self):
        valid, msg = validate_backup_paths(self.source_dir, self.source_dir)
        self.assertFalse(valid)
        self.assertIn("exact same folder", msg.lower())

    def test_destination_inside_source(self):
        sub_dest = self.source_dir / "backups"
        sub_dest.mkdir(parents=True, exist_ok=True)
        valid, msg = validate_backup_paths(self.source_dir, sub_dest)
        self.assertFalse(valid)
        self.assertIn("destination is inside your source", msg.lower())

    def test_source_inside_destination(self):
        sub_source = self.dest_dir / "sub_source"
        sub_source.mkdir(parents=True, exist_ok=True)
        valid, msg = validate_backup_paths(sub_source, self.dest_dir)
        self.assertFalse(valid)
        self.assertIn("source folder is inside your backup destination", msg.lower())

    def test_safe_relative_path(self):
        # Valid relative paths
        self.assertTrue(is_safe_relative_path("notes.txt"))
        self.assertTrue(is_safe_relative_path("folder/subfolder/file.py"))
        self.assertTrue(is_safe_relative_path("my documents/test file (1).docx"))

        # Unsafe relative paths
        self.assertFalse(is_safe_relative_path("../escape.txt"))
        self.assertFalse(is_safe_relative_path("sub/../../escape.txt"))
        self.assertFalse(is_safe_relative_path("/absolute/path"))
        self.assertFalse(is_safe_relative_path("C:/Windows/System32"))
        self.assertFalse(is_safe_relative_path(""))
        self.assertFalse(is_safe_relative_path("."))

    def test_resolve_safe_subpath(self):
        root = self.base_path
        safe_file = resolve_safe_subpath(root, "folder/doc.txt")
        self.assertIsNotNone(safe_file)
        self.assertTrue(safe_file.is_relative_to(root))

        unsafe_file = resolve_safe_subpath(root, "../outside.txt")
        self.assertIsNone(unsafe_file)

    def test_unique_destination_dir(self):
        base_name = "Restore_Folder"
        first = get_unique_destination_dir(self.base_path, base_name)
        self.assertEqual(first.name, base_name)
        first.mkdir()

        second = get_unique_destination_dir(self.base_path, base_name)
        self.assertEqual(second.name, f"{base_name}_1")


if __name__ == "__main__":
    unittest.main()
