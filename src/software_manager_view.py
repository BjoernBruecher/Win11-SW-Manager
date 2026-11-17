"""Tkinter presentation layer for the Windows software manager."""

import math
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from .program_repository import format_install_date, format_size
from .rounded_widgets import (
    RoundedButton,
    RoundedButtonStyle,
    RoundedPanel,
    RoundedPanelStyle
)


class SoftwareManagerView:
    """Own the application widgets and the visible program-table state."""

    COLUMN_TITLES = {
        "name": "Programm",
        "version": "Version",
        "publisher": "Hersteller",
        "install_date": "Installiert am",
        "estimated_size": "Größe"
    }

    def __init__(
        self, root, on_refresh, on_export, on_import, on_uninstall
    ):
        """Create the window, controls, and empty program table."""
        self.root = root
        self.programs = []
        self.filtered = []
        self.program_icons = {}
        self.summary_values = {}
        self.search = tk.StringVar(master=self.root)

        self.root.title("Windows 11 Software Manager")
        self.root.geometry("1200x760")
        self.root.minsize(950, 600)
        self.setup_style()
        self.tree, self.status = self.create_interface(
            on_refresh, on_export, on_import, on_uninstall
        )
        self._update_sort_indicators("name", False)
        self.default_program_icon = self.create_default_program_icon()

    def setup_style(self):
        """Configure the application's ttk widget styles."""
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background="#0b1120")
        style.configure(
            "Toolbar.TFrame",
            background="#121d31"
        )
        style.configure(
            "Header.TLabel",
            background="#0b1120",
            foreground="#f1f5ff",
            font=("Segoe UI", 21, "bold")
        )
        style.configure(
            "Subheader.TLabel",
            background="#0b1120",
            foreground="#95a7c7",
            font=("Segoe UI", 10)
        )
        style.configure(
            "CardTitle.TLabel",
            background="#17243a",
            foreground="#95a7c7",
            font=("Segoe UI", 8, "bold")
        )
        style.configure(
            "CardValue.TLabel",
            background="#17243a",
            foreground="#f1f5ff",
            font=("Segoe UI", 17, "bold")
        )
        style.configure(
            "Toolbar.TLabel",
            background="#121d31",
            foreground="#c5d2e8",
            font=("Segoe UI", 10)
        )
        style.configure(
            "Status.TLabel",
            background="#121d31",
            foreground="#95a7c7",
            font=("Segoe UI", 10)
        )
        style.configure(
            "TEntry",
            fieldbackground="#0e192c",
            foreground="#e8eefb",
            insertcolor="#e8eefb",
            padding=(9, 7)
        )
        style.configure(
            "Treeview",
            background="#17243a",
            foreground="#e5ecfa",
            fieldbackground="#17243a",
            borderwidth=0,
            relief="flat",
            rowheight=38,
            font=("Segoe UI", 9)
        )
        style.layout(
            "Treeview",
            [
                ("Treeview.field", {
                    "sticky": "nswe",
                    "border": 0,
                    "children": [
                        ("Treeview.padding", {
                            "sticky": "nswe",
                            "children": [
                                ("Treeview.treearea", {"sticky": "nswe"})
                            ]
                        })
                    ]
                })
            ]
        )
        style.configure(
            "Treeview.Heading",
            background="#17243a",
            foreground="#c7d4eb",
            borderwidth=0,
            relief="flat",
            padding=(11, 12),
            font=("Segoe UI", 9, "bold")
        )
        style.map(
            "Treeview",
            background=[("selected", "#2c65b8")],
            foreground=[("selected", "white")]
        )
        style.map(
            "Treeview.Heading",
            background=[("active", "#202f49")],
            relief=[("pressed", "flat"), ("active", "flat")]
        )
        style.configure(
            "Vertical.TScrollbar",
            background="#24344e",
            troughcolor="#121d31",
            bordercolor="#121d31",
            arrowcolor="#9baccc"
        )

    def create_interface(
        self, on_refresh, on_export, on_import, on_uninstall
    ):
        """Build the branded header, action bar, table, and footer."""
        self.root.configure(bg="#0b1120")
        header = ttk.Frame(self.root, padding=(22, 18, 22, 13))
        header.pack(fill="x")
        RoundedButton(
            header,
            text="W",
            style=RoundedButtonStyle(
                background="#3277e8",
                foreground="#ffffff",
                hover_background="#3277e8",
                border="#4386f0",
                canvas_background="#0b1120",
                font=("Segoe UI", 14, "bold"),
                padx=12,
                pady=9,
                radius=11
            )
        ).pack(side="left", padx=(0, 12))

        title_block = ttk.Frame(header)
        title_block.pack(side="left", anchor="center")
        ttk.Label(
            title_block,
            text="Windows 11 Software Manager",
            style="Header.TLabel"
        ).pack(anchor="w")
        ttk.Label(
            title_block,
            text="Installierte Anwendungen verwalten",
            style="Subheader.TLabel"
        ).pack(anchor="w", pady=(3, 0))

        summary = ttk.Frame(self.root, padding=(18, 0, 18, 13))
        summary.pack(fill="x")
        for column in range(4):
            summary.columnconfigure(column, weight=1)
        self._create_summary_cards(summary)

        toolbar_panel = RoundedPanel(
            self.root,
            RoundedPanelStyle(
                fill="#121d31",
                background="#0b1120",
                outline="#263752",
                radius=16,
                inset=5
            )
        )
        toolbar_panel.pack(fill="x", padx=18)
        toolbar = toolbar_panel.content
        RoundedButton(
            toolbar,
            text="APPS",
            style=RoundedButtonStyle(
                background="#253858",
                foreground="#e5efff",
                hover_background="#253858",
                border="#344c70",
                canvas_background="#121d31",
                font=("Segoe UI", 9, "bold"),
                padx=12,
                pady=8,
                radius=10
            )
        ).pack(side="left", padx=(0, 8))
        self._create_toolbar_buttons(
            toolbar, on_refresh, on_export, on_import
        )
        self._create_search(toolbar)

        content = ttk.Frame(self.root, padding=(18, 11, 18, 0))
        content.pack(fill="both", expand=True)
        table_card = RoundedPanel(
            content,
            RoundedPanelStyle(
                fill="#121d31",
                background="#0b1120",
                outline="#263752",
                radius=15,
                inset=7
            )
        )
        table_card.pack(fill="both", expand=True)
        table_surface = RoundedPanel(
            table_card.content,
            RoundedPanelStyle(
                fill="#17243a",
                background="#121d31",
                outline="#344966",
                radius=17,
                inset=11
            )
        )
        table_surface.pack(fill="both", expand=True)
        tree = self._create_table(table_surface.content)
        status = self._create_footer(on_uninstall)
        return tree, status

    def _create_summary_cards(self, parent):
        """Create the four live inventory and selection counters."""
        cards = (
            ("installed", "INSTALLIERTE APPS"),
            ("visible", "IN DER LISTE"),
            ("selected", "ZUR DEINSTALLATION"),
            ("publishers", "HERSTELLER")
        )
        for column, (key, title) in enumerate(cards):
            card = RoundedPanel(
                parent,
                RoundedPanelStyle(
                    fill="#17243a",
                    background="#0b1120",
                    outline="#2a3b59",
                    radius=13,
                    inset=5
                )
            )
            right_padding = 8 if column < len(cards) - 1 else 0
            card.grid(
                row=0, column=column, sticky="ew",
                padx=(0, right_padding)
            )
            ttk.Label(
                card.content, text=title, style="CardTitle.TLabel"
            ).pack(anchor="w", padx=9, pady=(5, 0))
            value = ttk.Label(
                card.content, text="0", style="CardValue.TLabel"
            )
            value.pack(anchor="w", padx=9, pady=(3, 5))
            self.summary_values[key] = value

    def _create_toolbar_buttons(
        self, parent, on_refresh, on_export, on_import
    ):
        """Add inventory actions to the toolbar."""
        self._make_button(
            parent, "Aktualisieren", on_refresh, "Accent.TButton"
        )
        self._make_button(parent, "Alle auswählen", self.select_all)
        self._make_button(parent, "Auswahl aufheben", self.clear_selection)
        self._make_button(
            parent, "JSON importieren", on_import, "Import.TButton"
        )
        self._make_button(
            parent, "JSON exportieren", on_export, "Export.TButton"
        )

    def _create_search(self, parent):
        """Add the search field and bind it to table filtering."""
        search_frame = ttk.Frame(parent, style="Toolbar.TFrame")
        search_frame.pack(side="right", padx=(10, 0))
        ttk.Label(
            search_frame, text="Suchen", style="Toolbar.TLabel"
        ).pack(side="left", padx=(2, 8))
        search_panel = RoundedPanel(
            search_frame,
            RoundedPanelStyle(
                fill="#0e192c",
                background="#121d31",
                outline="#344966",
                radius=14,
                inset=3
            )
        )
        search_panel.pack(side="left")
        tk.Entry(
            search_panel.content,
            textvariable=self.search,
            width=20,
            background="#0e192c",
            foreground="#e8eefb",
            insertbackground="#e8eefb",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=("Segoe UI", 10)
        ).pack(padx=8, pady=5)
        self.search.trace_add("write", self.filter_programs)

    def _create_table(self, parent):
        """Create the sortable table and its vertical scrollbar."""
        columns = tuple(self.COLUMN_TITLES)
        tree = ttk.Treeview(
            parent, columns=columns, show="tree headings",
            selectmode="extended"
        )
        tree.heading("#0", text="")
        for column, title in self.COLUMN_TITLES.items():
            tree.heading(
                column,
                text=title,
                command=lambda selected=column: self.sort_programs(selected)
            )
        tree.column(
            "#0", width=42, minwidth=42, stretch=False, anchor="center"
        )
        tree.column("name", width=300, minwidth=180)
        tree.column("version", width=110, minwidth=80)
        tree.column("publisher", width=250, minwidth=120)
        tree.column(
            "install_date", width=125, minwidth=105, anchor="center"
        )
        tree.column(
            "estimated_size", width=105, minwidth=85, anchor="e"
        )
        tree.bind("<<TreeviewSelect>>", self.update_selection_count)

        scrollbar = ttk.Scrollbar(
            parent, orient="vertical", command=tree.yview,
            style="Vertical.TScrollbar"
        )
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return tree

    def _create_footer(self, on_uninstall):
        """Add status, uninstall action, and copyright notice."""
        footer_panel = RoundedPanel(
            self.root,
            RoundedPanelStyle(
                fill="#121d31",
                background="#0b1120",
                outline="#263752",
                radius=13,
                inset=12
            )
        )
        footer_panel.pack(fill="x", padx=18, pady=(8, 0))
        footer = footer_panel.content
        status = ttk.Label(footer, text="Bereit", style="Status.TLabel")
        status.pack(side="left")
        RoundedButton(
            footer,
            text="Ausgewählte Programme deinstallieren",
            command=on_uninstall,
            style=RoundedButtonStyle(
                background="#b83d50",
                foreground="#ffffff",
                hover_background="#9d3041",
                border="#cb5262",
                canvas_background="#121d31",
                font=("Segoe UI", 9, "bold"),
                padx=14,
                pady=8,
                radius=12
            )
        ).pack(side="right")

        copyright_footer = ttk.Frame(self.root, padding=(22, 0, 22, 9))
        copyright_footer.pack(fill="x")
        ttk.Label(
            copyright_footer,
            text="Copyright (C) 2026 Bjoern Bruecher.",
            style="Subheader.TLabel"
        ).pack(side="right")
        return status

    @staticmethod
    def _make_button(parent, text, command, style="TButton"):
        """Add a pill-shaped button using the requested color variant."""
        variants = {
            "TButton": RoundedButtonStyle(),
            "Accent.TButton": RoundedButtonStyle(
                background="#3478e5",
                foreground="#ffffff",
                hover_background="#2867cc",
                border="#4386f0"
            ),
            "Export.TButton": RoundedButtonStyle(),
            "Import.TButton": RoundedButtonStyle()
        }
        RoundedButton(
            parent, text, command, style=variants[style]
        ).pack(side="left", padx=4)

    def create_default_program_icon(self):
        """Create a generic icon for programs without a registered icon."""
        image = tk.PhotoImage(master=self.root, width=24, height=24)
        image.put("#2563eb", to=(2, 2, 22, 22))
        image.put("#bfdbfe", to=(5, 5, 19, 8))
        image.put("#eff6ff", to=(5, 11, 19, 13))
        image.put("#eff6ff", to=(5, 16, 15, 18))
        return image

    def set_programs(self, programs, program_icons):
        """Replace the inventory and render it using the supplied icons."""
        self.programs = programs
        self.program_icons = program_icons
        self.filter_programs()

    def set_status(self, text):
        """Update the status text in the application footer."""
        self.status.config(text=text)

    def selected_programs(self):
        """Return the program records selected in the visible table."""
        return [
            self.filtered[int(item_id)]
            for item_id in self.tree.selection()
        ]

    def filter_programs(self, *_):
        """Rebuild the table with programs matching the search field."""
        term = self.search.get().lower()
        self.filtered = [
            program for program in self.programs
            if term in program["name"].lower()
            or term in str(program.get("publisher", "")).lower()
        ]
        self._sort_filtered_programs()
        self._populate_program_table()

    def sort_programs(self, column):
        """Sort visible programs by a column and toggle its direction."""
        active_column, active_reverse = self._active_sort()
        reverse = not active_reverse if active_column == column else False
        selected = self.selected_programs()
        self._sort_filtered_programs(column, reverse)
        self._populate_program_table(selected)
        self._update_sort_indicators(column, reverse)

    def _active_sort(self):
        """Read the active column and direction from its heading indicator."""
        for column in self.COLUMN_TITLES:
            title = self.tree.heading(column, "text")
            if title.endswith(" ▲"):
                return column, False
            if title.endswith(" ▼"):
                return column, True
        return "name", False

    def _sort_filtered_programs(self, column=None, reverse=None):
        """Sort valid values while keeping missing values at the end."""
        if column is None or reverse is None:
            column, reverse = self._active_sort()

        sortable = []
        missing = []
        for program in self.filtered:
            value = self._program_sort_value(program, column)
            if value is None:
                missing.append(program)
            else:
                sortable.append((value, program))
        sortable.sort(key=lambda item: item[0], reverse=reverse)
        self.filtered = [program for _, program in sortable] + missing

    @staticmethod
    def _program_sort_value(program, column):
        """Return a type-aware sort value, or None for missing metadata."""
        value = program.get(column)
        if value is None or value == "":
            return None
        if column == "estimated_size":
            try:
                size = float(value)
            except (TypeError, ValueError):
                return None
            return size if math.isfinite(size) else None
        if column == "install_date":
            try:
                return datetime.strptime(str(value), "%Y%m%d")
            except ValueError:
                return None
        text = str(value).strip().casefold()
        return text or None

    def _populate_program_table(self, selected_programs=()):
        """Render the currently filtered and sorted programs."""
        selected_ids = {id(program) for program in selected_programs}
        self.tree.delete(*self.tree.get_children())
        for index, program in enumerate(self.filtered):
            icon_path = str(program.get("display_icon", "")).strip()
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                text="",
                image=self.program_icons.get(
                    icon_path, self.default_program_icon
                ),
                values=(
                    program["name"],
                    program.get("version", ""),
                    program.get("publisher", ""),
                    format_install_date(program.get("install_date")),
                    format_size(program.get("estimated_size"))
                )
            )
            if id(program) in selected_ids:
                self.tree.selection_add(str(index))
        self._update_program_stats()
        self.update_selection_count()

    def _update_program_stats(self):
        """Refresh installed, visible, and publisher summary counters."""
        publishers = {
            str(program.get("publisher", "")).strip().casefold()
            for program in self.programs
            if str(program.get("publisher", "")).strip()
        }
        self.summary_values["installed"].config(text=str(len(self.programs)))
        self.summary_values["visible"].config(text=str(len(self.filtered)))
        self.summary_values["publishers"].config(text=str(len(publishers)))

    def _update_sort_indicators(self, column, reverse):
        """Show the active sort column and direction in its heading."""
        for heading_column, title in self.COLUMN_TITLES.items():
            indicator = ""
            if heading_column == column:
                indicator = " ▼" if reverse else " ▲"
            self.tree.heading(heading_column, text=title + indicator)

    def update_selection_count(self, event=None):
        """Update the displayed count of selected programs."""
        tree = event.widget if event else self.tree
        self.summary_values["selected"].config(text=str(len(tree.selection())))

    def select_all(self):
        """Select all programs currently shown in the table."""
        self.tree.selection_set(self.tree.get_children())

    def clear_selection(self):
        """Clear the current table selection."""
        self.tree.selection_remove(self.tree.selection())
