"""Safely prepare and run Windows application uninstall commands."""

import ctypes
import os
import subprocess
from ctypes import wintypes


class ProgramUninstaller:
    """Encapsulate Windows uninstall command validation and execution."""

    @staticmethod
    def is_admin():
        """Return whether the current process has administrator privileges."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except (AttributeError, OSError):
            return False

    @staticmethod
    def split_command(command):
        """Parse a Windows command line without shell expansion."""
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        shell32.CommandLineToArgvW.argtypes = [
            wintypes.LPCWSTR,
            ctypes.POINTER(ctypes.c_int)
        ]
        shell32.CommandLineToArgvW.restype = (
            ctypes.POINTER(wintypes.LPWSTR)
        )

        argc = ctypes.c_int()
        argv = shell32.CommandLineToArgvW(
            command, ctypes.byref(argc)
        )
        if not argv:
            raise ctypes.WinError(ctypes.get_last_error())

        try:
            return [argv[index] for index in range(argc.value)]
        finally:
            ctypes.windll.kernel32.LocalFree(argv)

    @classmethod
    def prepare_arguments(cls, command):
        """Validate an uninstall command and prepare safe process arguments."""
        args = cls.split_command(command)
        if not args:
            raise ValueError("Leerer Befehl")

        executable = os.path.basename(args[0]).lower()
        if executable in ("msiexec", "msiexec.exe"):
            if any(
                argument.lower() in ("/qn", "/quiet")
                for argument in args
            ):
                raise ValueError(
                    "Unbeaufsichtigte MSI-Deinstallation wird aus "
                    "Sicherheitsgründen nicht automatisch ausgeführt."
                )

            for index, argument in enumerate(args):
                if argument.lower() == "/i":
                    args[index] = "/x"
                elif argument.lower().startswith("/i{"):
                    args[index] = "/x" + argument[2:]

        if executable.endswith((".bat", ".cmd", ".ps1", ".vbs")):
            raise ValueError(
                "Skriptbasierte Deinstallation benötigt eine manuelle Prüfung."
            )

        return args

    @classmethod
    def run(cls, command):
        """Run a validated uninstall command without invoking a shell."""
        return subprocess.run(
            cls.prepare_arguments(command),
            shell=False,
            check=False
        )
