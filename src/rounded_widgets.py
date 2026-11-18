"""Reusable rounded Tkinter panels and buttons."""

import math
import tkinter as tk
from tkinter import font as tkfont
from typing import NamedTuple
from typing import Callable, List, Optional, Tuple, Union


class RoundedPanelStyle(NamedTuple):
    """Colors and geometry for a rounded panel."""

    fill: str
    background: str
    outline: str = "#263752"
    radius: int = 14
    inset: int = 8


class RoundedButtonStyle(NamedTuple):
    """Colors and geometry for a pill-shaped button."""

    background: str = "#24344e"
    foreground: str = "#e8eefb"
    hover_background: str = "#304563"
    border: str = "#304563"
    canvas_background: str = "#121d31"
    font: Union[
        str,
        Tuple[str, int],
        Tuple[str, int, str]
    ] = ("Segoe UI", 9)
    padx: int = 11
    pady: int = 7
    radius: int = 10


class RoundedPanel(tk.Frame):
    """A frame with a rounded background and an inset child container."""

    def __init__(
        self, parent: tk.Misc, style: RoundedPanelStyle
    ) -> None:
        """Create a rounded panel that can contain normal Tk widgets."""
        super().__init__(
            parent,
            background=style.background,
            borderwidth=0,
            highlightthickness=0
        )
        self._fill = style.fill
        self._outline = style.outline
        self._radius = style.radius
        self._canvas: tk.Canvas = tk.Canvas(
            self,
            background=style.background,
            borderwidth=0,
            highlightthickness=0
        )
        self._canvas.place(relwidth=1, relheight=1)
        self._canvas.bind("<Configure>", self._draw_background)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.content: tk.Frame = tk.Frame(
            self,
            background=style.fill,
            borderwidth=0,
            highlightthickness=0
        )
        self.content.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=style.inset,
            pady=style.inset
        )

    def _draw_background(self, event: tk.Event) -> None:
        """Redraw the rounded panel when its size changes."""
        self._canvas.delete("panel")
        radius = min(
            self._radius,
            event.width / 2,
            event.height / 2
        )
        points = _rounded_rectangle_points(
            1, 1, event.width - 1, event.height - 1, radius
        )
        self._canvas.create_polygon(
            points,
            fill=self._fill,
            outline=self._outline,
            width=1,
            smooth=True,
            splinesteps=12,
            tags="panel"
        )


class RoundedButton:
    """A compact pill-shaped button drawn on a Tkinter canvas."""

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command: Optional[Callable[[], object]] = None,
        style: Optional[RoundedButtonStyle] = None
    ) -> None:
        """Create a rounded button with pointer and keyboard activation."""
        self._style: RoundedButtonStyle = style or RoundedButtonStyle()
        self._font: tkfont.Font = tkfont.Font(
            parent=parent, font=self._style.font
        )
        self._text: str = text
        self._command: Optional[Callable[[], object]] = command
        self._enabled: bool = True
        self._state: str = "normal"
        width = self._font.measure(text) + 2 * self._style.padx
        height = self._font.metrics("linespace") + 2 * self._style.pady
        self.widget = tk.Canvas(
            parent,
            width=width,
            height=height,
            background=self._style.canvas_background,
            borderwidth=0,
            highlightthickness=0,
            cursor="hand2" if command else "arrow",
            takefocus=bool(command)
        )
        self.widget.bind("<Configure>", self._draw_button)
        self.widget.bind("<Enter>", self._on_enter)
        self.widget.bind("<Leave>", self._on_leave)
        self.widget.bind("<ButtonPress-1>", self._on_press)
        self.widget.bind("<ButtonRelease-1>", self._on_release)
        self.widget.bind("<Return>", self._on_key)
        self.widget.bind("<space>", self._on_key)

    def pack(self, *args: object, **kwargs: object) -> None:
        """Pack the underlying canvas widget."""
        self.widget.pack(*args, **kwargs)

    def invoke(self) -> object:
        """Invoke the button command when one is configured."""
        if self._command and self._enabled:
            self._command()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable interaction while retaining the rounded style."""
        self._enabled = bool(enabled)
        self._state = "normal"
        self.widget.configure(
            cursor=(
                "hand2" if self._command and self._enabled else "arrow"
            ),
            takefocus=bool(self._command and self._enabled)
        )
        self._draw_button()

    def set_text(self, text: str) -> None:
        """Update the label and resize the button to fit it."""
        self._text = text
        self.widget.configure(
            width=self._font.measure(text) + 2 * self._style.padx
        )
        self._draw_button()

    def _draw_button(self, event: Optional[tk.Event] = None) -> None:
        """Draw the button background and centered label."""
        width = event.width if event else self.widget.winfo_width()
        height = event.height if event else self.widget.winfo_height()
        self.widget.delete("button")
        radius = min(self._style.radius, width / 2, height / 2)
        color = self._style.background
        foreground = self._style.foreground
        if not self._enabled:
            color = "#25334a"
            foreground = "#8192ad"
        elif self._state == "hover":
            color = self._style.hover_background

        points = _rounded_rectangle_points(
            1, 1, width - 1, height - 1, radius
        )
        self.widget.create_polygon(
            points,
            fill=color,
            outline=self._style.border,
            width=1,
            smooth=True,
            splinesteps=12,
            tags="button"
        )
        self.widget.create_text(
            width / 2,
            height / 2,
            text=self._text,
            fill=foreground,
            font=self._font,
            tags="button"
        )

    def _on_enter(self, event: tk.Event) -> None:
        """Show the hover color when the pointer enters the button."""
        if event.widget is self.widget and self._command and self._enabled:
            self._state = "hover"
            self._draw_button()

    def _on_leave(self, event: tk.Event) -> None:
        """Restore the normal color when the pointer leaves the button."""
        if event.widget is self.widget:
            self._state = "normal"
            self._draw_button()

    def _on_press(self, event: tk.Event) -> None:
        """Show the pressed state for an active button."""
        if event.widget is self.widget and self._command and self._enabled:
            self._state = "pressed"
            self._draw_button()

    def _on_release(self, event: tk.Event) -> None:
        """Invoke the action when release occurs inside the button."""
        should_invoke = (
            self._command
            and self._enabled
            and event.widget is self.widget
            and 0 <= event.x <= self.widget.winfo_width()
            and 0 <= event.y <= self.widget.winfo_height()
        )
        self._state = "hover" if should_invoke else "normal"
        self._draw_button()
        if should_invoke:
            self._command()

    def _on_key(self, event: tk.Event) -> Optional[str]:
        """Invoke the action using Enter or Space."""
        if (
            self._command
            and self._enabled
            and event.keysym in ("Return", "space")
        ):
            self.invoke()
            return "break"
        return None


def _rounded_rectangle_points(
    left: float,
    top: float,
    right: float,
    bottom: float,
    radius: float
) -> List[float]:
    """Return sampled corner points for a rounded rectangle polygon."""
    corners = (
        (left + radius, top + radius, 270, 180),
        (left + radius, bottom - radius, 180, 90),
        (right - radius, bottom - radius, 90, 0),
        (right - radius, top + radius, 0, -90)
    )
    points = []
    for center_x, center_y, start_angle, end_angle in corners:
        for step in range(9):
            angle = math.radians(
                start_angle + (end_angle - start_angle) * step / 8
            )
            points.extend((
                center_x + radius * math.cos(angle),
                center_y + radius * math.sin(angle)
            ))
    return points
