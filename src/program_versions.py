"""Look up installed program versions using Windows Package Manager."""

import re
import subprocess
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlsplit


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_COLUMN_PATTERN = re.compile(r"\S(?:.*?\S)?(?=\s{2,}|$)")
_HEADER_ROLES = {
    "available": {
        "available",
        "availableversion",
        "disponible",
        "disponibile",
        "disponivel",
        "verfugbar",
        "verfgbar",
    },
    "id": {"id", "packageid", "paketid", "identifiant"},
    "name": {"name", "nom", "nome"},
    "source": {"source", "quelle", "origine", "fonte", "fuente"},
    "version": {"version", "versione", "versiones"},
}
_INSTALLER_URL_LABELS = {
    "installerurl",
    "installationsprogrammurl",
    "urlduprogrammedinstallation",
    "urlinstallateur",
    "urlprogrammadiinstallazione",
    "urldellinstaller",
}


class ProgramVersionLookupError(RuntimeError):
    """Raised when winget cannot provide a usable installed-package list."""


def is_safe_download_url(url: str) -> bool:
    """Check that a download URL uses HTTP(S) without embedded credentials."""
    try:
        parsed_url = urlsplit(url)
    except ValueError:
        return False
    return (
        parsed_url.scheme in {"http", "https"}
        and bool(parsed_url.hostname)
        and parsed_url.username is None
        and parsed_url.password is None
    )


def get_program_version_status(program: Dict[str, Any]) -> str:
    """Return whether a program is current, has an update, or is unmatched."""
    if program.get("update_available"):
        return "update"
    installed = str(program.get("version", "")).strip().casefold()
    latest = str(program.get("latest_version", "")).strip().casefold()
    return "latest" if installed and installed == latest else ""


def has_safe_download_link(program: Dict[str, Any]) -> bool:
    """Return whether the program has a safe URL for an available update."""
    return (
        get_program_version_status(program) == "update"
        and is_safe_download_url(
            str(program.get("download_url", "")).strip()
        )
    )


def _normalize(value: object) -> str:
    return " ".join(str(value).split()).casefold()


def _header_role(value: str) -> Optional[str]:
    normalized = value.casefold().translate(
        str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss"})
    )
    normalized = re.sub(r"[^a-z]", "", normalized)
    for role, aliases in _HEADER_ROLES.items():
        if normalized in aliases:
            return role
    return None


def _installer_urls(output: str) -> List[str]:
    """Extract installer URLs from English and supported localized output."""
    urls = []
    for line in output.splitlines():
        label, separator, value = line.partition(":")
        normalized_label = re.sub(
            r"[^a-z]",
            "",
            label.casefold().translate(
                str.maketrans({
                    "ä": "a",
                    "ö": "o",
                    "ü": "u",
                    "ß": "ss",
                    "é": "e",
                    "è": "e",
                    "ê": "e",
                    "à": "a",
                    "’": "",
                    "'": ""
                })
            )
        )
        if separator and normalized_label in _INSTALLER_URL_LABELS:
            urls.append(value.strip())
    return urls


def _find_table_header(
    lines: List[str]
) -> Tuple[int, List[int], Dict[str, int]]:
    for index, line in enumerate(lines):
        matches = list(_COLUMN_PATTERN.finditer(line.rstrip()))
        starts = []
        line_roles = {}
        for match in matches:
            header = match.group().strip()
            role = _header_role(header)
            tokens = list(re.finditer(r"\S+", match.group()))
            token_roles = [
                (token, _header_role(token.group()))
                for token in tokens
            ]
            recognized_tokens = [
                (token, token_role)
                for token, token_role in token_roles
                if token_role
            ]

            if role is None and len(recognized_tokens) > 1:
                for token, token_role in recognized_tokens:
                    line_roles[token_role] = len(starts)
                    starts.append(match.start() + token.start())
            else:
                column = len(starts)
                starts.append(match.start())
                if role:
                    line_roles[role] = column
        if {"name", "id", "version"}.issubset(line_roles):
            return index, starts, line_roles
    raise ProgramVersionLookupError(
        "winget output did not contain a recognizable package table."
    )


def _parse_package_row(
    line: str,
    starts: List[int],
    roles: Dict[str, int]
) -> Optional[Tuple[str, str, str, bool]]:
    fields = [
        line[start:starts[column + 1]].strip()
        if column + 1 < len(starts)
        else line[start:].strip()
        for column, start in enumerate(starts)
    ]
    package_name = fields[roles["name"]]
    package_id = fields[roles["id"]]
    if not package_name or not package_id:
        return None

    available_column = roles.get("available")
    if available_column is not None and fields[available_column]:
        return package_name, package_id, fields[available_column], True

    source_column = roles.get("source")
    if source_column is not None and fields[source_column]:
        return package_name, package_id, fields[roles["version"]], False
    return None


def _parse_winget_list(
    output: str, programs: List[Dict[str, Any]]
) -> Tuple[List[str], List[str], List[bool]]:
    """Map exact winget package-name matches to versions and package IDs."""
    lines = _ANSI_ESCAPE.sub("", output).splitlines()
    header_index, starts, roles = _find_table_header(lines)
    matches_by_name: Dict[str, Set[Tuple[str, str, bool]]] = {}
    for line in lines[header_index + 1:]:
        if not line.strip() or re.fullmatch(r"[\s-]*-{3,}[\s-]*", line):
            continue
        package = _parse_package_row(line, starts, roles)
        if package is not None:
            name, package_id, version, update_available = package
            if version:
                matches_by_name.setdefault(_normalize(name), set()).add(
                    (version, package_id, update_available)
                )
    versions_by_name = {}
    package_ids_by_name = {}
    updates_by_name = {}
    for name, matches in matches_by_name.items():
        versions = {match[0] for match in matches}
        if len(versions) != 1:
            continue
        versions_by_name[name] = next(iter(versions))
        updates_by_name[name] = any(match[2] for match in matches)
        package_ids = {match[1] for match in matches}
        if len(package_ids) == 1:
            package_ids_by_name[name] = next(iter(package_ids))

    program_names = [
        _normalize(program.get("name", ""))
        for program in programs
    ]
    return (
        [versions_by_name.get(name, "") for name in program_names],
        [package_ids_by_name.get(name, "") for name in program_names],
        [updates_by_name.get(name, False) for name in program_names]
    )


def parse_winget_list(
    output: str, programs: List[Dict[str, Any]]
) -> List[str]:
    """Map exact winget package-name matches to their latest versions."""
    versions, _, _ = _parse_winget_list(output, programs)
    return versions


def _run_winget(arguments: List[str]) -> subprocess.CompletedProcess:
    """Run winget without a shell and report command failures explicitly."""
    try:
        result = subprocess.run(
            arguments,
            capture_output=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProgramVersionLookupError(str(exc)) from exc

    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ProgramVersionLookupError(
            detail or f"winget exited with code {result.returncode}."
        )
    return result


def get_latest_version_details(
    programs: List[Dict[str, Any]]
) -> Tuple[List[str], List[str], List[bool]]:
    """Return latest versions, exact package IDs, and update flags."""
    result = _run_winget([
        "winget",
        "list",
        "--disable-interactivity",
    ])
    return _parse_winget_list(result.stdout, programs)


def get_latest_versions(programs: List[Dict[str, Any]]) -> List[str]:
    """Return winget's latest available version for each exact name match."""
    versions, _, _ = get_latest_version_details(programs)
    return versions


def get_download_url(package_id: str, version: str) -> str:
    """Return a safe HTTP(S) installer URL for an exact package version."""
    result = _run_winget([
        "winget",
        "show",
        "--id",
        package_id,
        "--exact",
        "--version",
        version,
        "--disable-interactivity",
    ])
    for url in _installer_urls(result.stdout):
        if is_safe_download_url(url):
            return url
    raise ProgramVersionLookupError(
        f"winget did not provide an installer URL for {package_id} "
        f"version {version}."
    )
