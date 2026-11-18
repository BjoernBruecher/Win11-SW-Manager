"""Launch the Windows 11 Software Manager application."""

from src.admin import ensure_admin
from src.software_manager import main


if __name__ == "__main__":
    if ensure_admin():
        main()
