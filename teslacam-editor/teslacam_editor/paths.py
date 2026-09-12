"""Per-user directories for settings, caches and default exports."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "TeslaCamEditor"


def data_dir() -> Path:
    override = os.environ.get("TCE_DATA_DIR")
    if override:
        p = Path(override)
    elif sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        p = Path(base) / APP_NAME
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        p = Path(base) / "teslacam-editor"
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir() -> Path:
    p = data_dir() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def thumbs_dir() -> Path:
    p = cache_dir() / "thumbs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def projects_dir() -> Path:
    p = data_dir() / "projects"
    p.mkdir(parents=True, exist_ok=True)
    return p


def uploads_dir() -> Path:
    p = data_dir() / "uploads"
    p.mkdir(parents=True, exist_ok=True)
    return p


def default_export_dir() -> Path:
    home = Path.home()
    for candidate in (home / "Videos", home / "Movies", home / "Desktop", home):
        if candidate.is_dir():
            p = candidate / "TeslaCam Exports"
            p.mkdir(parents=True, exist_ok=True)
            return p
    p = data_dir() / "exports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def settings_file() -> Path:
    return data_dir() / "settings.json"
