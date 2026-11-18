"""Tkinter presentation layer for the Windows software manager."""

import math
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast
)

from .localization import (
    detect_system_language,
    detect_system_locale_name,
    translate
)
from .program_repository import format_install_date, format_size
from .rounded_widgets import (
    RoundedButton,
    RoundedButtonStyle,
    RoundedPanel,
    RoundedPanelStyle
)
from .version import APP_VERSION


class SoftwareManagerView:
    """Own the application widgets and the visible program-table state."""

    COLUMN_TITLES: Dict[str, str] = {
        "name": "column_name",
        "version": "column_version",
        "latest_version": "column_latest_version",
        "publisher": "column_publisher",
        "install_date": "column_install_date",
        "estimated_size": "column_estimated_size"
    }

    def __init__(
        self,
        root: tk.Tk,
        on_refresh: Callable[[], None],
        on_export: Callable[[], None],
        on_import: Callable[[], None],
        on_uninstall: Callable[[], None],
        *,
        on_download_update: Callable[[], None]
    ) -> None:
        """Create the window, controls, and empty program table."""
        self.root: tk.Tk = root
        self.programs: List[Dict[str, Any]] = []
        self.filtered: List[Dict[str, Any]] = []
        self.program_icons: Dict[str, tk.PhotoImage] = {}
        self.widgets: Dict[str, Dict[str, Any]] = {
            "summary_values": {},
            "labels": {},
            "action_buttons": {}
        }
        self.variables: Dict[str, tk.StringVar] = {
            "search": tk.StringVar(master=self.root),
            "language": tk.StringVar(
                master=self.root,
                value=detect_system_language()
            ),
            "system_locale": tk.StringVar(
                master=self.root,
                value=detect_system_locale_name()
            )
        }
        self.status_key: str = "status_ready"
        self.status_values: Dict[str, object] = {}
        self.tree: ttk.Treeview
        self.status: ttk.Label
        self.list_progress: ttk.Progressbar
        self.root.title(self._text("window_title"))
        if sys.platform == "win32":
            bundle_directory = Path(getattr(
                sys,
                "_MEIPASS",
                Path(__file__).resolve().parent.parent
            ))
            iconbitmap = cast(
                Callable[[str], object],
                getattr(self.root, "iconbitmap")
            )
            iconbitmap(str(
                bundle_directory / "assets" / "program.ico"
            ))
        window_height = min(
            800,
            max(600, self.root.winfo_screenheight() - 100)
        )
        self.root.geometry(f"1200x{window_height}")
        self.root.minsize(950, min(700, window_height))
        self.setup_style()
        self.tree, self.status, self.list_progress = self.create_interface(
            on_refresh,
            on_export,
            on_import,
            on_uninstall,
            on_download_update=on_download_update
        )
        self._update_sort_indicators("name", False)
        self.default_program_icon = self.create_default_program_icon()
        self.apply_language()

    @property
    def summary_values(self) -> Dict[str, ttk.Label]:
        """Return the summary value labels."""
        return self.widgets["summary_values"]

    @property
    def labels(self) -> Dict[str, ttk.Label]:
        """Return the translated text labels."""
        return self.widgets["labels"]

    @property
    def action_buttons(self) -> Dict[str, RoundedButton]:
        """Return the action buttons that need language updates."""
        return self.widgets["action_buttons"]

    @property
    def search(self) -> tk.StringVar:
        """Return the search text variable."""
        return self.variables["search"]

    @property
    def language(self) -> tk.StringVar:
        """Return the selected language variable."""
        return self.variables["language"]

    @property
    def system_locale_name(self) -> str:
        """Return the operating system locale name."""
        return self.variables["system_locale"].get()

    def setup_style(self) -> None:
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
            "Language.TRadiobutton",
            background="#121d31",
            foreground="#95a7c7",
            font=("Segoe UI", 9, "bold"),
            padding=(5, 3)
        )
        style.map(
            "Language.TRadiobutton",
            background=[("active", "#121d31")],
            foreground=[("selected", "#f1f5ff")]
        )
        style.configure(
            "Status.TLabel",
            background="#121d31",
            foreground="#95a7c7",
            font=("Segoe UI", 10)
        )
        style.configure(
            "Horizontal.TProgressbar",
            background="#3478e5",
            troughcolor="#0e192c",
            bordercolor="#263752",
            lightcolor="#3478e5",
            darkcolor="#3478e5",
            thickness=12
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
                ("Treeview.padding", {
                    "sticky": "nswe",
                    "children": [
                        ("Treeview.treearea", {"sticky": "nswe"})
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
        self,
        on_refresh: Callable[[], None],
        on_export: Callable[[], None],
        on_import: Callable[[], None],
        on_uninstall: Callable[[], None],
        *,
        on_download_update: Callable[[], None]
    ) -> Tuple[ttk.Treeview, ttk.Label, ttk.Progressbar]:
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
        title_label = ttk.Label(
            title_block,
            text=self._text("window_title"),
            style="Header.TLabel"
        )
        title_label.pack(anchor="w")
        self.labels["window_title"] = title_label
        subtitle_label = ttk.Label(
            title_block,
            text=self._text("subtitle"),
            style="Subheader.TLabel"
        )
        subtitle_label.pack(anchor="w", pady=(3, 0))
        self.labels["subtitle"] = subtitle_label
        os_language_label = ttk.Label(
            title_block,
            text=self._text(
                "os_language",
                locale=self.system_locale_name
            ),
            style="Subheader.TLabel"
        )
        os_language_label.pack(anchor="w", pady=(2, 0))
        self.labels["os_language"] = os_language_label
        self._create_language_selector(header)

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
        self.action_buttons["tab_apps"] = RoundedButton(
            toolbar,
            text=self._text("tab_apps"),
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
        )
        self.action_buttons["tab_apps"].pack(side="left", padx=(0, 8))
        self._create_toolbar_buttons(
            toolbar, on_refresh, on_export, on_import
        )
        self._create_search(toolbar)

        status, list_progress = self._create_footer(
            on_uninstall, on_download_update
        )
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
        return tree, status, list_progress

    def _create_summary_cards(self, parent: tk.Misc) -> None:
        """Create the four live inventory and selection counters."""
        cards = (
            ("installed", "summary_installed"),
            ("visible", "summary_visible"),
            ("selected", "summary_selected"),
            ("publishers", "summary_publishers")
        )
        for column, (key, title_key) in enumerate(cards):
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
            title = ttk.Label(
                card.content,
                text=self._text(title_key),
                style="CardTitle.TLabel"
            )
            title.pack(anchor="w", padx=9, pady=(5, 0))
            self.labels[title_key] = title
            value = ttk.Label(
                card.content, text="0", style="CardValue.TLabel"
            )
            value.pack(anchor="w", padx=9, pady=(3, 5))
            self.summary_values[key] = value

    def _create_toolbar_buttons(
        self,
        parent: tk.Misc,
        on_refresh: Callable[[], None],
        on_export: Callable[[], None],
        on_import: Callable[[], None]
    ) -> None:
        """Add inventory actions to the toolbar."""
        self._make_button(
            parent, "refresh", on_refresh, "Accent.TButton"
        )
        self._make_button(parent, "select_all", self.select_all)
        self._make_button(parent, "clear_selection", self.clear_selection)
        self._make_button(
            parent, "import_json", on_import, "Import.TButton"
        )
        self._make_button(
            parent, "export_json", on_export, "Export.TButton"
        )

    def _create_search(self, parent: tk.Misc) -> None:
        """Add the search field and bind it to table filtering."""
        search_frame = ttk.Frame(parent, style="Toolbar.TFrame")
        search_frame.pack(side="right", padx=(10, 0))
        search_label = ttk.Label(
            search_frame, text=self._text("search"), style="Toolbar.TLabel"
        )
        search_label.pack(side="left", padx=(2, 8))
        self.labels["search"] = search_label
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

    def _create_language_selector(self, parent: tk.Misc) -> None:
        """Add a rounded radio option for each supported locale."""
        selector = RoundedPanel(
            parent,
            RoundedPanelStyle(
                fill="#121d31",
                background="#0b1120",
                outline="#263752",
                radius=12,
                inset=3
            )
        )
        selector.pack(side="right")
        for language in ("DE", "US", "FR", "IT"):
            ttk.Radiobutton(
                selector.content,
                text=language,
                variable=self.language,
                value=language,
                style="Language.TRadiobutton",
                command=self.apply_language
            ).pack(side="left", padx=4)

    def _text(self, key: str, **values: object) -> str:
        """Return a translated string for the currently selected language."""
        return translate(self.language.get(), key, **values)

    def apply_language(self) -> None:
        """Refresh all visible GUI text after a language change."""
        for key, label in self.labels.items():
            if key == "os_language":
                continue
            label.config(text=self._text(key))
        self.labels["os_language"].config(
            text=self._text(
                "os_language",
                locale=self.system_locale_name
            )
        )
        for key, button in self.action_buttons.items():
            button.set_text(self._text(key))
        self.root.title(self._text("window_title"))
        column, reverse = self._active_sort()
        self._update_sort_indicators(column, reverse)
        self._populate_program_table(self.selected_programs())
        self.status.config(
            text=self._text(
                self.status_key,
                **self.status_values
            )
        )

    def _create_table(self, parent: tk.Misc) -> ttk.Treeview:
        """Create the sortable table and its vertical scrollbar."""
        columns = tuple(self.COLUMN_TITLES)
        tree = ttk.Treeview(
            parent, columns=columns, show="tree headings",
            selectmode="extended"
        )
        self.tree = tree
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
        tree.column("name", width=270, minwidth=180)
        tree.column("version", width=105, minwidth=80)
        tree.column("latest_version", width=125, minwidth=100)
        tree.column("publisher", width=225, minwidth=120)
        tree.column(
            "install_date", width=125, minwidth=105, anchor="center"
        )
        tree.column(
            "estimated_size", width=105, minwidth=85, anchor="e"
        )
        tree.bind("<<TreeviewSelect>>", self.update_selection_count)

        scrollbar = ttk.Scrollbar(
            parent,
            orient="vertical",
            command=self._scroll_treeview,
            style="Vertical.TScrollbar"
        )
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return tree

    def _create_footer(
        self,
        on_uninstall: Callable[[], None],
        on_download_update: Callable[[], None]
    ) -> Tuple[ttk.Label, ttk.Progressbar]:
        """Add status, uninstall action, version, and copyright notice."""
        copyright_footer = ttk.Frame(self.root, padding=(22, 0, 22, 9))
        copyright_footer.pack(side="bottom", fill="x")
        ttk.Label(
            copyright_footer,
            text=f"v{APP_VERSION}",
            style="Subheader.TLabel"
        ).pack(side="left")
        ttk.Label(
            copyright_footer,
            text="Copyright (C) 2026 Bjoern Bruecher",
            style="Subheader.TLabel"
        ).pack(side="right")

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
        footer_panel.pack(
            side="bottom", fill="x", padx=18, pady=(8, 0)
        )
        footer = footer_panel.content
        status = ttk.Label(
            footer,
            text=self._text(self.status_key),
            style="Status.TLabel"
        )
        status.pack(side="left")
        self.action_buttons["download_update"] = RoundedButton(
            footer,
            text=self._text("download_update"),
            command=on_download_update,
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
        self.action_buttons["download_update"].pack(
            side="right", padx=(0, 8)
        )
        self.action_buttons["download_update"].set_enabled(False)
        list_progress = ttk.Progressbar(
            footer,
            mode="indeterminate",
            style="Horizontal.TProgressbar"
        )
        self.action_buttons["uninstall_button"] = RoundedButton(
            footer,
            text=self._text("uninstall_button"),
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
        )
        self.action_buttons["uninstall_button"].pack(side="right")

        return status, list_progress

    def _make_button(
        self,
        parent: tk.Misc,
        key: str,
        command: Callable[[], object],
        style: str = "TButton"
    ) -> None:
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
        button = RoundedButton(
            parent,
            self._text(key),
            command,
            style=variants[style]
        )
        button.pack(side="left", padx=4)
        self.action_buttons[key] = button

    def create_default_program_icon(self) -> tk.PhotoImage:
        """Create a generic icon for programs without a registered icon."""
        image = tk.PhotoImage(master=self.root, width=24, height=24)
        image.put("#2563eb", to=(2, 2, 22, 22))
        image.put("#bfdbfe", to=(5, 5, 19, 8))
        image.put("#eff6ff", to=(5, 11, 19, 13))
        image.put("#eff6ff", to=(5, 16, 15, 18))
        return image

    def set_programs(
        self,
        programs: List[Dict[str, Any]],
        program_icons: Dict[str, tk.PhotoImage]
    ) -> None:
        """Replace the inventory and render it using the supplied icons."""
        self.programs = programs
        self.program_icons = program_icons
        self.filter_programs()

    def set_latest_versions(
        self,
        versions: List[str],
        *,
        package_ids: Optional[List[str]] = None,
        updates: Optional[List[bool]] = None,
        download_urls: Optional[List[str]] = None
    ) -> None:
        """Update version metadata while preserving the active table state."""
        selected = self.selected_programs()
        ids = package_ids or []
        update_flags = updates or []
        urls = download_urls or []
        for index, (program, version) in enumerate(
            zip(self.programs, versions)
        ):
            program["latest_version"] = version
            program["winget_id"] = (
                ids[index] if index < len(ids) else ""
            )
            program["update_available"] = (
                update_flags[index] if index < len(update_flags) else False
            )
            program["download_url"] = (
                urls[index] if index < len(urls) else ""
            )
        column, reverse = self._active_sort()
        if column == "latest_version":
            self._sort_filtered_programs(column, reverse)
        self._populate_program_table(selected)

    def set_status(self, key: str, **values: object) -> None:
        """Store and show a translated status message."""
        self.status_key = key
        self.status_values = dict(values)
        self.status.config(text=self._text(key, **values))

    def show_list_progress(
        self,
        mode: Literal["determinate", "indeterminate"] = "indeterminate",
        maximum: int = 100
    ) -> None:
        """Show registry-read or table-update progress in the footer."""
        self.list_progress.stop()
        self.list_progress.configure(
            mode=mode,
            maximum=max(maximum, 1),
            value=0
        )
        if not self.list_progress.winfo_manager():
            self.list_progress.pack(
                side="left", fill="x", expand=True, padx=14
            )
        if mode == "indeterminate":
            self.list_progress.start(12)

    def hide_list_progress(self) -> None:
        """Stop and hide the list progress indicator."""
        self.list_progress.stop()
        self.list_progress.pack_forget()

    def _scroll_treeview(
        self, *args: str
    ) -> Optional[Tuple[float, float]]:
        """Forward scrollbar requests to the Tkinter tree view."""
        yview = cast(
            Callable[..., Optional[Tuple[float, float]]],
            getattr(self.tree, "yview")
        )
        return yview(*args)

    def selected_programs(self) -> List[Dict[str, Any]]:
        """Return the program records selected in the visible table."""
        return [
            self.filtered[int(item_id)]
            for item_id in self.tree.selection()
        ]

    def filter_programs(self, *_: object) -> None:
        """Rebuild the table with programs matching the search field."""
        term = self.search.get().lower()
        self.filtered = [
            program for program in self.programs
            if term in program["name"].lower()
            or term in str(program.get("publisher", "")).lower()
        ]
        self._sort_filtered_programs()
        self._populate_program_table()

    def sort_programs(self, column: str) -> None:
        """Sort visible programs by a column and toggle its direction."""
        active_column, active_reverse = self._active_sort()
        reverse = not active_reverse if active_column == column else False
        selected = self.selected_programs()
        self._sort_filtered_programs(column, reverse)
        self._populate_program_table(selected)
        self._update_sort_indicators(column, reverse)

    def _active_sort(self) -> Tuple[str, bool]:
        """Read the active column and direction from its heading indicator."""
        for column in self.COLUMN_TITLES:
            title = self.tree.heading(column, "text")
            if title.endswith(" ▲"):
                return column, False
            if title.endswith(" ▼"):
                return column, True
        return "name", False

    def _sort_filtered_programs(
        self,
        column: Optional[str] = None,
        reverse: Optional[bool] = None
    ) -> None:
        """Sort valid values while keeping missing values at the end."""
        if column is None or reverse is None:
            column, reverse = self._active_sort()

        sortable: List[
            Tuple[Union[float, datetime, str], Dict[str, Any]]
        ] = []
        missing: List[Dict[str, Any]] = []
        for program in self.filtered:
            value = self._program_sort_value(program, column)
            if value is None:
                missing.append(program)
            else:
                sortable.append((value, program))
        sortable.sort(
            key=lambda item: item[0],
            reverse=reverse
        )
        self.filtered = [program for _, program in sortable] + missing

    @staticmethod
    def _program_sort_value(
        program: Dict[str, Any], column: str
    ) -> Optional[Union[float, datetime, str]]:
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

    def _populate_program_table(
        self, selected_programs: Sequence[Dict[str, Any]] = ()
    ) -> None:
        """Render the currently filtered and sorted programs."""
        selected_ids = {id(program) for program in selected_programs}
        self.tree.delete(*self.tree.get_children())
        total = len(self.filtered)
        show_progress = (
            self.list_progress.winfo_manager() == "pack"
            and str(self.list_progress.cget("mode")) == "determinate"
        )
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
                    program.get("latest_version", ""),
                    program.get("publisher", ""),
                    format_install_date(
                        program.get("install_date"), self.language.get()
                    ),
                    format_size(program.get("estimated_size"))
                )
            )
            if id(program) in selected_ids:
                self.tree.selection_add(str(index))
            if show_progress:
                self.list_progress.configure(value=index + 1)
                if index % 10 == 0 or index + 1 == total:
                    self.root.update_idletasks()
        self._update_program_stats()
        self.update_selection_count()

    def _update_program_stats(self) -> None:
        """Refresh installed, visible, and publisher summary counters."""
        publishers = {
            str(program.get("publisher", "")).strip().casefold()
            for program in self.programs
            if str(program.get("publisher", "")).strip()
        }
        self.summary_values["installed"].config(text=str(len(self.programs)))
        self.summary_values["visible"].config(text=str(len(self.filtered)))
        self.summary_values["publishers"].config(text=str(len(publishers)))

    def _update_sort_indicators(
        self, column: str, reverse: bool
    ) -> None:
        """Show the active sort column and direction in its heading."""
        for heading_column, title_key in self.COLUMN_TITLES.items():
            indicator = ""
            if heading_column == column:
                indicator = " ▼" if reverse else " ▲"
            self.tree.heading(
                heading_column,
                text=self._text(title_key) + indicator
            )

    def update_selection_count(self, event: Optional[tk.Event] = None) -> None:
        """Update the displayed count of selected programs."""
        tree = cast(
            ttk.Treeview,
            event.widget if event else self.tree
        )
        self.summary_values["selected"].config(text=str(len(tree.selection())))
        selected = self.selected_programs()
        self.action_buttons["download_update"].set_enabled(
            len(selected) == 1
            and bool(selected[0].get("update_available"))
            and bool(selected[0].get("download_url"))
        )

    def select_all(self) -> None:
        """Select all programs currently shown in the table."""
        self.tree.selection_set(self.tree.get_children())

    def clear_selection(self) -> None:
        """Clear the current table selection."""
        self.tree.selection_remove(self.tree.selection())
