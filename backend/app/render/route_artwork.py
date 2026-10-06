"""Shared route artwork location for source and packaged runtimes."""
from pathlib import Path
from app.config import RESOURCE_DIR
ICON_DIR = next((base / 'assets' / 'route-icons' for base in (Path(RESOURCE_DIR), Path(__file__).resolve().parents[3]) if (base / 'assets' / 'route-icons').is_dir()), Path(RESOURCE_DIR) / 'assets' / 'route-icons')
