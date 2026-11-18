"""Acquire a system-wide Windows mutex for the application lifetime."""

import ctypes
from ctypes import wintypes


_MUTEX_NAME = r"Global\Win11-SW-Manager"
_ERROR_ACCESS_DENIED = 5
_ERROR_ALREADY_EXISTS = 183


def _kernel32():
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


def acquire_application_mutex():
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


def release_application_mutex(handle):
    """Release a mutex handle returned by acquire_application_mutex."""
    if handle and not _kernel32().CloseHandle(handle):
        raise ctypes.WinError(ctypes.get_last_error())
