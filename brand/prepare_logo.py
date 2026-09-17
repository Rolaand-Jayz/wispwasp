"""
Turns the supplied logo into assets the app can use.

The source already carries an alpha channel - what looks like a white
background in a viewer is transparency. So there is no colour to key out;
the work is trimming the very generous empty margin and splitting the
lockup so the mark can be used alone where the wordmark would be too wide.

Pixels are handled through numpy rather than one at a time: the source is
2816x1536, which is over four million pixels and far too slow in a Python
loop.
"""
import sys
from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

SRC = Path.home() / "Downloads" / "Firefly.png"
OUT = Path(__file__).resolve().parent

app = QApplication([])

img = QImage(str(SRC))
if img.isNull():
    print(f"could not read {SRC}")
    sys.exit(1)
img = img.convertToFormat(QImage.Format_RGBA8888)
w, h = img.width(), img.height()
print(f"source: {w}x{h}")

ptr = img.constBits()
arr = np.frombuffer(ptr, dtype=np.uint8, count=h * w * 4).reshape(h, w, 4)
alpha = arr[:, :, 3]

opaque = int((alpha > 8).sum())
print(f"non-transparent pixels: {opaque:,} "
      f"({100 * opaque / (w * h):.1f}% of the canvas)")

if opaque == 0:
    print("the image is entirely transparent; nothing to do")
    sys.exit(1)


def bounds(mask):
    ys, xs = np.where(mask)
    return xs.min(), ys.min(), xs.max(), ys.max()


def save_crop(x0, y0, x1, y1, name, pad=2):
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(w - 1, x1 + pad)
    y1 = min(h - 1, y1 + pad)
    crop = img.copy(int(x0), int(y0), int(x1 - x0 + 1), int(y1 - y0 + 1))
    path = OUT / name
    crop.save(str(path))
    print(f"  {name:<24} {crop.width()}x{crop.height()}")
    return crop


mask = alpha > 8
x0, y0, x1, y1 = bounds(mask)
print(f"content bounds: x {x0}-{x1}, y {y0}-{y1}")
print("writing:")
save_crop(x0, y0, x1, y1, "wispwasp_logo.png")

# Split mark from wordmark by finding the widest empty band between them,
# rather than assuming a fixed proportion.
rows = mask.sum(axis=1)
lo, hi = int(y0 + (y1 - y0) * 0.35), int(y0 + (y1 - y0) * 0.9)
best = None
start = None
for y in range(lo, hi):
    if rows[y] == 0:
        if start is None:
            start = y
    elif start is not None:
        if best is None or (y - start) > (best[1] - best[0]):
            best = (start, y)
        start = None
if start is not None and (hi - start) > (0 if best is None
                                         else best[1] - best[0]):
    best = (start, hi)

if best:
    split = (best[0] + best[1]) // 2
    print(f"gap between mark and wordmark: y {best[0]}-{best[1]}")
    top = mask[:split, :]
    bx0, by0, bx1, by1 = bounds(top)
    save_crop(bx0, by0, bx1, by1, "wispwasp_mark.png")

    bottom = mask[split:, :]
    cx0, cy0, cx1, cy1 = bounds(bottom)
    save_crop(cx0, cy0 + split, cx1, cy1 + split, "wispwasp_wordmark.png")
else:
    print("no clear gap found; only the full lockup was written")
