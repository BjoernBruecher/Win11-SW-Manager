"""Tests for downloading update installers without executing them."""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.program_downloads import UpdateDownloadError, download_installer


class FakeResponse(io.BytesIO):
    """Provide an HTTP response stream with a final URL."""

    def __init__(self, content, url):
        super().__init__(content)
        self.url = url

    def geturl(self):
        return self.url


class DownloadInstallerTests(unittest.TestCase):
    """Verify safe URLs, filenames, and completed installer files."""

    def setUp(self):
        self.program = {
            "name": "Example App",
            "latest_version": "2.0",
            "update_available": True,
            "download_url": "https://example.com/installer.exe",
        }

    @patch("src.program_downloads.urllib.request.urlopen")
    def test_downloads_to_a_named_file_without_running_it(self, urlopen):
        urlopen.return_value = FakeResponse(
            b"installer-content",
            "https://example.com/installer.exe"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = download_installer(
                self.program, Path(temporary_directory)
            )

            self.assertEqual(path.name, "Example App 2.0.exe")
            self.assertEqual(path.read_bytes(), b"installer-content")

    @patch("src.program_downloads.urllib.request.urlopen")
    def test_does_not_overwrite_an_existing_download(self, urlopen):
        urlopen.side_effect = [
            FakeResponse(b"first", "https://example.com/installer.exe"),
            FakeResponse(b"second", "https://example.com/installer.exe"),
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            first = download_installer(self.program, directory)
            second = download_installer(self.program, directory)

            self.assertEqual(first.read_bytes(), b"first")
            self.assertEqual(second.read_bytes(), b"second")
            self.assertEqual(second.name, "Example App 2.0 (2).exe")

    @patch("src.program_downloads.urllib.request.urlopen")
    def test_rejects_an_unsafe_redirect(self, urlopen):
        urlopen.return_value = FakeResponse(b"installer", "file:///setup.exe")
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(UpdateDownloadError):
                download_installer(
                    self.program, Path(temporary_directory)
                )
            self.assertEqual(list(Path(temporary_directory).iterdir()), [])
