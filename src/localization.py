"""Load and format the application's translated interface text."""

import json
import locale
import subprocess
import sys
from pathlib import Path
from string import Formatter
from typing import Dict, Optional, Set


_LOCALE_FILES: Dict[str, str] = {
    "DE": "de.json",
    "US": "us.json",
    "FR": "fr.json",
    "IT": "it.json"
}
_LOCALE_LANGUAGE_CODES: Dict[str, str] = {
    "de": "DE",
    "german": "DE",
    "en": "US",
    "english": "US",
    "fr": "FR",
    "french": "FR",
    "it": "IT",
    "italian": "IT"
}
_LOCALE_DIRECTORY: Path = Path(__file__).resolve().parent / "locales"


def detect_system_language() -> str:
    """Choose the interface language from the first Windows user language."""
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    (
                        "$userLanguages = Get-WinUserLanguageList; "
                        "if ($userLanguages.Count -gt 0) { "
                        "$userLanguages[0].LanguageTag | "
                        "ConvertTo-Json -Compress }"
                    )
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            parsed_language_tag = (
                json.loads(result.stdout) if result.stdout.strip() else None
            )
            language_tag: Optional[str] = (
                parsed_language_tag
                if isinstance(parsed_language_tag, str)
                else None
            )
        except (
            OSError,
            subprocess.SubprocessError,
            json.JSONDecodeError,
            UnicodeError
        ):
            language_tag = None
    else:
        try:
            language_tag = locale.getlocale()[0]
        except (locale.Error, ValueError):
            language_tag = None

    if not language_tag:
        return "US"

    language_name = language_tag.replace("-", "_").split("_", 1)[0].lower()
    return _LOCALE_LANGUAGE_CODES.get(language_name, "US")


def _load_locale(filename: str) -> Dict[str, str]:
    """Load one UTF-8 locale file and validate its string entries."""
    path = _LOCALE_DIRECTORY / filename
    try:
        with path.open("r", encoding="utf-8") as locale_file:
            translations = json.load(locale_file)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid localization JSON in {path}: {error}"
        ) from error

    if not isinstance(translations, dict):
        raise ValueError(
            f"Localization file {path} must contain a JSON object."
        )

    invalid_entries = [
        key for key, value in translations.items()
        if not isinstance(key, str) or not isinstance(value, str)
    ]
    if invalid_entries:
        raise ValueError(
            f"Localization file {path} must map string keys to string "
            "values."
        )
    return translations


def _format_fields(value: str, language: str, key: str) -> Set[str]:
    """Return format placeholders, reporting malformed strings clearly."""
    try:
        return {
            field_name
            for _, field_name, _, _ in Formatter().parse(value)
            if field_name is not None
        }
    except ValueError as error:
        raise ValueError(
            f"Invalid format string for '{key}' in the {language} locale."
        ) from error


def _load_translations() -> Dict[str, Dict[str, str]]:
    """Load all locales and ensure keys and placeholders stay in sync."""
    translations = {
        language: _load_locale(filename)
        for language, filename in _LOCALE_FILES.items()
    }
    default_keys = set(translations["DE"])

    for language, locale_translations in translations.items():
        locale_keys = set(locale_translations)
        if locale_keys != default_keys:
            missing = sorted(default_keys - locale_keys)
            unexpected = sorted(locale_keys - default_keys)
            raise ValueError(
                f"The {language} locale has mismatched keys; "
                f"missing: {missing}; unexpected: {unexpected}."
            )

    for key in default_keys:
        german_fields = _format_fields(translations["DE"][key], "DE", key)
        for language, locale_translations in translations.items():
            if language == "DE":
                continue
            locale_fields = _format_fields(
                locale_translations[key], language, key
            )
            if german_fields != locale_fields:
                raise ValueError(
                    f"The '{key}' placeholder fields differ between DE "
                    f"and {language}."
                )
    return translations


TRANSLATIONS: Dict[str, Dict[str, str]] = _load_translations()


def translate(language: str, key: str, **values: object) -> str:
    """Return a translated string, interpolating any supplied values."""
    return TRANSLATIONS[language][key].format(**values)
