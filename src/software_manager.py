"""Application controller connecting the inventory, view, and services."""

import ctypes
import json
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from .program_icons import get_program_icon_ppm
from .program_repository import ProgramRepository
from .program_uninstaller import ProgramUninstaller
from .software_manager_view import SoftwareManagerView

JSON_FILE = "installierte_programme.json"


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
        self.refresh()

    def refresh(self):
        """Reload installed programs and icons in a background thread."""
        if self.busy:
            return

        self.busy = True
        self.view.set_status("Suche installierte Programme ...")
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
            self.view.set_status("Fehler")
            messagebox.showerror("Fehler", error)
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
        self.view.set_programs(programs, program_images)
        self.view.set_status("Programmliste aktualisiert")

    def export_json(self):
        """Save the full program inventory as a JSON file."""
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile=JSON_FILE,
            filetypes=[("JSON Dateien", "*.json")]
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
            self.view.set_status("JSON exportiert")
            messagebox.showinfo(
                "Export", "Programmliste wurde gespeichert."
            )
        except (OSError, TypeError, ValueError) as exc:
            messagebox.showerror("Exportfehler", str(exc))

    def import_json(self):
        """Load and validate a program inventory from a JSON file."""
        path = filedialog.askopenfilename(
            filetypes=[("JSON Dateien", "*.json")]
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as json_file:
                data = json.load(json_file)
            if not isinstance(data, dict):
                raise ValueError("Ungültiges JSON-Format")

            imported = data.get("programs", [])
            if not isinstance(imported, list):
                raise ValueError("Ungültiges JSON-Format")
            if any(
                not isinstance(program, dict)
                or not isinstance(program.get("name"), str)
                for program in imported
            ):
                raise ValueError("Ungültige Programmeinträge")

            self.view.set_programs(imported, self.view.program_icons)
            self.view.set_status("JSON importiert")
        except (OSError, TypeError, UnicodeError, ValueError) as exc:
            messagebox.showerror("Importfehler", str(exc))

    def uninstall_selected(self):
        """Confirm the selection and process each uninstall request."""
        programs = self.view.selected_programs()
        if not programs:
            messagebox.showwarning(
                "Hinweis", "Bitte Programme auswählen."
            )
            return

        names = "\n".join(program["name"] for program in programs)
        confirm = messagebox.askyesno(
            "Deinstallation bestätigen",
            "Folgende Programme werden zur Deinstallation "
            "vorgemerkt:\n\n"
            + names
            + "\n\nFortfahren?"
        )
        if not confirm:
            return

        self._uninstall_programs(programs)
        self.refresh()

    def _create_uninstall_progress(self, total):
        """Create a window showing uninstall successes and remaining items."""
        window = tk.Toplevel(self.root)
        window.title("Deinstallationsfortschritt")
        window.transient(self.root)
        window.resizable(False, False)

        frame = ttk.Frame(window, padding=18)
        frame.pack(fill="both", expand=True)
        status = ttk.Label(
            frame, text="", justify="left", wraplength=420
        )
        status.pack(fill="x", pady=(0, 12))

        progress = ttk.Progressbar(
            frame, mode="determinate", maximum=total, length=420
        )
        progress.pack(fill="x")
        close_button = ttk.Button(
            frame, text="Schließen", command=window.destroy
        )
        close_button.state(["disabled"])
        close_button.pack(anchor="e", pady=(14, 0))
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

    @staticmethod
    def _update_uninstall_progress(widgets, counts, current_program=""):
        """Refresh uninstall counts and the progress bar."""
        window, progress, status = widgets
        successful, processed, total = counts
        status_text = (
            f"{successful} von {total} erfolgreich deinstalliert; "
            f"{total - successful} verbleibend "
            f"({processed} von {total} bearbeitet)"
        )
        if current_program:
            status_text += f"\nAktuell: {current_program}"
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

        close_button.state(["!disabled"])
        self.view.set_status(
            f"Deinstallation beendet: {successful} von "
            f"{total} erfolgreich"
        )

    def uninstall_one(self, program):
        """Confirm and safely run one program's uninstall command."""
        name = program["name"]
        confirm = messagebox.askyesno(
            "Einzelbestätigung",
            f"Möchtest du {name} wirklich deinstallieren?"
        )
        if not confirm:
            return False

        command = (
            program.get("uninstall_string", "")
            or program.get("quiet_uninstall_string", "")
        )
        if not command:
            messagebox.showwarning(
                "Nicht möglich",
                f"Kein Deinstallationsbefehl für {name}."
            )
            return False

        try:
            result = self.uninstaller.run(command)
        except (OSError, ValueError, ctypes.ArgumentError) as exc:
            messagebox.showerror(
                "Deinstallationsfehler",
                f"{name}:\n{exc}"
            )
            return False

        if result.returncode == 0:
            messagebox.showinfo(
                "Deinstallation",
                f"Deinstallationsprozess von {name} beendet."
            )
            return True
        messagebox.showwarning(
            "Deinstallation",
            f"Prozess beendet mit Exit-Code {result.returncode}."
        )
        return False


def main():
    """Launch the Windows software manager."""
    main_window = tk.Tk()
    SoftwareManager(main_window)
    main_window.mainloop()
