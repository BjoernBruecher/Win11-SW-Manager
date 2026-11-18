"""Tests for application-level version lookup behavior."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.software_manager import (
    LatestVersionLookup,
    SoftwareManager,
    WINGET_TROUBLESHOOTING_URL,
)


class SoftwareManagerTests(unittest.TestCase):
    """Verify troubleshooting guidance for winget lookup failures."""

    def test_failed_lookup_exposes_troubleshooting_link(self):
        """Expose the README link when latest-version lookup fails."""
        programs = []
        view = Mock()
        view.programs = programs
        manager = SoftwareManager.__new__(SoftwareManager)
        manager.latest_version_lookup_generation = 3
        manager.view = view

        manager._finish_latest_version_lookup(  # pylint: disable=protected-access
            programs,
            3,
            LatestVersionLookup(None, None, None, None, 0)
        )

        view.set_status_link.assert_called_once_with(
            "status_versions_unavailable",
            manager.open_winget_troubleshooting
        )

    @patch("src.software_manager.webbrowser.open", return_value=True)
    def test_troubleshooting_link_opens_readme_anchor(self, open_browser):
        """Open the README section from the status link callback."""
        manager = SoftwareManager.__new__(SoftwareManager)

        manager.open_winget_troubleshooting()

        open_browser.assert_called_once_with(WINGET_TROUBLESHOOTING_URL)

    @patch("src.software_manager.messagebox.showerror")
    @patch("src.software_manager.webbrowser.open", return_value=False)
    def test_troubleshooting_link_reports_browser_failure(
        self, _open_browser, show_error
    ):
        """Report when the user's browser cannot open the README link."""
        manager = SoftwareManager.__new__(SoftwareManager)
        manager.view = SimpleNamespace(
            language=SimpleNamespace(get=lambda: "US")
        )

        manager.open_winget_troubleshooting()

        show_error.assert_called_once_with(
            "Error",
            "The troubleshooting guide could not be opened in a browser."
        )
