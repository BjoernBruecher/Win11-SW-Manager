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
- Do not execute uninstall commands while capturing or validating.
- Run `python -m compileall -q Win11-SW-Manager.py src` after README asset
  changes.
