"""
Layout switching test.

The claim being checked is that switching reparents the same panel objects
rather than rebuilding them, and that no widget gets destroyed by Qt's
parent ownership along the way.
"""
import time

from PySide6.QtWidgets import QApplication

from avcore.config import Settings
from avcore.engine import Engine
from avgui import theme
from avgui.window import MainWindow
from demo_stubs import install_stubs

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  {'PASS' if cond else '*** FAIL ***':<14} {name}"
          + (f"  [{detail}]" if detail else ""))


app = QApplication([])
app.setStyleSheet(theme.QSS)

s = Settings.load()
s.set("ui.layout", "hybrid")
eng = Engine(s)
install_stubs(eng, autostart=True)
win = MainWindow(eng)
win.resize(1200, 760)
win.show()
eng.start()


def pump(seconds):
    """Let Qt process events without blocking the loop."""
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.02)


def wait_for(predicate, seconds=30):
    """
    Wait for something to happen rather than guessing how long it takes.

    A fixed sleep here was marginal: a demo cycle is a 3s clip plus a 2.4s
    render, so seven seconds passed on an idle machine and failed when the
    build was compiling in the background.
    """
    end = time.time() + seconds
    while time.time() < end:
        if predicate():
            return True
        app.processEvents()
        time.sleep(0.05)
    return False


print("=== panels are created once ===")
ids = {k: id(p) for k, p in win._panels.items()}
check("started in hybrid", win.layout_name == "hybrid")
# A machine without ComfyUI opens on Setup, so the Live page is asked for
# explicitly rather than assumed to be showing.
win.show_panel("live")
pump(0.2)
check("prompt strip visible in hybrid", win.live.strip.isVisible())

wait_for(lambda: eng.snapshot().get("image"))
first_image = eng.snapshot().get("image")
check("engine produced an image before switching",
      first_image is not None)

print("\n=== cycling every layout twice ===")
order = ["sidebar", "split", "hybrid", "split", "sidebar", "hybrid"]
for name in order:
    win.set_layout(name)
    pump(0.6)
    same = all(id(win._panels[k]) == ids[k] for k in ids)
    # Touching a widget whose C++ side was destroyed raises RuntimeError,
    # which is exactly the failure this test exists to catch.
    try:
        win.live.status.text()
        win.prompt.box.toPlainText()
        win.gallery.count.text()
        win.settings.suffix.text()
        alive = True
    except RuntimeError as exc:
        alive = False
        print(f"      widget destroyed: {exc}")
    check(f"{name}: same objects reused, all widgets alive", same and alive)

print("\n=== layout-specific structure ===")
# Page counts include Customize, which has no nav entry of its own - it
# unrolls under Settings - but still needs a page in the stack.
win.set_layout("hybrid")
pump(0.3)
check("hybrid shows the strip", win.live.strip.isVisible())
check("hybrid nav lists every panel", len(win._page_keys) == 6,
      str(win._page_keys))

win.set_layout("sidebar")
pump(0.3)
check("panels layout hides the strip", not win.live.strip.isVisible())
check("panels nav lists every panel", len(win._page_keys) == 6,
      str(win._page_keys))

win.set_layout("split")
pump(0.3)
check("split hides the strip", not win.live.strip.isVisible())
check("split merges live and prompt into one entry",
      len(win._page_keys) == 5, str(win._page_keys))
check("every layout carries the Customize sub-page",
      "customize" in win._page_keys)
check("split built a splitter", win.splitter is not None)
check("splitter holds live and prompt", win.splitter.count() == 2)

print("\n=== nothing was lost across the switches ===")
check("overlay image survived", eng.snapshot().get("image") is not None)
check("still listening", eng.snapshot().get("listening") is True)
wait_for(lambda: eng.snapshot().get("generated", 0) >= 1)
snap = eng.snapshot()
check("engine kept generating through the switches",
      snap.get("generated", 0) >= 1)
check("live panel is showing the current image",
      win.live.preview._path == snap.get("image"))

print("\n=== a dragged splitter size is remembered ===")
win.set_layout("split")
pump(0.6)
initial = win.splitter.sizes()
print(f"    default split: {initial}")
# Guard against the whole check passing on zeroes, which would verify
# nothing at all.
check("splitter actually has a width", sum(initial) > 100)
check("live side gets the larger share by default",
      initial[0] > initial[1])

win.splitter.setSizes([760, 340])
pump(0.4)
settled = win.splitter.sizes()
print(f"    after dragging: {settled}")
win.set_layout("hybrid")
pump(0.4)
win.set_layout("split")
pump(0.6)
restored = win.splitter.sizes()
print(f"    after a round trip: {restored}")
check("splitter kept its proportions",
      sum(restored) > 100 and abs(restored[0] - settled[0]) < 20)

eng.shutdown()
bad = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed")
if bad:
    print("FAILURES:")
    for n in bad:
        print(f"  - {n}")
    raise SystemExit(1)
print("layout switching is safe")
