"""
Finding bundled assets.

Frozen builds unpack into a temporary folder, so an asset path worked out
from __file__ points somewhere that does not exist once packaged. This is
the one place that difference is handled.
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


def asset_dir():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).resolve().parent.parent / "assets"


def asset(name):
    return asset_dir() / name


def load_pixmap(name, width=None, dpr=1.0):
    """
    Load an asset, scaled to a width in logical pixels.

    Scaling is done at the device pixel ratio and the ratio recorded on the
    pixmap, so the artwork stays sharp on a high-DPI display instead of
    being upscaled from a too-small bitmap.
    """
    path = asset(name)
    if not path.exists():
        return None
    pm = QPixmap(str(path))
    if pm.isNull():
        return None
    if width:
        pm = pm.scaledToWidth(int(width * dpr), Qt.SmoothTransformation)
        pm.setDevicePixelRatio(dpr)
    return pm
