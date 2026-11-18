"""Acquire a system-wide Windows mutex for the application lifetime."""

import ctypes
from ctypes import wintypes
from typing import Optional


_MUTEX_NAME: str = r"Global\Win11-SW-Manager"
_ERROR_ACCESS_DENIED: int = 5
_ERROR_ALREADY_EXISTS: int = 183


def _kernel32() -> ctypes.WinDLL:
    """Load kernel32 and declare the APIs used by the mutex guard."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.LPCWSTR
    )
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


def acquire_application_mutex() -> Optional[int]:
    """Return a mutex handle, or None if another instance owns the name."""
    kernel32 = _kernel32()
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    error = ctypes.get_last_error()

    if not handle:
        if error == _ERROR_ACCESS_DENIED:
            return None
        raise ctypes.WinError(error)

    if error == _ERROR_ALREADY_EXISTS:
        if not kernel32.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())
        return None

    return handle


def release_application_mutex(handle: Optional[int]) -> None:
    """Release a mutex handle returned by acquire_application_mutex."""
    if handle and not _kernel32().CloseHandle(handle):
        raise ctypes.WinError(ctypes.get_last_error())
