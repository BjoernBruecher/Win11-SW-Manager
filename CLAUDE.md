# Claude Code instructions

## Project overview

This is a Windows 11 software manager implemented in Python 3.9+ and Tkinter.
`Win11-SW-Manager.py` is the root-level launcher. The `src/` package contains
the application modules: `software_manager.py` coordinates application
workflows, `software_manager_view.py` owns the GUI, and dedicated repository
and uninstaller modules handle registry access and uninstall commands.
`program_icons.py` extracts application icons.

Internal imports between modules in `src/` must be package-relative. The
launcher imports the controller through `src.software_manager`.

## Project conventions

- Keep changes compatible with Windows and the Python standard library unless
  a task explicitly requires otherwise.
- Follow the existing Tkinter/ttk patterns and keep all user-facing text
  translated for the DE/US/FR/IT language selector. Select the operating
  system locale when supported and fall back to German otherwise.
- Treat registry metadata and icons as optional. Missing or invalid values must
  not prevent the application list from loading.
- Keep imported/exported JSON backward-compatible with older files that lack
  newer metadata fields.
- Preserve uninstall confirmations and safety checks. Do not execute commands
  through a shell or silently, and do not run uninstall commands during
  development or validation.
- Update `README.md` when changing user-visible behavior.

## Validation

Run a focused check for each change. For Python syntax validation, use:

```powershell
python -m compileall -q Win11-SW-Manager.py src
```

See `.github/skills/windows-software-manager/SKILL.md` for additional
project-specific implementation guidance.
