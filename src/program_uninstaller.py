"""Safely prepare and run Windows application uninstall commands."""

import ctypes
import os
import subprocess
from ctypes import wintypes
from typing import List

from .localization import translate


class ProgramUninstaller:
    """Encapsulate Windows uninstall command validation and execution."""

    @staticmethod
    def is_admin() -> bool:
        """Return whether the current process has administrator privileges."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except (AttributeError, OSError):
            return False

    @staticmethod
    def split_command(command: str) -> List[str]:
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
    def prepare_arguments(cls, command: str, language: str = "DE") -> List[str]:
        """Validate an uninstall command and prepare safe process arguments."""
        args = cls.split_command(command)
        if not args:
            raise ValueError(translate(language, "empty_command"))

        executable = os.path.basename(args[0]).lower()
        if executable in ("msiexec", "msiexec.exe"):
            if any(
                argument.lower() in ("/qn", "/quiet")
                for argument in args
            ):
                raise ValueError(
                    translate(language, "silent_msi_blocked")
                )

            for index, argument in enumerate(args):
                if argument.lower() == "/i":
                    args[index] = "/x"
                elif argument.lower().startswith("/i{"):
                    args[index] = "/x" + argument[2:]

        if executable.endswith((".bat", ".cmd", ".ps1", ".vbs")):
            raise ValueError(
                translate(language, "script_uninstall_blocked")
            )

        return args

    @classmethod
    def run(
        cls, command: str, language: str = "DE"
    ) -> subprocess.CompletedProcess[bytes]:
        """Run a validated uninstall command without invoking a shell."""
        return subprocess.run(
            cls.prepare_arguments(command, language),
            shell=False,
            check=False
        )
