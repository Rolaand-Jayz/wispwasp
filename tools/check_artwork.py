"""
Does decoration ever touch a generated image?

The exclusion lives in shared code, so in principle it covers every
theme. In principle is not evidence: a painter that ignores the region
it is handed would still wash over the artwork, and only looking at the
pixels can tell. Thumbnails are filled with exact flat colours, so any
tint at all shows as a mismatch.
"""
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication

from avcore.catalog import Catalog
from avcore.config import Settings
from avcore.engine import Engine
from avgui import theme
from avgui.themes import options_for, theme_names
from avgui.window import MainWindow
from demo_stubs import write_png

app = QApplication([])
tmp = Path("_artworkcheck")
shutil.rmtree(tmp, ignore_errors=True)
(tmp / "out").mkdir(parents=True)

TINTS = [(255, 255, 255), (0, 255, 0), (255, 0, 0), (0, 0, 255)]

s = Settings.load(path=tmp / "settings.json")
s.set("paths.overlay_dir", str(tmp / "out"))
s.set("paths.manual_dir", str(tmp / "out"))
s.set("ui.layout", "hybrid")
s.set("ui.decor_animate", True)
s.save()
theme.apply_to(app, s)
eng = Engine(s)
eng.catalog = Catalog(tmp / "c.json")

for i, tint in enumerate(TINTS):
    path = tmp / "out" / f"pic_{i}.png"
    write_png(path, 640, 360, tint)
    os.utime(path, (time.time() - i * 60,) * 2)

win = MainWindow(eng)
win.resize(1180, 760)
win.show()


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


pump(1.5)
win.show_panel("gallery")
pump(1.2)


def sample_thumbnails():
    """Colour at the centre of each thumbnail, as actually rendered."""
    shot = app.primaryScreen().grabWindow(win.winId()).toImage()
    # The capture may be scaled by the display; work in its own space.
    sx = shot.width() / win.width()
    sy = shot.height() / win.height()
    found = []
    for index in range(win.gallery.grid.count()):
        thumb = win.gallery.grid.itemAt(index).widget()
        pixmap = thumb.image.pixmap()
        if pixmap is None or pixmap.isNull():
            continue
        top_left = thumb.image.mapTo(win, thumb.image.rect().topLeft())
        cx = (top_left.x() + thumb.image.width() / 2) * sx
        cy = (top_left.y() + thumb.image.height() / 2) * sy
        pixel = shot.pixel(int(cx), int(cy))
        found.append((thumb.path.name,
                      ((pixel >> 16) & 255, (pixel >> 8) & 255, pixel & 255)))
    return found


expected = {f"pic_{i}.png": tint for i, tint in enumerate(TINTS)}
failures = []

print(f"  {'theme':<12}{'mode':<10}{'worst drift from the true colour':>34}")
for key, _label, _note in theme_names():
    modes = [False]
    if "enhance" in options_for(key):
        modes.append(True)
    for rich in modes:
        s.set("ui.decor_theme", key)
        s.set("ui.decor_enhanced", rich)
        s.save()
        win._apply_decor()
        pump(0.7)
        win.decor._remeasure()
        pump(0.4)

        worst = 0
        worst_name = ""
        for name, got in sample_thumbnails():
            want = expected.get(name)
            if want is None:
                continue
            drift = max(abs(a - b) for a, b in zip(got, want))
            if drift > worst:
                worst, worst_name = drift, name
        mode = "enhanced" if rich else "plain"
        flag = "" if worst <= 2 else f"   <-- {worst_name} tinted"
        print(f"  {key:<12}{mode:<10}{worst:>30}{flag}")
        if worst > 2:
            failures.append(f"{key} ({mode}): {worst_name} off by {worst}")

eng.shutdown()
shutil.rmtree(tmp, ignore_errors=True)

if failures:
    print("\n  decoration is tinting artwork:")
    for line in failures:
        print(f"    {line}")
    raise SystemExit(1)
print("\n  no theme touches a generated image")
