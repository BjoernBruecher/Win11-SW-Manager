"""Application controller connecting the inventory, view, and services."""

import ctypes
import json
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from .localization import detect_system_language, translate
from .program_icons import get_program_icon_ppm
from .program_repository import ProgramRepository
from .program_uninstaller import ProgramUninstaller
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


class SoftwareManager:
    """Coordinate application workflows and background registry refreshes."""

    def __init__(self, root):
        """Create services and view, then start the initial inventory scan."""
        self.root = root
        self.repository = ProgramRepository()
        self.uninstaller = ProgramUninstaller()
        self.busy = False
        self.view = SoftwareManagerView(
            root,
            on_refresh=self.refresh,
            on_export=self.export_json,
            on_import=self.import_json,
            on_uninstall=self.uninstall_selected
        )
        self._initial_refresh_id = self.root.after(
            100, self._start_initial_refresh
        )

    def _start_initial_refresh(self):
        """Start the initial scan after the main window has rendered."""
        self._initial_refresh_id = None
        self.refresh()

    def _text(self, key, **values):
        """Return translated text for the current interface language."""
        return translate(self.view.language.get(), key, **values)

    def refresh(self):
        """Reload installed programs and icons in a background thread."""
        if self._initial_refresh_id is not None:
            self.root.after_cancel(self._initial_refresh_id)
            self._initial_refresh_id = None
        if self.busy:
            return

        self.busy = True
        self.view.set_status("status_searching")
        self.view.show_list_progress()
        threading.Thread(
            target=self._refresh_worker, daemon=True
        ).start()

    def _refresh_worker(self):
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
    def _load_program_icons(programs):
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

    def _finish_refresh(self, programs, icon_data, error):
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

    def export_json(self):
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

    def import_json(self):
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
        except (OSError, TypeError, UnicodeError, ValueError) as exc:
            messagebox.showerror(
                self._text("import_error_title"), str(exc)
            )

    def uninstall_selected(self):
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

    def _create_uninstall_progress(self, total):
        """Create a window showing uninstall successes and remaining items."""
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
        self, widgets, counts, current_program=""
    ):
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

    def _uninstall_programs(self, programs):
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

    def uninstall_one(self, program):
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


def main():
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
