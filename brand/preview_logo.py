"""Previews the prepared assets on the app's own background colours."""
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

HERE = Path(__file__).resolve().parent
SLATE = "#1A1F26"
PANEL = "#222932"

app = QApplication([])

items = [
    ("wispwasp_logo.png", "full lockup", 300),
    ("wispwasp_mark.png", "mark only", 220),
    ("wispwasp_wordmark.png", "wordmark, at sidebar width (168px)", 148),
]

sheet = QImage(560, 640, QImage.Format_ARGB32)
sheet.fill(QColor(SLATE))
p = QPainter(sheet)
p.setRenderHint(QPainter.SmoothPixmapTransform)
p.setRenderHint(QPainter.Antialiasing)

y = 24
for name, label, target_w in items:
    img = QImage(str(HERE / name))
    if img.isNull():
        continue
    scaled = img.scaledToWidth(target_w, Qt.SmoothTransformation)
    # Panel colour behind it, since that is what the sidebar uses.
    p.fillRect(QRectF(20, y, 520, scaled.height() + 30), QColor(PANEL))
    p.drawImage(QRectF(30, y + 10, scaled.width(), scaled.height()), scaled)
    p.setPen(QColor("#8A94A3"))
    p.setFont(QFont("Segoe UI", 9))
    p.drawText(QRectF(30, y + scaled.height() + 12, 500, 18), Qt.AlignLeft,
               f"{label}   ({img.width()}x{img.height()} source)")
    y += scaled.height() + 46

p.end()
out = HERE / "logo_preview.png"
sheet.save(str(out))
print(f"wrote {out}")
