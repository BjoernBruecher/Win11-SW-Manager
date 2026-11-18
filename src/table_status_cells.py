"""Helpers for colored status labels over Tkinter Treeview cells."""

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional

from .program_versions import has_safe_download_link


def create_status_cell(
    tree: ttk.Treeview,
    labels: Dict[str, tk.Label],
    item_id: str,
    text: str,
    color: str,
    *,
    on_activate: Optional[Callable[[str], None]] = None
) -> None:
    """Create a colored label overlay for one status cell."""
    label = tk.Label(
        tree,
        text=text,
        anchor="e",
        background="#17243a",
        foreground=color,
        font=("Segoe UI", 9),
        borderwidth=0,
        padx=0,
        pady=0,
        cursor="hand2" if on_activate else "arrow"
    )
    if on_activate:
        for event_name in ("<Button-1>", "<Return>", "<space>"):
            label.bind(
                event_name,
                lambda _event, row_id=item_id: on_activate(row_id)
            )
    labels[item_id] = label


def position_status_cells(
    tree: ttk.Treeview, labels: Dict[str, tk.Label]
) -> None:
    """Align the overlay labels with visible cells and selected rows."""
    selected = set(tree.selection())
    for item_id, label in labels.items():
        bounds = tree.bbox(item_id, "update_status")
        if not bounds:
            label.place_forget()
            continue
        x, y, width, height = bounds
        label.configure(
            background="#2c65b8" if item_id in selected else "#17243a"
        )
        label.place(
            x=x + 8,
            y=y,
            width=max(width - 16, 1),
            height=height
        )


def set_table_scroll(
    scrollbar: ttk.Scrollbar,
    tree: ttk.Treeview,
    labels: Dict[str, tk.Label],
    first: str,
    last: str
) -> None:
    """Update the scrollbar and reposition status-cell overlays."""
    scrollbar.set(first, last)
    tree.after_idle(position_status_cells, tree, labels)


def activate_status_link(
    tree: ttk.Treeview,
    programs: List[Dict[str, Any]],
    item_id: str,
    *,
    on_selection_change: Callable[[], None],
    on_open: Callable[[], object]
) -> None:
    """Select a program and open its safe installer link."""
    if not has_safe_download_link(programs[int(item_id)]):
        return
    tree.selection_set(item_id)
    tree.focus(item_id)
    on_selection_change()
    on_open()


def open_status_link(
    tree: ttk.Treeview,
    event: tk.Event,
    programs: List[Dict[str, Any]],
    *,
    on_selection_change: Callable[[], None],
    on_open: Callable[[], object]
) -> Optional[str]:
    """Open the installer when the update-status cell is clicked."""
    item_id = tree.identify_row(event.y)
    columns = tuple(tree["columns"])
    status_column = f"#{columns.index('update_status') + 1}"
    if (
        not item_id
        or tree.identify_column(event.x) != status_column
        or not has_safe_download_link(programs[int(item_id)])
    ):
        return None
    activate_status_link(
        tree,
        programs,
        item_id,
        on_selection_change=on_selection_change,
        on_open=on_open
    )
    return "break"


def format_status_text(
    program: Dict[str, Any], translate: Callable[[str], str]
) -> str:
    """Translate the short current/update status label."""
    status = program.get("update_status")
    key = {
        "latest": "table_is_latest",
        "update": "table_download_update"
    }.get(status)
    return translate(key) if key else ""


def make_status_link_callback(
    tree: ttk.Treeview,
    programs: List[Dict[str, Any]],
    on_selection_change: Callable[[], None],
    on_open: Callable[[], object]
) -> Callable[[str], None]:
    """Create the label callback that selects and opens an update row."""
    return lambda item_id: activate_status_link(
        tree,
        programs,
        item_id,
        on_selection_change=on_selection_change,
        on_open=on_open
    )
