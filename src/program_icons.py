"""Extract Windows application icons for display in Tkinter."""

import ctypes
import os
from ctypes import wintypes
from typing import Optional, Tuple


class _BitmapInfoHeader(ctypes.Structure):
    """Represent the bitmap header used by the Windows icon renderer."""

    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def parse_display_icon(value: object) -> Tuple[str, int]:
    """Parse a DisplayIcon value into an expanded path and resource index."""
    entry = str(value).strip()
    icon_index = 0

    if entry.startswith('"'):
        closing_quote = entry.find('"', 1)
        if closing_quote != -1:
            path = entry[1:closing_quote]
            suffix = entry[closing_quote + 1:].strip()
            if suffix.startswith(","):
                try:
                    icon_index = int(suffix[1:].strip())
                except ValueError:
                    pass
        else:
            path = entry.strip('"')
    else:
        path = entry
        if "," in entry:
            possible_path, possible_index = entry.rsplit(",", 1)
            try:
                icon_index = int(possible_index.strip())
                path = possible_path.strip()
            except ValueError:
                pass

    return os.path.expandvars(path), icon_index


def _extract_icon_handles(
    path: str, icon_index: int
) -> Tuple[ctypes.c_void_p, ctypes.c_void_p]:
    """Extract large and small Windows icon handles from a file."""
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    extract_icon = shell32.ExtractIconExW
    extract_icon.argtypes = [
        wintypes.LPCWSTR,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.UINT
    ]
    extract_icon.restype = wintypes.UINT

    large_icon = ctypes.c_void_p()
    small_icon = ctypes.c_void_p()
    extract_icon(
        path,
        icon_index,
        ctypes.byref(large_icon),
        ctypes.byref(small_icon),
        1
    )
    return large_icon, small_icon


def _destroy_icon_handles(
    large_icon: ctypes.c_void_p, small_icon: ctypes.c_void_p
) -> None:
    """Release distinct icon handles returned by the Windows shell."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    destroy_icon = user32.DestroyIcon
    destroy_icon.argtypes = [ctypes.c_void_p]
    destroy_icon.restype = wintypes.BOOL

    if large_icon.value:
        destroy_icon(large_icon)
    if small_icon.value and small_icon.value != large_icon.value:
        destroy_icon(small_icon)


def _render_icon_ppm(icon: int, size: int) -> Optional[bytes]:
    """Draw a Windows icon into a PPM image buffer."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

    create_dc = gdi32.CreateCompatibleDC
    create_dc.argtypes = [ctypes.c_void_p]
    create_dc.restype = ctypes.c_void_p

    create_dib = gdi32.CreateDIBSection
    create_dib.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_BitmapInfoHeader),
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
        wintypes.DWORD
    ]
    create_dib.restype = ctypes.c_void_p

    select_object = gdi32.SelectObject
    select_object.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    select_object.restype = ctypes.c_void_p

    draw_icon = user32.DrawIconEx
    draw_icon.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
        ctypes.c_void_p,
        wintypes.UINT
    ]
    draw_icon.restype = wintypes.BOOL

    delete_object = gdi32.DeleteObject
    delete_object.argtypes = [ctypes.c_void_p]
    delete_object.restype = wintypes.BOOL

    delete_dc = gdi32.DeleteDC
    delete_dc.argtypes = [ctypes.c_void_p]
    delete_dc.restype = wintypes.BOOL

    dc = None
    bitmap = None
    previous_bitmap = None
    try:
        dc = create_dc(None)
        if not dc:
            return None

        header = _BitmapInfoHeader(
            ctypes.sizeof(_BitmapInfoHeader),
            size,
            -size,
            1,
            32,
            0,
            size * size * 4,
            0,
            0,
            0,
            0
        )
        pixel_data = ctypes.c_void_p()
        bitmap = create_dib(
            dc, ctypes.byref(header), 0,
            ctypes.byref(pixel_data), None, 0
        )
        if not bitmap or not pixel_data.value:
            return None

        previous_bitmap = select_object(dc, bitmap)
        if not previous_bitmap:
            return None

        background = bytes((0x37, 0x24, 0x18, 0xFF))
        ctypes.memmove(
            pixel_data,
            background * (size * size),
            size * size * 4
        )

        if not draw_icon(dc, 0, 0, icon, size, size, 0, None, 3):
            return None

        bgra = ctypes.string_at(pixel_data, size * size * 4)
        rgb = bytearray(size * size * 3)
        for pixel in range(size * size):
            source = pixel * 4
            target = pixel * 3
            rgb[target:target + 3] = bytes((
                bgra[source + 2],
                bgra[source + 1],
                bgra[source]
            ))

        return (
            f"P6\n{size} {size}\n255\n".encode("ascii")
            + rgb
        )
    finally:
        if previous_bitmap and dc:
            select_object(dc, previous_bitmap)
        if bitmap:
            delete_object(bitmap)
        if dc:
            delete_dc(dc)


def get_program_icon_ppm(
    value: object, size: int = 24
) -> Optional[bytes]:
    """Extract a Windows application icon as PPM data for Tkinter."""
    path, icon_index = parse_display_icon(value)
    if not path or not os.path.isfile(path):
        return None

    large_icon, small_icon = _extract_icon_handles(path, icon_index)
    try:
        icon = small_icon.value or large_icon.value
        if not icon:
            return None
        return _render_icon_ppm(icon, size)
    finally:
        _destroy_icon_handles(large_icon, small_icon)
