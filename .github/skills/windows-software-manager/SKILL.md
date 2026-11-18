---
name: windows-software-manager
description: >-
  Use when changing this project's Python GUI, Windows registry integration,
  application metadata, JSON import/export, or uninstall flow.
---

# Windows 11 Software Manager

Use these project-specific guidelines when changing this repository:

- Keep the application compatible with Windows 11, Python 3.9+, and the
  standard library. Do not add dependencies unless the task requires them.
- Keep `Win11-SW-Manager.py` as the root-level launcher and application
  modules in `src/`. Use package-relative imports between modules in `src/`.
- Follow the existing Tkinter/ttk interface patterns. Keep all user-facing
  labels translated for the DE/US/FR/IT selector. Select the operating
  system locale at startup when supported; otherwise fall back to German.
- Store translations in UTF-8 JSON files under `src/locales/`; preserve the
  same keys and format placeholders in each locale.
- For visual changes, follow `.github/skills/rounded-gui/SKILL.md` and reuse
  the existing rounded widgets.
- Treat registry metadata such as install dates, sizes, and display icons as
  optional. Missing or invalid values must not prevent the program list from
  loading.
- Keep imported and exported JSON compatible with older files that do not
  contain newer metadata fields.
- Preserve the uninstall safety checks. Never execute uninstall commands
  through a shell, silently, or without the existing confirmation flow.
- Keep the system-wide single-instance mutex held for the application's
  lifetime.
- Update the README when changing user-visible features.
- Validate Python changes with a syntax check and focused tests where possible.
  Do not run uninstall commands as part of validation.
