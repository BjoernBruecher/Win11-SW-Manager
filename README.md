# Win11-SW-Manager

A small Windows utility for overview and management of installed programs on Windows 11.

## Overview

This project reads installed applications from the Windows registry, displays them in a clear GUI, and allows you to:

- Search for programs by name or vendor
- View the program name, version, and publisher
- Select multiple entries
- Export the program list as JSON
- Import a previously exported JSON file
- Uninstall selected programs with safety checks

## Features

- Lists all installed applications from:
  - `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`
  - `HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall`
  - `HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`
- Real-time filtering through the search field
- Total count of visible and available programs
- Safety mechanisms during uninstallation:
  - Prevents automatic execution of MSI/silent uninstallation commands without verification
  - Blocks script-based commands such as `.bat`, `.cmd`, `.ps1`, and `.vbs` for security reasons
  - Displays warnings and confirmation prompts

## Requirements

- Windows 11 (or a compatible Windows system with the same registry structure)
- Python 3.9+
- Tkinter (usually included with Python installations)

## Run the application

1. Install Python if it is not already available.
2. Clone the repository or download the files.
3. Run the following command in a terminal:

```bash
python Win11-SW-Manager.py
```

## Usage notes

- The application uses the Windows registry and the uninstall strings of installed applications.
- Some programs may require administrator rights to uninstall successfully.
- A confirmation prompt is shown before uninstalling. Unsafe or script-based uninstall commands are not executed automatically.

## Project structure

```text
Win11-SW-Manager/
├── README.md
├── Win11-SW-Manager.py
└── installierte_programme.json   (generated during export)
```

## Example: export to JSON

Once the app is running, the complete list can be saved as a JSON file. That file can then be imported again in another session to reuse the list.

## License

This project was created without a specific license agreement. Please use it according to the rules of your operating environment.
