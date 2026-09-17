"""Renders the icon concepts onto one sheet for comparison."""
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).parent))
from concepts import CONCEPTS, PANEL, SLATE

app = QApplication([])

BIG = 180
SMALLS = [48, 32, 16]
PAD = 26
ROW_H = BIG + 78
sheet_w = PAD * 2 + BIG + 40 + sum(s + 26 for s in SMALLS)
sheet_h = PAD * 2 + ROW_H * len(CONCEPTS)

sheet = QImage(sheet_w, sheet_h, QImage.Format_ARGB32)
sheet.fill(QColor(SLATE))
p = QPainter(sheet)
p.setRenderHint(QPainter.Antialiasing)
p.setRenderHint(QPainter.SmoothPixmapTransform)


def draw(svg, x, y, size):
    r = QSvgRenderer(QByteArray(svg.encode()))
    # Render at 4x then scale down, so small sizes get properly
    # antialiased rather than rasterised straight onto a tiny grid.
    hi = QImage(size * 4, size * 4, QImage.Format_ARGB32)
    hi.fill(Qt.transparent)
    hp = QPainter(hi)
    hp.setRenderHint(QPainter.Antialiasing)
    r.render(hp, QRectF(0, 0, size * 4, size * 4))
    hp.end()
    p.drawImage(QRectF(x, y, size, size),
                hi.scaled(size, size, Qt.KeepAspectRatio,
                          Qt.SmoothTransformation))


label = QFont("Segoe UI", 10)
small_font = QFont("Segoe UI", 8)

for i, (name, svg) in enumerate(CONCEPTS):
    top = PAD + i * ROW_H
    # Panel-coloured plate behind each row, as the icon will sit on chrome.
    p.fillRect(QRectF(PAD - 10, top - 10, sheet_w - PAD * 2 + 20,
                      ROW_H - 14), QColor(PANEL))
    draw(svg, PAD, top, BIG)

    p.setPen(QColor("#E4E8EE"))
    p.setFont(label)
    p.drawText(QRectF(PAD, top + BIG + 8, 300, 22), Qt.AlignLeft,
               f"{i + 1}.  {name.replace('_', ' ')}")

    x = PAD + BIG + 40
    for s in SMALLS:
        y = top + (BIG - s) // 2
        draw(svg, x, y, s)
        p.setPen(QColor("#8A94A3"))
        p.setFont(small_font)
        p.drawText(QRectF(x - 8, y + s + 8, s + 16, 16), Qt.AlignHCenter,
                   f"{s}px")
        x += s + 26

p.end()
out = Path(__file__).parent / "concepts.png"
sheet.save(str(out))
print(f"wrote {out} ({sheet_w}x{sheet_h})")
