"""How long does a frame take, plain versus enhanced?"""
import sys
import time
from pathlib import Path

# Run from anywhere: the project root is one level up from tools/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtGui import QColor, QImage, QPainter, QRegion
from PySide6.QtWidgets import QApplication

from avgui.themes import painter_for, theme_names

app = QApplication([])
W, H = 1180, 760
FRAMES = 40


class Fake:
    """Enough of a window for the painters to measure against."""

    def findChildren(self, _kind):
        return []

    def rect(self):
        from PySide6.QtCore import QRect
        return QRect(0, 0, W, H)

    def mapFromGlobal(self, point):
        return point

    live = None
    prompt = None


win = Fake()
whole = QRegion(0, 0, W, H)

print(f"  {'theme':<12}{'plain':>10}{'enhanced':>12}   budget at 14fps"
      f" = 71ms")
for key, _label, _note in theme_names():
    fn = painter_for(key)
    if fn is None:
        continue
    timings = []
    for rich in (False, True):
        image = QImage(W, H, QImage.Format_ARGB32)
        p = QPainter(image)
        p.setRenderHint(QPainter.Antialiasing)
        # One warm-up frame, then the measured run.
        fn(p, W, H, win, whole, whole, 0.0, rich)
        start = time.perf_counter()
        for i in range(FRAMES):
            fn(p, W, H, win, whole, whole, i * 0.07, rich)
        timings.append((time.perf_counter() - start) / FRAMES * 1000)
        p.end()
    plain, enhanced = timings
    flag = "" if enhanced < 71 else "   OVER BUDGET"
    print(f"  {key:<12}{plain:>8.1f}ms{enhanced:>10.1f}ms{flag}")
