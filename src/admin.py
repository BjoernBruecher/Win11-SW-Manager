"""Request administrator privileges before starting the application."""

import ctypes
import os
import subprocess
import sys
from ctypes import wintypes


def ensure_admin() -> bool:
    """Return whether this process is elevated, relaunching it if necessary."""
    if sys.platform != "win32":
        return True

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.IsUserAnAdmin.restype = ctypes.c_int
    shell32.ShellExecuteW.argtypes = (
        wintypes.HWND,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.c_int
    )
    shell32.ShellExecuteW.restype = ctypes.c_void_p

    if shell32.IsUserAnAdmin():
        return True

    if getattr(sys, "frozen", False):
        executable = sys.executable
        arguments = sys.argv[1:]
    else:
        executable = sys.executable
        arguments = [os.path.abspath(sys.argv[0]), *sys.argv[1:]]

    ctypes.set_last_error(0)
    result = shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        subprocess.list2cmdline(arguments),
        os.getcwd(),
        1
    )
    if result and result > 32:
        return False
    last_error = ctypes.get_last_error()
    if last_error == 1223:
        return False
    error = result if result is not None else last_error
    raise OSError(
        f"Could not restart with administrator privileges "
        f"(ShellExecuteW error {error})."
    )
