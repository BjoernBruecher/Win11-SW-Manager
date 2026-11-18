---
name: rounded-gui
description: >-
  Use when adding or modifying GUI widgets in this project and keep the
  dark rounded-box visual style consistent.
---

# Rounded GUI Style

Use these guidelines for all GUI changes in this repository:

- Keep the existing dark navy palette, rounded panels, and pill-shaped
  controls. New cards, toolbars, table areas, search fields, and status
  containers should visually match the existing rounded surfaces.
- Reuse `RoundedPanel`, `RoundedPanelStyle`, `RoundedButton`, and
  `RoundedButtonStyle` from `src/rounded_widgets.py`. Do not draw a competing
  rounded style or use square ttk buttons for primary actions.
- For editable controls, place a flat, borderless input inside a rounded panel.
  Keep its fill and text colors consistent with the panel, and put labels
  outside the input surface.
- Tkinter `Treeview` cells cannot have rounded corners. Keep the table inset
  inside a clearly visible rounded surface so its square edges do not replace
  the rounded table frame.
- Preserve visible hover and keyboard-focus behavior, readable contrast,
  translations for DE, US, FR, and IT, and existing table interactions.
  Select the operating system locale at startup when supported; otherwise
  fall back to German.
- Keep translated strings in the UTF-8 JSON files under `src/locales/`; do
  not hard-code user-facing text in view or controller code. Keep all locale
  keys and format placeholders consistent.
- Keep the interface dependency-free unless a task explicitly requires a new
  package.
- After visual changes, run syntax checks, Flake8, Pylint, and a focused GUI
  smoke test. Do not execute uninstall commands during validation.
