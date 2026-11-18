---
name: update-readme-screenshot
description: >-
  Use when asked to create or update the README.md image that shows the
  Win11-SW-Manager application.
---

# Update the README Application Screenshot

When adding or refreshing an application screenshot for the README:

- Capture the real Tkinter application window at its standard `1200x760`
  client size.
- Capture the complete top-level window, including its title bar, rather than
  only the Tk client-area HWND.
- On Windows, use the visible frame bounds from
  `DwmGetWindowAttribute` with `DWMWA_EXTENDED_FRAME_BOUNDS` when capturing the
  window. A raw `GetWindowRect` can include DWM shadow margins and reveal
  desktop pixels around the application.
- Configure the GUI language to US/English for documentation screenshots,
  regardless of the operating system locale.
- Do not change the application's normal locale detection; only force English
  in the temporary screenshot capture process.
- Save the image as `assets/screenshot.png` and use a Markdown image reference
  in `README.md`:

  ```markdown
  ## Screenshot

  ![Windows 11 Software Manager](assets/screenshot.png)
  ```

- Avoid capturing the editor, terminal, desktop, dialogs, or uninstall actions.
- Inspect the saved PNG itself before finishing. Confirm it includes the full
  title bar, all of the client area through the version/copyright row at the
  bottom, and no surrounding desktop or cropped edges.
- Do not execute uninstall commands while capturing or validating.
- Run `python -m compileall -q Win11-SW-Manager.py src` after README asset
  changes.
