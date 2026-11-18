"""Look up installed program versions using Windows Package Manager."""

import re
import subprocess
from typing import Any, Dict, List, Optional, Set, Tuple


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
    },
    "id": {"id", "packageid", "paketid", "identifiant"},
    "name": {"name", "nom", "nome"},
    "source": {"source", "quelle", "origine", "fonte", "fuente"},
    "version": {"version", "versione", "versiones"},
}


class ProgramVersionLookupError(RuntimeError):
    """Raised when winget cannot provide a usable installed-package list."""


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


def _find_table_header(
    lines: List[str]
) -> Tuple[int, List[re.Match], Dict[str, int]]:
    for index, line in enumerate(lines):
        matches = list(_COLUMN_PATTERN.finditer(line.rstrip()))
        line_roles = {
            _header_role(match.group().strip()): column
            for column, match in enumerate(matches)
            if _header_role(match.group().strip())
        }
        if {"name", "id", "version"}.issubset(line_roles):
            return index, matches, line_roles
    raise ProgramVersionLookupError(
        "winget output did not contain a recognizable package table."
    )


def _parse_package_row(
    line: str,
    starts: List[int],
    roles: Dict[str, int]
) -> Optional[Tuple[str, str]]:
    fields = [
        line[start:starts[column + 1]].strip()
        if column + 1 < len(starts)
        else line[start:].strip()
        for column, start in enumerate(starts)
    ]
    package_name = fields[roles["name"]]
    if not package_name or not fields[roles["id"]]:
        return None

    available_column = roles.get("available")
    if available_column is not None and fields[available_column]:
        return package_name, fields[available_column]

    source_column = roles.get("source")
    if source_column is not None and fields[source_column]:
        return package_name, fields[roles["version"]]
    return None


def parse_winget_list(
    output: str, programs: List[Dict[str, Any]]
) -> List[str]:
    """Map exact winget package-name matches to their latest versions."""
    lines = _ANSI_ESCAPE.sub("", output).splitlines()
    header_index, header_matches, roles = _find_table_header(lines)
    starts = [match.start() for match in header_matches]
    matches_by_name: Dict[str, Set[str]] = {}
    for line in lines[header_index + 1:]:
        if not line.strip() or re.fullmatch(r"[\s-]*-{3,}[\s-]*", line):
            continue
        package = _parse_package_row(line, starts, roles)
        if package is not None:
            name, version = package
            if version:
                matches_by_name.setdefault(_normalize(name), set()).add(
                    version
                )
    versions_by_name = {
        name: next(iter(versions))
        for name, versions in matches_by_name.items()
        if len(versions) == 1
    }
    return [
        versions_by_name.get(_normalize(program.get("name", "")), "")
        for program in programs
    ]


def get_latest_versions(programs: List[Dict[str, Any]]) -> List[str]:
    """Return winget's latest available version for each exact name match."""
    try:
        result = subprocess.run(
            [
                "winget",
                "list",
                "--disable-interactivity",
            ],
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
    return parse_winget_list(result.stdout, programs)
