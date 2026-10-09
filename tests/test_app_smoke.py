"""Automated smoke test for the SafeVault GUI application lifecycle."""

import tempfile
import unittest
from pathlib import Path

from safevault.app import SafeVaultApp


class TestAppSmoke(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "smoke_test.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_app_initialization_and_page_navigation(self):
        """Verify that the GUI window, views, and navigation initialize without errors."""
        app = SafeVaultApp(db_path=self.db_path)

        # Test switching across all 7 views
        pages = ["dashboard", "setup", "history", "restore", "activity", "settings", "about"]
        for p in pages:
            app.navigate_to(p)
            self.assertEqual(app._current_page, p)
            self.assertIn(p, app.views)

        # Trigger manual view refreshes
        app.views["dashboard"].refresh_dashboard()
        app.views["setup"].refresh_setup()
        app.views["history"].refresh_history()
        app.views["restore"].refresh_restore_page()
        app.views["activity"].refresh_activity_page()
        app.views["settings"].refresh_settings()

        # Stop scheduler and destroy window cleanly
        app.scheduler.stop()
        app.root.update_idletasks()
        app.root.destroy()


if __name__ == "__main__":
    unittest.main()
