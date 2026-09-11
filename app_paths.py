"""Separate immutable application assets from persistent owner data."""
import os
import sys
from pathlib import Path

def data_directory(root):
    override = os.environ.get('NELSONICT_DATA_DIR')
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, 'frozen', False):
        if sys.platform == 'win32':
            base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
        else:
            base = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
        return base / 'nelsonict-router-manager'
    return root / 'data'
