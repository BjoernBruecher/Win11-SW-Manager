"""Tests for application-level version lookup behavior."""

import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.software_manager import (
    LatestVersionLookup,
    SoftwareManager,
    WINGET_TROUBLESHOOTING_URL,
)
from src.software_manager_view import SoftwareManagerView


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

    @patch("src.software_manager.threading.Thread")
    def test_selected_updates_are_started_as_one_batch(self, thread):
        """Include every selected safe update and ignore non-updates."""
        selected = [
            {
                "name": "First App",
                "update_available": True,
                "download_url": "https://example.com/first.exe",
            },
            {
                "name": "Second App",
                "update_available": True,
                "download_url": "https://example.com/second.exe",
            },
            {"name": "Current App", "update_available": False},
        ]
        manager = SoftwareManager.__new__(SoftwareManager)
        manager.downloads_in_progress = False
        manager.view = SimpleNamespace(
            selected_programs=lambda: selected,
            set_downloads_in_progress=Mock(),
            set_status=Mock()
        )

        manager.download_selected_updates()

        self.assertEqual(len(thread.call_args.kwargs["args"][0]), 2)
        self.assertEqual(thread.call_args.kwargs["args"][1], [])
        thread.return_value.start.assert_called_once()
        self.assertTrue(manager.downloads_in_progress)

    def test_download_worker_never_runs_more_than_two_downloads(self):
        """Run parallel downloads with a hard two-worker ceiling."""
        manager = SoftwareManager.__new__(SoftwareManager)
        manager.root = Mock()
        lock = threading.Lock()
        start_together = threading.Barrier(2)
        active = 0
        maximum_active = 0
        started = 0

        def fake_download(program, _directory):
            nonlocal active, maximum_active, started
            with lock:
                started += 1
                wait_for_pair = started <= 2
                active += 1
                maximum_active = max(maximum_active, active)
            try:
                if wait_for_pair:
                    start_together.wait(timeout=2)
                time.sleep(0.02)
                return Path(program["name"])
            finally:
                with lock:
                    active -= 1

        programs = [
            {"name": f"App {index}"} for index in range(5)
        ]
        with patch(
            "src.software_manager.download_installer",
            side_effect=fake_download
        ):
            manager._download_updates_worker(  # pylint: disable=protected-access
                programs, []
            )

        self.assertEqual(maximum_active, 2)
        self.assertEqual(
            manager.root.after.call_args.args[1],
            manager._finish_download_batch
        )

    @patch("src.software_manager_view.position_status_cells")
    def test_multiple_updateable_selections_enable_downloads(
        self, _position_status_cells
    ):
        """Enable the batch action when selected rows have safe update links."""
        view = SoftwareManagerView.__new__(SoftwareManagerView)
        view.tree = Mock()
        view.tree.selection.return_value = ("1", "2")
        view.widgets = {
            "summary_values": {"selected": Mock()},
            "action_buttons": {"download_update": Mock()},
            "status_cells": {},
        }
        view.downloads_in_progress = False
        view.selected_programs = Mock(return_value=[
            {
                "update_available": True,
                "download_url": "https://example.com/first.exe",
            },
            {
                "update_available": True,
                "download_url": "https://example.com/second.exe",
            },
        ])

        view.update_selection_count()

        button = view.action_buttons["download_update"]
        button.set_enabled.assert_called_once_with(True)

        view.set_downloads_in_progress(True)

        self.assertFalse(button.set_enabled.call_args.args[0])

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
