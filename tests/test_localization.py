"""Tests for Windows language detection and localization."""

import unittest
from unittest.mock import Mock, patch

from src.localization import (
    detect_system_language,
)


class LocalizationTests(unittest.TestCase):
    """Verify locale detection and fallback behavior."""

    def test_first_windows_user_language_is_detected(self):
        """Map the first preferred Windows language to the interface."""
        with patch("src.localization.sys.platform", "win32"):
            with patch(
                "src.localization.subprocess.run",
                return_value=Mock(stdout='"de-DE"')
            ):
                self.assertEqual(detect_system_language(), "DE")

    def test_unsupported_first_windows_language_falls_back_to_us(self):
        """Do not skip an unsupported first preference for later languages."""
        with patch("src.localization.sys.platform", "win32"):
            with patch(
                "src.localization.subprocess.run",
                return_value=Mock(stdout='"es-ES"')
            ):
                self.assertEqual(detect_system_language(), "US")

    def test_windows_language_detection_failure_falls_back_to_us(self):
        """Use US when Windows language preferences cannot be read."""
        with patch("src.localization.sys.platform", "win32"):
            with patch(
                "src.localization.subprocess.run",
                side_effect=OSError("PowerShell unavailable")
            ):
                self.assertEqual(detect_system_language(), "US")

    def test_supported_non_windows_locale_is_detected(self):
        """Map a supported locale when running outside Windows."""
        with patch("src.localization.sys.platform", "linux"):
            with patch("src.localization.locale.getlocale", return_value=("de_DE", "UTF-8")):
                self.assertEqual(detect_system_language(), "DE")

    def test_unsupported_non_windows_locale_falls_back_to_us(self):
        """Fall back to US when the locale has no supported language."""
        with patch("src.localization.sys.platform", "linux"):
            with patch("src.localization.locale.getlocale", return_value=("es_ES", "UTF-8")):
                self.assertEqual(detect_system_language(), "US")
