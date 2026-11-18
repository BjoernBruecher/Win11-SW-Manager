"""Tests for Windows Package Manager version lookup."""

import unittest
from unittest.mock import patch

from src.program_versions import (
    ProgramVersionLookupError,
    get_download_url,
    get_latest_version_details,
    get_latest_versions,
    parse_winget_list,
)


def format_winget_table(rows, include_available=True, headers=None):
    """Format simple fixed-width winget output for parser tests."""
    headers = list(headers or ["Name", "Id", "Version"])
    widths = [16, 23, 11]
    if include_available:
        if len(headers) == 3:
            headers.append("Available")
        widths.append(11)
    if len(headers) == len(widths):
        headers.append("Source")
    header = "".join(
        f"{value:<{width}}"
        for value, width in zip(headers[:-1], widths)
    ) + headers[-1]
    lines = [header, "-" * len(header)]
    for row in rows:
        values = list(row)
        lines.append(
            "".join(
                f"{value:<{width}}"
                for value, width in zip(values[:-1], widths)
            ) + values[-1]
        )
    return "\n".join(lines)


class ParseWingetListTests(unittest.TestCase):
    """Verify package matching and winget command handling."""

    def test_reads_available_and_current_versions_by_exact_name(self):
        """Use an available version, or current version when up to date."""
        output = format_winget_table(
            [
                ("Example Editor", "Example.Editor", "1.0.0", "1.2.0", "winget"),
                ("Example Player", "Example.Player", "3.4.0", "", "winget"),
                ("Example Edit", "Example.Edit", "7.0.0", "8.0.0", "winget"),
            ]
        )
        programs = [
            {"name": "Example Editor"},
            {"name": "Example Player"},
            {"name": "Example Edit"},
            {"name": "Not Listed"},
        ]

        self.assertEqual(
            parse_winget_list(output, programs),
            ["1.2.0", "3.4.0", "8.0.0", ""],
        )

    def test_ambiguous_name_does_not_guess(self):
        """Leave duplicate package names blank when versions disagree."""
        output = format_winget_table(
            [
                ("Example App", "Example.App.Stable", "1.0", "2.0", "winget"),
                ("Example App", "Example.App.Beta", "1.0", "3.0", "winget"),
            ]
        )

        self.assertEqual(
            parse_winget_list(output, [{"name": "Example App"}]),
            [""],
        )

    def test_reads_current_version_when_no_update_column_exists(self):
        """Use a matched installed version if winget omits the update column."""
        output = format_winget_table(
            [
                ("Example Player", "Example.Player", "3.4.0", "winget"),
            ],
            include_available=False,
        )

        self.assertEqual(
            parse_winget_list(output, [{"name": "Example Player"}]),
            ["3.4.0"],
        )

    def test_reads_german_winget_column_headings(self):
        """Recognize the localized headings used by German Windows."""
        output = format_winget_table(
            [
                ("Example Player", "Example.Player", "3.4.0", "3.5.0", "winget"),
            ],
            headers=["Name", "Id", "Version", "Verfügbar"],
        )

        self.assertEqual(
            parse_winget_list(output, [{"name": "Example Player"}]),
            ["3.5.0"],
        )

    @patch("src.program_versions.subprocess.run")
    def test_returns_exact_package_ids_and_update_flags(self, run):
        """Only available updates are marked for installer lookup."""
        run.return_value.returncode = 0
        run.return_value.stdout = format_winget_table(
            [
                ("Example Editor", "Example.Editor", "1.0", "1.2", "winget"),
                ("Example Player", "Example.Player", "3.4", "", "winget"),
            ]
        )
        run.return_value.stderr = ""

        self.assertEqual(
            get_latest_version_details(
                [{"name": "Example Editor"}, {"name": "Example Player"}]
            ),
            (["1.2", "3.4"], ["Example.Editor", "Example.Player"], [True, False]),
        )

    @patch("src.program_versions.subprocess.run")
    def test_does_not_guess_package_id_for_duplicate_names(self, run):
        """Keep ambiguous IDs unavailable even when names share a version."""
        run.return_value.returncode = 0
        run.return_value.stdout = format_winget_table(
            [
                ("Example App", "Example.App.Stable", "1.0", "2.0", "winget"),
                ("Example App", "Example.App.Beta", "1.0", "2.0", "winget"),
            ]
        )
        run.return_value.stderr = ""

        self.assertEqual(
            get_latest_version_details([{"name": "Example App"}]),
            (["2.0"], [""], [True]),
        )

    def test_unrecognized_output_is_an_error(self):
        """Reject output that cannot be parsed as a package list."""
        with self.assertRaises(ProgramVersionLookupError):
            parse_winget_list("winget could not connect", [{"name": "App"}])

    @patch("src.program_versions.subprocess.run")
    def test_runs_winget_without_a_shell(self, run):
        """Call winget through argv, not through a command shell."""
        run.return_value.returncode = 0
        run.return_value.stdout = format_winget_table(
            [
                ("Example Editor", "Example.Editor", "1.0.0", "1.2.0", "winget"),
            ]
        )
        run.return_value.stderr = ""

        versions = get_latest_versions([{"name": "Example Editor"}])

        self.assertEqual(versions, ["1.2.0"])
        self.assertEqual(run.call_args.args[0][:2], ["winget", "list"])
        self.assertFalse(run.call_args.kwargs["shell"])

    @patch("src.program_versions.subprocess.run")
    def test_reads_installer_url_for_the_exact_available_version(self, run):
        """Resolve the installer URL for a specific package version."""
        run.return_value.returncode = 0
        run.return_value.stdout = (
            "Version: 1.2.0\n"
            "Installer Url: https://example.test/download/1.2.0.exe\n"
        )
        run.return_value.stderr = ""

        self.assertEqual(
            get_download_url("Example.Editor", "1.2.0"),
            "https://example.test/download/1.2.0.exe",
        )
        self.assertEqual(
            run.call_args.args[0][2:],
            [
                "--id",
                "Example.Editor",
                "--exact",
                "--version",
                "1.2.0",
                "--disable-interactivity",
            ],
        )
        self.assertFalse(run.call_args.kwargs["shell"])

    @patch("src.program_versions.subprocess.run")
    def test_reads_a_localized_installer_url_label(self, run):
        """Recognize translated winget field labels for installer URLs."""
        run.return_value.returncode = 0
        run.return_value.stdout = (
            "Version: 1.2.0\n"
            "Installationsprogramm-URL: "
            "https://example.test/download/1.2.0.exe\n"
        )
        run.return_value.stderr = ""

        self.assertEqual(
            get_download_url("Example.Editor", "1.2.0"),
            "https://example.test/download/1.2.0.exe",
        )

    @patch("src.program_versions.subprocess.run")
    def test_requires_an_http_installer_url(self, run):
        """Reject winget metadata without a safe web installer URL."""
        run.return_value.returncode = 0
        run.return_value.stdout = "Installer Url: file:///local/setup.exe\n"
        run.return_value.stderr = ""

        with self.assertRaisesRegex(ProgramVersionLookupError, "installer URL"):
            get_download_url("Example.Editor", "1.2.0")

    @patch("src.program_versions.subprocess.run")
    def test_reports_winget_source_errors(self, run):
        """Do not treat a failed winget lookup as a successful empty result."""
        run.return_value.returncode = 1
        run.return_value.stdout = ""
        run.return_value.stderr = "Source agreements have not been accepted."

        with self.assertRaisesRegex(ProgramVersionLookupError, "agreements"):
            get_latest_versions([{"name": "Example Editor"}])


if __name__ == "__main__":
    unittest.main()
