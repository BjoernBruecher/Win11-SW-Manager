"""Application controller connecting the inventory, view, and services."""

import ctypes
import json
import logging
import threading
import tkinter as tk
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from .localization import detect_system_language, translate
from .program_downloads import UpdateDownloadError, download_installer
from .program_icons import get_program_icon_ppm
from .program_repository import ProgramRepository
from .program_uninstaller import ProgramUninstaller
from .program_versions import (
    ProgramVersionLookupError,
    get_download_url,
    get_latest_version_details,
    has_safe_download_link
)
from .rounded_widgets import (
    RoundedButton,
    RoundedButtonStyle,
    RoundedPanel,
    RoundedPanelStyle
)
from .single_instance import (
    acquire_application_mutex,
    release_application_mutex
)
from .software_manager_view import SoftwareManagerView


WINGET_TROUBLESHOOTING_URL = (
    "https://github.com/BjoernBruecher/Win11-SW-Manager/"
    "blob/main/README.md#troubleshooting-winget-source-issues"
)


class LatestVersionLookup(NamedTuple):
    """Version metadata and installer links produced by a lookup."""

    versions: Optional[List[str]]
    package_ids: Optional[List[str]]
    updates: Optional[List[bool]]
    download_urls: Optional[List[str]]
    unavailable_links: int


class SoftwareManager:
    """Coordinate application workflows and background registry refreshes."""

    def __init__(self, root: tk.Tk) -> None:
        """Create services and view, then start the initial inventory scan."""
        self.root: tk.Tk = root
        self.repository: ProgramRepository = ProgramRepository()
        self.uninstaller: ProgramUninstaller = ProgramUninstaller()
        self.busy: bool = False
        self.downloads_in_progress: bool = False
        self.latest_version_lookup_generation: int = 0
        self.view: SoftwareManagerView = SoftwareManagerView(
            root,
            on_refresh=self.refresh,
            on_export=self.export_json,
            on_import=self.import_json,
            on_uninstall=self.uninstall_selected,
            on_download_update=self.download_selected_updates
        )
        self._initial_refresh_id: Optional[str] = self.root.after(
            100, self._start_initial_refresh
        )

    def _start_initial_refresh(self) -> None:
        """Start the initial scan after the main window has rendered."""
        self._initial_refresh_id = None
        self.refresh()

    def _text(self, key: str, **values: object) -> str:
        """Return translated text for the current interface language."""
        return translate(self.view.language.get(), key, **values)

    def refresh(self) -> None:
        """Reload installed programs and icons in a background thread."""
        if self._initial_refresh_id is not None:
            self.root.after_cancel(self._initial_refresh_id)
            self._initial_refresh_id = None
        if self.busy:
            return

        self.latest_version_lookup_generation += 1
        self.busy = True
        self.view.set_status("status_searching")
        self.view.show_list_progress()
        threading.Thread(
            target=self._refresh_worker, daemon=True
        ).start()

    def _refresh_worker(self) -> None:
        """Read registry data and dispatch the result to the UI thread."""
        try:
            programs = self.repository.load_programs()
            icon_data = self._load_program_icons(programs)
        except (OSError, ValueError, ctypes.ArgumentError) as exc:
            programs = []
            icon_data = {}
            error = str(exc)
        else:
            error = None

        self.root.after(
            0, self._finish_refresh, programs, icon_data, error
        )

    @staticmethod
    def _load_program_icons(
        programs: List[Dict[str, Any]]
    ) -> Dict[str, Optional[bytes]]:
        """Load each distinct registry-provided icon."""
        icon_data = {}
        for program in programs:
            icon_path = str(program.get("display_icon", "")).strip()
            if not icon_path or icon_path in icon_data:
                continue
            try:
                icon_data[icon_path] = get_program_icon_ppm(icon_path)
            except (OSError, ValueError, ctypes.ArgumentError):
                icon_data[icon_path] = None
        return icon_data

    def _finish_refresh(
        self,
        programs: List[Dict[str, Any]],
        icon_data: Dict[str, Optional[bytes]],
        error: Optional[str]
    ) -> None:
        """Update widgets after the background program scan finishes."""
        self.busy = False
        if error:
            self.view.hide_list_progress()
            self.view.set_status("status_error")
            messagebox.showerror(self._text("status_error"), error)
            return

        program_images = {}
        for icon_path, image_data in icon_data.items():
            if not image_data:
                continue
            try:
                program_images[icon_path] = tk.PhotoImage(
                    master=self.root,
                    data=image_data
                )
            except tk.TclError:
                continue
        self.view.show_list_progress(
            mode="determinate", maximum=len(programs)
        )
        try:
            self.view.set_programs(programs, program_images)
        finally:
            self.view.hide_list_progress()
        self.view.set_status("status_refreshed")
        self._start_latest_version_lookup(programs)

    def _start_latest_version_lookup(
        self, programs: List[Dict[str, Any]]
    ) -> None:
        """Check package sources without blocking the interface."""
        if not programs:
            return
        self.latest_version_lookup_generation += 1
        generation = self.latest_version_lookup_generation
        self.view.set_latest_versions([""] * len(programs))
        self.view.set_status("status_checking_versions")
        threading.Thread(
            target=self._latest_version_worker,
            args=(programs, generation),
            daemon=True
        ).start()

    def _latest_version_worker(
        self, programs: List[Dict[str, Any]], generation: int
    ) -> None:
        """Retrieve versions and update download links in the background."""
        try:
            versions, package_ids, updates = get_latest_version_details(
                programs
            )
        except ProgramVersionLookupError:
            lookup = LatestVersionLookup(
                None, None, None, None, 0
            )
        except Exception:
            logging.exception("Could not check latest program versions.")
            lookup = LatestVersionLookup(
                None, None, None, None, 0
            )
        else:
            download_urls = [""] * len(programs)
            unavailable_links = 0
            lookup = LatestVersionLookup(
                versions,
                package_ids,
                updates,
                list(download_urls),
                0
            )
            self.root.after(
                0,
                self._finish_latest_version_lookup,
                programs,
                generation,
                lookup,
                False
            )
            for index, (package_id, version, update_available) in enumerate(
                zip(package_ids, versions, updates)
            ):
                if not update_available:
                    continue
                if not package_id:
                    unavailable_links += 1
                    continue
                try:
                    download_urls[index] = get_download_url(
                        package_id, version
                    )
                except ProgramVersionLookupError as exc:
                    logging.warning(
                        "Could not get the download link for %s %s: %s",
                        package_id,
                        version,
                        exc
                    )
                    unavailable_links += 1
                except Exception:
                    logging.exception(
                        "Unexpected error getting the download link for %s %s.",
                        package_id,
                        version
                    )
                    unavailable_links += 1
            lookup = LatestVersionLookup(
                versions,
                package_ids,
                updates,
                download_urls,
                unavailable_links
            )
        self.root.after(
            0,
            self._finish_latest_version_lookup,
            programs,
            generation,
            lookup
        )

    def _finish_latest_version_lookup(
        self,
        programs: List[Dict[str, Any]],
        generation: int,
        lookup: LatestVersionLookup,
        links_complete: bool = True
    ) -> None:
        """Apply version data only if it still belongs to the shown list."""
        if (
            generation != self.latest_version_lookup_generation
            or self.view.programs is not programs
        ):
            return
        if lookup.versions is None:
            self.view.set_status_link(
                "status_versions_unavailable",
                self.open_winget_troubleshooting
            )
            return
        self.view.set_latest_versions(
            lookup.versions,
            package_ids=lookup.package_ids,
            updates=lookup.updates,
            download_urls=lookup.download_urls
        )
        if not links_complete:
            return
        if lookup.unavailable_links:
            self.view.set_status(
                "status_download_links_unavailable",
                count=lookup.unavailable_links
            )
        else:
            self.view.set_status("status_versions_checked")

    def open_winget_troubleshooting(self) -> None:
        """Open the README section for winget source troubleshooting."""
        try:
            opened = webbrowser.open(WINGET_TROUBLESHOOTING_URL)
        except (OSError, webbrowser.Error):
            opened = False
        if not opened:
            messagebox.showerror(
                self._text("status_error"),
                self._text("troubleshooting_browser_error")
            )

    def download_selected_updates(self) -> None:
        """Download selected update installers, with no more than two active."""
        if self.downloads_in_progress:
            return

        selected_updates = [
            program for program in self.view.selected_programs()
            if program.get("update_available")
        ]
        if not selected_updates:
            messagebox.showwarning(
                self._text("download_selection_title"),
                self._text("download_selection_required")
            )
            return

        programs = [
            program for program in selected_updates
            if has_safe_download_link(program)
        ]
        failures = [
            (
                str(program.get("name", "")),
                self._text("download_link_unavailable")
            )
            for program in selected_updates
            if not has_safe_download_link(program)
        ]
        if not programs:
            messagebox.showerror(
                self._text("download_error_title"),
                self._text("download_link_unavailable")
            )
            return

        self.downloads_in_progress = True
        self.view.set_downloads_in_progress(True)
        self.view.set_status(
            "status_downloading_updates",
            completed=0,
            total=len(programs)
        )
        try:
            threading.Thread(
                target=self._download_updates_worker,
                args=(programs, failures),
                daemon=True
            ).start()
        except (OSError, RuntimeError) as exc:
            self.downloads_in_progress = False
            self.view.set_downloads_in_progress(False)
            self.view.set_status(
                "status_downloads_failed",
                downloaded=0,
                failed=len(programs) + len(failures)
            )
            messagebox.showerror(
                self._text("download_error_title"), str(exc)
            )

    def _download_updates_worker(
        self,
        programs: List[Dict[str, Any]],
        failures: List[Tuple[str, str]]
    ) -> None:
        """Download the batch with at most two concurrent installer requests."""
        downloaded = 0
        completed = 0
        total = len(programs)
        try:
            download_directory = Path.home() / "Downloads"
        except (OSError, RuntimeError) as exc:
            logging.exception("Could not locate the Downloads folder.")
            failures.extend(
                (str(program.get("name", "")), str(exc))
                for program in programs
            )
            self.root.after(
                0, self._finish_download_batch, downloaded, failures
            )
            return

        try:
            executor = ThreadPoolExecutor(
                max_workers=2, thread_name_prefix="update-download"
            )
        except (OSError, RuntimeError) as exc:
            logging.exception("Could not start update download workers.")
            failures.extend(
                (str(program.get("name", "")), str(exc))
                for program in programs
            )
            self.root.after(
                0, self._finish_download_batch, downloaded, failures
            )
            return

        with executor:
            futures = {}
            for program in programs:
                try:
                    future = executor.submit(
                        download_installer, program, download_directory
                    )
                except RuntimeError as exc:
                    name = str(program.get("name", ""))
                    logging.exception(
                        "Could not start the download for %s.", name
                    )
                    failures.append((name, str(exc)))
                    completed += 1
                    self.root.after(
                        0, self._update_download_progress, completed, total
                    )
                    continue
                futures[future] = program

            for future in as_completed(futures):
                program = futures[future]
                name = str(program.get("name", ""))
                try:
                    path = future.result()
                except UpdateDownloadError as exc:
                    logging.warning(
                        "Could not download the update for %s: %s", name, exc
                    )
                    failures.append((name, str(exc)))
                except Exception as exc:
                    logging.exception(
                        "Unexpected error downloading the update for %s.",
                        name
                    )
                    failures.append((name, str(exc)))
                else:
                    downloaded += 1
                    logging.info("Downloaded update for %s to %s", name, path)
                completed += 1
                self.root.after(
                    0, self._update_download_progress, completed, total
                )
        self.root.after(
            0, self._finish_download_batch, downloaded, failures
        )

    def _update_download_progress(
        self, completed: int, total: int
    ) -> None:
        """Update the footer as each selected installer finishes."""
        self.view.set_status(
            "status_downloading_updates",
            completed=completed,
            total=total
        )

    def _finish_download_batch(
        self,
        downloaded: int,
        failures: List[Tuple[str, str]]
    ) -> None:
        """Restore the download action and report the batch result."""
        self.downloads_in_progress = False
        self.view.set_downloads_in_progress(False)
        if failures:
            failed = len(failures)
            self.view.set_status(
                "status_downloads_partial" if downloaded else
                "status_downloads_failed",
                downloaded=downloaded,
                failed=failed
            )
            details = "\n".join(
                f"{name}: {reason}" for name, reason in failures
            )
            show_message = (
                messagebox.showwarning if downloaded
                else messagebox.showerror
            )
            show_message(
                self._text("download_error_title"),
                self._text("download_batch_errors", errors=details)
            )
            return
        self.view.set_status(
            "status_downloads_complete", count=downloaded
        )

    def export_json(self) -> None:
        """Save the full program inventory as a JSON file."""
        path = filedialog.asksaveasfilename(
            title=self._text("export_title"),
            defaultextension=".json",
            initialfile=self._text("json_filename"),
            filetypes=[(self._text("json_files"), "*.json")]
        )
        if not path:
            return

        data = {
            "export_date": datetime.now().isoformat(),
            "program_count": len(self.view.programs),
            "programs": self.view.programs
        }
        try:
            with open(path, "w", encoding="utf-8") as json_file:
                json.dump(data, json_file, indent=4, ensure_ascii=False)
            self.view.set_status("status_exported")
            messagebox.showinfo(
                self._text("export_title"),
                self._text("export_success")
            )
        except (OSError, TypeError, ValueError) as exc:
            messagebox.showerror(
                self._text("export_error_title"), str(exc)
            )

    def import_json(self) -> None:
        """Load and validate a program inventory from a JSON file."""
        path = filedialog.askopenfilename(
            title=self._text("import_json"),
            initialfile=self._text("json_filename"),
            filetypes=[(self._text("json_files"), "*.json")]
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as json_file:
                data = json.load(json_file)
            if not isinstance(data, dict):
                raise ValueError(self._text("invalid_json"))

            imported = data.get("programs", [])
            if not isinstance(imported, list):
                raise ValueError(self._text("invalid_json"))
            if any(
                not isinstance(program, dict)
                or not isinstance(program.get("name"), str)
                for program in imported
            ):
                raise ValueError(self._text("invalid_programs"))
            self.view.show_list_progress(
                mode="determinate", maximum=len(imported)
            )
            try:
                self.view.set_programs(imported, self.view.program_icons)
            finally:
                self.view.hide_list_progress()
            self.view.set_status("status_imported")
            self._start_latest_version_lookup(imported)
        except (OSError, TypeError, UnicodeError, ValueError) as exc:
            messagebox.showerror(
                self._text("import_error_title"), str(exc)
            )

    def uninstall_selected(self) -> None:
        """Confirm the selection and process each uninstall request."""
        programs = self.view.selected_programs()
        if not programs:
            messagebox.showwarning(
                self._text("selection_warning_title"),
                self._text("selection_warning")
            )
            return

        names = "\n".join(program["name"] for program in programs)
        confirm = messagebox.askyesno(
            self._text("confirm_title"),
            self._text("confirm_message", names=names)
        )
        if not confirm:
            return

        self._uninstall_programs(programs)
        self.refresh()

    def _create_uninstall_progress(
        self, total: int
    ) -> Tuple[
        tk.Toplevel,
        ttk.Progressbar,
        ttk.Label,
        RoundedButton
    ]:
        """Create a window showing uninstall progress for a batch."""
        window = tk.Toplevel(self.root)
        window.title(self._text("progress_title"))
        window.transient(self.root)
        window.resizable(False, False)
        window.configure(background="#0b1120")

        panel = RoundedPanel(
            window,
            RoundedPanelStyle(
                fill="#121d31",
                background="#0b1120",
                outline="#263752",
                radius=13,
                inset=14
            )
        )
        panel.pack(fill="both", expand=True, padx=12, pady=12)
        frame = panel.content
        status = ttk.Label(
            frame,
            text="",
            justify="left",
            wraplength=460,
            style="Status.TLabel"
        )
        status.pack(fill="x", pady=(0, 12))

        progress = ttk.Progressbar(
            frame,
            mode="determinate",
            maximum=total,
            length=440,
            style="Horizontal.TProgressbar"
        )
        if total > 1:
            progress.pack(fill="x")
        close_button = RoundedButton(
            frame,
            self._text("progress_close"),
            command=window.destroy,
            style=RoundedButtonStyle(
                background="#3478e5",
                foreground="#ffffff",
                hover_background="#2867cc",
                border="#4386f0",
                canvas_background="#121d31",
                font=("Segoe UI", 9, "bold"),
                padx=14,
                pady=8,
                radius=12
            )
        )
        close_button.pack(side="right", pady=(14, 0))
        close_button.set_enabled(False)
        window.protocol("WM_DELETE_WINDOW", close_button.invoke)

        window.update_idletasks()
        x = self.root.winfo_rootx() + (
            self.root.winfo_width() - window.winfo_width()
        ) // 2
        y = self.root.winfo_rooty() + (
            self.root.winfo_height() - window.winfo_height()
        ) // 2
        window.geometry(f"+{x}+{y}")
        window.lift()
        return window, progress, status, close_button

    def _update_uninstall_progress(
        self,
        widgets: Tuple[tk.Toplevel, ttk.Progressbar, ttk.Label],
        counts: Tuple[int, int, int],
        current_program: str = ""
    ) -> None:
        """Refresh uninstall counts and the progress bar."""
        window, progress, status = widgets
        successful, processed, total = counts
        status_text = self._text(
            "progress_status",
            successful=successful,
            total=total,
            remaining=total - successful,
            processed=processed
        )
        if current_program:
            status_text += self._text(
                "progress_current", program=current_program
            )
        progress.config(value=processed)
        status.config(text=status_text)
        window.update_idletasks()

    def _uninstall_programs(
        self, programs: List[Dict[str, Any]]
    ) -> None:
        """Uninstall selected programs and update their progress."""
        total = len(programs)
        window, progress, status, close_button = (
            self._create_uninstall_progress(total)
        )
        progress_widgets = window, progress, status
        successful = 0
        for processed, program in enumerate(programs, start=1):
            self._update_uninstall_progress(
                progress_widgets,
                (successful, processed - 1, total),
                program["name"]
            )
            if self.uninstall_one(program):
                successful += 1
            self._update_uninstall_progress(
                progress_widgets, (successful, processed, total)
            )

        close_button.set_enabled(True)
        self.view.set_status(
            "status_uninstall_finished",
            successful=successful,
            total=total
        )

    def uninstall_one(self, program: Dict[str, Any]) -> bool:
        """Confirm and safely run one program's uninstall command."""
        name = program["name"]
        confirm = messagebox.askyesno(
            self._text("single_confirm_title"),
            self._text("single_confirm_message", name=name)
        )
        if not confirm:
            return False

        command = (
            program.get("uninstall_string", "")
            or program.get("quiet_uninstall_string", "")
        )
        if not command:
            messagebox.showwarning(
                self._text("no_uninstall_title"),
                self._text("no_uninstall_command", name=name)
            )
            return False

        try:
            result = self.uninstaller.run(
                command, language=self.view.language.get()
            )
        except (OSError, ValueError, ctypes.ArgumentError) as exc:
            messagebox.showerror(
                self._text("uninstall_error_title"),
                f"{name}:\n{exc}"
            )
            return False

        if result.returncode == 0:
            messagebox.showinfo(
                self._text("uninstall_success_title"),
                self._text("uninstall_success", name=name)
            )
            return True
        messagebox.showwarning(
            self._text("uninstall_failed_title"),
            self._text(
                "uninstall_failed", code=result.returncode
            )
        )
        return False


def main() -> None:
    """Launch the Windows software manager."""
    instance_mutex = acquire_application_mutex()
    if instance_mutex is None:
        language = detect_system_language()
        messagebox.showinfo(
            translate(language, "already_running_title"),
            translate(language, "already_running_message")
        )
        return

    try:
        main_window = tk.Tk()
        SoftwareManager(main_window)
        main_window.mainloop()
    finally:
        release_application_mutex(instance_mutex)
