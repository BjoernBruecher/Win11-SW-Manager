"""Tests for operating-system locale detection and localization."""

import unittest
from unittest.mock import patch

from src.localization import (
    detect_system_language,
    detect_system_locale_name,
)


class LocalizationTests(unittest.TestCase):
    """Verify locale detection and fallback behavior."""

    def test_supported_system_language_is_detected(self):
        """Map a supported OS locale to its interface language."""
        with patch("src.localization.locale.getlocale", return_value=("de_DE", "UTF-8")):
            self.assertEqual(detect_system_language(), "DE")

    def test_unsupported_system_language_falls_back_to_german(self):
        """Fall back to German for an unsupported OS locale."""
        with patch("src.localization.locale.getlocale", return_value=("es_ES", "UTF-8")):
            self.assertEqual(detect_system_language(), "DE")

    def test_locale_name_is_normalized_for_the_gui(self):
        """Display underscore-based locale names with a hyphen."""
        with patch("src.localization.sys.platform", "linux"):
            with patch(
                "src.localization.locale.getlocale",
                return_value=("fr_FR", "UTF-8"),
            ):
                self.assertEqual(detect_system_locale_name(), "fr-FR")
