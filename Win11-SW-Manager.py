
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import winreg
import json
import os
import subprocess
import ctypes
from ctypes import wintypes
from datetime import datetime
import threading

APP_TITLE = "Windows 11 Software Manager"
JSON_FILE = "installierte_programme.json"

REGISTRY_PATH = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
)

REGISTRY_ROOTS = [
    (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY),
    (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY),
    (winreg.HKEY_CURRENT_USER, 0),
]


def read_value(key, name):
    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return ""


def get_installed_programs():
    programs = []
    seen = set()

    for root, view in REGISTRY_ROOTS:
        try:
            registry = winreg.OpenKey(
                root, REGISTRY_PATH, 0,
                winreg.KEY_READ | view
            )
        except OSError:
            continue

        with registry:
            count = winreg.QueryInfoKey(registry)[0]

            for i in range(count):
                try:
                    subname = winreg.EnumKey(registry, i)

                    with winreg.OpenKey(registry, subname) as key:
                        name = read_value(key, "DisplayName")

                        if not name:
                            continue

                        uninstall = read_value(
                            key, "UninstallString"
                        )

                        quiet_uninstall = read_value(
                            key, "QuietUninstallString"
                        )

                        item = {
                            "name": name,
                            "version": read_value(
                                key, "DisplayVersion"
                            ),
                            "publisher": read_value(
                                key, "Publisher"
                            ),
                            "install_location": read_value(
                                key, "InstallLocation"
                            ),
                            "uninstall_string": uninstall,
                            "quiet_uninstall_string": quiet_uninstall,
                            "registry_key": subname
                        }

                        uid = (
                            name.lower(),
                            item["version"],
                            uninstall
                        )

                        if uid not in seen:
                            seen.add(uid)
                            programs.append(item)

                except OSError:
                    continue

    return sorted(
        programs,
        key=lambda x: x["name"].lower()
    )


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def split_command(command):
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)

    shell32.CommandLineToArgvW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.c_int)
    ]
    shell32.CommandLineToArgvW.restype = (
        ctypes.POINTER(wintypes.LPWSTR)
    )

    argc = ctypes.c_int()
    argv = shell32.CommandLineToArgvW(
        command, ctypes.byref(argc)
    )

    if not argv:
        raise ctypes.WinError(ctypes.get_last_error())

    try:
        return [argv[i] for i in range(argc.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(argv)


class SoftwareManager:

    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1100x700")
        self.root.minsize(850, 550)

        self.programs = []
        self.filtered = []
        self.busy = False

        self.setup_style()
        self.create_interface()
        self.refresh()

    def setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Treeview",
            background="#202936",
            foreground="white",
            fieldbackground="#202936",
            rowheight=30
        )

        style.configure(
            "Treeview.Heading",
            background="#304258",
            foreground="white",
            padding=8
        )

        style.map(
            "Treeview",
            background=[("selected", "#1769aa")]
        )

    def create_interface(self):
        self.root.configure(bg="#17212f")

        header = tk.Frame(
            self.root, bg="#17212f", padx=20, pady=15
        )
        header.pack(fill="x")

        tk.Label(
            header,
            text="Windows 11 Software Manager",
            font=("Segoe UI", 20, "bold"),
            fg="white",
            bg="#17212f"
        ).pack(side="left")

        self.count_label = tk.Label(
            header,
            text="0 Programme",
            font=("Segoe UI", 10),
            fg="#a9c3dd",
            bg="#17212f"
        )
        self.count_label.pack(side="right")

        toolbar = tk.Frame(
            self.root, bg="#26374b", padx=15, pady=12
        )
        toolbar.pack(fill="x", padx=15)

        self.search = tk.StringVar()

        search_entry = tk.Entry(
            toolbar,
            textvariable=self.search,
            font=("Segoe UI", 11),
            width=28
        )
        search_entry.pack(side="left", padx=5)
        search_entry.insert(0, "")

        self.search.trace_add(
            "write", lambda *args: self.filter_programs()
        )

        self.make_button(
            toolbar, "Aktualisieren",
            self.refresh, "#1769aa"
        )

        self.make_button(
            toolbar, "Alle auswählen",
            self.select_all, "#40566f"
        )

        self.make_button(
            toolbar, "Auswahl aufheben",
            self.clear_selection, "#40566f"
        )

        self.make_button(
            toolbar, "JSON exportieren",
            self.export_json, "#287b59"
        )

        self.make_button(
            toolbar, "JSON importieren",
            self.import_json, "#6c579d"
        )

        content = tk.Frame(
            self.root, bg="#17212f", padx=15, pady=15
        )
        content.pack(fill="both", expand=True)

        columns = (
            "name", "version", "publisher"
        )

        self.tree = ttk.Treeview(
            content,
            columns=columns,
            show="tree headings",
            selectmode="extended"
        )

        self.tree.heading("#0", text="Auswahl")
        self.tree.heading("name", text="Programm")
        self.tree.heading("version", text="Version")
        self.tree.heading("publisher", text="Hersteller")

        self.tree.column("#0", width=65, anchor="center")
        self.tree.column("name", width=350)
        self.tree.column("version", width=120)
        self.tree.column("publisher", width=280)

        scrollbar = ttk.Scrollbar(
            content,
            orient="vertical",
            command=self.tree.yview
        )

        self.tree.configure(
            yscrollcommand=scrollbar.set
        )

        self.tree.pack(
            side="left", fill="both", expand=True
        )
        scrollbar.pack(side="right", fill="y")

        footer = tk.Frame(
            self.root, bg="#17212f", padx=20, pady=15
        )
        footer.pack(fill="x")

        self.status = tk.Label(
            footer,
            text="Bereit",
            fg="#a9c3dd",
            bg="#17212f"
        )
        self.status.pack(side="left")

        self.make_button(
            footer,
            "Ausgewählte Programme deinstallieren",
            self.uninstall_selected,
            "#b73535"
        )

    def make_button(self, parent, text, command, color):
        tk.Button(
            parent,
            text=text,
            command=command,
            bg=color,
            fg="white",
            activebackground=color,
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 9)
        ).pack(side="left", padx=4)

    def refresh(self):
        if self.busy:
            return

        self.busy = True
        self.status.config(text="Suche installierte Programme ...")

        def worker():
            try:
                result = get_installed_programs()
                error = None
            except Exception as exc:
                result = []
                error = str(exc)

            def finish():
                self.busy = False

                if error:
                    self.status.config(text="Fehler")
                    messagebox.showerror("Fehler", error)
                    return

                self.programs = result
                self.filter_programs()
                self.status.config(
                    text="Programmliste aktualisiert"
                )

            self.root.after(0, finish)

        threading.Thread(
            target=worker, daemon=True
        ).start()

    def filter_programs(self):
        term = self.search.get().lower()

        self.filtered = [
            p for p in self.programs
            if term in p["name"].lower()
            or term in p["publisher"].lower()
        ]

        self.tree.delete(*self.tree.get_children())

        for index, program in enumerate(self.filtered):
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                text="☐",
                values=(
                    program["name"],
                    program["version"],
                    program["publisher"]
                )
            )

        self.count_label.config(
            text=f"{len(self.filtered)} von "
                 f"{len(self.programs)} Programmen"
        )

    def select_all(self):
        self.tree.selection_set(
            self.tree.get_children()
        )

    def clear_selection(self):
        self.tree.selection_remove(
            self.tree.selection()
        )

    def export_json(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile=JSON_FILE,
            filetypes=[("JSON Dateien", "*.json")]
        )

        if not path:
            return

        data = {
            "export_date": datetime.now().isoformat(),
            "program_count": len(self.programs),
            "programs": self.programs
        }

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    data, f, indent=4, ensure_ascii=False
                )

            self.status.config(text="JSON exportiert")
            messagebox.showinfo(
                "Export", "Programmliste wurde gespeichert."
            )

        except Exception as exc:
            messagebox.showerror("Exportfehler", str(exc))

    def import_json(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON Dateien", "*.json")]
        )

        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            imported = data.get("programs", [])

            if not isinstance(imported, list):
                raise ValueError("Ungültiges JSON-Format")

            if any(
                not isinstance(p, dict)
                or not isinstance(p.get("name"), str)
                for p in imported
            ):
                raise ValueError("Ungültige Programmeinträge")

            self.programs = imported
            self.filter_programs()

            self.status.config(text="JSON importiert")

        except Exception as exc:
            messagebox.showerror("Importfehler", str(exc))

    def uninstall_selected(self):
        selected = self.tree.selection()

        if not selected:
            messagebox.showwarning(
                "Hinweis", "Bitte Programme auswählen."
            )
            return

        programs = [
            self.filtered[int(i)] for i in selected
        ]

        names = "\n".join(p["name"] for p in programs)

        confirm = messagebox.askyesno(
            "Deinstallation bestätigen",
            "Folgende Programme werden zur Deinstallation "
            "vorgemerkt:\n\n"
            + names
            + "\n\nFortfahren?"
        )

        if not confirm:
            return

        for program in programs:
            self.uninstall_one(program)

        self.refresh()

    def uninstall_one(self, program):
        name = program["name"]

        confirm = messagebox.askyesno(
            "Einzelbestätigung",
            f"Möchtest du {name} wirklich deinstallieren?"
        )

        if not confirm:
            return

        command = (
            program.get("uninstall_string", "")
            or program.get("quiet_uninstall_string", "")
        )

        if not command:
            messagebox.showwarning(
                "Nicht möglich",
                f"Kein Deinstallationsbefehl für {name}."
            )
            return

        # Vor Ausführung muss der Befehl geprüft werden.
        try:
            args = split_command(command)

            if not args:
                raise ValueError("Leerer Befehl")

            executable = os.path.basename(args[0]).lower()

            if executable in ("msiexec", "msiexec.exe"):
                if any(
                    a.lower() == "/qn" or
                    a.lower() == "/quiet"
                    for a in args
                ):
                    raise ValueError(
                        "Unbeaufsichtigte MSI-Deinstallation "
                        "wird aus Sicherheitsgründen nicht "
                        "automatisch ausgeführt."
                    )

                for i, arg in enumerate(args):
                    if arg.lower() == "/i":
                        args[i] = "/x"
                    elif arg.lower().startswith("/i{"):
                        args[i] = "/x" + arg[2:]

            # Keine Ausführung von Skriptdateien oder Shell-Befehlen.
            if executable.endswith((".bat", ".cmd", ".ps1", ".vbs")):
                raise ValueError(
                    "Skriptbasierte Deinstallation benötigt "
                    "eine manuelle Prüfung."
                )

            result = subprocess.run(
                args,
                shell=False,
                check=False
            )

            if result.returncode == 0:
                messagebox.showinfo(
                    "Deinstallation",
                    f"Deinstallationsprozess von {name} beendet."
                )
            else:
                messagebox.showwarning(
                    "Deinstallation",
                    f"Prozess beendet mit Exit-Code "
                    f"{result.returncode}."
                )

        except Exception as exc:
            messagebox.showerror(
                "Deinstallationsfehler",
                f"{name}:\n{exc}"
            )


if __name__ == "__main__":
    root = tk.Tk()
    app = SoftwareManager(root)
    root.mainloop()
