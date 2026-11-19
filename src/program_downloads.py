"""Download selected update installers without executing them."""

import http.client
import os
import re
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict
from urllib.parse import unquote, urlsplit

from .program_versions import has_safe_download_link, is_safe_download_url


class UpdateDownloadError(RuntimeError):
    """Raised when an update installer cannot be downloaded safely."""


def _safe_filename_component(value: object, fallback: str) -> str:
    component = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value).strip())
    component = component.rstrip(" .")[:120]
    if not component or component in {".", ".."}:
        return fallback
    if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$", component, re.I):
        return f"_{component}"
    return component


def _installer_filename(program: Dict[str, Any], url: str) -> str:
    name = _safe_filename_component(program.get("name", ""), "update")
    version = _safe_filename_component(
        program.get("latest_version", ""), "latest"
    )
    extension = Path(unquote(urlsplit(url).path)).suffix
    if not re.fullmatch(r"\.[A-Za-z0-9]{1,10}", extension):
        extension = ""
    filename = f"{name} {version}"
    filename = filename[:180 - len(extension)].rstrip(" .")
    return f"{filename}{extension}"


def _move_to_unique_destination(
    temporary_path: Path, directory: Path, filename: str
) -> Path:
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    for index in range(1, 10000):
        candidate_name = (
            filename if index == 1 else f"{stem} ({index}){suffix}"
        )
        destination = directory / candidate_name
        try:
            temporary_path.rename(destination)
        except FileExistsError:
            continue
        return destination
    raise UpdateDownloadError(
        f"Could not choose a unique filename for {filename}."
    )


def download_installer(
    program: Dict[str, Any], download_directory: Path
) -> Path:
    """Download a safe update URL to disk without launching the installer."""
    url = str(program.get("download_url", "")).strip()
    if not has_safe_download_link(program):
        raise UpdateDownloadError("A valid download link is not available.")

    try:
        download_directory.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".win11-sw-manager-",
            suffix=".part",
            dir=str(download_directory)
        )
    except OSError as exc:
        raise UpdateDownloadError(str(exc)) from exc

    temporary_path = Path(temporary_name)
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Win11-SW-Manager"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            if not is_safe_download_url(response.geturl()):
                raise UpdateDownloadError(
                    "The installer redirected to an unsafe URL."
                )
            size = 0
            with os.fdopen(descriptor, "wb") as installer_file:
                descriptor = -1
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    installer_file.write(chunk)
                    size += len(chunk)
        if not size:
            raise UpdateDownloadError("The installer download was empty.")
        return _move_to_unique_destination(
            temporary_path,
            download_directory,
            _installer_filename(program, url)
        )
    except UpdateDownloadError:
        raise
    except (
        OSError,
        urllib.error.URLError,
        http.client.HTTPException,
        ValueError
    ) as exc:
        raise UpdateDownloadError(str(exc)) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
