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

    @patch("src.software_manager.get_download_url")
    @patch("src.software_manager.get_latest_version_details")
    def test_versions_are_dispatched_before_download_link_lookups(
        self, get_versions, get_download_url
    ):
        """Show available versions without waiting for installer URLs."""
        programs = [{"name": "Example App"}]
        scheduled = []
        manager = SoftwareManager.__new__(SoftwareManager)
        manager.root = SimpleNamespace(
            after=lambda delay, callback, *args: scheduled.append(args)
        )
        get_versions.return_value = (["2.0"], ["Example.App"], [True])

        def find_download_url(*_args):
            self.assertEqual(len(scheduled), 1)
            return "https://example.com/installer.exe"

        get_download_url.side_effect = find_download_url

        manager._latest_version_worker(  # pylint: disable=protected-access
            programs, 3
        )

        self.assertEqual(len(scheduled), 2)
        self.assertEqual(scheduled[0][2].versions, ["2.0"])
        self.assertEqual(scheduled[0][2].download_urls, [""])
        self.assertFalse(scheduled[0][3])
        self.assertEqual(scheduled[1][2].download_urls, [
            "https://example.com/installer.exe"
        ])

    @patch("src.software_manager.get_latest_version_details")
    def test_unexpected_lookup_error_is_reported_to_ui(self, get_versions):
        """Dispatch a failure result instead of leaving the status checking."""
        programs = []
        manager = SoftwareManager.__new__(SoftwareManager)
        manager.root = Mock()
        get_versions.side_effect = RuntimeError("unexpected failure")

        with self.assertLogs("root", level="ERROR"):
            manager._latest_version_worker(  # pylint: disable=protected-access
                programs, 3
            )

        manager.root.after.assert_called_once()
        self.assertIsNone(manager.root.after.call_args.args[4].versions)

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
