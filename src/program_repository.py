"""Read installed application metadata from the Windows registry."""

from datetime import datetime

import winreg


class ProgramRepository:
    """Provide installed application records from Windows uninstall keys."""

    REGISTRY_PATH = (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    )
    REGISTRY_ROOTS = (
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY),
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY),
        (winreg.HKEY_CURRENT_USER, 0),
    )

    @staticmethod
    def _read_value(key, name):
        """Read a registry value or return an empty string when absent."""
        try:
            return winreg.QueryValueEx(key, name)[0]
        except OSError:
            return ""

    def load_programs(self):
        """Collect, deduplicate, and alphabetize installed applications."""
        programs = []
        seen = set()

        for root, view in self.REGISTRY_ROOTS:
            try:
                registry = winreg.OpenKey(
                    root,
                    self.REGISTRY_PATH,
                    0,
                    winreg.KEY_READ | view
                )
            except OSError:
                continue

            with registry:
                count = winreg.QueryInfoKey(registry)[0]

                for index in range(count):
                    try:
                        subname = winreg.EnumKey(registry, index)
                        with winreg.OpenKey(registry, subname) as key:
                            name = self._read_value(key, "DisplayName")
                            if not name:
                                continue

                            uninstall = self._read_value(
                                key, "UninstallString"
                            )
                            item = {
                                "name": name,
                                "version": self._read_value(
                                    key, "DisplayVersion"
                                ),
                                "install_date": self._read_value(
                                    key, "InstallDate"
                                ),
                                "estimated_size": self._read_value(
                                    key, "EstimatedSize"
                                ),
                                "display_icon": self._read_value(
                                    key, "DisplayIcon"
                                ),
                                "publisher": self._read_value(
                                    key, "Publisher"
                                ),
                                "install_location": self._read_value(
                                    key, "InstallLocation"
                                ),
                                "uninstall_string": uninstall,
                                "quiet_uninstall_string": self._read_value(
                                    key, "QuietUninstallString"
                                ),
                                "registry_key": subname
                            }
                            unique_id = (
                                name.lower(),
                                item["version"],
                                uninstall
                            )
                            if unique_id not in seen:
                                seen.add(unique_id)
                                programs.append(item)
                    except OSError:
                        continue

        return sorted(programs, key=lambda program: program["name"].lower())


def format_install_date(value):
    """Format a registry install date for display."""
    if not value:
        return "—"

    try:
        return datetime.strptime(str(value), "%Y%m%d").strftime("%d.%m.%Y")
    except ValueError:
        return "—"


def format_size(value):
    """Format an estimated size in kilobytes for display."""
    try:
        size_kb = float(value)
    except (TypeError, ValueError):
        return "—"

    if size_kb < 0:
        return "—"
    if size_kb >= 1024:
        return f"{size_kb / 1024:.1f} MB"
    return f"{size_kb:g} KB"
