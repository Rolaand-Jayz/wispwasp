"""
Does the enhance flag actually change what is drawn?

A flag that arrives and is ignored passes every "it paints without
raising" test. The only honest check is to render both and compare the
pixels - which is how the scallop and lozenge patterns were caught
silently ignoring theirs.
"""
import sys
from pathlib import Path

# Run from anywhere: the project root is one level up.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QPainter, QRegion
from PySide6.QtWidgets import QApplication

from avgui.themes import options_for, painter_for, theme_names

app = QApplication([])
W, H = 900, 600


class Fake:
    def findChildren(self, _kind):
        return []

    def rect(self):
        return QRect(0, 0, W, H)

    def mapFromGlobal(self, point):
        return point

    live = None
    prompt = None


def render(fn, rich, phase=0.0):
    image = QImage(W, H, QImage.Format_ARGB32)
    image.fill(0)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    whole = QRegion(0, 0, W, H)
    fn(p, W, H, Fake(), whole, whole, phase, rich)
    p.end()
    return image


def difference(a, b):
    """Fraction of pixels that differ at all."""
    differing = 0
    total = 0
    for y in range(0, H, 3):
        for x in range(0, W, 3):
            total += 1
            if a.pixel(x, y) != b.pixel(x, y):
                differing += 1
    return differing / max(1, total)


print(f"  {'theme':<12}{'pixels changed by the enhance flag':>38}")
worst = None
for key, _label, _note in theme_names():
    fn = painter_for(key)
    if fn is None:
        continue
    if "enhance" not in options_for(key):
        # A theme with no enhanced artwork does not offer the toggle,
        # so there is nothing here to check.
        print(f"  {key:<12}{'no enhanced set yet':>38}")
        continue
    share = difference(render(fn, False), render(fn, True))
    # The bar is "did anything change at all", not "did a lot change".
    # How much moves depends on how much of the window the enhanced
    # elements happen to cover: kawaii swaps only its bows and hearts,
    # a small share of the pixels but perfectly correct. A flag that
    # never arrives produces exactly zero, which is what this catches.
    flag = "" if share > 0.001 else "   <-- flag appears to be ignored"
    print(f"  {key:<12}{share * 100:>32.1f}%{flag}")
    if share <= 0.001:
        worst = key

if worst:
    print(f"\n  {worst} barely changes: check the flag reaches the drawing")
    raise SystemExit(1)
print("\n  every theme draws differently with it on")
