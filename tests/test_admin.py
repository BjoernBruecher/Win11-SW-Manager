"""Tests for startup administrator elevation."""

import unittest
from unittest.mock import patch

from src.admin import ensure_admin


class AdminTests(unittest.TestCase):
    """Verify startup privilege checks and relaunch arguments."""

    @patch("src.admin.ctypes.WinDLL", create=True)
    def test_elevated_process_does_not_relaunch(self, load_dll):
        """Continue directly when Windows reports administrator privileges."""
        shell32 = load_dll.return_value
        shell32.IsUserAnAdmin.return_value = 1

        with patch("src.admin.sys.platform", "win32"):
            self.assertTrue(ensure_admin())

        shell32.ShellExecuteW.assert_not_called()

    @patch("src.admin.ctypes.WinDLL", create=True)
    def test_non_elevated_process_relaunches_with_original_arguments(
        self, load_dll
    ):
        """Use the UAC runas verb and preserve the script's arguments."""
        shell32 = load_dll.return_value
        shell32.IsUserAnAdmin.return_value = 0
        shell32.ShellExecuteW.return_value = 33
        script_path = r"C:\My App\Win11-SW-Manager.py"
        with patch("src.admin.sys.platform", "win32"), \
                patch("src.admin.sys.argv", ["Win11-SW-Manager.py", "--help"]), \
                patch("src.admin.sys.executable", r"C:\Python\python.exe"), \
                patch("src.admin.sys.frozen", False, create=True), \
                patch("src.admin.os.path.abspath", return_value=script_path), \
                patch("src.admin.os.getcwd", return_value=r"C:\My App"), \
                patch("src.admin.ctypes.set_last_error", create=True), \
                patch("src.admin.ctypes.get_last_error", return_value=0, create=True):
            self.assertFalse(ensure_admin())

        arguments = shell32.ShellExecuteW.call_args.args
        self.assertEqual(arguments[1:3], ("runas", r"C:\Python\python.exe"))
        self.assertEqual(arguments[3], f'"{script_path}" --help')
        self.assertEqual(arguments[4], r"C:\My App")


if __name__ == "__main__":
    unittest.main()
