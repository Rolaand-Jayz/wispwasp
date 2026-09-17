"""
Builds the square app icon from the wasp in the mark.

The lockup is far too wide for an icon - Windows would letterbox it into a
sliver. So the wasp is isolated from the right-hand side of the mark and
centred on a square canvas with a little breathing room.

Also writes a .ico with the sizes Windows actually asks for. Each entry is
stored as PNG, which Vista and later accept, so no palette conversion is
needed.
"""
import struct
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
SIZES = [16, 24, 32, 48, 64, 128, 256]

app = QApplication([])

mark = QImage(str(ASSETS / "wispwasp_mark.png"))
if mark.isNull():
    raise SystemExit("wispwasp_mark.png is missing; run prepare_logo first")
mark = mark.convertToFormat(QImage.Format_RGBA8888)
w, h = mark.width(), mark.height()

ptr = mark.constBits()
arr = np.frombuffer(ptr, dtype=np.uint8, count=h * w * 4).reshape(h, w, 4)
alpha = arr[:, :, 3] > 8

# The waveform runs into the wasp from the left. Column density falls away
# across the waveform and rises again over the body, so the wasp is taken
# as the densest run at the right-hand end rather than a guessed fraction.
cols = alpha.sum(axis=0)
half = cols[w // 2:]
threshold = half.max() * 0.18
start = w // 2
for x in range(w // 2, w):
    if cols[x] > threshold:
        start = x
        break

sub = alpha[:, start:]
ys, xs = np.where(sub)
x0, x1 = start + xs.min(), start + xs.max()
y0, y1 = ys.min(), ys.max()
print(f"wasp bounds: x {x0}-{x1}, y {y0}-{y1}")

crop = mark.copy(int(x0), int(y0), int(x1 - x0 + 1), int(y1 - y0 + 1))

# Square canvas with a margin, so the shape is not jammed against the edge
# once Windows rounds the icon's corners in some contexts.
side = int(max(crop.width(), crop.height()) * 1.14)
canvas = QImage(side, side, QImage.Format_ARGB32)
canvas.fill(Qt.transparent)
p = QPainter(canvas)
p.setRenderHint(QPainter.SmoothPixmapTransform)
p.drawImage((side - crop.width()) // 2, (side - crop.height()) // 2, crop)
p.end()

canvas.save(str(ASSETS / "wispwasp_icon.png"))
print(f"wrote wispwasp_icon.png ({side}x{side})")

# --- the .ico itself ---------------------------------------------------
# Written by hand rather than with an image library: the format is a small
# header plus one PNG per size, and this avoids adding a dependency for
# something used once at build time.
pngs = []
for size in SIZES:
    scaled = canvas.scaled(size, size, Qt.KeepAspectRatio,
                           Qt.SmoothTransformation)
    tmp = HERE / f"_icon_{size}.png"
    scaled.save(str(tmp))
    pngs.append((size, tmp.read_bytes()))
    tmp.unlink()

ico = ASSETS / "wispwasp.ico"
with open(ico, "wb") as fh:
    fh.write(struct.pack("<HHH", 0, 1, len(pngs)))     # reserved, type, count
    offset = 6 + 16 * len(pngs)
    for size, data in pngs:
        # 256 is stored as 0 in the directory, which is the convention.
        dim = 0 if size >= 256 else size
        fh.write(struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32,
                             len(data), offset))
        offset += len(data)
    for _size, data in pngs:
        fh.write(data)

print(f"wrote wispwasp.ico ({ico.stat().st_size // 1024} KB, "
      f"{len(pngs)} sizes: {', '.join(str(s) for s, _ in pngs)})")

# --- a preview at real sizes -------------------------------------------
sheet = QImage(560, 150, QImage.Format_ARGB32)
sheet.fill(QColor("#222932"))
sp = QPainter(sheet)
sp.setRenderHint(QPainter.SmoothPixmapTransform)
x = 20
for size in [128, 64, 48, 32, 24, 16]:
    scaled = canvas.scaled(size, size, Qt.KeepAspectRatio,
                           Qt.SmoothTransformation)
    sp.drawImage(x, 20 + (128 - size) // 2, scaled)
    sp.setPen(QColor("#8A94A3"))
    sp.drawText(x, 166 - 20, f"{size}")
    x += size + 22
sp.end()
sheet.save(str(HERE / "icon_preview.png"))
print("wrote icon_preview.png")
