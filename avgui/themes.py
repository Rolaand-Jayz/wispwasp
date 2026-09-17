"""
The decorative themes.

Each painter takes (painter, width, height, window, clip, phase) and
fills the clip region. `phase` advances only while animation is on, so a
painter that reads it stands still when "Fancy" is off rather than
needing a separate still version.
"""

import math
import random

from PySide6.QtCore import QPoint, QRect, QRectF, QPointF, Qt
from PySide6.QtGui import (
    QColor, QConicalGradient, QCursor, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
    QRadialGradient,
    QRegion, QTransform,
)
from PySide6.QtWidgets import QSplitter, QWidget

THEMES = [
    ("none", "None", "The plain interface."),
    ("halloween", "Halloween",
     "Lantern wallpaper, cobwebs, spiders and candlelight."),
    ("starfield", "Starfield",
     "Twinkling stars, nebula light and the occasional streak."),
    ("underwater", "Underwater",
     "Sunlit water, rising bubbles, weed, fish and a few crabs."),
    ("kawaii", "Kawaii",
     "Pastel skies, fluffy clouds, bows, hearts and sparkles."),
    ("cryptic", "Cryptic",
     "Turning sigils, drifting marks, and something watching."),
    ("aero", "Frutiger Aero",
     "Wet glass, aqua light, ribbons and a lot of shine."),
    ("desert", "Desert",
     "Dusty orange sky, sand, heat haze and old stone."),
    ("arctic", "Arctic",
     "Ice, snow, pale blue light, and somebody waddling."),
]

# What each theme brings with it. The options panel is built from this
# rather than from a fixed list, so a theme without sounds never shows a
# sound toggle - an option that does nothing is worse than no option,
# because the user has to work out that it does nothing.
OPTIONS = {
    "halloween": ("animate", "sounds", "enhance"),
    "starfield": ("animate", "sounds", "enhance"),
    "underwater": ("animate", "sounds", "enhance"),
    "kawaii": ("animate", "sounds", "enhance"),
    "cryptic": ("animate", "sounds", "enhance"),
    "aero": ("animate", "sounds", "enhance"),
    "desert": ("animate", "sounds", "enhance"),
    "arctic": ("animate", "sounds", "enhance"),
}


# Names that have changed. A setting saved under the old one still
# resolves, instead of quietly falling back to no decoration.
ALIASES = {"sanrio": "kawaii"}


def canonical(name):
    """The current key for a theme, following any rename."""
    key = (name or "").strip().lower()
    return ALIASES.get(key, key)


def options_for(name):
    """Which extra options a theme offers. Empty for plain themes."""
    return OPTIONS.get(canonical(name), ())


# What each theme calls its options. "Spooky sounds" is right for
# Halloween and absurd for a starfield, so the wording belongs to the
# theme rather than to the panel.
OPTION_LABELS = {
    "halloween": {"animate": "Fancy", "sounds": "Spooky sounds"},
    "starfield": {"animate": "Fancy", "sounds": "Cosmic sounds"},
    "underwater": {"animate": "Fancy", "sounds": "Watery sounds"},
    "kawaii": {"animate": "Fancy", "sounds": "Cute sounds"},
    "cryptic": {"animate": "Fancy", "sounds": "Arcane sounds"},
    "aero": {"animate": "Fancy", "sounds": "Glassy sounds"},
    "desert": {"animate": "Fancy", "sounds": "Desert sounds"},
    "arctic": {"animate": "Fancy", "sounds": "Icy sounds"},
}

DEFAULT_LABELS = {"animate": "Animate", "sounds": "Theme sounds",
                  "enhance": "Enhance visuals"}


def option_label(theme, option):
    """What to call an option under a given theme."""
    per_theme = OPTION_LABELS.get(canonical(theme), {})
    return per_theme.get(option, DEFAULT_LABELS.get(option, option))


# ---- shared pieces ----------------------------------------------------

def _web(p, x, y, size, start, end, alpha=96, torn=0.0, seed=0,
         rich=False):
    if rich and not torn:
        # The torn variant is bespoke and has no enhanced twin, so
        # it keeps its own drawing either way.
        _web_rich(p, x, y, size)
        return
    rng = random.Random(seed or int(x * 7 + y * 13 + size))
    pen = QPen(QColor(228, 234, 246, alpha))
    pen.setWidthF(1.15)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    spokes = 8
    angles = [math.radians(start + (end - start) * i / (spokes - 1))
              for i in range(spokes)]
    for a in angles:
        if torn and rng.random() < torn * 0.5:
            continue
        reach = size * (rng.uniform(0.45, 0.8)
                        if torn and rng.random() < torn else 1.0)
        p.drawLine(QPointF(x, y),
                   QPointF(x + math.cos(a) * reach,
                           y + math.sin(a) * reach))
    for ring in range(1, 7):
        r = size * ring / 6.5
        for i in range(spokes - 1):
            if torn and rng.random() < torn:
                continue
            a1, a2 = angles[i], angles[i + 1]
            mid = (a1 + a2) / 2
            path = QPainterPath(QPointF(x + math.cos(a1) * r,
                                        y + math.sin(a1) * r))
            path.quadTo(QPointF(x + math.cos(mid) * r * 0.85,
                                y + math.sin(mid) * r * 0.85),
                        QPointF(x + math.cos(a2) * r,
                                y + math.sin(a2) * r))
            p.drawPath(path)


def _lace(p, y, width, seed=5):
    """A scalloped web fringe. Reads as cobweb where straight drips read
    as a barcode, which is what an earlier attempt looked like."""
    rng = random.Random(seed)
    p.setPen(QPen(QColor(224, 230, 242, 56), 1.0))
    p.setBrush(Qt.NoBrush)
    x = 0
    while x < width:
        span = rng.uniform(46, 92)
        path = QPainterPath(QPointF(x, y))
        path.quadTo(QPointF(x + span / 2, y + rng.uniform(7, 17)),
                    QPointF(x + span, y))
        p.drawPath(path)
        x += span


def _spider(p, x, y, drop, scale=1.0, sway=0.0, rich=False):
    if rich:
        _spider_rich(p, x + sway, y, drop, scale)
        return
    """A spider on a thread. `sway` swings both thread and body, so the
    whole thing moves as one rather than the body sliding on a fixed
    line."""
    foot = QPointF(x + sway, y + drop)
    p.setPen(QPen(QColor(226, 232, 244, 100), 1.0))
    thread = QPainterPath(QPointF(x, y))
    thread.quadTo(QPointF(x + sway * 0.35, y + drop * 0.6), foot)
    p.setBrush(Qt.NoBrush)
    p.drawPath(thread)

    bx, by = foot.x(), foot.y()
    p.setBrush(QColor(16, 14, 20, 240))
    p.setPen(QPen(QColor(220, 224, 236, 150), 1.0))
    p.drawEllipse(QPointF(bx, by + 7 * scale), 6.5 * scale, 7.5 * scale)
    p.drawEllipse(QPointF(bx, by), 4.0 * scale, 4.0 * scale)
    for side in (-1, 1):
        for i, spread in enumerate((10, 13, 12, 9)):
            ay = by + (2 + i * 3.5) * scale
            p.drawLine(QPointF(bx, ay),
                       QPointF(bx + side * spread * scale,
                               ay + (i - 1.5) * 4 * scale))


def _lantern(p, size, rich=False):
    if rich:
        _lantern_rich(p, size)
        return
    r = size / 2
    body = QPainterPath()
    body.addEllipse(QPointF(0, 0), r, r * 0.86)
    p.drawPath(body)
    for offset in (-0.52, 0.0, 0.52):
        rib = QPainterPath(QPointF(r * offset, -r * 0.78))
        rib.quadTo(QPointF(r * offset * 1.9, 0),
                   QPointF(r * offset, r * 0.78))
        p.drawPath(rib)
    stem = QPainterPath(QPointF(-r * 0.11, -r * 0.84))
    stem.lineTo(QPointF(-r * 0.07, -r * 1.16))
    stem.lineTo(QPointF(r * 0.12, -r * 1.12))
    stem.lineTo(QPointF(r * 0.09, -r * 0.84))
    p.drawPath(stem)
    for side in (-1, 1):
        eye = QPainterPath(QPointF(side * r * 0.46, -r * 0.24))
        eye.lineTo(QPointF(side * r * 0.14, -r * 0.10))
        eye.lineTo(QPointF(side * r * 0.44, r * 0.06))
        eye.closeSubpath()
        p.drawPath(eye)
    mouth = QPainterPath(QPointF(-r * 0.52, r * 0.28))
    for i, x in enumerate((-0.34, -0.16, 0.02, 0.20, 0.38, 0.52)):
        mouth.lineTo(QPointF(r * x, r * (0.46 if i % 2 else 0.24)))
    mouth.lineTo(QPointF(r * 0.44, r * 0.56))
    mouth.lineTo(QPointF(-r * 0.44, r * 0.56))
    mouth.closeSubpath()
    p.drawPath(mouth)


def _wallpaper(p, rect, size=32, gap=86, rich=False):
    """Lanterns tiled like gift wrap, canted alternately."""
    p.save()
    p.setClipRect(rect, Qt.IntersectClip)
    p.setPen(QPen(QColor(158, 104, 206, 44), 1.1))
    p.setBrush(Qt.NoBrush)
    row = 0
    y = rect.top() + gap * 0.45
    while y < rect.bottom() + gap:
        x = rect.left() + (gap * 0.5 if row % 2 else 0) + gap * 0.4
        col = 0
        while x < rect.right() + gap:
            angle = 14 if (row + col) % 2 == 0 else -14
            p.save()
            p.setTransform(QTransform().translate(x, y).rotate(angle), True)
            _lantern(p, size, rich)
            p.restore()
            x += gap
            col += 1
        y += gap * 0.9
        row += 1
    p.restore()


def _candle(p, x, base, height, phase, width=7.0, rich=False):
    if rich:
        _candle_rich(p, x, base, height, phase, width)
        return
    sway = math.sin(phase) * 1.5 + math.sin(phase * 2.7) * 0.7
    flare = 1.0 + math.sin(phase * 1.9) * 0.16

    pool = QRadialGradient(QPointF(x, base), 46 * flare)
    pool.setColorAt(0.0, QColor(255, 168, 70, 62))
    pool.setColorAt(1.0, QColor(255, 168, 70, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(pool)
    p.drawEllipse(QPointF(x, base), 46 * flare, 26 * flare)

    body = QRectF(x - width / 2, base - height, width, height)
    p.setBrush(QColor(226, 214, 196, 205))
    p.setPen(QPen(QColor(120, 108, 96, 140), 0.8))
    p.drawRoundedRect(body, 2, 2)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(198, 184, 166, 190))
    p.drawEllipse(QRectF(body.left(), body.top() - 1.6, width, 3.2))

    wick = base - height - 2.5
    p.setPen(QPen(QColor(40, 34, 30, 220), 1.0))
    p.drawLine(QPointF(x, base - height), QPointF(x, wick))

    halo = QRadialGradient(QPointF(x, wick - 5), 22 * flare)
    halo.setColorAt(0.0, QColor(255, 176, 72, 120))
    halo.setColorAt(1.0, QColor(255, 140, 40, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(halo)
    p.drawEllipse(QPointF(x, wick - 5), 22 * flare, 26 * flare)

    flame = QPainterPath(QPointF(x - 3.1, wick))
    flame.quadTo(QPointF(x - 4.4, wick - 7 * flare),
                 QPointF(x + sway, wick - 13 * flare))
    flame.quadTo(QPointF(x + 4.4, wick - 7 * flare),
                 QPointF(x + 3.1, wick))
    flame.quadTo(QPointF(x, wick + 1.6), QPointF(x - 3.1, wick))
    p.setBrush(QColor(255, 166, 54, 235))
    p.drawPath(flame)

    core = QPainterPath(QPointF(x - 1.5, wick - 0.5))
    core.quadTo(QPointF(x - 2.0, wick - 4.5 * flare),
                QPointF(x + sway * 0.6, wick - 7.5 * flare))
    core.quadTo(QPointF(x + 2.0, wick - 4.5 * flare),
                QPointF(x + 1.5, wick - 0.5))
    p.setBrush(QColor(255, 232, 176, 240))
    p.drawPath(core)


def _sidebar_width(win):
    """The sidebar is a fixed-width frame; ask it rather than guess."""
    for child in win.findChildren(QWidget):
        if child.objectName() == "sidebar" and child.isVisible():
            return child.width()
    return 132


def _splitters(p, win):
    """Recolour the divider handles to pumpkin."""
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(186, 98, 28, 165))
    for split in win.findChildren(QSplitter):
        if not split.isVisible():
            continue
        for i in range(1, split.count()):
            handle = split.handle(i)
            if handle is None or not handle.isVisible():
                continue
            top_left = handle.mapTo(win, QPoint(0, 0))
            p.drawRect(QRectF(top_left.x(), top_left.y(),
                              handle.width(), handle.height()))


def _candles(p, win, height, phase, sidebar, rich=False):
    """Three candles on the sidebar floor, under the OBS links."""
    lowest = 0
    for widget in win.findChildren(QWidget):
        if not widget.isVisible():
            continue
        try:
            top_left = widget.mapTo(win, QPoint(0, 0))
        except RuntimeError:
            continue
        if top_left.x() < sidebar and widget.width() < sidebar:
            lowest = max(lowest, top_left.y() + widget.height())
    base = min(height - 12, max(lowest + 30, height - 46))
    for x, tall, offset, width in ((30, 22, 0.0, 6.5),
                                   (58, 15, 2.1, 6.5),
                                   (84, 27, 4.3, 7.5)):
        if x < sidebar - 6:
            _candle(p, x, base, tall, phase + offset, width, rich)


def _tally_glow(p, win, live, phase):
    """
    Candlelight around the tally lamp.

    The colour follows what the lamp is actually doing rather than being
    fixed warm: red while live, amber while the GPU works, a dim ember at
    rest. A decorative glow that stayed orange through a live broadcast
    would be the theme telling a lie about the app's state.
    """
    tally = getattr(live, "tally", None) if live else None
    if tally is None or not tally.isVisible():
        return
    state = getattr(tally, "_state", "idle")
    colour, reach = {
        "live": (QColor(232, 64, 48), 30),
        "working": (QColor(240, 163, 46), 26),
    }.get(state, (QColor(170, 96, 40), 16))

    at = tally.mapTo(win, QPoint(0, 0))
    centre = QPointF(at.x() + tally.width() / 2,
                     at.y() + tally.height() / 2)
    # The same wobble the candles use, so the two read as one light
    # source rather than two unrelated effects.
    flare = 1.0 + math.sin(phase * 2.3) * 0.14 + math.sin(phase * 5.1) * 0.05
    glow = QRadialGradient(centre, reach * flare)
    glow.setColorAt(0.0, QColor(colour.red(), colour.green(), colour.blue(),
                                150))
    glow.setColorAt(0.45, QColor(colour.red(), colour.green(),
                                 colour.blue(), 60))
    glow.setColorAt(1.0, QColor(colour.red(), colour.green(),
                                colour.blue(), 0))
    p.setPen(Qt.NoPen)
    p.setBrush(glow)
    p.drawEllipse(centre, reach * flare, reach * flare)


def halloween(p, w, h, win, clip, safe, phase, rich=False):
    """
    Pumpkins, cobwebs, spiders and candlelight.

    The tint, candles and dividers are drawn outside the clip: they are
    placed deliberately, and a rectangular bite taken out of a candle's
    glow to dodge a nearby label would read as a fault rather than care.
    """
    tint = QLinearGradient(0, 0, 0, h)
    tint.setColorAt(0.0, QColor(64, 28, 8, 70))
    tint.setColorAt(0.55, QColor(30, 14, 26, 36))
    tint.setColorAt(1.0, QColor(46, 18, 34, 54))
    # Even the tint respects the artwork: a wash over a generated image
    # is still covering it.
    p.save()
    p.setClipRegion(safe, Qt.IntersectClip)
    p.fillRect(QRectF(0, 0, w, h), tint)
    p.restore()

    sidebar = _sidebar_width(win)
    live = getattr(win, "live", None)
    strip = getattr(live, "strip", None) if live else None
    strip_top = h
    if strip is not None and strip.isVisible():
        strip_top = strip.mapTo(win, QPoint(0, 0)).y()

    p.save()
    p.setClipRegion(clip, Qt.IntersectClip)

    _wallpaper(p, QRectF(0, 0, sidebar, h), rich=rich)
    _wallpaper(p, QRectF(sidebar, 0, w - sidebar, 38), size=24,
               gap=74, rich=rich)
    if strip_top < h:
        _wallpaper(p, QRectF(sidebar, strip_top, w - sidebar,
                             h - strip_top), size=26, gap=78,
                   rich=rich)

    _web(p, 0, 0, 132, 0, 90, alpha=70, rich=rich)
    _web(p, w, 0, 172, 90, 180, alpha=66, rich=rich)
    _web(p, w, h, 170, 180, 270, rich=rich)
    _lace(p, 38, w)

    # Two hanging spiders, swinging gently and out of step with each
    # other so they never look mechanical.
    _spider(p, w * 0.44, 38, 88, sway=math.sin(phase * 0.7) * 5.0,
            rich=rich)
    _spider(p, w * 0.78, 38, 46, scale=0.8,
            sway=math.sin(phase * 0.9 + 1.7) * 3.4, rich=rich)

    tally = getattr(live, "tally", None) if live else None
    if tally is not None and tally.isVisible():
        at = tally.mapTo(win, QPoint(0, 0))
        _web(p, at.x() - 22, at.y() - 18, 44, 0, 90, alpha=126)
    p.restore()

    p.save()
    p.setClipRegion(safe, Qt.IntersectClip)
    _splitters(p, win)
    _candles(p, win, h, phase, sidebar, rich)
    _tally_glow(p, win, live, phase)
    p.restore()




# ---- per-theme styling -------------------------------------------------
#
# Decoration may not paint on controls, so a theme changes their shape
# through the stylesheet instead. That keeps buttons legible and clickable
# while still letting them belong to the theme.

HALLOWEEN_QSS = """
/* Carved corners: one diagonal rounded, the other cut square. It reads
   as hand-cut rather than as a rounded rectangle, and costs none of the
   hit area. */
QPushButton {
    border-top-left-radius: 10px;
    border-bottom-right-radius: 10px;
    border-top-right-radius: 2px;
    border-bottom-left-radius: 2px;
    border: 1px solid #5C3A22;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #2E2620, stop:1 #241D19);
    color: #E8DCCB;
}
QPushButton:hover {
    border: 1px solid #8A5A2E;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #3A2E24, stop:1 #2B221C);
}
QPushButton:disabled {
    border: 1px solid #3A2C22;
    color: #6B5A4A;
}

/* The primary button is the lit one: a lantern rather than a flat
   colour. */
#primaryButton {
    border: 1px solid #7A3E12;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #F0902E, stop:0.5 #D9701C,
                                stop:1 #A84F10);
    color: #2A1405;
    font-weight: 600;
}
#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #FFA542, stop:0.5 #E87F26,
                                stop:1 #BC5C14);
}

/* The confirmations keep their own colours - green means applied and red
   means destroyed, whatever the theme - but take the carved shape. */
#confirmButton, #denyButton {
    border-top-left-radius: 10px;
    border-bottom-right-radius: 10px;
    border-top-right-radius: 2px;
    border-bottom-left-radius: 2px;
}

/* Inputs get the same cut, so the two halves of the interface do not
   disagree with each other. */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox,
QDoubleSpinBox {
    border-top-left-radius: 8px;
    border-bottom-right-radius: 8px;
    border-top-right-radius: 2px;
    border-bottom-left-radius: 2px;
    border: 1px solid #4A3527;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #A9702F;
}

#feedList {
    border: 1px solid #4A3527;
    border-top-left-radius: 8px;
    border-bottom-right-radius: 8px;
}
"""


STARFIELD_QSS = """
/* Soft capsules rather than carved corners: nothing in a starfield has a
   hard edge, so the controls should not either. */
QPushButton {
    border-radius: 13px;
    border: 1px solid #2F3A63;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #212844, stop:1 #191E36);
    color: #D9E2F7;
}
QPushButton:hover {
    border: 1px solid #5A78C8;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #2A3356, stop:1 #1F2642);
}
QPushButton:disabled {
    border: 1px solid #262E4A;
    color: #5A6484;
}

/* The primary button is the bright one in the sky. */
#primaryButton {
    border: 1px solid #3E6FC4;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #6FA8F0, stop:0.5 #4C82DC,
                                stop:1 #3358A8);
    color: #06101F;
    font-weight: 600;
}
#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #84B8FF, stop:0.5 #5B92EC,
                                stop:1 #3C66BC);
}

/* Confirm and Deny keep their own colours - green means applied and red
   means destroyed whatever the theme - but take the capsule shape. */
#confirmButton, #denyButton {
    border-radius: 13px;
}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox,
QDoubleSpinBox {
    border-radius: 10px;
    border: 1px solid #2C3558;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #5A86D8;
}

#feedList {
    border: 1px solid #2C3558;
    border-radius: 10px;
}
"""



# ---- starfield ---------------------------------------------------------

def _constellation(p, size, seed, rich=False):
    if rich:
        _constellation_rich(p, size, seed)
        return
    """
    A small cluster of stars with lines between them.

    The tiled motif for flat panels, matching what the lanterns do in
    Halloween: something repeating and quiet, so a panel reads as
    decorated rather than as empty space with stars thrown at it.
    """
    rng = random.Random(seed)
    points = []
    for _ in range(rng.randint(4, 6)):
        points.append(QPointF(rng.uniform(-size / 2, size / 2),
                              rng.uniform(-size / 2, size / 2)))
    pen = QPen(QColor(150, 176, 230, 34))
    pen.setWidthF(0.9)
    p.setPen(pen)
    for i in range(len(points) - 1):
        p.drawLine(points[i], points[i + 1])
    p.setPen(Qt.NoPen)
    for i, point in enumerate(points):
        p.setBrush(QColor(198, 214, 250, 70 if i % 2 else 48))
        r = 1.5 if i % 3 else 2.2
        p.drawEllipse(point, r, r)


def _star_pattern(p, rect, size=44, gap=104, seed=1, rich=False):
    """Constellations tiled across a panel, canted alternately."""
    p.save()
    p.setClipRect(rect, Qt.IntersectClip)
    row = 0
    y = rect.top() + gap * 0.45
    while y < rect.bottom() + gap:
        x = rect.left() + (gap * 0.5 if row % 2 else 0) + gap * 0.4
        col = 0
        while x < rect.right() + gap:
            angle = 12 if (row + col) % 2 == 0 else -12
            p.save()
            p.setTransform(QTransform().translate(x, y).rotate(angle), True)
            _constellation(p, size, seed + row * 31 + col * 7, rich)
            p.restore()
            x += gap
            col += 1
        y += gap * 0.9
        row += 1
    p.restore()


def _stars(p, w, h, phase, count=240, seed=7, rich=False):
    """
    Stationary stars that twinkle in place.

    Each keeps its own rate and offset, so the field never pulses as one
    - which is what makes a random scatter look like sky rather than like
    a string of fairy lights.
    """
    rng = random.Random(seed)
    p.setPen(Qt.NoPen)
    for _ in range(count):
        x = rng.uniform(0, w)
        y = rng.uniform(0, h)
        base = rng.uniform(0.7, 2.1)
        tint = rng.choice((
            (255, 255, 255), (206, 224, 255), (255, 234, 214),
            (222, 210, 255),
        ))
        rate = rng.uniform(0.6, 2.4)
        offset = rng.uniform(0, 6.28)
        twinkle = 0.55 + 0.45 * math.sin(phase * rate + offset)
        alpha = int(rng.uniform(70, 205) * twinkle)
        if alpha <= 6:
            continue
        if rich:
            _star_rich(p, x, y, base * (0.7 + 0.5 * twinkle), tint)
            continue
        p.setBrush(QColor(tint[0], tint[1], tint[2], alpha))
        size = base * (0.85 + 0.3 * twinkle)
        p.drawEllipse(QPointF(x, y), size, size)
        if base > 1.7:
            pen = QPen(QColor(tint[0], tint[1], tint[2], alpha // 2))
            pen.setWidthF(0.8)
            p.setPen(pen)
            reach = size * 3.2
            p.drawLine(QPointF(x - reach, y), QPointF(x + reach, y))
            p.drawLine(QPointF(x, y - reach), QPointF(x, y + reach))
            p.setPen(Qt.NoPen)


def _nebula(p, w, h):
    """Faint colour bloom in the corners, so the dark is not flat."""
    clouds = (
        (0, 0, (92, 70, 200), 0.46),
        (w, 0, (40, 110, 190), 0.40),
        (w * 0.2, h, (120, 60, 170), 0.42),
        (w, h * 0.78, (40, 120, 170), 0.36),
    )
    for cx, cy, rgb, spread in clouds:
        glow = QRadialGradient(QPointF(cx, cy), max(w, h) * spread)
        glow.setColorAt(0.0, QColor(rgb[0], rgb[1], rgb[2], 44))
        glow.setColorAt(1.0, QColor(rgb[0], rgb[1], rgb[2], 0))
        p.fillRect(QRectF(0, 0, w, h), glow)


def _shooting_star(p, w, h, phase):
    """
    One streak, now and then.

    On a slow cycle with a long gap: something that crosses the screen
    every few seconds stops being a surprise and starts being a
    distraction while you are trying to read.
    """
    period = 23.0
    t = (phase % period) / period
    if t > 0.13:            # visible for roughly three seconds in twenty
        return
    # A different path each pass, chosen from the cycle number so it does
    # not jump about mid-flight.
    rng = random.Random(int(phase // period))
    start_x = rng.uniform(w * 0.25, w * 0.95)
    start_y = rng.uniform(h * 0.05, h * 0.35)
    length = rng.uniform(120, 260)
    angle = math.radians(rng.uniform(150, 200))

    travel = t / 0.13
    head = QPointF(start_x + math.cos(angle) * length * travel,
                   start_y + math.sin(angle) * length * travel)
    tail = QPointF(head.x() - math.cos(angle) * 70,
                   head.y() - math.sin(angle) * 70)
    fade = math.sin(math.pi * travel)

    trail = QLinearGradient(tail, head)
    trail.setColorAt(0.0, QColor(190, 214, 255, 0))
    trail.setColorAt(1.0, QColor(226, 238, 255, int(150 * fade)))
    pen = QPen(trail, 1.8)
    p.setPen(pen)
    p.drawLine(tail, head)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, int(200 * fade)))
    p.drawEllipse(head, 1.9, 1.9)


def _cool_splitters(p, win, colour):
    """Recolour the divider handles, whatever the theme's accent is."""
    p.setPen(Qt.NoPen)
    p.setBrush(colour)
    for split in win.findChildren(QSplitter):
        if not split.isVisible():
            continue
        for i in range(1, split.count()):
            handle = split.handle(i)
            if handle is None or not handle.isVisible():
                continue
            top_left = handle.mapTo(win, QPoint(0, 0))
            p.drawRect(QRectF(top_left.x(), top_left.y(),
                              handle.width(), handle.height()))


def starfield(p, w, h, win, clip, safe, phase, rich=False):
    """
    Deep space: twinkling stars, nebula bloom, the occasional streak.

    Follows the same two-region rule as Halloween. The tint and the
    nebula are placed, so they avoid only the artwork; the stars and the
    constellation pattern avoid text and controls as well, because a star
    sitting inside a word is just a typo.
    """
    tint = QLinearGradient(0, 0, 0, h)
    tint.setColorAt(0.0, QColor(10, 12, 34, 86))
    tint.setColorAt(0.6, QColor(16, 14, 40, 62))
    tint.setColorAt(1.0, QColor(22, 16, 46, 78))

    p.save()
    p.setClipRegion(safe, Qt.IntersectClip)
    p.fillRect(QRectF(0, 0, w, h), tint)
    _nebula(p, w, h)
    p.restore()

    sidebar = _sidebar_width(win)
    live = getattr(win, "live", None)
    strip = getattr(live, "strip", None) if live else None
    strip_top = h
    if strip is not None and strip.isVisible():
        strip_top = strip.mapTo(win, QPoint(0, 0)).y()

    p.save()
    p.setClipRegion(clip, Qt.IntersectClip)
    _star_pattern(p, QRectF(0, 0, sidebar, h), rich=rich)
    _star_pattern(p, QRectF(sidebar, 0, w - sidebar, 38), size=30,
                  gap=86, seed=5, rich=rich)
    if strip_top < h:
        _star_pattern(p, QRectF(sidebar, strip_top, w - sidebar,
                                h - strip_top), size=34, gap=92,
                      seed=9, rich=rich)
    _stars(p, w, h, phase, rich=rich)
    _shooting_star(p, w, h, phase)
    p.restore()

    p.save()
    p.setClipRegion(safe, Qt.IntersectClip)
    _cool_splitters(p, win, QColor(92, 132, 210, 175))
    _tally_glow(p, win, live, phase)
    p.restore()




# ---- underwater --------------------------------------------------------

def _light_shafts(p, w, h, phase, rich=False):
    if rich:
        _shafts_rich(p, w, h, phase)
        return
    """Sunlight coming down through the surface, swaying slowly."""
    rng = random.Random(3)
    for i in range(5):
        base = rng.uniform(0.05, 0.95) * w
        width = rng.uniform(60, 140)
        lean = rng.uniform(-0.35, 0.35)
        drift = math.sin(phase * 0.25 + i * 1.3) * 26
        top_x = base + drift
        bottom_x = top_x + lean * h
        shaft = QPainterPath(QPointF(top_x - width / 2, 0))
        shaft.lineTo(QPointF(top_x + width / 2, 0))
        shaft.lineTo(QPointF(bottom_x + width * 0.9, h))
        shaft.lineTo(QPointF(bottom_x - width * 0.9, h))
        shaft.closeSubpath()
        grad = QLinearGradient(top_x, 0, bottom_x, h)
        grad.setColorAt(0.0, QColor(150, 224, 236, 30))
        grad.setColorAt(0.6, QColor(120, 200, 220, 12))
        grad.setColorAt(1.0, QColor(90, 170, 200, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawPath(shaft)


def _bubbles(p, w, h, phase, count=34, seed=11, rich=False):
    """
    Bubbles rising in columns, each popping near the top of its run.

    Every bubble keeps its own column, speed and starting offset, so they
    never rise as a sheet. A pop is drawn as an expanding ring rather
    than the bubble simply vanishing - things that disappear without
    explanation read as a glitch.
    """
    rng = random.Random(seed)
    for _ in range(count):
        x = rng.uniform(0, w)
        radius = rng.uniform(1.6, 5.2)
        speed = rng.uniform(0.045, 0.14)
        offset = rng.uniform(0, 1)
        wobble = rng.uniform(4, 13)
        rate = rng.uniform(0.8, 2.2)

        progress = (phase * speed + offset) % 1.0
        y = h - progress * (h + 40) + 20
        sway = math.sin(phase * rate + offset * 6.28) * wobble

        if progress > 0.94:
            # The pop: a thin ring opening out as it fades.
            burst = (progress - 0.94) / 0.06
            ring = QColor(196, 234, 246, int(120 * (1 - burst)))
            pen = QPen(ring)
            pen.setWidthF(1.2)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(x + sway, y),
                          radius * (1 + burst * 2.4),
                          radius * (1 + burst * 2.4))
            continue

        if rich:
            _bubble_rich(p, x + sway, y, radius)
            continue
        p.setPen(QPen(QColor(198, 236, 248, 110), 1.0))
        p.setBrush(QColor(150, 214, 236, 40))
        p.drawEllipse(QPointF(x + sway, y), radius, radius)
        # A highlight, which is most of what makes a circle read as a
        # bubble rather than a dot.
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(236, 250, 255, 130))
        p.drawEllipse(QPointF(x + sway - radius * 0.32,
                              y - radius * 0.34), radius * 0.24,
                      radius * 0.24)


def _seaweed(p, w, floor, phase, seed=17, rich=False):
    """Strands rooted at the floor, swaying out of step with each other."""
    rng = random.Random(seed)
    for _ in range(14):
        x = rng.uniform(0, w)
        height = rng.uniform(60, 190)
        width = rng.uniform(3.5, 8)
        rate = rng.uniform(0.5, 1.1)
        offset = rng.uniform(0, 6.28)
        hue = rng.choice((
            QColor(58, 140, 96, 120), QColor(44, 118, 104, 120),
            QColor(76, 152, 84, 110),
        ))

        if rich:
            _weed_rich(p, x + math.sin(phase * rate + offset) * 10,
                       floor, height, width)
            continue
        segments = 7
        left = QPainterPath(QPointF(x - width / 2, floor))
        right_points = []
        for i in range(1, segments + 1):
            t = i / segments
            y = floor - height * t
            # The sway grows towards the tip: a strand anchored in sand
            # does not move at the root.
            lean = math.sin(phase * rate + offset + t * 2.4) * 18 * t * t
            taper = width * (1 - t * 0.75)
            left.lineTo(QPointF(x + lean - taper / 2, y))
            right_points.append(QPointF(x + lean + taper / 2, y))
        for point in reversed(right_points):
            left.lineTo(point)
        left.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(hue)
        p.drawPath(left)


def _crab(p, x, floor, phase, scale=1.0, offset=0.0, rich=False):
    if rich:
        bob = math.sin(phase * 0.8 + offset) * 1.2 * scale
        _crab_rich(p, x, floor + bob, scale)
        return
    """
    A small red crab, sitting about.

    Mostly still: it shifts its weight and twitches a claw now and then,
    which reads as alive without pulling the eye the way walking would.
    """
    bob = math.sin(phase * 0.8 + offset) * 1.2 * scale
    y = floor - 7 * scale + bob
    shell = QColor(198, 62, 48)
    dark = QColor(150, 40, 32)

    p.setPen(QPen(dark, 1.0))
    # Legs first, so the shell sits on top of them.
    for side in (-1, 1):
        for i in range(3):
            spread = (7 + i * 4) * scale
            drop = (3 + i * 1.2) * scale
            twitch = math.sin(phase * 1.6 + offset + i) * 0.8 * scale
            p.drawLine(QPointF(x + side * 3 * scale, y + 1),
                       QPointF(x + side * spread, y + drop + twitch))

    claw_lift = math.sin(phase * 0.9 + offset * 1.7)
    for side in (-1, 1):
        cx = x + side * (10 * scale)
        cy = y - 2 * scale - (2.2 * scale if claw_lift > 0.7 else 0)
        p.setBrush(shell)
        p.drawEllipse(QPointF(cx, cy), 3.4 * scale, 2.8 * scale)

    p.setBrush(shell)
    p.setPen(QPen(dark, 1.0))
    p.drawEllipse(QPointF(x, y), 8 * scale, 5.6 * scale)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(20, 16, 18))
    for side in (-1, 1):
        p.drawEllipse(QPointF(x + side * 2.6 * scale, y - 3.4 * scale),
                      1.1 * scale, 1.1 * scale)


def _fish(p, w, h, phase, seed=23, rich=False):
    """A few fish crossing at different depths, speeds and directions."""
    rng = random.Random(seed)
    for _ in range(6):
        depth = rng.uniform(0.12, 0.88) * h
        speed = rng.uniform(0.02, 0.06)
        offset = rng.uniform(0, 1)
        size = rng.uniform(7, 16)
        rightward = rng.random() < 0.5
        colour = rng.choice((
            QColor(236, 186, 92, 150), QColor(226, 130, 78, 150),
            QColor(128, 196, 214, 150), QColor(198, 210, 120, 140),
        ))

        travel = (phase * speed + offset) % 1.0
        x = travel * (w + 160) - 80
        if not rightward:
            x = w - x
        facing = 1 if rightward else -1
        # A gentle rise and fall, plus a tail that beats faster than the
        # body moves - the two together read as swimming.
        y = depth + math.sin(phase * 1.4 + offset * 6.28) * 9
        beat = math.sin(phase * 7.0 + offset * 6.28) * size * 0.34

        if rich:
            p.save()
            if facing < 0:
                # Mirrored about its own centre, so the enhanced fish
                # can be drawn once and face either way.
                p.translate(x, 0)
                p.scale(-1, 1)
                p.translate(-x, 0)
            _fish_rich(p, x, y, size, colour, beat)
            p.restore()
            continue
        body = QPainterPath(QPointF(x + facing * size, y))
        body.quadTo(QPointF(x, y - size * 0.52),
                    QPointF(x - facing * size * 0.75, y))
        body.quadTo(QPointF(x, y + size * 0.52),
                    QPointF(x + facing * size, y))
        p.setPen(Qt.NoPen)
        p.setBrush(colour)
        p.drawPath(body)

        tail = QPainterPath(QPointF(x - facing * size * 0.7, y))
        tail.lineTo(QPointF(x - facing * size * 1.35, y - size * 0.42 + beat))
        tail.lineTo(QPointF(x - facing * size * 1.35, y + size * 0.42 + beat))
        tail.closeSubpath()
        p.drawPath(tail)

        p.setBrush(QColor(18, 24, 30, 190))
        p.drawEllipse(QPointF(x + facing * size * 0.55, y - size * 0.1),
                      size * 0.1, size * 0.1)


def _scallops(p, rect, size=30, gap=76, rich=False):
    """The tiled motif for flat panels: overlapping waves."""
    p.save()
    p.setClipRect(rect, Qt.IntersectClip)
    pen = QPen(QColor(130, 200, 220, 40))
    pen.setWidthF(1.1)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    row = 0
    y = rect.top() + gap * 0.5
    while y < rect.bottom() + gap:
        x = rect.left() + (gap * 0.5 if row % 2 else 0)
        while x < rect.right() + gap:
            if rich:
                _scallop_rich(p, x, y, size)
                x += gap
                continue
            for ring in (0.55, 0.8, 1.0):
                arc = QRectF(x - size * ring / 2, y - size * ring / 2,
                             size * ring, size * ring)
                p.drawArc(arc, 20 * 16, 140 * 16)
            x += gap
        y += gap * 0.72
        row += 1
    p.restore()


def underwater(p, w, h, win, clip, safe, phase, rich=False):
    """
    Down in the water: light from above, bubbles, weed, crabs and fish.

    Same two-region rule as the others. The living things use the tighter
    region, so a crab never sits on top of a button and a fish never
    swims through a sentence; the water itself and the light only avoid
    the artwork.
    """
    tint = QLinearGradient(0, 0, 0, h)
    tint.setColorAt(0.0, QColor(20, 78, 108, 74))
    tint.setColorAt(0.55, QColor(12, 52, 84, 58))
    tint.setColorAt(1.0, QColor(8, 32, 58, 82))

    p.save()
    p.setClipRegion(safe, Qt.IntersectClip)
    p.fillRect(QRectF(0, 0, w, h), tint)
    _light_shafts(p, w, h, phase, rich)
    p.restore()

    sidebar = _sidebar_width(win)
    live = getattr(win, "live", None)
    strip = getattr(live, "strip", None) if live else None
    strip_top = h
    if strip is not None and strip.isVisible():
        strip_top = strip.mapTo(win, QPoint(0, 0)).y()

    p.save()
    p.setClipRegion(clip, Qt.IntersectClip)
    _scallops(p, QRectF(0, 0, sidebar, h), rich=rich)
    _scallops(p, QRectF(sidebar, 0, w - sidebar, 38), size=22, gap=62,
              rich=rich)
    if strip_top < h:
        _scallops(p, QRectF(sidebar, strip_top, w - sidebar,
                            h - strip_top), size=26, gap=68, rich=rich)

    _fish(p, w, h, phase, rich=rich)
    _bubbles(p, w, h, phase, rich=rich)
    p.restore()

    # The floor is placed, not patterned: crabs and weed live on the
    # bottom edge, and clipping them around a text box chopped them into
    # fragments. They sit low enough not to cover anything being read.
    p.save()
    p.setClipRegion(safe, Qt.IntersectClip)
    # Far enough up that a crab's legs are not cut off by the window
    # edge, which looked like a rendering fault rather than a margin.
    floor = h - 11
    _seaweed(p, w, floor, phase, rich=rich)
    _crab(p, sidebar * 0.42, floor, phase, scale=1.0, offset=0.0,
          rich=rich)
    _crab(p, w * 0.52, floor, phase, scale=0.8, offset=2.3, rich=rich)
    _crab(p, w * 0.86, floor, phase, scale=1.15, offset=4.1,
          rich=rich)
    _cool_splitters(p, win, QColor(64, 150, 174, 180))
    _tally_glow(p, win, live, phase)
    p.restore()


UNDERWATER_QSS = """
/* Rounded like a pebble worn smooth, with a cool rim. */
QPushButton {
    border-radius: 11px;
    border: 1px solid #235A6B;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #17394B, stop:1 #102A3A);
    color: #CFE8F0;
}
QPushButton:hover {
    border: 1px solid #3E93AC;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #1D4A60, stop:1 #143347);
}
QPushButton:disabled {
    border: 1px solid #1C3B49;
    color: #4E6E7C;
}

#primaryButton {
    border: 1px solid #1E7E96;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #46C4D4, stop:0.5 #2196B4,
                                stop:1 #146C8C);
    color: #04202B;
    font-weight: 600;
}
#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #5AD6E4, stop:0.5 #29A8C6,
                                stop:1 #187C9E);
}

#confirmButton, #denyButton {
    border-radius: 11px;
}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox,
QDoubleSpinBox {
    border-radius: 9px;
    border: 1px solid #21495C;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #3E93AC;
}

#feedList {
    border: 1px solid #21495C;
    border-radius: 9px;
}
"""


def painter_for(name):
    """The painter for a theme, or None for no decoration."""
    return PAINTERS.get(canonical(name))


def theme_names():
    return [(key, label, note) for key, label, note in THEMES]




# ---- sanrio ------------------------------------------------------------
#
# The kawaii pastel look, not the characters: clouds, bows, hearts and
# sparkles are the general vocabulary of the style, and none of them
# belongs to anyone. Drawing a recognisable mascot would be copying
# somebody's property, which is a different thing from a theme.

def _cloud(p, x, y, size, alpha=70, tint=(255, 255, 255)):
    """
    A drawn cloud rather than a row of circles.

    Built as one closed path so it has a single silhouette, then shaded:
    a brighter crown, a cooler underside, and a soft rim. Overlapping
    flat circles read as a diagram of a cloud; this reads as a drawing of
    one.
    """
    r, g, b = tint
    w = size * 1.5
    h = size * 0.92

    body = QPainterPath()
    # Lumps of deliberately uneven size, which is most of what stops a
    # cloud looking machine-made.
    lumps = ((-0.60, 0.06, 0.34), (-0.34, -0.20, 0.44),
             (-0.02, -0.30, 0.50), (0.30, -0.16, 0.42),
             (0.58, 0.04, 0.32), (0.16, 0.10, 0.38),
             (-0.22, 0.12, 0.36))
    for dx, dy, rad in lumps:
        lump = QPainterPath()
        lump.addEllipse(QPointF(x + dx * w, y + dy * h), rad * w * 0.5,
                        rad * h * 0.72)
        body = body.united(lump)
    base = QPainterPath()
    base.addRoundedRect(QRectF(x - w * 0.60, y + h * 0.02,
                               w * 1.20, h * 0.34),
                        h * 0.17, h * 0.17)
    body = body.united(base)

    # Shading, top to bottom, inside the one silhouette.
    shade = QLinearGradient(x, y - h * 0.55, x, y + h * 0.40)
    shade.setColorAt(0.0, QColor(min(255, r + 12), min(255, g + 10),
                                 min(255, b + 8), alpha))
    shade.setColorAt(0.55, QColor(r, g, b, alpha))
    shade.setColorAt(1.0, QColor(int(r * 0.88), int(g * 0.86),
                                 int(b * 0.95), int(alpha * 0.92)))
    p.setPen(Qt.NoPen)
    p.setBrush(shade)
    p.drawPath(body)

    # A rim, brighter than the fill, which gives the edge some drawing.
    rim = QPen(QColor(255, 255, 255, int(alpha * 0.75)))
    rim.setWidthF(1.4)
    p.setPen(rim)
    p.setBrush(Qt.NoBrush)
    p.drawPath(body)

    # Two highlights on the crown, the way a sticker would have them.
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, int(alpha * 0.55)))
    p.drawEllipse(QPointF(x - w * 0.06, y - h * 0.34), w * 0.13, h * 0.13)
    p.drawEllipse(QPointF(x + w * 0.24, y - h * 0.20), w * 0.07, h * 0.08)


def _clouds(p, w, h, phase, seed=31):
    """
    Clouds drifting across, wrapping round the edges.

    Slow enough to be scenery rather than motion you track - a cloud that
    visibly moves while you read is a distraction.
    """
    rng = random.Random(seed)
    for _ in range(9):
        size = rng.uniform(44, 120)
        y = rng.uniform(0.05, 0.92) * h
        speed = rng.uniform(0.004, 0.013)
        offset = rng.uniform(0, 1)
        # Bright enough to read as fluff rather than smoke: on a
        # dark interface a faint white cloud just looks grey.
        alpha = int(rng.uniform(76, 128))
        tint = rng.choice((
            (255, 255, 255), (255, 232, 244), (226, 240, 255),
        ))
        drift = (phase * speed + offset) % 1.0
        x = drift * (w + size * 3) - size * 1.5
        bob = math.sin(phase * 0.5 + offset * 6.28) * 4
        _cloud(p, x, y + bob, size, alpha, tint)


def _bow(p, size, rich=False):
    if rich:
        _bow_rich(p, size)
        return
    """A ribbon bow, drawn around the origin."""
    r = size / 2
    for side in (-1, 1):
        loop = QPainterPath(QPointF(0, 0))
        loop.cubicTo(QPointF(side * r * 1.5, -r * 1.05),
                     QPointF(side * r * 1.7, r * 0.55),
                     QPointF(0, 0))
        p.drawPath(loop)
        tail = QPainterPath(QPointF(side * r * 0.18, r * 0.16))
        tail.cubicTo(QPointF(side * r * 0.6, r * 0.9),
                     QPointF(side * r * 0.5, r * 1.3),
                     QPointF(side * r * 0.95, r * 1.5))
        tail.cubicTo(QPointF(side * r * 0.42, r * 1.2),
                     QPointF(side * r * 0.3, r * 0.7),
                     QPointF(side * r * 0.05, r * 0.2))
        p.drawPath(tail)
    p.drawEllipse(QPointF(0, 0), r * 0.28, r * 0.26)


def _heart(p, x, y, size):
    """A rounded heart, from two lobes and a point."""
    path = QPainterPath(QPointF(x, y + size * 0.62))
    path.cubicTo(QPointF(x - size * 1.15, y - size * 0.18),
                 QPointF(x - size * 0.48, y - size * 0.92),
                 QPointF(x, y - size * 0.24))
    path.cubicTo(QPointF(x + size * 0.48, y - size * 0.92),
                 QPointF(x + size * 1.15, y - size * 0.18),
                 QPointF(x, y + size * 0.62))
    p.drawPath(path)


def _hearts(p, w, h, phase, seed=37, rich=False):
    """Hearts rising slowly, fading as they go."""
    rng = random.Random(seed)
    for _ in range(16):
        x = rng.uniform(0, w)
        size = rng.uniform(5, 11)
        speed = rng.uniform(0.02, 0.055)
        offset = rng.uniform(0, 1)
        sway = rng.uniform(6, 18)
        rate = rng.uniform(0.7, 1.6)
        tint = rng.choice((
            (255, 158, 196), (255, 190, 214), (188, 206, 255),
            (255, 214, 168),
        ))
        progress = (phase * speed + offset) % 1.0
        y = h - progress * (h + 60) + 30
        drift = math.sin(phase * rate + offset * 6.28) * sway
        # Brightest in the middle of the climb, so they arrive and leave
        # gently instead of blinking in and out.
        alpha = int(120 * math.sin(math.pi * progress))
        if alpha <= 4:
            continue
        if rich:
            _heart_rich(p, x + drift, y, size, tint)
            continue
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(tint[0], tint[1], tint[2], alpha))
        _heart(p, x + drift, y, size)


def _sparkles(p, w, h, phase, count=46, seed=41):
    """Four-pointed twinkles, each on its own little clock."""
    rng = random.Random(seed)
    for _ in range(count):
        x = rng.uniform(0, w)
        y = rng.uniform(0, h)
        size = rng.uniform(3.5, 9)
        rate = rng.uniform(0.8, 2.6)
        offset = rng.uniform(0, 6.28)
        tint = rng.choice((
            (255, 255, 255), (255, 226, 242), (255, 244, 206),
        ))
        pulse = 0.5 + 0.5 * math.sin(phase * rate + offset)
        alpha = int(180 * pulse)
        if alpha <= 8:
            continue
        reach = size * (0.55 + 0.45 * pulse)
        star = QPainterPath(QPointF(x, y - reach))
        star.quadTo(QPointF(x, y), QPointF(x + reach, y))
        star.quadTo(QPointF(x, y), QPointF(x, y + reach))
        star.quadTo(QPointF(x, y), QPointF(x - reach, y))
        star.quadTo(QPointF(x, y), QPointF(x, y - reach))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(tint[0], tint[1], tint[2], alpha))
        p.drawPath(star)


def _bow_pattern(p, rect, size=26, gap=78, rich=False):
    """Bows and hearts tiled across the flat panels."""
    p.save()
    p.setClipRect(rect, Qt.IntersectClip)
    pen = QPen(QColor(255, 190, 216, 52))
    pen.setWidthF(1.1)
    row = 0
    y = rect.top() + gap * 0.45
    while y < rect.bottom() + gap:
        x = rect.left() + (gap * 0.5 if row % 2 else 0) + gap * 0.35
        col = 0
        while x < rect.right() + gap:
            p.save()
            p.setTransform(
                QTransform().translate(x, y).rotate(
                    10 if (row + col) % 2 == 0 else -10), True)
            if (row + col) % 3 == 0:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(255, 196, 220, 44))
                _heart(p, 0, 0, size * 0.42)
            else:
                p.setPen(pen)
                p.setBrush(QColor(255, 214, 232, 26))
                _bow(p, size, rich)
            p.restore()
            x += gap
            col += 1
        y += gap * 0.86
        row += 1
    p.restore()


def _rainbow(p, w, h, phase):
    """
    A soft arc across a corner, fading out at both ends.

    Each band is an annulus wedge filled with a conical gradient. A
    conical gradient sweeps by angle around its centre, which is exactly
    how an arc is described - so the fade follows the bow itself.

    The obvious approach, drawing the arc in short segments of varying
    alpha, leaves visible stripes: neighbouring segments have to overlap
    to avoid gaps, and the overlap doubles the alpha at every seam.
    """
    breathe = 1.0 + math.sin(phase * 0.3) * 0.02
    cx, cy = w * 0.12, h * 1.02
    bands = ((255, 176, 190), (255, 214, 176), (255, 244, 186),
             (192, 232, 200), (186, 212, 248), (208, 190, 240))
    span_start, span_len = 10.0, 76.0
    thickness = 11.0

    for i, tint in enumerate(bands):
        radius = (h * 0.52 + i * thickness) * breathe
        outer = QRectF(cx - radius - thickness / 2,
                       cy - radius - thickness / 2,
                       (radius + thickness / 2) * 2,
                       (radius + thickness / 2) * 2)
        inner = QRectF(cx - radius + thickness / 2,
                       cy - radius + thickness / 2,
                       (radius - thickness / 2) * 2,
                       (radius - thickness / 2) * 2)

        wedge = QPainterPath()
        wedge.arcMoveTo(outer, span_start)
        wedge.arcTo(outer, span_start, span_len)
        wedge.arcTo(inner, span_start + span_len, -span_len)
        wedge.closeSubpath()

        # Positions run anticlockwise from the gradient's own angle, so
        # the arc occupies the first span_len/360 of the sweep.
        grad = QConicalGradient(QPointF(cx, cy), span_start)
        reach = span_len / 360.0
        base = QColor(tint[0], tint[1], tint[2])
        for stop in (0.0, 0.12, 0.5, 0.88, 1.0):
            fade = math.sin(math.pi * stop) ** 1.4
            colour = QColor(base)
            colour.setAlpha(int(64 * fade))
            grad.setColorAt(stop * reach, colour)
        tail = QColor(base)
        tail.setAlpha(0)
        grad.setColorAt(min(1.0, reach + 0.001), tail)
        grad.setColorAt(1.0, tail)

        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawPath(wedge)


def kawaii(p, w, h, win, clip, safe, phase, rich=False):
    """
    Pastel skies: clouds, bows, hearts and sparkles.

    Same two-region rule as the rest. The wash and the rainbow are
    placed, so they avoid only the artwork; everything with a shape
    avoids text and controls too.
    """
    wash = QLinearGradient(0, 0, 0, h)
    wash.setColorAt(0.0, QColor(255, 214, 232, 92))
    wash.setColorAt(0.45, QColor(228, 216, 255, 74))
    wash.setColorAt(1.0, QColor(200, 230, 255, 88))

    p.save()
    p.setClipRegion(safe, Qt.IntersectClip)
    p.fillRect(QRectF(0, 0, w, h), wash)
    _rainbow(p, w, h, phase)
    p.restore()

    sidebar = _sidebar_width(win)
    live = getattr(win, "live", None)
    strip = getattr(live, "strip", None) if live else None
    strip_top = h
    if strip is not None and strip.isVisible():
        strip_top = strip.mapTo(win, QPoint(0, 0)).y()

    p.save()
    p.setClipRegion(clip, Qt.IntersectClip)
    _bow_pattern(p, QRectF(0, 0, sidebar, h), rich=rich)
    _bow_pattern(p, QRectF(sidebar, 0, w - sidebar, 38), size=20,
                 gap=64, rich=rich)
    if strip_top < h:
        _bow_pattern(p, QRectF(sidebar, strip_top, w - sidebar,
                               h - strip_top), size=22, gap=70,
                     rich=rich)
    _clouds(p, w, h, phase)
    _hearts(p, w, h, phase, rich=rich)
    _sparkles(p, w, h, phase)
    p.restore()

    p.save()
    p.setClipRegion(safe, Qt.IntersectClip)
    _cool_splitters(p, win, QColor(255, 168, 202, 190))
    _tally_glow(p, win, live, phase)
    p.restore()


KAWAII_QSS = """
/* Fully rounded, with a soft pink rim: everything here is a pebble or a
   sweet, nothing is a rectangle. */
QPushButton {
    border-radius: 15px;
    border: 1px solid #6E4C60;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #3A2B38, stop:1 #2C2029);
    color: #F6DEEA;
}
QPushButton:hover {
    border: 1px solid #C97BA4;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #4A3546, stop:1 #372833);
}
QPushButton:disabled {
    border: 1px solid #4A3742;
    color: #7E6673;
}

#primaryButton {
    border: 1px solid #C2507F;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #FFA9C8, stop:0.5 #F27FAC,
                                stop:1 #D25588);
    color: #3A0E24;
    font-weight: 600;
}
#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #FFBED6, stop:0.5 #FF93BC,
                                stop:1 #E0669A);
}

#confirmButton, #denyButton {
    border-radius: 15px;
}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox,
QDoubleSpinBox {
    border-radius: 12px;
    border: 1px solid #5E4352;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #C97BA4;
}

#feedList {
    border: 1px solid #5E4352;
    border-radius: 12px;
}
"""




# ---- cryptic -----------------------------------------------------------
#
# Drawn rather than assembled: the eye is one lens shape with a radial
# iris and a lid path over it, the sigil ring fades along its own sweep
# with a conical gradient, and the glyphs are stroked paths rather than
# characters from a font.

def _glyph(p, x, y, size, seed, alpha):
    """
    One invented mark.

    Built from a few connected strokes with the occasional detached dot,
    which is what makes a shape read as writing rather than as scribble -
    real scripts have strokes that meet.
    """
    rng = random.Random(seed)
    pen = QPen(QColor(150, 226, 208, alpha))
    pen.setWidthF(max(0.9, size * 0.10))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    half = size / 2
    nodes = [QPointF(x + rng.uniform(-half, half),
                     y + rng.uniform(-half, half)) for _ in range(4)]
    stroke = QPainterPath(nodes[0])
    for node in nodes[1:]:
        if rng.random() < 0.35:
            # A curve among the straights keeps it from looking like a
            # circuit diagram.
            stroke.quadTo(QPointF(x + rng.uniform(-half, half),
                                  y + rng.uniform(-half, half)), node)
        else:
            stroke.lineTo(node)
    p.drawPath(stroke)

    if rng.random() < 0.5:
        p.drawLine(QPointF(x - half * 0.8, y + half * 0.7),
                   QPointF(x + half * 0.8, y + half * 0.7))
    if rng.random() < 0.4:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(150, 226, 208, alpha))
        p.drawEllipse(QPointF(x + rng.uniform(-half, half),
                              y - half * 0.9), size * 0.07, size * 0.07)


def _glyph_rain(p, w, h, phase, seed=53):
    """
    Columns of marks drifting down, fading as they fall.

    Each column keeps its own speed and glyph seeds, so the same mark
    never appears twice in a row - which is the tell that turns a cipher
    back into a pattern.
    """
    rng = random.Random(seed)
    for column in range(16):
        x = rng.uniform(0, w)
        size = rng.uniform(9, 17)
        speed = rng.uniform(0.012, 0.035)
        offset = rng.uniform(0, 1)
        count = rng.randint(4, 8)
        spacing = size * 2.1
        base_seed = rng.randint(0, 9999)

        head = ((phase * speed + offset) % 1.0) * (h + count * spacing)
        for i in range(count):
            y = head - i * spacing
            if y < -size or y > h + size:
                continue
            # Brightest at the head of the column, trailing off behind.
            fade = (1.0 - i / count) ** 1.6
            alpha = int(120 * fade)
            if alpha <= 6:
                continue
            _glyph(p, x, y, size, base_seed + i * 17, alpha)


def _sigil_ring(p, cx, cy, radius, phase, rate=0.06, alpha=64):
    """
    A slowly turning ring of marks, fading around its own sweep.

    The conical gradient does the fading: a stroked circle can only be
    one flat colour, and a ring that is equally bright all the way round
    reads as a drawn circle rather than as something half-seen.
    """
    spin = phase * rate
    p.save()
    p.translate(cx, cy)
    p.rotate(math.degrees(spin))

    for scale, width in ((1.0, 1.6), (0.82, 1.0), (0.58, 0.9)):
        r = radius * scale
        grad = QConicalGradient(QPointF(0, 0), 0)
        for stop in (0.0, 0.25, 0.5, 0.75, 1.0):
            fade = 0.35 + 0.65 * (math.sin(math.pi * stop * 2) * 0.5 + 0.5)
            grad.setColorAt(stop, QColor(140, 220, 206, int(alpha * fade)))
        pen = QPen(grad, width)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), r, r)

    # Tick marks and a polygon inside, drawn as one path so the strokes
    # join properly at the corners.
    p.setPen(QPen(QColor(140, 220, 206, int(alpha * 0.8)), 1.1))
    for i in range(12):
        angle = math.radians(i * 30)
        inner = radius * 0.88
        p.drawLine(QPointF(math.cos(angle) * inner,
                           math.sin(angle) * inner),
                   QPointF(math.cos(angle) * radius,
                           math.sin(angle) * radius))

    star = QPainterPath()
    points = 7
    step = 3
    for i in range(points + 1):
        angle = math.radians((i * step) * (360 / points) - 90)
        point = QPointF(math.cos(angle) * radius * 0.58,
                        math.sin(angle) * radius * 0.58)
        if i == 0:
            star.moveTo(point)
        else:
            star.lineTo(point)
    p.setPen(QPen(QColor(150, 226, 208, int(alpha * 0.7)), 1.2))
    p.drawPath(star)
    p.restore()


def _eye(p, cx, cy, size, phase, offset=0.0, look_at=None):
    """
    An eye that opens, watches, and blinks.

    Drawn as a lens shape with a radial iris inside it and a lid brought
    down over the top, rather than a stack of circles: the lid is what
    makes it an eye, and a circle with a dot in it is a target.
    """
    # Mostly open, with a quick blink on a long cycle.
    cycle = (phase * 0.18 + offset) % 1.0
    if cycle > 0.955:
        openness = 1.0 - (cycle - 0.955) / 0.0225
    elif cycle > 0.9775:
        openness = (cycle - 0.9775) / 0.0225
    else:
        openness = 1.0
    openness = max(0.06, min(1.0, openness))

    w = size
    h = size * 0.52 * openness

    lens = QPainterPath(QPointF(cx - w / 2, cy))
    lens.quadTo(QPointF(cx, cy - h), QPointF(cx + w / 2, cy))
    lens.quadTo(QPointF(cx, cy + h), QPointF(cx - w / 2, cy))

    p.save()
    p.setClipPath(lens)

    # The white, which is really a dim glow so it sits in the dark.
    white = QRadialGradient(QPointF(cx, cy), w * 0.6)
    white.setColorAt(0.0, QColor(196, 236, 226, 46))
    white.setColorAt(1.0, QColor(120, 180, 176, 16))
    p.setPen(Qt.NoPen)
    p.setBrush(white)
    p.drawPath(lens)

    # The iris follows the cursor when there is one, and drifts on its
    # own otherwise. Tracking costs a single cursor query per frame -
    # the layer is already repainting for the animation, so nothing
    # extra is drawn and no new timer is needed.
    iris_r = size * 0.21
    reach_x, reach_y = w * 0.17, h * 0.30
    if look_at is not None:
        dx = look_at.x() - cx
        dy = look_at.y() - cy
        distance = math.hypot(dx, dy)
        if distance > 0.5:
            # Clamped to an ellipse inside the lens, so the iris slides
            # towards the cursor but never leaves the eye.
            pull = min(1.0, distance / (size * 2.4))
            look = (dx / distance) * reach_x * pull
            look_v = (dy / distance) * reach_y * pull
        else:
            look = look_v = 0.0
    else:
        look = math.sin(phase * 0.22 + offset * 4.1) * reach_x * 0.8
        look_v = math.sin(phase * 0.17 + offset * 2.3) * reach_y * 0.3

    iris = QRadialGradient(QPointF(cx + look, cy + look_v), iris_r)
    iris.setColorAt(0.0, QColor(120, 230, 208, 190))
    iris.setColorAt(0.55, QColor(58, 150, 142, 170))
    iris.setColorAt(1.0, QColor(20, 70, 74, 150))
    p.setBrush(iris)
    p.drawEllipse(QPointF(cx + look, cy + look_v), iris_r, iris_r)

    p.setBrush(QColor(6, 14, 18, 220))
    p.drawEllipse(QPointF(cx + look, cy + look_v),
                  iris_r * 0.42, iris_r * 0.42)
    # The catchlight stays on the same side of the iris whatever it is
    # looking at, as a real one would with a fixed light source.
    p.setBrush(QColor(226, 250, 244, 150))
    p.drawEllipse(QPointF(cx + look - iris_r * 0.3,
                          cy + look_v - iris_r * 0.32),
                  iris_r * 0.16, iris_r * 0.16)
    p.restore()

    pen = QPen(QColor(150, 226, 208, 110))
    pen.setWidthF(1.3)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawPath(lens)

    # Lashes, only while open enough to have any.
    if openness > 0.5:
        p.setPen(QPen(QColor(150, 226, 208, 70), 1.0))
        for i in range(-2, 3):
            ax = cx + i * w * 0.16
            ay = cy - h * (1 - abs(i) * 0.18) * 0.86
            p.drawLine(QPointF(ax, ay),
                       QPointF(ax + i * w * 0.03, ay - h * 0.34))


def _cartouche(p, size, seed, rich=False):
    if rich:
        _cartouche_rich(p, size, seed)
        _glyph(p, 0, 0, size * 0.52, seed, 30)
        return
    """A framed mark: the tiled motif for flat panels."""
    r = size / 2
    frame = QPainterPath()
    frame.moveTo(QPointF(-r, -r * 0.72))
    frame.lineTo(QPointF(-r * 0.72, -r))
    frame.lineTo(QPointF(r * 0.72, -r))
    frame.lineTo(QPointF(r, -r * 0.72))
    frame.lineTo(QPointF(r, r * 0.72))
    frame.lineTo(QPointF(r * 0.72, r))
    frame.lineTo(QPointF(-r * 0.72, r))
    frame.lineTo(QPointF(-r, r * 0.72))
    frame.closeSubpath()
    pen = QPen(QColor(130, 206, 192, 34))
    pen.setWidthF(1.0)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawPath(frame)
    _glyph(p, 0, 0, size * 0.52, seed, 30)


def _cartouche_pattern(p, rect, size=26, gap=80, seed=61,
                       rich=False):
    p.save()
    p.setClipRect(rect, Qt.IntersectClip)
    row = 0
    y = rect.top() + gap * 0.45
    while y < rect.bottom() + gap:
        x = rect.left() + (gap * 0.5 if row % 2 else 0) + gap * 0.35
        col = 0
        while x < rect.right() + gap:
            p.save()
            p.setTransform(QTransform().translate(x, y), True)
            _cartouche(p, size, seed + row * 13 + col * 5, rich)
            p.restore()
            x += gap
            col += 1
        y += gap * 0.88
        row += 1
    p.restore()


def _motes(p, w, h, phase, count=30, seed=67):
    """Slow points of light, breathing in and out."""
    rng = random.Random(seed)
    p.setPen(Qt.NoPen)
    for _ in range(count):
        x = rng.uniform(0, w)
        y = rng.uniform(0, h)
        size = rng.uniform(1.2, 3.0)
        rate = rng.uniform(0.3, 0.9)
        offset = rng.uniform(0, 6.28)
        drift = math.sin(phase * rate * 0.5 + offset) * 10
        pulse = 0.4 + 0.6 * math.sin(phase * rate + offset)
        alpha = int(120 * max(0.0, pulse))
        if alpha <= 6:
            continue
        glow = QRadialGradient(QPointF(x, y + drift), size * 4)
        glow.setColorAt(0.0, QColor(150, 226, 208, alpha))
        glow.setColorAt(1.0, QColor(150, 226, 208, 0))
        p.setBrush(glow)
        p.drawEllipse(QPointF(x, y + drift), size * 4, size * 4)
        p.setBrush(QColor(206, 244, 232, min(255, alpha + 60)))
        p.drawEllipse(QPointF(x, y + drift), size * 0.5, size * 0.5)


def cryptic(p, w, h, win, clip, safe, phase, rich=False):
    """
    Something half-decoded: turning sigils, drifting marks, an eye.

    Same two-region rule as the rest. The wash and the eye are placed -
    the eye is the theme's one deliberate focal point and should not be
    chopped around a label - while everything written avoids text and
    controls.
    """
    wash = QLinearGradient(0, 0, 0, h)
    wash.setColorAt(0.0, QColor(8, 20, 26, 96))
    wash.setColorAt(0.5, QColor(10, 16, 30, 74))
    wash.setColorAt(1.0, QColor(6, 14, 22, 100))

    p.save()
    p.setClipRegion(safe, Qt.IntersectClip)
    p.fillRect(QRectF(0, 0, w, h), wash)
    # A faint vignette, so the middle reads as lit and the edges as not.
    corner = QRadialGradient(QPointF(w * 0.5, h * 0.5), max(w, h) * 0.72)
    corner.setColorAt(0.0, QColor(0, 0, 0, 0))
    corner.setColorAt(1.0, QColor(0, 0, 0, 90))
    p.fillRect(QRectF(0, 0, w, h), corner)
    p.restore()

    sidebar = _sidebar_width(win)
    live = getattr(win, "live", None)
    strip = getattr(live, "strip", None) if live else None
    strip_top = h
    if strip is not None and strip.isVisible():
        strip_top = strip.mapTo(win, QPoint(0, 0)).y()

    p.save()
    p.setClipRegion(clip, Qt.IntersectClip)
    _cartouche_pattern(p, QRectF(0, 0, sidebar, h), rich=rich)
    _cartouche_pattern(p, QRectF(sidebar, 0, w - sidebar, 38), size=20,
                       gap=64, seed=71, rich=rich)
    if strip_top < h:
        _cartouche_pattern(p, QRectF(sidebar, strip_top, w - sidebar,
                                     h - strip_top), size=22, gap=70,
                           seed=79, rich=rich)

    _sigil_ring(p, w * 0.78, h * 0.30, min(w, h) * 0.22, phase)
    _sigil_ring(p, w * 0.22, h * 0.74, min(w, h) * 0.15, phase,
                rate=-0.045, alpha=48)
    _glyph_rain(p, w, h, phase)
    _motes(p, w, h, phase)
    p.restore()

    p.save()
    p.setClipRegion(safe, Qt.IntersectClip)
    # Where the cursor is, in this window's coordinates. None when it is
    # somewhere else entirely, so the eye goes back to drifting rather
    # than staring at a corner.
    cursor = None
    try:
        local = win.mapFromGlobal(QCursor.pos())
        if win.rect().contains(local):
            cursor = QPointF(local)
    except RuntimeError:
        cursor = None
    _eye(p, w * 0.5, h * 0.44, min(w, h) * 0.16, phase, look_at=cursor)
    _cool_splitters(p, win, QColor(96, 186, 172, 165))
    _tally_glow(p, win, live, phase)
    p.restore()


CRYPTIC_QSS = """
/* Cut corners and a thin rim: something stamped or engraved rather than
   moulded. */
QPushButton {
    border-top-left-radius: 2px;
    border-top-right-radius: 9px;
    border-bottom-right-radius: 2px;
    border-bottom-left-radius: 9px;
    border: 1px solid #2A4A48;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #16262C, stop:1 #101A20);
    color: #BFE4DA;
}
QPushButton:hover {
    border: 1px solid #4C8C82;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #1D3238, stop:1 #14222A);
}
QPushButton:disabled {
    border: 1px solid #22383A;
    color: #55716F;
}

#primaryButton {
    border: 1px solid #2E7E72;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #4FC4AE, stop:0.5 #2E9A8C,
                                stop:1 #1C6A64);
    color: #042020;
    font-weight: 600;
}
#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #62D6BE, stop:0.5 #38AC9C,
                                stop:1 #237C74);
}

#confirmButton, #denyButton {
    border-top-left-radius: 2px;
    border-top-right-radius: 9px;
    border-bottom-right-radius: 2px;
    border-bottom-left-radius: 9px;
}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox,
QDoubleSpinBox {
    border-top-left-radius: 2px;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 2px;
    border-bottom-left-radius: 8px;
    border: 1px solid #274442;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #4C8C82;
}

#feedList {
    border: 1px solid #274442;
    border-top-left-radius: 2px;
    border-bottom-right-radius: 2px;
}
"""




# ---- frutiger aero -----------------------------------------------------
#
# The mid-2000s glossy look: wet glass, aqua gradients, ribbons of light
# and a lot of shine. Every piece is drawn and shaded rather than
# assembled - a water bead in particular is almost entirely lighting, and
# a flat circle with a dot on it reads as a bubble sticker instead.

def _bead(p, x, y, size, squash=1.0, alpha=1.0):
    """
    A droplet of water sitting on the glass.

    Four passes, in the order a real one reads: the shadow it casts, the
    body refracting what is behind it, the bright crescent where light
    leaves the far side, and the specular pinpoint where it enters.

    The crescent is at the bottom and the highlight at the top, which is
    the wrong way round for a solid ball. That inversion is exactly what
    makes it look like water rather than a marble.
    """
    rx, ry = size, size * squash

    # Cast shadow, offset down and slightly right.
    shadow = QRadialGradient(QPointF(x + rx * 0.16, y + ry * 0.26), rx * 1.2)
    shadow.setColorAt(0.0, QColor(6, 26, 34, int(70 * alpha)))
    shadow.setColorAt(1.0, QColor(6, 26, 34, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(shadow)
    p.drawEllipse(QPointF(x + rx * 0.16, y + ry * 0.26), rx * 1.2, ry * 1.2)

    # Body: darker at the top where it takes colour from above, paler
    # towards the lower edge.
    body = QLinearGradient(x, y - ry, x, y + ry)
    body.setColorAt(0.0, QColor(126, 186, 208, int(96 * alpha)))
    body.setColorAt(0.45, QColor(176, 222, 236, int(58 * alpha)))
    body.setColorAt(1.0, QColor(226, 248, 252, int(132 * alpha)))
    p.setBrush(body)
    p.drawEllipse(QPointF(x, y), rx, ry)

    # The lit crescent along the lower rim.
    crescent = QPainterPath()
    crescent.moveTo(QPointF(x - rx * 0.78, y + ry * 0.18))
    crescent.quadTo(QPointF(x, y + ry * 1.18),
                    QPointF(x + rx * 0.78, y + ry * 0.18))
    crescent.quadTo(QPointF(x, y + ry * 0.72),
                    QPointF(x - rx * 0.78, y + ry * 0.18))
    p.setBrush(QColor(250, 255, 255, int(150 * alpha)))
    p.drawPath(crescent)

    # Rim, thin and cool.
    rim = QPen(QColor(236, 250, 255, int(110 * alpha)))
    rim.setWidthF(max(0.7, size * 0.07))
    p.setPen(rim)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(x, y), rx, ry)

    # Specular: one hard pinpoint and one soft bloom around it.
    p.setPen(Qt.NoPen)
    glow = QRadialGradient(QPointF(x - rx * 0.34, y - ry * 0.38), rx * 0.7)
    glow.setColorAt(0.0, QColor(255, 255, 255, int(120 * alpha)))
    glow.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.setBrush(glow)
    p.drawEllipse(QPointF(x - rx * 0.34, y - ry * 0.38), rx * 0.7, ry * 0.7)
    p.setBrush(QColor(255, 255, 255, int(215 * alpha)))
    p.drawEllipse(QPointF(x - rx * 0.36, y - ry * 0.40),
                  rx * 0.20, ry * 0.24)


def _beads(p, w, h, phase, seed=101):
    """
    Beads on the glass: most sitting still, a few running down.

    A runner leaves a faint trail and shrinks as it goes, because a drop
    that slides loses water to the track behind it.
    """
    rng = random.Random(seed)
    for _ in range(26):
        x = rng.uniform(0, w)
        size = rng.uniform(3.5, 11)
        squash = rng.uniform(0.86, 1.06)
        runs = rng.random() < 0.3

        if not runs:
            _bead(p, x, rng.uniform(0, h), size, squash)
            continue

        speed = rng.uniform(0.03, 0.08)
        offset = rng.uniform(0, 1)
        travel = (phase * speed + offset) % 1.0
        y = travel * (h + 60) - 30

        trail = QLinearGradient(x, y - size * 9, x, y)
        trail.setColorAt(0.0, QColor(210, 240, 250, 0))
        trail.setColorAt(1.0, QColor(210, 240, 250, 40))
        p.setPen(Qt.NoPen)
        p.setBrush(trail)
        p.drawRoundedRect(QRectF(x - size * 0.34, y - size * 9,
                                 size * 0.68, size * 9),
                          size * 0.34, size * 0.34)
        _bead(p, x, y, size * (1.0 - travel * 0.25), squash)


def _swoosh(p, w, h, phase, seed=103, rich=False):
    if rich:
        _swoosh_rich(p, w, h, phase, seed)
        return
    """
    Ribbons of light crossing the background.

    Two curves with a gradient between them rather than a thick stroke:
    a ribbon has to be wide in the middle and fine at the ends, which a
    pen of constant width cannot do.
    """
    rng = random.Random(seed)
    for i in range(4):
        y0 = rng.uniform(0.1, 0.9) * h
        y1 = rng.uniform(0.1, 0.9) * h
        lift = rng.uniform(0.12, 0.4) * h
        width = rng.uniform(18, 54)
        drift = math.sin(phase * 0.16 + i * 1.7) * 16

        top = QPainterPath(QPointF(-40, y0 + drift))
        top.cubicTo(QPointF(w * 0.32, y0 - lift + drift),
                    QPointF(w * 0.68, y1 + lift + drift),
                    QPointF(w + 40, y1 + drift))
        bottom = QPainterPath(QPointF(w + 40, y1 + width + drift))
        bottom.cubicTo(QPointF(w * 0.68, y1 + lift + width * 1.6 + drift),
                       QPointF(w * 0.32, y0 - lift + width * 1.6 + drift),
                       QPointF(-40, y0 + width + drift))
        ribbon = QPainterPath(top)
        ribbon.connectPath(bottom)
        ribbon.closeSubpath()

        fill = QLinearGradient(0, y0, w, y1)
        fill.setColorAt(0.0, QColor(190, 235, 250, 0))
        fill.setColorAt(0.35, QColor(210, 245, 255, 30))
        fill.setColorAt(0.6, QColor(236, 252, 255, 44))
        fill.setColorAt(1.0, QColor(190, 235, 250, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(fill)
        p.drawPath(ribbon)


def _sun_flare(p, w, h, phase):
    """A bright corner bloom with a few lens ghosts along its axis."""
    cx, cy = w * 0.84, h * 0.12
    pulse = 1.0 + math.sin(phase * 0.4) * 0.05

    bloom = QRadialGradient(QPointF(cx, cy), max(w, h) * 0.34 * pulse)
    bloom.setColorAt(0.0, QColor(255, 252, 226, 86))
    bloom.setColorAt(0.35, QColor(198, 238, 255, 34))
    bloom.setColorAt(1.0, QColor(160, 220, 255, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(bloom)
    p.drawRect(QRectF(0, 0, w, h))

    # Ghosts run from the light towards the opposite corner.
    for step, size, alpha in ((0.28, 16, 26), (0.46, 9, 20),
                              (0.62, 22, 16), (0.8, 12, 12)):
        gx = cx + (w * 0.5 - cx) * step * 2
        gy = cy + (h * 0.5 - cy) * step * 2
        ghost = QRadialGradient(QPointF(gx, gy), size * 2.2)
        ghost.setColorAt(0.0, QColor(214, 246, 255, alpha))
        ghost.setColorAt(0.7, QColor(190, 236, 255, int(alpha * 0.4)))
        ghost.setColorAt(1.0, QColor(190, 236, 255, 0))
        p.setBrush(ghost)
        p.drawEllipse(QPointF(gx, gy), size * 2.2, size * 2.2)


def _grass(p, w, floor, phase, seed=107):
    """
    Glossy blades along the bottom, each with a lit edge.

    Two-tone: a darker body and a bright strip down one side, which is
    what gives a flat shape the look of a curved, waxy leaf.
    """
    rng = random.Random(seed)
    for _ in range(22):
        x = rng.uniform(-20, w + 20)
        height = rng.uniform(40, 130)
        width = rng.uniform(5, 13)
        lean = rng.uniform(-0.5, 0.5)
        rate = rng.uniform(0.4, 0.9)
        offset = rng.uniform(0, 6.28)
        sway = math.sin(phase * rate + offset) * 12

        tip = QPointF(x + lean * height + sway, floor - height)
        blade = QPainterPath(QPointF(x - width / 2, floor))
        blade.quadTo(QPointF(x - width * 0.9 + lean * height * 0.4 + sway * 0.5,
                             floor - height * 0.55), tip)
        blade.quadTo(QPointF(x + width * 1.1 + lean * height * 0.4 + sway * 0.5,
                             floor - height * 0.5),
                     QPointF(x + width / 2, floor))
        blade.closeSubpath()

        body = QLinearGradient(x - width, floor - height, x + width, floor)
        body.setColorAt(0.0, QColor(62, 148, 78, 150))
        body.setColorAt(0.55, QColor(40, 116, 66, 150))
        body.setColorAt(1.0, QColor(22, 82, 54, 150))
        p.setPen(Qt.NoPen)
        p.setBrush(body)
        p.drawPath(blade)

        shine = QPainterPath(QPointF(x - width * 0.16, floor))
        shine.quadTo(QPointF(x - width * 0.4 + lean * height * 0.4 + sway * 0.5,
                             floor - height * 0.55), tip)
        shine.quadTo(QPointF(x + width * 0.06 + lean * height * 0.4 + sway * 0.5,
                             floor - height * 0.5),
                     QPointF(x + width * 0.1, floor))
        shine.closeSubpath()
        p.setBrush(QColor(168, 226, 150, 70))
        p.drawPath(shine)


def _gloss_pattern(p, rect, size=34, gap=92, rich=False):
    """The tiled motif: a glass lozenge with a highlight across its top."""
    p.save()
    p.setClipRect(rect, Qt.IntersectClip)
    row = 0
    y = rect.top() + gap * 0.45
    while y < rect.bottom() + gap:
        x = rect.left() + (gap * 0.5 if row % 2 else 0) + gap * 0.35
        while x < rect.right() + gap:
            if rich:
                _lozenge_rich(p, x, y, size)
                x += gap
                continue
            pill = QRectF(x - size * 0.6, y - size * 0.3,
                          size * 1.2, size * 0.6)
            glass = QLinearGradient(x, pill.top(), x, pill.bottom())
            glass.setColorAt(0.0, QColor(224, 248, 255, 34))
            glass.setColorAt(0.48, QColor(186, 228, 244, 16))
            glass.setColorAt(0.52, QColor(150, 200, 224, 22))
            glass.setColorAt(1.0, QColor(206, 240, 252, 12))
            p.setPen(QPen(QColor(220, 246, 255, 26), 1.0))
            p.setBrush(glass)
            p.drawRoundedRect(pill, size * 0.3, size * 0.3)
            x += gap
        y += gap * 0.82
        row += 1
    p.restore()


def aero(p, w, h, win, clip, safe, phase, rich=False):
    """
    Frutiger Aero: wet glass, aqua light, ribbons and greenery.

    Same two-region rule as the rest. The sky, the flare and the beads
    are placed - beads sit *on* the glass, so clipping them around a text
    box would cut them in half - while the ribbons, the tiled glass and
    the grass keep clear of text and controls.
    """
    sky = QLinearGradient(0, 0, 0, h)
    sky.setColorAt(0.0, QColor(96, 186, 232, 96))
    sky.setColorAt(0.42, QColor(140, 218, 238, 70))
    sky.setColorAt(0.72, QColor(96, 186, 196, 74))
    sky.setColorAt(1.0, QColor(44, 122, 132, 92))

    p.save()
    p.setClipRegion(safe, Qt.IntersectClip)
    p.fillRect(QRectF(0, 0, w, h), sky)
    _sun_flare(p, w, h, phase)
    p.restore()

    sidebar = _sidebar_width(win)
    live = getattr(win, "live", None)
    strip = getattr(live, "strip", None) if live else None
    strip_top = h
    if strip is not None and strip.isVisible():
        strip_top = strip.mapTo(win, QPoint(0, 0)).y()

    p.save()
    p.setClipRegion(clip, Qt.IntersectClip)
    _swoosh(p, w, h, phase, rich=rich)
    _gloss_pattern(p, QRectF(0, 0, sidebar, h), rich=rich)
    _gloss_pattern(p, QRectF(sidebar, 0, w - sidebar, 38), size=26,
                   gap=70, rich=rich)
    if strip_top < h:
        _gloss_pattern(p, QRectF(sidebar, strip_top, w - sidebar,
                                 h - strip_top), size=28, gap=76,
                       rich=rich)
    p.restore()

    p.save()
    p.setClipRegion(safe, Qt.IntersectClip)
    _grass(p, w, h - 6, phase)
    _beads(p, w, h, phase)
    _cool_splitters(p, win, QColor(120, 214, 236, 190))
    _tally_glow(p, win, live, phase)
    p.restore()


AERO_QSS = """
/* Glass buttons: a light upper half, a darker lower one, and a hard
   line between them. That split is the whole look - it is how a surface
   says it is polished. */
QPushButton {
    border-radius: 9px;
    border: 1px solid #2D6E86;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #2B5C6C, stop:0.49 #1E4656,
                                stop:0.51 #163846, stop:1 #1B4152);
    color: #DDF3FA;
}
QPushButton:hover {
    border: 1px solid #58A8C4;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #37718A, stop:0.49 #265A6E,
                                stop:0.51 #1D4859, stop:1 #235468);
}
QPushButton:disabled {
    border: 1px solid #27505E;
    color: #5E8494;
}

#primaryButton {
    border: 1px solid #1E86A8;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #7FE0F4, stop:0.49 #3FBCDC,
                                stop:0.51 #1F9CC2, stop:1 #38B4D4);
    color: #04242E;
    font-weight: 600;
}
#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #9AECFF, stop:0.49 #55CCEA,
                                stop:0.51 #2EAED2, stop:1 #4AC6E4);
}

#confirmButton, #denyButton {
    border-radius: 9px;
}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox,
QDoubleSpinBox {
    border-radius: 8px;
    border: 1px solid #2B5E70;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #58A8C4;
}

#feedList {
    border: 1px solid #2B5E70;
    border-radius: 8px;
}
"""


# ---- enhanced drawings -------------------------------------------------
#
# The "Enhance visuals" option swaps these in for the plainer originals.
# Both sets are kept: the originals are lighter to draw and some people
# prefer them, so this is a preference rather than a fix. Every one of
# these is the same subject drawn with shading, joints and highlights
# instead of assembled from primitives.

def _lantern_rich(p, size):
    """
    A lit lantern rather than an outline of one.

    Filled and shaded, with the face cut out and glowing from inside, so
    it reads as an object with a candle in it instead of a diagram.
    """
    r = size / 2
    body = QPainterPath()
    body.addEllipse(QPointF(0, r * 0.04), r, r * 0.88)
    for offset in (-0.58, 0.58):
        lobe = QPainterPath()
        lobe.addEllipse(QPointF(r * offset * 0.62, r * 0.04),
                        r * 0.62, r * 0.86)
        body = body.united(lobe)

    fill = QRadialGradient(QPointF(-r * 0.28, -r * 0.34), r * 1.7)
    fill.setColorAt(0.0, QColor(196, 146, 236, 92))
    fill.setColorAt(0.55, QColor(150, 98, 200, 70))
    fill.setColorAt(1.0, QColor(92, 56, 132, 62))
    p.setPen(Qt.NoPen)
    p.setBrush(fill)
    p.drawPath(body)

    # Ribs as shading rather than lines: two soft darker seams.
    p.setPen(QPen(QColor(88, 52, 126, 54), max(1.0, size * 0.05)))
    p.setBrush(Qt.NoBrush)
    for offset in (-0.34, 0.34):
        rib = QPainterPath(QPointF(r * offset, -r * 0.74))
        rib.quadTo(QPointF(r * offset * 1.7, r * 0.02),
                   QPointF(r * offset, r * 0.80))
        p.drawPath(rib)

    stem = QPainterPath(QPointF(-r * 0.13, -r * 0.82))
    stem.cubicTo(QPointF(-r * 0.22, -r * 1.18), QPointF(r * 0.06, -r * 1.3),
                 QPointF(r * 0.16, -r * 1.06))
    stem.cubicTo(QPointF(r * 0.14, -r * 0.94), QPointF(r * 0.1, -r * 0.86),
                 QPointF(r * 0.11, -r * 0.8))
    stem.closeSubpath()
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(110, 154, 96, 86))
    p.drawPath(stem)

    face = QPainterPath()
    for side in (-1, 1):
        eye = QPainterPath()
        eye.moveTo(QPointF(side * r * 0.50, -r * 0.30))
        eye.lineTo(QPointF(side * r * 0.16, -r * 0.06))
        eye.lineTo(QPointF(side * r * 0.46, r * 0.04))
        eye.closeSubpath()
        face = face.united(eye)
    mouth = QPainterPath(QPointF(-r * 0.54, r * 0.26))
    for i, mx in enumerate((-0.36, -0.18, 0.0, 0.18, 0.36, 0.54)):
        mouth.lineTo(QPointF(r * mx, r * (0.50 if i % 2 else 0.28)))
    mouth.lineTo(QPointF(r * 0.46, r * 0.60))
    mouth.lineTo(QPointF(-r * 0.46, r * 0.60))
    mouth.closeSubpath()
    face = face.united(mouth)

    # The glow sits behind the cut-out, so the face is lit from within.
    glow = QRadialGradient(QPointF(0, r * 0.1), r * 1.1)
    glow.setColorAt(0.0, QColor(255, 214, 140, 150))
    glow.setColorAt(1.0, QColor(255, 170, 90, 70))
    p.setBrush(glow)
    p.drawPath(face)


def _star_rich(p, x, y, size, tint):
    """
    A four-point star with a bloom, instead of a dot with a cross on it.

    The points are curved in rather than straight, which is how a lens
    actually flares, and the bloom carries the colour so the star itself
    can stay near-white.
    """
    bloom = QRadialGradient(QPointF(x, y), size * 5.0)
    bloom.setColorAt(0.0, QColor(*tint, 110))
    bloom.setColorAt(0.35, QColor(*tint, 40))
    bloom.setColorAt(1.0, QColor(*tint, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(bloom)
    p.drawEllipse(QPointF(x, y), size * 5.0, size * 5.0)

    long_reach = size * 4.4
    short_reach = size * 1.5
    star = QPainterPath(QPointF(x, y - long_reach))
    star.quadTo(QPointF(x + size * 0.3, y - size * 0.3),
                QPointF(x + short_reach, y))
    star.quadTo(QPointF(x + size * 0.3, y + size * 0.3),
                QPointF(x, y + long_reach))
    star.quadTo(QPointF(x - size * 0.3, y + size * 0.3),
                QPointF(x - short_reach, y))
    star.quadTo(QPointF(x - size * 0.3, y - size * 0.3),
                QPointF(x, y - long_reach))
    p.setBrush(QColor(255, 255, 255, 190))
    p.drawPath(star)

    core = QRadialGradient(QPointF(x, y), size * 1.2)
    core.setColorAt(0.0, QColor(255, 255, 255, 240))
    core.setColorAt(1.0, QColor(*tint, 90))
    p.setBrush(core)
    p.drawEllipse(QPointF(x, y), size * 1.2, size * 1.2)


def _fish_rich(p, x, y, size, colour, beat=0.0):
    """
    A fish with a back, a belly and fins.

    The old one was two mirrored curves, which gives a leaf shape. A real
    fish is asymmetric top to bottom - a curved back and a flatter belly -
    and that asymmetry is most of what makes it read as a fish.
    """
    facing = 1
    body = QPainterPath(QPointF(x + size * 1.05, y + size * 0.04))
    body.cubicTo(QPointF(x + size * 0.35, y - size * 0.62),
                 QPointF(x - size * 0.35, y - size * 0.54),
                 QPointF(x - size * 0.78, y - size * 0.06))
    body.cubicTo(QPointF(x - size * 0.4, y + size * 0.46),
                 QPointF(x + size * 0.35, y + size * 0.44),
                 QPointF(x + size * 1.05, y + size * 0.04))

    shade = QLinearGradient(x, y - size * 0.6, x, y + size * 0.5)
    shade.setColorAt(0.0, colour.lighter(126))
    shade.setColorAt(0.55, colour)
    shade.setColorAt(1.0, colour.darker(148))
    p.setPen(Qt.NoPen)
    p.setBrush(shade)
    p.drawPath(body)

    # Dorsal and pelvic fins, translucent so they read as thin.
    fin = QPainterPath(QPointF(x - size * 0.1, y - size * 0.46))
    fin.quadTo(QPointF(x + size * 0.1, y - size * 0.95),
               QPointF(x + size * 0.42, y - size * 0.34))
    fin.closeSubpath()
    p.setBrush(QColor(colour.red(), colour.green(), colour.blue(), 120))
    p.drawPath(fin)

    pelvic = QPainterPath(QPointF(x + size * 0.06, y + size * 0.36))
    pelvic.quadTo(QPointF(x + size * 0.12, y + size * 0.72),
                  QPointF(x + size * 0.42, y + size * 0.3))
    pelvic.closeSubpath()
    p.drawPath(pelvic)

    tail = QPainterPath(QPointF(x - size * 0.7, y - size * 0.04))
    tail.cubicTo(QPointF(x - size * 1.1, y - size * 0.5 + beat),
                 QPointF(x - size * 1.4, y - size * 0.44 + beat),
                 QPointF(x - size * 1.42, y - size * 0.2 + beat))
    tail.quadTo(QPointF(x - size * 1.2, y + beat * 0.6),
                QPointF(x - size * 1.42, y + size * 0.22 + beat))
    tail.cubicTo(QPointF(x - size * 1.36, y + size * 0.48 + beat),
                 QPointF(x - size * 1.06, y + size * 0.44 + beat),
                 QPointF(x - size * 0.7, y - size * 0.04))
    p.setBrush(shade)
    p.drawPath(tail)

    # Gill line, then the eye with a catchlight.
    p.setPen(QPen(QColor(255, 255, 255, 70), max(0.8, size * 0.05)))
    p.setBrush(Qt.NoBrush)
    gill = QPainterPath(QPointF(x + size * 0.42, y - size * 0.34))
    gill.quadTo(QPointF(x + size * 0.28, y), QPointF(x + size * 0.44,
                                                     y + size * 0.3))
    p.drawPath(gill)

    p.setPen(Qt.NoPen)
    p.setBrush(QColor(250, 252, 255, 210))
    p.drawEllipse(QPointF(x + size * 0.68, y - size * 0.12),
                  size * 0.15, size * 0.15)
    p.setBrush(QColor(14, 20, 26, 235))
    p.drawEllipse(QPointF(x + size * 0.70, y - size * 0.12),
                  size * 0.09, size * 0.09)
    p.setBrush(QColor(255, 255, 255, 210))
    p.drawEllipse(QPointF(x + size * 0.66, y - size * 0.17),
                  size * 0.035, size * 0.035)


def _crab_rich(p, x, floor, scale=1.0):
    """
    A crab with a shaded carapace, jointed claws and eyestalks.

    The old one was flat ellipses and straight legs. Shell shading and
    bent joints are what turn a diagram of a crab into a crab.
    """
    y = floor - 8 * scale
    shell = QColor(206, 68, 52)

    # Legs: two segments each, bending backwards.
    p.setPen(QPen(shell.darker(150), max(1.0, 1.5 * scale),
                  Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    for side in (-1, 1):
        for i in range(3):
            knee = QPointF(x + side * (7 + i * 4.4) * scale,
                           y - (1.6 - i * 0.8) * scale)
            foot = QPointF(x + side * (10 + i * 5.6) * scale,
                           y + (5.5 + i * 1.1) * scale)
            leg = QPainterPath(QPointF(x + side * 3.4 * scale, y + scale))
            leg.quadTo(knee, foot)
            p.drawPath(leg)

    # Claws: an upper arm, then a pincer with a gap.
    for side in (-1, 1):
        elbow = QPointF(x + side * 8.5 * scale, y - 1.0 * scale)
        hand = QPointF(x + side * 13.5 * scale, y - 5.0 * scale)
        p.setPen(QPen(shell.darker(140), max(1.0, 1.6 * scale),
                      Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(x + side * 5 * scale, y - 0.5 * scale), elbow)

        pincer = QPainterPath(hand)
        pincer.quadTo(QPointF(hand.x() + side * 3.4 * scale,
                              hand.y() - 3.4 * scale),
                      QPointF(hand.x() + side * 5.4 * scale,
                              hand.y() - 0.6 * scale))
        pincer.quadTo(QPointF(hand.x() + side * 2.6 * scale,
                              hand.y() + 1.0 * scale), hand)
        claw = QLinearGradient(hand.x(), hand.y() - 4 * scale,
                               hand.x(), hand.y() + 2 * scale)
        claw.setColorAt(0.0, shell.lighter(130))
        claw.setColorAt(1.0, shell.darker(120))
        p.setPen(QPen(shell.darker(155), max(0.8, 1.0 * scale)))
        p.setBrush(claw)
        p.drawPath(pincer)
        # The lower jaw of the pincer, slightly open.
        jaw = QPainterPath(hand)
        jaw.quadTo(QPointF(hand.x() + side * 3.0 * scale,
                           hand.y() + 2.6 * scale),
                   QPointF(hand.x() + side * 5.0 * scale,
                           hand.y() + 0.4 * scale))
        p.drawPath(jaw)

    # Carapace: wider than tall, lit from above.
    carapace = QPainterPath()
    carapace.moveTo(QPointF(x - 9 * scale, y + 0.6 * scale))
    carapace.cubicTo(QPointF(x - 8.6 * scale, y - 5.4 * scale),
                     QPointF(x + 8.6 * scale, y - 5.4 * scale),
                     QPointF(x + 9 * scale, y + 0.6 * scale))
    carapace.cubicTo(QPointF(x + 6 * scale, y + 5.0 * scale),
                     QPointF(x - 6 * scale, y + 5.0 * scale),
                     QPointF(x - 9 * scale, y + 0.6 * scale))
    body = QLinearGradient(x, y - 6 * scale, x, y + 5 * scale)
    body.setColorAt(0.0, shell.lighter(136))
    body.setColorAt(0.5, shell)
    body.setColorAt(1.0, shell.darker(152))
    p.setPen(QPen(shell.darker(168), max(0.8, 1.0 * scale)))
    p.setBrush(body)
    p.drawPath(carapace)

    # A pale sheen across the top of the shell.
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 210, 196, 70))
    p.drawEllipse(QRectF(x - 5.4 * scale, y - 4.4 * scale,
                         10.8 * scale, 3.4 * scale))

    # Eyestalks, which is the detail that gives it a face.
    for side in (-1, 1):
        p.setPen(QPen(shell.darker(140), max(0.9, 1.2 * scale),
                      Qt.SolidLine, Qt.RoundCap))
        top = QPointF(x + side * 3.4 * scale, y - 8.4 * scale)
        p.drawLine(QPointF(x + side * 2.8 * scale, y - 4.6 * scale), top)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(24, 18, 20))
        p.drawEllipse(top, 1.5 * scale, 1.6 * scale)
        p.setBrush(QColor(255, 255, 255, 190))
        p.drawEllipse(QPointF(top.x() - 0.4 * scale, top.y() - 0.5 * scale),
                      0.5 * scale, 0.5 * scale)


def _web_rich(p, x, y, size):
    """
    A web with weight in it: thicker anchors, finer spirals, and dew.

    One pen width for everything is what makes the old one look like
    graph paper. A real web has heavy radials and gossamer between them,
    and it sags more the further from the anchor.
    """
    rng = random.Random(7)
    spokes = 9
    angles = [math.radians(90 * i / (spokes - 1)) for i in range(spokes)]

    anchor = QPen(QColor(226, 234, 248, 120))
    anchor.setWidthF(1.5)
    anchor.setCapStyle(Qt.RoundCap)
    p.setPen(anchor)
    p.setBrush(Qt.NoBrush)
    for a in angles:
        p.drawLine(QPointF(x, y),
                   QPointF(x + math.cos(a) * size, y + math.sin(a) * size))

    for ring in range(1, 8):
        r = size * ring / 7.4
        # Finer and fainter towards the middle, where the silk is newer.
        fine = QPen(QColor(222, 232, 246, int(60 + 60 * (ring / 7.4))))
        fine.setWidthF(0.55 + 0.45 * (ring / 7.4))
        p.setPen(fine)
        for i in range(spokes - 1):
            a1, a2 = angles[i], angles[i + 1]
            mid = (a1 + a2) / 2
            sag = r * (0.90 - 0.13 * (ring / 7.4))
            path = QPainterPath(QPointF(x + math.cos(a1) * r,
                                        y + math.sin(a1) * r))
            path.quadTo(QPointF(x + math.cos(mid) * sag,
                                y + math.sin(mid) * sag),
                        QPointF(x + math.cos(a2) * r,
                                y + math.sin(a2) * r))
            p.drawPath(path)

    # Dew: a few beads hanging on the strands, which is the detail that
    # makes a web look spun rather than ruled.
    p.setPen(Qt.NoPen)
    for _ in range(7):
        a = rng.uniform(angles[0], angles[-1])
        r = rng.uniform(size * 0.25, size * 0.95)
        bx = x + math.cos(a) * r
        by = y + math.sin(a) * r
        rad = rng.uniform(0.9, 1.9)
        p.setBrush(QColor(236, 246, 255, 150))
        p.drawEllipse(QPointF(bx, by), rad, rad * 1.15)
        p.setBrush(QColor(255, 255, 255, 200))
        p.drawEllipse(QPointF(bx - rad * 0.3, by - rad * 0.4),
                      rad * 0.3, rad * 0.3)


# ---- render the comparison --------------------------------------------


def _spider_rich(p, x, y, drop, scale=1.0):
    """
    A spider with a rounded abdomen and legs that bend.

    Straight legs radiating from a point are what make the old one look
    like an asterisk. Real legs rise from the body, peak at a joint, then
    drop - and the two front pairs reach forward while the back pairs
    trail, which is what gives it a direction.
    """
    p.setPen(QPen(QColor(226, 232, 244, 120), 1.0))
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(x, y), QPointF(x, y + drop))
    cx, cy = x, y + drop

    body = QColor(22, 18, 26)
    p.setPen(QPen(body.lighter(180), max(0.9, 1.1 * scale),
                  Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    for side in (-1, 1):
        for i, (reach, lift) in enumerate(((11, 7), (13, 4),
                                           (12, -2), (9.5, -6))):
            knee = QPointF(cx + side * reach * 0.55 * scale,
                           cy - (lift * 0.7 + 4) * scale)
            foot = QPointF(cx + side * reach * scale,
                           cy + (6 - lift * 0.35) * scale)
            leg = QPainterPath(QPointF(cx + side * 1.6 * scale,
                                       cy + 1.5 * scale))
            leg.quadTo(knee, foot)
            p.drawPath(leg)

    abdomen = QRadialGradient(QPointF(cx - 1.6 * scale, cy + 5 * scale),
                              8 * scale)
    abdomen.setColorAt(0.0, QColor(62, 54, 74))
    abdomen.setColorAt(0.6, body)
    abdomen.setColorAt(1.0, QColor(10, 8, 14))
    p.setPen(Qt.NoPen)
    p.setBrush(abdomen)
    p.drawEllipse(QPointF(cx, cy + 6.5 * scale), 6.8 * scale, 7.8 * scale)

    head = QRadialGradient(QPointF(cx - 1.2 * scale, cy - 1 * scale),
                           4.4 * scale)
    head.setColorAt(0.0, QColor(56, 48, 66))
    head.setColorAt(1.0, QColor(14, 12, 18))
    p.setBrush(head)
    p.drawEllipse(QPointF(cx, cy), 4.2 * scale, 3.8 * scale)

    # A pale marking on the back, and two eye glints.
    p.setBrush(QColor(198, 190, 214, 90))
    mark = QPainterPath(QPointF(cx, cy + 2.6 * scale))
    mark.quadTo(QPointF(cx + 2.4 * scale, cy + 6 * scale),
                QPointF(cx, cy + 10 * scale))
    mark.quadTo(QPointF(cx - 2.4 * scale, cy + 6 * scale),
                QPointF(cx, cy + 2.6 * scale))
    p.drawPath(mark)
    p.setBrush(QColor(236, 240, 250, 170))
    for side in (-1, 1):
        p.drawEllipse(QPointF(cx + side * 1.5 * scale, cy - 1.2 * scale),
                      0.8 * scale, 0.8 * scale)


def _weed_rich(p, x, floor, height, width):
    """
    A blade with a curl and a lit edge.

    The old one is a flat tapered strip, so it reads as a ribbon of
    colour. Giving it a spine highlight and a darker underside turns it
    into something with a surface facing the light.
    """
    segments = 9
    spine = []
    for i in range(segments + 1):
        t = i / segments
        lean = math.sin(t * 2.6) * 22 * t * t
        spine.append(QPointF(x + lean, floor - height * t))

    def edge(offset):
        pts = []
        for i, point in enumerate(spine):
            t = i / segments
            taper = width * (1 - t * 0.82) * offset
            pts.append(QPointF(point.x() + taper, point.y()))
        return pts

    left_edge = edge(-0.5)
    right_edge = edge(0.5)
    blade = QPainterPath(left_edge[0])
    for point in left_edge[1:]:
        blade.lineTo(point)
    for point in reversed(right_edge):
        blade.lineTo(point)
    blade.closeSubpath()

    body = QLinearGradient(x - width, floor, x + width, floor - height)
    body.setColorAt(0.0, QColor(24, 86, 66, 200))
    body.setColorAt(0.5, QColor(48, 132, 88, 200))
    body.setColorAt(1.0, QColor(30, 100, 74, 200))
    p.setPen(Qt.NoPen)
    p.setBrush(body)
    p.drawPath(blade)

    # The spine catch-light, running most of the length.
    highlight = QPainterPath(spine[0])
    for point in spine[1:]:
        highlight.lineTo(point)
    pen = QPen(QColor(150, 220, 160, 90))
    pen.setWidthF(max(1.0, width * 0.22))
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawPath(highlight)


def _bubble_rich(p, x, y, radius):
    """
    A bubble is a shell, not a disc.

    Nearly hollow, with a bright rim where the film is edge-on, a soft
    band of reflected light and two highlights - one hard from the source
    and one faint from below.
    """
    p.setPen(Qt.NoPen)
    body = QRadialGradient(QPointF(x, y), radius)
    body.setColorAt(0.0, QColor(150, 214, 236, 10))
    body.setColorAt(0.72, QColor(160, 220, 240, 26))
    body.setColorAt(0.93, QColor(206, 242, 252, 86))
    body.setColorAt(1.0, QColor(226, 250, 255, 20))
    p.setBrush(body)
    p.drawEllipse(QPointF(x, y), radius, radius)

    rim = QPen(QColor(214, 246, 255, 120))
    rim.setWidthF(max(0.6, radius * 0.10))
    p.setPen(rim)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(x, y), radius, radius)

    # Reflected band along the lower right, where light comes back up
    # through the water.
    p.setPen(QPen(QColor(236, 252, 255, 90), max(0.6, radius * 0.13),
                  Qt.SolidLine, Qt.RoundCap))
    p.drawArc(QRectF(x - radius * 0.78, y - radius * 0.78,
                     radius * 1.56, radius * 1.56),
              -70 * 16, 58 * 16)

    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 210))
    p.drawEllipse(QPointF(x - radius * 0.34, y - radius * 0.36),
                  radius * 0.20, radius * 0.24)
    p.setBrush(QColor(255, 255, 255, 80))
    p.drawEllipse(QPointF(x + radius * 0.30, y + radius * 0.40),
                  radius * 0.12, radius * 0.12)


def _bow_rich(p, size):
    """
    A ribbon bow with folds.

    The old one is two outlined loops. Filling them, shading each loop
    darker towards the knot, and adding a small fold line gives the
    ribbon thickness - and the knot sits on top rather than being a dot
    in a gap.
    """
    r = size / 2
    for side in (-1, 1):
        loop = QPainterPath(QPointF(side * r * 0.16, 0))
        loop.cubicTo(QPointF(side * r * 1.45, -r * 1.15),
                     QPointF(side * r * 1.85, r * 0.35),
                     QPointF(side * r * 0.22, r * 0.18))
        loop.cubicTo(QPointF(side * r * 0.7, r * 0.1),
                     QPointF(side * r * 0.6, -r * 0.1),
                     QPointF(side * r * 0.16, 0))
        shade = QLinearGradient(side * r * 1.8, -r, side * r * 0.1, r * 0.3)
        shade.setColorAt(0.0, QColor(255, 206, 228, 150))
        shade.setColorAt(0.7, QColor(246, 166, 200, 130))
        shade.setColorAt(1.0, QColor(214, 122, 166, 120))
        p.setPen(QPen(QColor(255, 226, 240, 90), 1.0))
        p.setBrush(shade)
        p.drawPath(loop)

        tail = QPainterPath(QPointF(side * r * 0.2, r * 0.2))
        tail.cubicTo(QPointF(side * r * 0.72, r * 0.95),
                     QPointF(side * r * 0.58, r * 1.35),
                     QPointF(side * r * 1.02, r * 1.6))
        tail.cubicTo(QPointF(side * r * 0.5, r * 1.28),
                     QPointF(side * r * 0.34, r * 0.76),
                     QPointF(side * r * 0.06, r * 0.24))
        tail.closeSubpath()
        p.setBrush(QColor(238, 152, 192, 125))
        p.drawPath(tail)

        # A fold, which is the cheapest way to suggest thickness.
        p.setPen(QPen(QColor(198, 108, 154, 90), 1.0))
        p.setBrush(Qt.NoBrush)
        fold = QPainterPath(QPointF(side * r * 0.3, r * 0.02))
        fold.quadTo(QPointF(side * r * 0.8, -r * 0.32),
                    QPointF(side * r * 1.12, -r * 0.06))
        p.drawPath(fold)

    knot = QRadialGradient(QPointF(-r * 0.08, -r * 0.08), r * 0.42)
    knot.setColorAt(0.0, QColor(255, 220, 236, 190))
    knot.setColorAt(1.0, QColor(224, 132, 176, 160))
    p.setPen(QPen(QColor(255, 232, 244, 90), 1.0))
    p.setBrush(knot)
    p.drawEllipse(QPointF(0, 0), r * 0.32, r * 0.29)


def _candle_rich(p, x, base, height, phase, width=7.0):
    """
    A candle that has been burning: wax down one side, a hollowed rim,
    and a flame with a dark base where the wick starves it of oxygen.

    The old flame is a solid teardrop. A real one is banded - dim blue at
    the very bottom, bright core, softer tip - and that banding is most
    of what sells it at this size.
    """
    sway = math.sin(phase) * 1.5 + math.sin(phase * 2.7) * 0.7
    flare = 1.0 + math.sin(phase * 1.9) * 0.16

    pool = QRadialGradient(QPointF(x, base), 50 * flare)
    pool.setColorAt(0.0, QColor(255, 176, 84, 76))
    pool.setColorAt(0.55, QColor(240, 140, 60, 30))
    pool.setColorAt(1.0, QColor(220, 120, 50, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(pool)
    p.drawEllipse(QPointF(x, base), 50 * flare, 28 * flare)

    # Wax body, lit from the flame above rather than flat.
    body = QRectF(x - width / 2, base - height, width, height)
    wax = QLinearGradient(body.left(), 0, body.right(), 0)
    wax.setColorAt(0.0, QColor(186, 172, 152, 210))
    wax.setColorAt(0.34, QColor(238, 228, 210, 215))
    wax.setColorAt(1.0, QColor(172, 158, 138, 210))
    p.setBrush(wax)
    p.setPen(QPen(QColor(120, 108, 96, 120), 0.8))
    p.drawRoundedRect(body, width * 0.28, width * 0.28)

    # A run of wax down one side: two curves meeting in a blunt tip.
    run = QPainterPath(QPointF(x - width * 0.42, base - height + 2))
    run.cubicTo(QPointF(x - width * 0.62, base - height * 0.62),
                QPointF(x - width * 0.36, base - height * 0.52),
                QPointF(x - width * 0.34, base - height * 0.34))
    run.cubicTo(QPointF(x - width * 0.16, base - height * 0.5),
                QPointF(x - width * 0.2, base - height * 0.72),
                QPointF(x - width * 0.42, base - height + 2))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(248, 240, 226, 150))
    p.drawPath(run)

    # Hollowed rim: a lip, with the melted well darker inside it.
    rim = QRectF(body.left(), body.top() - 2.0, width, 4.0)
    p.setBrush(QColor(246, 238, 224, 220))
    p.drawEllipse(rim)
    p.setBrush(QColor(196, 170, 138, 190))
    p.drawEllipse(QRectF(rim.left() + width * 0.18, rim.top() + 1.0,
                         width * 0.64, 2.0))

    wick_base = base - height - 1.0
    wick_top = wick_base - 3.0
    p.setPen(QPen(QColor(46, 38, 32, 230), 1.1, Qt.SolidLine, Qt.RoundCap))
    wick = QPainterPath(QPointF(x, wick_base))
    wick.quadTo(QPointF(x + sway * 0.2, wick_base - 2),
                QPointF(x + sway * 0.35, wick_top))
    p.setBrush(Qt.NoBrush)
    p.drawPath(wick)

    halo = QRadialGradient(QPointF(x, wick_top - 6), 26 * flare)
    halo.setColorAt(0.0, QColor(255, 190, 96, 130))
    halo.setColorAt(0.5, QColor(255, 150, 50, 46))
    halo.setColorAt(1.0, QColor(255, 130, 40, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(halo)
    p.drawEllipse(QPointF(x, wick_top - 6), 26 * flare, 30 * flare)

    def teardrop(spread, lift, tilt):
        path = QPainterPath(QPointF(x - spread, wick_top))
        path.quadTo(QPointF(x - spread * 1.35, wick_top - lift * 0.55),
                    QPointF(x + tilt, wick_top - lift))
        path.quadTo(QPointF(x + spread * 1.35, wick_top - lift * 0.55),
                    QPointF(x + spread, wick_top))
        path.quadTo(QPointF(x, wick_top + spread * 0.5),
                    QPointF(x - spread, wick_top))
        return path

    # Outer flame, then core, then the cool base at the wick.
    p.setBrush(QColor(255, 158, 44, 190))
    p.drawPath(teardrop(3.6, 15 * flare, sway))
    p.setBrush(QColor(255, 200, 96, 230))
    p.drawPath(teardrop(2.5, 11 * flare, sway * 0.75))
    p.setBrush(QColor(255, 244, 206, 245))
    p.drawPath(teardrop(1.4, 6.5 * flare, sway * 0.5))
    p.setBrush(QColor(120, 150, 220, 120))
    p.drawEllipse(QPointF(x + sway * 0.2, wick_top - 1.2), 1.5, 2.2)


def _constellation_rich(p, size, seed):
    """
    Stars of real variety, joined by lines that fade towards the middle.

    Every dot the same brightness is what makes the old one look like a
    connect-the-dots puzzle. A constellation is mostly faint, with one or
    two that carry it.
    """
    rng = random.Random(seed)
    points = [QPointF(rng.uniform(-size / 2, size / 2),
                      rng.uniform(-size / 2, size / 2))
              for _ in range(rng.randint(4, 6))]

    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        line = QLinearGradient(a, b)
        line.setColorAt(0.0, QColor(150, 176, 230, 70))
        line.setColorAt(0.5, QColor(150, 176, 230, 22))
        line.setColorAt(1.0, QColor(150, 176, 230, 70))
        pen = QPen(line, 0.8)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawLine(a, b)

    p.setPen(Qt.NoPen)
    for i, point in enumerate(points):
        bright = (i % 3 == 0)
        radius = 2.6 if bright else 1.4
        glow = QRadialGradient(point, radius * 4)
        glow.setColorAt(0.0, QColor(210, 226, 255, 110 if bright else 54))
        glow.setColorAt(1.0, QColor(190, 210, 255, 0))
        p.setBrush(glow)
        p.drawEllipse(point, radius * 4, radius * 4)
        p.setBrush(QColor(238, 244, 255, 235 if bright else 150))
        p.drawEllipse(point, radius, radius)


def _heart_rich(p, x, y, size, tint):
    """
    A heart with a lit upper lobe and a soft underside.

    Flat fill makes it a symbol; a gradient and one highlight make it an
    object with a surface.
    """
    path = QPainterPath(QPointF(x, y + size * 0.66))
    path.cubicTo(QPointF(x - size * 1.18, y - size * 0.2),
                 QPointF(x - size * 0.5, y - size * 0.98),
                 QPointF(x, y - size * 0.26))
    path.cubicTo(QPointF(x + size * 0.5, y - size * 0.98),
                 QPointF(x + size * 1.18, y - size * 0.2),
                 QPointF(x, y + size * 0.66))

    fill = QLinearGradient(x - size * 0.5, y - size * 0.8,
                           x + size * 0.4, y + size * 0.7)
    fill.setColorAt(0.0, QColor(min(255, tint[0] + 34),
                                min(255, tint[1] + 30),
                                min(255, tint[2] + 26), 220))
    fill.setColorAt(0.55, QColor(*tint, 205))
    fill.setColorAt(1.0, QColor(int(tint[0] * 0.72), int(tint[1] * 0.6),
                                int(tint[2] * 0.7), 195))
    p.setPen(Qt.NoPen)
    p.setBrush(fill)
    p.drawPath(path)

    p.setBrush(QColor(255, 255, 255, 110))
    glint = QPainterPath(QPointF(x - size * 0.46, y - size * 0.3))
    glint.quadTo(QPointF(x - size * 0.6, y - size * 0.62),
                 QPointF(x - size * 0.18, y - size * 0.56))
    glint.quadTo(QPointF(x - size * 0.34, y - size * 0.34),
                 QPointF(x - size * 0.46, y - size * 0.3))
    p.drawPath(glint)


def _cartouche_rich(p, size, seed):
    """
    An engraved frame: a cut edge with a lit side and a shadowed one.

    A single-weight outline reads as a sticker. Offsetting a light stroke
    up-left and a dark one down-right makes the same shape look chiselled
    into the surface.
    """
    r = size / 2
    corners = ((-r, -r * 0.72), (-r * 0.72, -r), (r * 0.72, -r),
               (r, -r * 0.72), (r, r * 0.72), (r * 0.72, r),
               (-r * 0.72, r), (-r, r * 0.72))
    frame = QPainterPath(QPointF(*corners[0]))
    for point in corners[1:]:
        frame.lineTo(QPointF(*point))
    frame.closeSubpath()

    # Recessed interior, barely there.
    inner = QLinearGradient(-r, -r, r, r)
    inner.setColorAt(0.0, QColor(90, 170, 160, 20))
    inner.setColorAt(1.0, QColor(40, 90, 88, 8))
    p.setPen(Qt.NoPen)
    p.setBrush(inner)
    p.drawPath(frame)

    p.save()
    p.translate(-0.7, -0.7)
    p.setPen(QPen(QColor(170, 240, 224, 60), 1.0))
    p.setBrush(Qt.NoBrush)
    p.drawPath(frame)
    p.restore()

    p.save()
    p.translate(0.7, 0.7)
    p.setPen(QPen(QColor(20, 60, 62, 70), 1.0))
    p.drawPath(frame)
    p.restore()

    p.setPen(QPen(QColor(130, 206, 192, 74), 1.0))
    p.drawPath(frame)

    # Corner studs, the detail that makes it look fixed to something.
    p.setPen(Qt.NoPen)
    for sx, sy in ((-r * 0.84, -r * 0.84), (r * 0.84, -r * 0.84),
                   (r * 0.84, r * 0.84), (-r * 0.84, r * 0.84)):
        p.setBrush(QColor(150, 226, 208, 60))
        p.drawEllipse(QPointF(sx, sy), size * 0.045, size * 0.045)


def _lozenge_rich(p, x, y, size):
    """
    A glass pill with a real specular arc.

    The old one has the light/dark split, which is the start of gloss,
    but nothing on top of it. A curved highlight sitting inside the upper
    half, plus a thin bright edge along the bottom, is what makes glass
    look wet rather than merely shaded.
    """
    pill = QRectF(x - size * 0.6, y - size * 0.3, size * 1.2, size * 0.6)
    radius = size * 0.3

    glass = QLinearGradient(x, pill.top(), x, pill.bottom())
    glass.setColorAt(0.0, QColor(232, 250, 255, 86))
    glass.setColorAt(0.49, QColor(178, 224, 244, 46))
    glass.setColorAt(0.51, QColor(126, 184, 212, 58))
    glass.setColorAt(1.0, QColor(196, 234, 250, 34))
    p.setPen(Qt.NoPen)
    p.setBrush(glass)
    p.drawRoundedRect(pill, radius, radius)

    # Specular: a lens shape filling the upper half, brightest at the top.
    gloss = QPainterPath(QPointF(pill.left() + radius * 0.6, y - size * 0.04))
    gloss.quadTo(QPointF(x, pill.top() - size * 0.06),
                 QPointF(pill.right() - radius * 0.6, y - size * 0.04))
    gloss.quadTo(QPointF(x, y + size * 0.08),
                 QPointF(pill.left() + radius * 0.6, y - size * 0.04))
    sheen = QLinearGradient(x, pill.top(), x, y)
    sheen.setColorAt(0.0, QColor(255, 255, 255, 120))
    sheen.setColorAt(1.0, QColor(255, 255, 255, 18))
    p.setBrush(sheen)
    p.drawPath(gloss)

    # Bright lower lip, where light bends back through.
    p.setPen(QPen(QColor(226, 250, 255, 80), max(0.8, size * 0.035)))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(pill.left() + size * 0.08, pill.top() + size * 0.06,
                     pill.width() - size * 0.16, pill.height() - size * 0.1),
              -150 * 16, 120 * 16)
    p.setPen(QPen(QColor(214, 244, 255, 54), 1.0))
    p.drawRoundedRect(pill, radius, radius)


def _scallop_rich(p, x, y, size):
    """
    A scallop shell, drawn from its own anatomy.

    The fan version failed because straight ribs radiating from a point
    is the geometry of a folding fan, not a shell. A real one has a
    wavy outer edge whose bumps line up with the ribs, ribs that widen
    and curve as they travel, and small ears either side of the hinge.

    Building the outline from the rib tips is what ties the two
    together: each bump in the edge belongs to a rib, so the shape reads
    as grown rather than assembled from parts that happen to overlap.
    """
    hinge = QPointF(x, y + size * 0.40)
    ribs = 8
    spread = 116.0
    start = 90 - spread / 2
    reach = size * 0.72

    def at(angle_deg, radius):
        a = math.radians(angle_deg)
        return QPointF(hinge.x() + math.cos(a) * radius,
                       hinge.y() - math.sin(a) * radius)

    # Tips vary slightly, so the edge is not machine-regular.
    tips = []
    for i in range(ribs + 1):
        t = i / ribs
        angle = start + spread * t
        # Fuller in the middle, tapering to the hinge corners.
        fall = math.sin(math.pi * t) ** 0.42
        tips.append((angle, reach * (0.78 + 0.22 * fall)))

    # Outline: up one side, scalloped across the top, down the other.
    shell = QPainterPath(hinge)
    shell.lineTo(at(tips[0][0], tips[0][1]))
    for i in range(ribs):
        a0, r0 = tips[i]
        a1, r1 = tips[i + 1]
        mid = (a0 + a1) / 2
        # The bump between two ribs bulges past both of them.
        bulge = max(r0, r1) * 1.07
        shell.quadTo(at(mid, bulge), at(a1, r1))
    shell.lineTo(hinge)
    shell.closeSubpath()

    body = QLinearGradient(hinge.x(), hinge.y(), hinge.x(),
                           hinge.y() - reach)
    body.setColorAt(0.0, QColor(74, 146, 174, 30))
    body.setColorAt(0.6, QColor(140, 206, 224, 34))
    body.setColorAt(1.0, QColor(196, 238, 248, 24))
    p.setPen(Qt.NoPen)
    p.setBrush(body)
    p.drawPath(shell)

    # Ribs as slivers that widen towards the edge, not as lines. A ridge
    # has a lit side and a shaded one, which a stroke cannot have.
    for i, (angle, radius) in enumerate(tips):
        if i in (0, ribs):
            continue
        half = spread / ribs * 0.30
        crest = QPainterPath(hinge)
        crest.quadTo(at(angle - half * 0.5, radius * 0.55),
                     at(angle - half, radius * 0.97))
        crest.quadTo(at(angle, radius * 1.02),
                     at(angle + half, radius * 0.97))
        crest.quadTo(at(angle + half * 0.5, radius * 0.55), hinge)
        weight = math.sin(math.pi * (i / ribs)) ** 0.6
        p.setBrush(QColor(212, 242, 250, int(16 + 22 * weight)))
        p.drawPath(crest)
        # The groove on one side of each ridge.
        p.setPen(QPen(QColor(58, 122, 150, int(20 + 26 * weight)), 0.7))
        p.setBrush(Qt.NoBrush)
        groove = QPainterPath(hinge)
        groove.quadTo(at(angle + half * 1.4, radius * 0.5),
                      at(angle + half * 1.6, radius * 0.95))
        p.drawPath(groove)
        p.setPen(Qt.NoPen)

    # Ears: the little flat wings either side of the hinge.
    for side in (-1, 1):
        ear = QPainterPath(hinge)
        ear.lineTo(QPointF(hinge.x() + side * size * 0.30,
                           hinge.y() - size * 0.04))
        ear.quadTo(QPointF(hinge.x() + side * size * 0.26,
                           hinge.y() - size * 0.16),
                   QPointF(hinge.x() + side * size * 0.08,
                           hinge.y() - size * 0.17))
        ear.closeSubpath()
        p.setBrush(QColor(168, 222, 238, 26))
        p.drawPath(ear)

    p.setPen(QPen(QColor(198, 238, 248, 46), 1.0))
    p.setBrush(Qt.NoBrush)
    p.drawPath(shell)

    # Umbo: the knot at the hinge everything radiates from.
    p.setPen(Qt.NoPen)
    knot = QRadialGradient(hinge, size * 0.09)
    knot.setColorAt(0.0, QColor(222, 246, 252, 64))
    knot.setColorAt(1.0, QColor(150, 206, 226, 18))
    p.setBrush(knot)
    p.drawEllipse(hinge, size * 0.09, size * 0.07)


def _cubic(p0, p1, p2, p3, t):
    """A point on a cubic, and the tangent there."""
    mt = 1 - t
    point = QPointF(
        mt ** 3 * p0.x() + 3 * mt * mt * t * p1.x()
        + 3 * mt * t * t * p2.x() + t ** 3 * p3.x(),
        mt ** 3 * p0.y() + 3 * mt * mt * t * p1.y()
        + 3 * mt * t * t * p2.y() + t ** 3 * p3.y())
    tangent = QPointF(
        3 * mt * mt * (p1.x() - p0.x()) + 6 * mt * t * (p2.x() - p1.x())
        + 3 * t * t * (p3.x() - p2.x()),
        3 * mt * mt * (p1.y() - p0.y()) + 6 * mt * t * (p2.y() - p1.y())
        + 3 * t * t * (p3.y() - p2.y()))
    return point, tangent


def _through_buffer(p, w, h, draw, scale=4):
    """
    Run `draw` into a buffer a quarter the size, then scale it up.

    Stacked translucent bands each keep an edge of their own, and across
    a wide shape those edges show as steps - measured at up to fifteen
    levels of brightness on the underwater shafts, which reads as faint
    coloured wedges. Scaling a small buffer up interpolates every one of
    those edges away.

    It is also much cheaper, which is the happy part: this work is
    overdraw-bound, so a sixteenth of the area is close to a sixteenth
    of the cost. `draw` receives its own painter and the buffer's size.
    """
    bw, bh = max(1, int(w // scale)), max(1, int(h // scale))
    buffer = QImage(bw, bh, QImage.Format_ARGB32_Premultiplied)
    buffer.fill(0)
    q = QPainter(buffer)
    q.setRenderHint(QPainter.Antialiasing)
    try:
        draw(q, bw, bh, scale)
    finally:
        q.end()
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    p.drawImage(QRectF(0, 0, w, h), buffer)
    p.restore()


def _ribbon(p0, p1, p2, p3, half_width, steps=48):
    """
    A closed band around a cubic spine.

    Sampled rather than offset analytically: Qt has no offset-curve
    operation, and for a shape this soft a polygon of fifty points is
    indistinguishable from a true offset.
    """
    left, right = [], []
    for i in range(steps + 1):
        t = i / steps
        point, tangent = _cubic(p0, p1, p2, p3, t)
        length = math.hypot(tangent.x(), tangent.y()) or 1.0
        nx, ny = -tangent.y() / length, tangent.x() / length
        w = half_width(t)
        left.append(QPointF(point.x() + nx * w, point.y() + ny * w))
        right.append(QPointF(point.x() - nx * w, point.y() - ny * w))

    path = QPainterPath(left[0])
    for point in left[1:]:
        path.lineTo(point)
    for point in reversed(right):
        path.lineTo(point)
    path.closeSubpath()
    return path


# Variant B, chosen after comparing three densities side by side. C is
# kept below rather than discarded: it is closer to the period
# wallpapers, but bright enough to compete with generated artwork on the
# Live page, so it waits for a reason to exist.
SWOOSH_PRESETS = {
    "medium": {"layers": 8, "peak": 50, "strength": 1.0, "core": True},
    "pronounced": {"layers": 10, "peak": 72, "strength": 1.5,
                   "core": True},
}


def _swoosh_rich(p, w, h, phase, seed=103, preset="medium"):
    """
    Veils of light: nested bands, faint and wide outside, bright at the
    spine.

    Stacking is what removes the edge. Each band is drawn at a low
    alpha, so where they overlap the light accumulates towards the
    middle and falls to nothing at the rim. A single filled shape cannot
    do that however carefully its gradient is set: a gradient along the
    length still leaves both long sides as hard boundaries.

    Drawn through a scaled buffer, which interpolates away the step at
    each band's own edge and costs a fraction as much - see
    `_through_buffer`.
    """
    settings = SWOOSH_PRESETS.get(preset, SWOOSH_PRESETS["medium"])
    layers = settings["layers"]
    peak = settings["peak"]
    strength = settings["strength"]

    def paint(q, bw, bh, scale):
        rng = random.Random(seed)
        for i in range(4):
            y0 = rng.uniform(0.12, 0.88) * bh
            y1 = rng.uniform(0.12, 0.88) * bh
            lift = rng.uniform(0.14, 0.42) * bh
            widest = (peak / scale) * rng.uniform(0.7, 1.3)
            drift = math.sin(phase * 0.16 + i * 1.7) * (16 / scale)

            p0 = QPointF(-60 / scale, y0 + drift)
            p1 = QPointF(bw * 0.32, y0 - lift + drift)
            p2 = QPointF(bw * 0.68, y1 + lift + drift)
            p3 = QPointF(bw + 60 / scale, y1 + drift)

            q.setPen(Qt.NoPen)
            for layer in range(layers):
                outer = 1.0 - layer / layers
                alpha = int(7 * strength * (1.0 - outer * 0.45))

                def half(t, outer=outer, widest=widest):
                    # Tapered to nothing at both ends, so a veil emerges
                    # from the background rather than entering at the
                    # frame edge.
                    return widest * outer * math.sin(math.pi * t) ** 0.7

                q.setBrush(QColor(214, 244, 255, max(1, alpha)))
                q.drawPath(_ribbon(p0, p1, p2, p3, half, steps=28))

            if settings["core"]:
                def spine(t, widest=widest):
                    return max(0.4, widest * 0.10
                               * math.sin(math.pi * t) ** 0.8)

                q.setBrush(QColor(244, 253, 255, int(16 * strength)))
                q.drawPath(_ribbon(p0, p1, p2, p3, spine, steps=28))

    _through_buffer(p, w, h, paint)


# ---- desert ------------------------------------------------------------

def _dunes(p, w, h, phase, rich=False):
    if rich:
        _dunes_rich(p, w, h)
        return
    """
    Layered dune ridges, palest at the back.

    Depth comes from tone rather than detail: the far ridges are lighter
    and lower-contrast because there is more air between them and the
    viewer, which is what makes a flat silhouette read as distance.
    """
    bands = (
        (0.62, (206, 158, 108), 26, 0.9),
        (0.72, (186, 132, 86), 34, 1.3),
        (0.84, (150, 100, 66), 46, 1.8),
    )
    for depth, tint, alpha, roll in bands:
        base = h * depth
        ridge = QPainterPath(QPointF(-20, h + 10))
        ridge.lineTo(QPointF(-20, base))
        steps = 7
        for i in range(steps + 1):
            t = i / steps
            x = -20 + (w + 40) * t
            # A slow drift, so the horizon breathes rather than sitting
            # perfectly still.
            lift = (math.sin(t * 5.2 + roll + phase * 0.03) * 16 * roll
                    + math.sin(t * 11 + roll * 2) * 5 * roll)
            ridge.lineTo(QPointF(x, base + lift))
        ridge.lineTo(QPointF(w + 20, h + 10))
        ridge.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(tint[0], tint[1], tint[2], alpha))
        p.drawPath(ridge)


def _sun(p, w, h, phase, rich=False):
    if rich:
        pulse = 1.0 + math.sin(phase * 0.25) * 0.03
        _sun_rich(p, w * 0.72, h * 0.30, 34 * pulse)
        return
    """A low sun with a wide dusty bloom around it."""
    cx, cy = w * 0.72, h * 0.30
    pulse = 1.0 + math.sin(phase * 0.25) * 0.03

    bloom = QRadialGradient(QPointF(cx, cy), max(w, h) * 0.42 * pulse)
    bloom.setColorAt(0.0, QColor(255, 218, 150, 58))
    bloom.setColorAt(0.28, QColor(246, 176, 104, 26))
    bloom.setColorAt(1.0, QColor(226, 140, 84, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(bloom)
    p.drawRect(QRectF(0, 0, w, h))

    disc = QRadialGradient(QPointF(cx, cy), 34 * pulse)
    disc.setColorAt(0.0, QColor(255, 244, 214, 150))
    disc.setColorAt(0.7, QColor(255, 214, 150, 92))
    disc.setColorAt(1.0, QColor(255, 196, 130, 0))
    p.setBrush(disc)
    p.drawEllipse(QPointF(cx, cy), 34 * pulse, 34 * pulse)


def _haze(p, w, h, phase):
    """
    Heat shimmer: shallow bands that ripple sideways above the sand.

    Kept low on the screen and very faint. Haze is a distortion of what
    is behind it, and since a decoration layer cannot distort the
    interface, the honest substitute is a suggestion of moving air rather
    than a visible object.
    """
    for i in range(7):
        y = h * (0.52 + i * 0.055)
        amp = 3 + i * 0.7
        alpha = int(20 - i * 1.6)
        if alpha <= 2:
            continue
        band = QPainterPath(QPointF(-20, y))
        steps = 26
        for step in range(steps + 1):
            t = step / steps
            x = -20 + (w + 40) * t
            wobble = math.sin(t * 9 + phase * (1.1 + i * 0.2) + i) * amp
            band.lineTo(QPointF(x, y + wobble))
        for step in range(steps, -1, -1):
            t = step / steps
            x = -20 + (w + 40) * t
            wobble = math.sin(t * 9 + phase * (1.1 + i * 0.2) + i) * amp
            band.lineTo(QPointF(x, y + wobble + 7))
        band.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 236, 206, max(1, alpha - 8)))
        p.drawPath(band)


def _ruins(p, w, h, phase, rich=False):
    """
    Broken columns and an arch on the horizon.

    Silhouettes only, and set back behind the dunes: ruins are scenery
    here, and anything with detail at this distance would read as a
    foreground object sitting oddly in the middle of the interface.
    """
    base = h * 0.63
    ink = QColor(92, 58, 40, 120)
    p.setPen(Qt.NoPen)
    p.setBrush(ink)

    # A row of columns, some snapped part way up.
    for i, (x_rel, height, broken) in enumerate((
            (0.08, 0.16, False), (0.13, 0.10, True), (0.17, 0.14, False),
            (0.22, 0.06, True), (0.90, 0.12, False), (0.95, 0.08, True))):
        x = w * x_rel
        if rich:
            _column_rich(p, x, base, h * height, broken)
            continue
        top = base - h * height
        width = 11
        column = QPainterPath(QPointF(x - width / 2, base))
        column.lineTo(QPointF(x - width * 0.42, top))
        if broken:
            # A snapped shaft has a diagonal break, not a flat top.
            column.lineTo(QPointF(x + width * 0.42, top + h * 0.02))
        else:
            column.lineTo(QPointF(x + width * 0.42, top))
        column.lineTo(QPointF(x + width / 2, base))
        column.closeSubpath()
        p.drawPath(column)
        if not broken:
            p.drawRect(QRectF(x - width * 0.8, top - 5, width * 1.6, 5))

    # A standing arch, a little further along.
    ax, span, rise = w * 0.32, 74, h * 0.15
    arch = QPainterPath(QPointF(ax - span / 2, base))
    arch.lineTo(QPointF(ax - span / 2, base - rise * 0.55))
    arch.quadTo(QPointF(ax, base - rise * 1.25),
                QPointF(ax + span / 2, base - rise * 0.55))
    arch.lineTo(QPointF(ax + span / 2, base))
    arch.lineTo(QPointF(ax + span / 2 - 13, base))
    arch.lineTo(QPointF(ax + span / 2 - 13, base - rise * 0.5))
    arch.quadTo(QPointF(ax, base - rise * 0.95),
                QPointF(ax - span / 2 + 13, base - rise * 0.5))
    arch.lineTo(QPointF(ax - span / 2 + 13, base))
    arch.closeSubpath()
    p.drawPath(arch)


def _sand_drift(p, w, h, phase, seed=131):
    """Grains carried on the wind, streaking as they go."""
    rng = random.Random(seed)
    p.setPen(Qt.NoPen)
    for _ in range(60):
        y = rng.uniform(0.3, 1.0) * h
        speed = rng.uniform(0.05, 0.16)
        offset = rng.uniform(0, 1)
        size = rng.uniform(0.8, 2.2)
        travel = (phase * speed + offset) % 1.0
        x = travel * (w + 120) - 60
        lift = math.sin(phase * 1.4 + offset * 6.28) * 6
        alpha = int(110 * math.sin(math.pi * travel))
        if alpha <= 4:
            continue
        p.setBrush(QColor(250, 226, 190, alpha))
        p.drawEllipse(QPointF(x, y + lift), size, size * 0.8)
        p.setBrush(QColor(250, 226, 190, alpha // 3))
        p.drawRect(QRectF(x - size * 5, y + lift - size * 0.3,
                          size * 5, size * 0.6))


def _sun_disc_pattern(p, rect, size=28, gap=84, rich=False):
    """The tiled motif: a carved sun disc with rays."""
    p.save()
    p.setClipRect(rect, Qt.IntersectClip)
    pen = QPen(QColor(224, 168, 112, 40))
    pen.setWidthF(1.0)
    row = 0
    y = rect.top() + gap * 0.45
    while y < rect.bottom() + gap:
        x = rect.left() + (gap * 0.5 if row % 2 else 0) + gap * 0.35
        while x < rect.right() + gap:
            if rich:
                _sun_disc_rich(p, x, y, size)
                x += gap
                continue
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(x, y), size * 0.3, size * 0.3)
            for i in range(8):
                angle = math.radians(i * 45)
                p.drawLine(
                    QPointF(x + math.cos(angle) * size * 0.42,
                            y + math.sin(angle) * size * 0.42),
                    QPointF(x + math.cos(angle) * size * 0.58,
                            y + math.sin(angle) * size * 0.58))
            x += gap
        y += gap * 0.86
        row += 1
    p.restore()


def desert(p, w, h, win, clip, safe, phase, rich=False):
    """
    Dusty orange sky, sand, heat and old stone.

    Same two-region rule as the rest. The sky, sun, dunes, ruins and haze
    are placed - they are the landscape, and cutting them around a text
    box would break the horizon - while the carved pattern and the
    blowing sand keep clear of text and controls.
    """
    sky = QLinearGradient(0, 0, 0, h)
    sky.setColorAt(0.0, QColor(196, 108, 62, 54))
    sky.setColorAt(0.34, QColor(224, 148, 84, 44))
    sky.setColorAt(0.60, QColor(238, 186, 126, 38))
    sky.setColorAt(1.0, QColor(178, 120, 74, 52))

    p.save()
    p.setClipRegion(safe, Qt.IntersectClip)
    p.fillRect(QRectF(0, 0, w, h), sky)
    _sun(p, w, h, phase, rich)
    _ruins(p, w, h, phase, rich)
    _dunes(p, w, h, phase, rich)
    _haze(p, w, h, phase)
    p.restore()

    sidebar = _sidebar_width(win)
    live = getattr(win, "live", None)
    strip = getattr(live, "strip", None) if live else None
    strip_top = h
    if strip is not None and strip.isVisible():
        strip_top = strip.mapTo(win, QPoint(0, 0)).y()

    p.save()
    p.setClipRegion(clip, Qt.IntersectClip)
    _sun_disc_pattern(p, QRectF(0, 0, sidebar, h), rich=rich)
    _sun_disc_pattern(p, QRectF(sidebar, 0, w - sidebar, 38), size=22,
                      gap=68, rich=rich)
    if strip_top < h:
        _sun_disc_pattern(p, QRectF(sidebar, strip_top, w - sidebar,
                                    h - strip_top), size=24, gap=74,
                          rich=rich)
    _sand_drift(p, w, h, phase)
    p.restore()

    p.save()
    p.setClipRegion(safe, Qt.IntersectClip)
    _cool_splitters(p, win, QColor(206, 132, 70, 185))
    _tally_glow(p, win, live, phase)
    p.restore()


DESERT_QSS = """
/* Sun-baked stone: warm, matte, with a soft top edge as though worn
   smooth rather than polished. */
QPushButton {
    border-radius: 7px;
    border: 1px solid #6E4630;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #3A2A20, stop:1 #2A1E18);
    color: #F0DCC4;
}
QPushButton:hover {
    border: 1px solid #A8683E;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #4A362A, stop:1 #34261E);
}
QPushButton:disabled {
    border: 1px solid #4A3629;
    color: #806550;
}

#primaryButton {
    border: 1px solid #9A5220;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #F2A855, stop:0.5 #DE8434,
                                stop:1 #B2621F);
    color: #2A1206;
    font-weight: 600;
}
#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #FFBC6E, stop:0.5 #EE9444,
                                stop:1 #C4722A);
}

#confirmButton, #denyButton {
    border-radius: 7px;
}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox,
QDoubleSpinBox {
    border-radius: 6px;
    border: 1px solid #5C4030;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #A8683E;
}

#feedList {
    border: 1px solid #5C4030;
    border-radius: 6px;
}
"""


def _dunes_rich(p, w, h):
    """
    Dunes with a lit face and a shaded lee, plus wind ripples.

    A flat silhouette says "there is a shape here"; a dune is really two
    surfaces meeting at a crest - one facing the sun, one turned away -
    and a hard line between them is what makes the ridge read as an edge
    rather than an outline.
    """
    for depth, lit, shade, roll in (
            (0.42, (226, 186, 138), (176, 130, 92), 0.9),
            (0.58, (208, 160, 112), (150, 104, 72), 1.3),
            (0.76, (178, 128, 86), (112, 74, 50), 1.8)):
        base = h * depth
        steps = 40
        crest = []
        for i in range(steps + 1):
            t = i / steps
            x = -20 + (w + 40) * t
            lift = (math.sin(t * 5.2 + roll) * 16 * roll
                    + math.sin(t * 11 + roll * 2) * 5 * roll)
            crest.append(QPointF(x, base + lift))

        body = QPainterPath(QPointF(-20, h + 10))
        body.lineTo(crest[0])
        for point in crest[1:]:
            body.lineTo(point)
        body.lineTo(QPointF(w + 20, h + 10))
        body.closeSubpath()

        fill = QLinearGradient(0, base - 40, 0, h)
        fill.setColorAt(0.0, QColor(*lit, 54))
        fill.setColorAt(0.35, QColor(*lit, 42))
        fill.setColorAt(1.0, QColor(*shade, 58))
        p.setPen(Qt.NoPen)
        p.setBrush(fill)
        p.drawPath(body)

        # The crest itself, caught by the light.
        pen = QPen(QColor(250, 224, 184, 54))
        pen.setWidthF(1.3)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        line = QPainterPath(crest[0])
        for point in crest[1:]:
            line.lineTo(point)
        p.drawPath(line)

        # Wind ripples on the sunward face: shallow arcs following the
        # slope, finer as they recede.
        rng = random.Random(int(depth * 1000))
        p.setPen(QPen(QColor(*shade, 30), 0.8))
        for _ in range(14):
            t = rng.uniform(0.04, 0.96)
            index = int(t * steps)
            anchor = crest[index]
            drop = rng.uniform(10, 44)
            span = rng.uniform(26, 70)
            ripple = QPainterPath(
                QPointF(anchor.x() - span / 2, anchor.y() + drop))
            ripple.quadTo(QPointF(anchor.x(), anchor.y() + drop - 5),
                          QPointF(anchor.x() + span / 2,
                                  anchor.y() + drop))
            p.drawPath(ripple)


def _column_rich(p, x, base, height, broken=False):
    """
    A column with flutes, a capital and a cast shadow.

    Depth comes from three vertical bands rather than one flat fill: a
    round shaft is lit down one side and shaded on the other, and the
    flutes are what make it stone rather than a post.
    """
    width = 22
    top = base - height
    stone = QColor(126, 92, 66)

    # Cast shadow on the sand, thrown away from the sun.
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(96, 62, 44, 42))
    shadow = QPainterPath(QPointF(x - width * 0.5, base))
    shadow.lineTo(QPointF(x - width * 1.9, base + 6))
    shadow.lineTo(QPointF(x - width * 1.6, base + 10))
    shadow.lineTo(QPointF(x + width * 0.5, base + 3))
    shadow.closeSubpath()
    p.drawPath(shadow)

    shaft = QPainterPath(QPointF(x - width / 2, base))
    shaft.lineTo(QPointF(x - width * 0.42, top))
    if broken:
        # A snapped shaft breaks unevenly, with a lip on one side.
        shaft.lineTo(QPointF(x - width * 0.18, top + height * 0.03))
        shaft.lineTo(QPointF(x + width * 0.12, top + height * 0.10))
        shaft.lineTo(QPointF(x + width * 0.42, top + height * 0.06))
    else:
        shaft.lineTo(QPointF(x + width * 0.42, top))
    shaft.lineTo(QPointF(x + width / 2, base))
    shaft.closeSubpath()

    body = QLinearGradient(x - width / 2, 0, x + width / 2, 0)
    body.setColorAt(0.0, QColor(stone.darker(140).red(),
                                stone.darker(140).green(),
                                stone.darker(140).blue(), 132))
    body.setColorAt(0.32, QColor(stone.lighter(122).red(),
                                 stone.lighter(122).green(),
                                 stone.lighter(122).blue(), 132))
    body.setColorAt(1.0, QColor(stone.darker(160).red(),
                                stone.darker(160).green(),
                                stone.darker(160).blue(), 138))
    p.setBrush(body)
    p.drawPath(shaft)

    # Flutes: fine grooves down the shaft, densest where it curves away.
    p.setPen(QPen(QColor(86, 56, 40, 70), 0.9))
    p.setBrush(Qt.NoBrush)
    for offset in (-0.28, -0.08, 0.12, 0.30):
        gx = x + width * offset
        flute_top = top + (height * 0.08 if broken else 2)
        p.drawLine(QPointF(gx, flute_top), QPointF(gx, base - 2))

    if not broken:
        # Capital: a slab with a lit top edge.
        cap = QRectF(x - width * 0.82, top - 10, width * 1.64, 10)
        slab = QLinearGradient(0, cap.top(), 0, cap.bottom())
        slab.setColorAt(0.0, QColor(196, 154, 114, 140))
        slab.setColorAt(1.0, QColor(120, 82, 58, 140))
        p.setPen(Qt.NoPen)
        p.setBrush(slab)
        p.drawRect(cap)
        p.setPen(QPen(QColor(236, 204, 166, 110), 1.0))
        p.drawLine(QPointF(cap.left(), cap.top()),
                   QPointF(cap.right(), cap.top()))

    # A base block, wider than the shaft.
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(118, 80, 56, 134))
    p.drawRect(QRectF(x - width * 0.7, base - 5, width * 1.4, 5))


def _sun_rich(p, cx, cy, r):
    """
    A sun seen through dust: layered corona, flattened disc, limb glow.

    Low sun is squashed by refraction and dimmed at its edge, and the
    air around it scatters in bands rather than one smooth falloff.
    Three nested gradients at different widths do more for it than any
    amount of brightness.
    """
    # Outer scatter, wide and cool at its rim.
    for reach, alpha, tint in ((5.2, 26, (238, 158, 96)),
                               (3.4, 34, (248, 186, 122)),
                               (2.1, 48, (255, 214, 156))):
        halo = QRadialGradient(QPointF(cx, cy), r * reach)
        halo.setColorAt(0.0, QColor(*tint, alpha))
        halo.setColorAt(0.45, QColor(*tint, int(alpha * 0.45)))
        halo.setColorAt(1.0, QColor(*tint, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(halo)
        p.drawEllipse(QPointF(cx, cy), r * reach, r * reach * 0.86)

    # The disc, slightly flattened as a low sun is.
    disc = QRadialGradient(QPointF(cx, cy - r * 0.1), r * 1.1)
    disc.setColorAt(0.0, QColor(255, 250, 230, 220))
    disc.setColorAt(0.55, QColor(255, 232, 182, 190))
    # Limb darkening: the edge of the disc is dimmer than its middle.
    disc.setColorAt(0.92, QColor(250, 198, 134, 150))
    disc.setColorAt(1.0, QColor(246, 180, 118, 40))
    p.setBrush(disc)
    p.drawEllipse(QPointF(cx, cy), r, r * 0.94)

    # Two dust bands crossing the disc, which is what sells "through
    # atmosphere" rather than "in space".
    p.setPen(Qt.NoPen)
    # One band, and faint: at the size this is drawn on screen two
    # solid bars read as stripes painted on the sun rather than dust
    # drifting in front of it.
    band = QLinearGradient(cx - r, cy, cx + r, cy)
    band.setColorAt(0.0, QColor(214, 150, 104, 0))
    band.setColorAt(0.5, QColor(214, 150, 104, 26))
    band.setColorAt(1.0, QColor(214, 150, 104, 0))
    p.setBrush(band)
    p.drawRect(QRectF(cx - r * 1.02, cy - r * 0.06, r * 2.04, r * 0.12))


def _sun_disc_rich(p, x, y, size):
    """
    A carved sun disc: cut into the surface rather than drawn on it.

    The same trick as the cryptic cartouche - a light stroke offset one
    way, a dark one the other - which turns a flat outline into
    something with a chiselled edge.
    """
    def rings(pen):
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), size * 0.30, size * 0.30)
        for i in range(12):
            angle = math.radians(i * 30)
            inner = size * (0.42 if i % 2 == 0 else 0.38)
            outer = size * (0.60 if i % 2 == 0 else 0.50)
            p.drawLine(QPointF(math.cos(angle) * inner,
                               math.sin(angle) * inner),
                       QPointF(math.cos(angle) * outer,
                               math.sin(angle) * outer))

    p.save()
    p.translate(x, y)

    # Recessed centre, so the disc looks sunk into the stone.
    dish = QRadialGradient(QPointF(-size * 0.08, -size * 0.08), size * 0.34)
    dish.setColorAt(0.0, QColor(196, 142, 92, 26))
    dish.setColorAt(1.0, QColor(110, 70, 44, 14))
    p.setPen(Qt.NoPen)
    p.setBrush(dish)
    p.drawEllipse(QPointF(0, 0), size * 0.30, size * 0.30)

    p.save()
    p.translate(-0.7, -0.7)
    rings(QPen(QColor(248, 206, 158, 46), 1.0))
    p.restore()
    p.save()
    p.translate(0.7, 0.7)
    rings(QPen(QColor(74, 44, 28, 54), 1.0))
    p.restore()
    rings(QPen(QColor(224, 168, 112, 40), 1.0))
    p.restore()




# ---- arctic ------------------------------------------------------------
#
# A pale theme, so every alpha here is roughly half what a dark theme
# would use. Desert taught that twice: values judged on their own look
# right and then bury the interface text once they are over it.

def _snow_drifts(p, w, h, phase, rich=False):
    if rich:
        _drifts_rich(p, w, h)
        return
    """Banked snow, palest at the back."""
    bands = (
        (0.60, (232, 242, 252), 22, 0.8),
        (0.71, (214, 230, 246), 27, 1.2),
        (0.83, (190, 212, 234), 34, 1.7),
    )
    for depth, tint, alpha, roll in bands:
        base = h * depth
        drift = QPainterPath(QPointF(-20, h + 10))
        drift.lineTo(QPointF(-20, base))
        steps = 9
        for i in range(steps + 1):
            t = i / steps
            x = -20 + (w + 40) * t
            lift = (math.sin(t * 4.4 + roll + phase * 0.02) * 14 * roll
                    + math.sin(t * 9 + roll * 3) * 4 * roll)
            drift.lineTo(QPointF(x, base + lift))
        drift.lineTo(QPointF(w + 20, h + 10))
        drift.closeSubpath()
        p.setPen(Qt.NoPen)
        soften = QLinearGradient(0, base - 14, 0, h)
        soften.setColorAt(0.0, QColor(tint[0], tint[1], tint[2], 0))
        soften.setColorAt(0.22, QColor(tint[0], tint[1], tint[2],
                                       int(alpha * 0.55)))
        soften.setColorAt(1.0, QColor(tint[0], tint[1], tint[2], alpha))
        p.setBrush(soften)
        p.drawPath(drift)


def _icicles(p, w, y, phase, seed=181, rich=False):
    if rich:
        _icicles_rich(p, w, y, seed)
        return
    """
    Ice hanging from a bar's lower edge: the frozen interface.

    Widths and lengths vary and the tips are drawn as curves rather than
    points, because real icicles taper unevenly and a row of identical
    triangles reads as bunting.
    """
    rng = random.Random(seed)
    x = 6
    while x < w:
        width = rng.uniform(5, 13)
        length = rng.uniform(8, 34)
        lean = rng.uniform(-1.6, 1.6)
        spike = QPainterPath(QPointF(x, y))
        spike.quadTo(QPointF(x + width * 0.12, y + length * 0.7),
                     QPointF(x + width * 0.5 + lean, y + length))
        spike.quadTo(QPointF(x + width * 0.88, y + length * 0.7),
                     QPointF(x + width, y))
        spike.closeSubpath()
        ice = QLinearGradient(x, y, x, y + length)
        ice.setColorAt(0.0, QColor(212, 234, 250, 64))
        ice.setColorAt(0.6, QColor(186, 218, 242, 44))
        ice.setColorAt(1.0, QColor(236, 248, 255, 70))
        p.setPen(Qt.NoPen)
        p.setBrush(ice)
        p.drawPath(spike)
        x += width + rng.uniform(12, 46)


def _snowfall(p, w, h, phase, count=90, seed=191, rich=False):
    """
    Flakes drifting down, each on its own sideways sway.

    Nearer flakes fall faster and larger. That difference is all the
    depth a field of dots can have, and without it snow reads as static.
    """
    rng = random.Random(seed)
    p.setPen(Qt.NoPen)
    for _ in range(count):
        near = rng.uniform(0.3, 1.0)
        x0 = rng.uniform(0, w)
        speed = 0.02 + near * 0.06
        offset = rng.uniform(0, 1)
        sway = rng.uniform(8, 26) * near
        rate = rng.uniform(0.5, 1.3)

        progress = (phase * speed + offset) % 1.0
        y = progress * (h + 40) - 20
        x = x0 + math.sin(phase * rate + offset * 6.28) * sway
        size = 0.9 + near * 2.0
        alpha = int(60 + 120 * near)
        if rich and near > 0.72:
            _flake_rich(p, x, y, size * 1.5, alpha)
            continue
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(246, 252, 255, alpha))
        p.drawEllipse(QPointF(x, y), size, size)


def _penguin(p, x, base, size, lean, step, rich=False):
    if rich:
        _penguin_rich(p, x, base, size, lean, step)
        return
    """
    One penguin, mid-waddle.

    A waddle is a rock from foot to foot, not a wobble in place: the body
    tips about the planted foot, and the lift on the other side follows
    the same beat. Tying the two together is what makes it read as
    walking rather than as a shape being shaken.
    """
    p.save()
    # Rock about the feet rather than the middle, so the bird pivots on
    # the ground the way a real one does.
    p.translate(x, base)
    p.rotate(lean)
    p.translate(-x, -base)

    body_h = size * 2.0
    body_w = size * 1.25
    top = base - body_h

    # Feet: the trailing one lifts as the body tips towards it.
    p.setPen(Qt.NoPen)
    lift = max(0.0, math.sin(step)) * size * 0.18
    p.setBrush(QColor(226, 158, 72, 150))
    p.drawEllipse(QRectF(x - body_w * 0.46, base - size * 0.10,
                         body_w * 0.42, size * 0.20))
    p.drawEllipse(QRectF(x + body_w * 0.06, base - size * 0.10 - lift,
                         body_w * 0.42, size * 0.20))

    # Back and head, one silhouette.
    back = QPainterPath(QPointF(x - body_w * 0.5, base))
    back.cubicTo(QPointF(x - body_w * 0.62, top + body_h * 0.28),
                 QPointF(x - body_w * 0.44, top),
                 QPointF(x, top))
    back.cubicTo(QPointF(x + body_w * 0.44, top),
                 QPointF(x + body_w * 0.62, top + body_h * 0.28),
                 QPointF(x + body_w * 0.5, base))
    back.closeSubpath()
    p.setBrush(QColor(34, 44, 60, 172))
    p.drawPath(back)

    # Belly, inset and pale.
    belly = QPainterPath(QPointF(x - body_w * 0.30, base))
    belly.cubicTo(QPointF(x - body_w * 0.40, top + body_h * 0.40),
                  QPointF(x - body_w * 0.22, top + body_h * 0.16),
                  QPointF(x, top + body_h * 0.14))
    belly.cubicTo(QPointF(x + body_w * 0.22, top + body_h * 0.16),
                  QPointF(x + body_w * 0.40, top + body_h * 0.40),
                  QPointF(x + body_w * 0.30, base))
    belly.closeSubpath()
    p.setBrush(QColor(246, 251, 255, 168))
    p.drawPath(belly)

    # A flipper on the near side, swinging opposite to the lean.
    swing = -lean * 0.5
    flipper = QPainterPath(QPointF(x - body_w * 0.46, top + body_h * 0.34))
    flipper.quadTo(QPointF(x - body_w * 0.78 - swing,
                           top + body_h * 0.62),
                   QPointF(x - body_w * 0.52, top + body_h * 0.80))
    flipper.quadTo(QPointF(x - body_w * 0.50, top + body_h * 0.55),
                   QPointF(x - body_w * 0.46, top + body_h * 0.34))
    p.setBrush(QColor(28, 38, 54, 172))
    p.drawPath(flipper)

    # Beak and eye.
    p.setBrush(QColor(232, 166, 78, 160))
    beak = QPainterPath(QPointF(x + body_w * 0.26, top + body_h * 0.13))
    beak.lineTo(QPointF(x + body_w * 0.54, top + body_h * 0.17))
    beak.lineTo(QPointF(x + body_w * 0.26, top + body_h * 0.21))
    beak.closeSubpath()
    p.drawPath(beak)
    p.setBrush(QColor(246, 250, 255, 150))
    p.drawEllipse(QPointF(x + body_w * 0.16, top + body_h * 0.10),
                  size * 0.10, size * 0.10)
    p.setBrush(QColor(20, 26, 38, 180))
    p.drawEllipse(QPointF(x + body_w * 0.18, top + body_h * 0.10),
                  size * 0.05, size * 0.05)
    p.restore()


def _penguins(p, w, floor, phase, seed=197, rich=False):
    """
    A few birds crossing the snow, each at its own pace.

    They turn round at the edges rather than wrapping, because something
    that vanishes off one side and reappears on the other reads as two
    penguins rather than one walking.
    """
    rng = random.Random(seed)
    for i in range(3):
        size = rng.uniform(15, 21)
        speed = rng.uniform(0.014, 0.026)
        offset = rng.uniform(0, 1)
        beat = rng.uniform(2.6, 3.6)

        # A triangle wave: out across the screen and back again.
        travel = (phase * speed + offset) % 2.0
        facing = 1 if travel < 1.0 else -1
        across = travel if travel < 1.0 else 2.0 - travel
        x = 40 + across * (w - 80)

        step = phase * beat + offset * 6.28
        lean = math.sin(step) * 7.0
        bob = abs(math.cos(step)) * size * 0.08

        p.save()
        if facing < 0:
            p.translate(x, 0)
            p.scale(-1, 1)
            p.translate(-x, 0)
        _penguin(p, x, floor - bob, size, lean, step, rich)
        p.restore()


def _frost_pattern(p, rect, size=26, gap=78, rich=False):
    """The tiled motif: a six-armed frost crystal."""
    p.save()
    p.setClipRect(rect, Qt.IntersectClip)
    pen = QPen(QColor(206, 230, 248, 40))
    pen.setWidthF(1.0)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    row = 0
    y = rect.top() + gap * 0.45
    while y < rect.bottom() + gap:
        x = rect.left() + (gap * 0.5 if row % 2 else 0) + gap * 0.35
        while x < rect.right() + gap:
            for i in range(6):
                angle = math.radians(i * 60)
                tip = QPointF(x + math.cos(angle) * size * 0.5,
                              y + math.sin(angle) * size * 0.5)
                p.drawLine(QPointF(x, y), tip)
                # Barbs, which is what makes it a snowflake and not a
                # wheel spoke.
                for along in (0.45, 0.72):
                    mid = QPointF(x + math.cos(angle) * size * 0.5 * along,
                                  y + math.sin(angle) * size * 0.5 * along)
                    for side in (-1, 1):
                        barb = angle + side * math.radians(52)
                        p.drawLine(mid, QPointF(
                            mid.x() + math.cos(barb) * size * 0.14,
                            mid.y() + math.sin(barb) * size * 0.14))
            x += gap
        y += gap * 0.86
        row += 1
    p.restore()


def arctic(p, w, h, win, clip, safe, phase, rich=False):
    """
    Cold light, snow, ice on the interface, and somebody waddling.

    Same two-region rule as the rest. The sky, drifts, igloo, icicles and
    penguins are placed - they are the scene, and a penguin chopped in
    half around a text box would be worse than no penguin - while the
    frost pattern and the falling snow keep clear of text and controls.
    """
    sidebar = _sidebar_width(win)
    live = getattr(win, "live", None)
    strip = getattr(live, "strip", None) if live else None
    strip_top = h
    if strip is not None and strip.isVisible():
        strip_top = strip.mapTo(win, QPoint(0, 0)).y()

    sky = QLinearGradient(0, 0, 0, h)
    sky.setColorAt(0.0, QColor(148, 190, 226, 44))
    sky.setColorAt(0.38, QColor(186, 214, 238, 30))
    sky.setColorAt(0.68, QColor(214, 232, 246, 22))
    sky.setColorAt(1.0, QColor(168, 196, 222, 34))

    p.save()
    p.setClipRegion(safe, Qt.IntersectClip)
    p.fillRect(QRectF(0, 0, w, h), sky)

    # A cold sun, low and weak - it gives the scene a direction without
    # warming it.
    glow = QRadialGradient(QPointF(w * 0.24, h * 0.22), max(w, h) * 0.34)
    glow.setColorAt(0.0, QColor(252, 253, 255, 54))
    glow.setColorAt(0.4, QColor(226, 240, 252, 22))
    glow.setColorAt(1.0, QColor(210, 230, 248, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(glow)
    p.drawRect(QRectF(0, 0, w, h))

    if rich:
        _aurora(p, w, h, phase)
    _snow_drifts(p, w, h, phase, rich)
    _icicles(p, w, 38, phase, rich=rich)
    # Low, just above whatever bar sits at the foot of the window. A
    # fixed offset rather than a fraction of the height: the gap that
    # keeps them clear of the bottom bar is the same however tall the
    # window is, where a percentage drifts with it.
    # Above the bottom bar when a panel has one, near the floor when it
    # does not. Landing them inside the prompt box looked like they were
    # standing on the text field.
    floor = (strip_top - 6) if strip_top < h else (h - 58)
    _penguins(p, w, floor, phase, rich=rich)
    p.restore()

    p.save()
    p.setClipRegion(clip, Qt.IntersectClip)
    _frost_pattern(p, QRectF(0, 0, sidebar, h), rich=rich)
    _frost_pattern(p, QRectF(sidebar, 0, w - sidebar, 38), size=20,
                   gap=64, rich=rich)
    if strip_top < h:
        _frost_pattern(p, QRectF(sidebar, strip_top, w - sidebar,
                                 h - strip_top), size=22, gap=70,
                       rich=rich)
    _snowfall(p, w, h, phase, rich=rich)
    p.restore()

    p.save()
    p.setClipRegion(safe, Qt.IntersectClip)
    _cool_splitters(p, win, QColor(150, 200, 232, 180))
    _tally_glow(p, win, live, phase)
    p.restore()


ARCTIC_QSS = """
/* Frozen glass: cold, pale-rimmed, with a bright top edge like light
   catching an ice surface. */
QPushButton {
    border-radius: 8px;
    border: 1px solid #3C6484;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #223A4E, stop:1 #16283A);
    color: #DCEDF8;
}
QPushButton:hover {
    border: 1px solid #74AACF;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #2C4C64, stop:1 #1C3246);
}
QPushButton:disabled {
    border: 1px solid #2A4256;
    color: #5E7E94;
}

#primaryButton {
    border: 1px solid #4A90BE;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #BEE4F8, stop:0.5 #82C0E4,
                                stop:1 #4E92BC);
    color: #07202E;
    font-weight: 600;
}
#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #D4EEFF, stop:0.5 #96D0F0,
                                stop:1 #5EA2CC);
}

#confirmButton, #denyButton {
    border-radius: 8px;
}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox,
QDoubleSpinBox {
    border-radius: 7px;
    border: 1px solid #345A76;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #74AACF;
}

#feedList {
    border: 1px solid #345A76;
    border-radius: 7px;
}
"""


def _drifts_rich(p, w, h):
    """
    Snow with a lit crest, a blue-shadowed lee, and sparkle on top.

    Snow shadows are blue, not grey - the sky is what lights them - and
    that colour shift does more to say "snow" than any amount of white.
    The sparkle is sparse and only on the sunward faces.
    """
    for depth, lit, shade, roll in (
            (0.42, (250, 253, 255), (176, 198, 226), 0.8),
            (0.58, (240, 248, 255), (156, 182, 214), 1.2),
            (0.76, (230, 242, 254), (134, 162, 198), 1.7)):
        base = h * depth
        steps = 40
        crest = []
        for i in range(steps + 1):
            t = i / steps
            x = -20 + (w + 40) * t
            lift = (math.sin(t * 4.4 + roll) * 14 * roll
                    + math.sin(t * 9 + roll * 3) * 4 * roll)
            crest.append(QPointF(x, base + lift))

        body = QPainterPath(QPointF(-20, h + 10))
        body.lineTo(crest[0])
        for point in crest[1:]:
            body.lineTo(point)
        body.lineTo(QPointF(w + 20, h + 10))
        body.closeSubpath()

        fill = QLinearGradient(0, base - 24, 0, h)
        fill.setColorAt(0.0, QColor(*lit, 0))
        fill.setColorAt(0.18, QColor(*lit, 34))
        fill.setColorAt(0.45, QColor(*lit, 28))
        fill.setColorAt(1.0, QColor(*shade, 40))
        p.setPen(Qt.NoPen)
        p.setBrush(fill)
        p.drawPath(body)

        pen = QPen(QColor(255, 255, 255, 34))
        pen.setWidthF(1.1)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        line = QPainterPath(crest[0])
        for point in crest[1:]:
            line.lineTo(point)
        p.drawPath(line)

        # Wind-carved scallops, shallower than the desert's ripples.
        rng = random.Random(int(depth * 977))
        p.setPen(QPen(QColor(*shade, 22), 0.8))
        for _ in range(10):
            index = int(rng.uniform(0.05, 0.95) * steps)
            anchor = crest[index]
            drop = rng.uniform(8, 34)
            span = rng.uniform(30, 76)
            sweep = QPainterPath(
                QPointF(anchor.x() - span / 2, anchor.y() + drop))
            sweep.quadTo(QPointF(anchor.x(), anchor.y() + drop - 4),
                         QPointF(anchor.x() + span / 2, anchor.y() + drop))
            p.drawPath(sweep)

        # Sparkle: a few points catching the light along the crest.
        p.setPen(Qt.NoPen)
        for _ in range(7):
            index = int(rng.uniform(0.03, 0.97) * steps)
            point = crest[index]
            gy = point.y() + rng.uniform(2, 16)
            size = rng.uniform(0.8, 1.7)
            p.setBrush(QColor(255, 255, 255, 150))
            p.drawEllipse(QPointF(point.x() + rng.uniform(-14, 14), gy),
                          size, size)


def _penguin_rich(p, x, base, size, lean, step):
    """
    A penguin with a rounded back, a shadow, and a bit of gloss.

    The flat black silhouette is the weak part: a real bird is lit along
    its back and darker underneath, and a soft shadow under the feet is
    what stops it looking pasted onto the snow.
    """
    p.save()
    p.translate(x, base)
    p.rotate(lean)
    p.translate(-x, -base)
    body_h, body_w = size * 2.0, size * 1.25
    top = base - body_h

    # Shadow first, so everything else sits on it.
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(126, 152, 186, 60))
    p.drawEllipse(QRectF(x - body_w * 0.52, base - size * 0.07,
                         body_w * 1.04, size * 0.18))

    lift = max(0.0, math.sin(step)) * size * 0.18
    for fx, fy in ((-0.46, 0.0), (0.06, -lift)):
        foot = QPainterPath(QPointF(x + body_w * fx, base + fy))
        foot.quadTo(QPointF(x + body_w * (fx + 0.30), base + fy - size * 0.16),
                    QPointF(x + body_w * (fx + 0.44), base + fy))
        foot.quadTo(QPointF(x + body_w * (fx + 0.22), base + fy + size * 0.06),
                    QPointF(x + body_w * fx, base + fy))
        p.setBrush(QColor(226, 152, 64, 215))
        p.drawPath(foot)

    back = QPainterPath(QPointF(x - body_w * 0.5, base))
    back.cubicTo(QPointF(x - body_w * 0.62, top + body_h * 0.28),
                 QPointF(x - body_w * 0.44, top), QPointF(x, top))
    back.cubicTo(QPointF(x + body_w * 0.44, top),
                 QPointF(x + body_w * 0.62, top + body_h * 0.28),
                 QPointF(x + body_w * 0.5, base))
    back.closeSubpath()
    coat = QLinearGradient(x - body_w * 0.5, top, x + body_w * 0.5, base)
    coat.setColorAt(0.0, QColor(64, 78, 100, 235))
    coat.setColorAt(0.45, QColor(34, 44, 62, 238))
    coat.setColorAt(1.0, QColor(18, 24, 36, 240))
    p.setBrush(coat)
    p.drawPath(back)

    # Gloss down the back, where the sky catches it.
    gloss = QPainterPath(QPointF(x - body_w * 0.34, top + body_h * 0.20))
    gloss.quadTo(QPointF(x - body_w * 0.50, top + body_h * 0.62),
                 QPointF(x - body_w * 0.34, top + body_h * 0.92))
    gloss.quadTo(QPointF(x - body_w * 0.26, top + body_h * 0.56),
                 QPointF(x - body_w * 0.34, top + body_h * 0.20))
    p.setBrush(QColor(150, 178, 212, 60))
    p.drawPath(gloss)

    belly = QPainterPath(QPointF(x - body_w * 0.30, base))
    belly.cubicTo(QPointF(x - body_w * 0.40, top + body_h * 0.40),
                  QPointF(x - body_w * 0.22, top + body_h * 0.16),
                  QPointF(x, top + body_h * 0.14))
    belly.cubicTo(QPointF(x + body_w * 0.22, top + body_h * 0.16),
                  QPointF(x + body_w * 0.40, top + body_h * 0.40),
                  QPointF(x + body_w * 0.30, base))
    belly.closeSubpath()
    front = QLinearGradient(x, top + body_h * 0.14, x, base)
    front.setColorAt(0.0, QColor(255, 255, 255, 240))
    front.setColorAt(0.7, QColor(236, 244, 252, 235))
    front.setColorAt(1.0, QColor(198, 214, 232, 230))
    p.setBrush(front)
    p.drawPath(belly)

    swing = -lean * 0.5
    flipper = QPainterPath(QPointF(x - body_w * 0.46, top + body_h * 0.34))
    flipper.quadTo(QPointF(x - body_w * 0.80 - swing, top + body_h * 0.62),
                   QPointF(x - body_w * 0.52, top + body_h * 0.82))
    flipper.quadTo(QPointF(x - body_w * 0.50, top + body_h * 0.56),
                   QPointF(x - body_w * 0.46, top + body_h * 0.34))
    p.setBrush(QColor(26, 34, 50, 238))
    p.drawPath(flipper)

    # Beak with a darker tip, and an eye with a catchlight.
    beak = QPainterPath(QPointF(x + body_w * 0.26, top + body_h * 0.12))
    beak.lineTo(QPointF(x + body_w * 0.58, top + body_h * 0.17))
    beak.lineTo(QPointF(x + body_w * 0.26, top + body_h * 0.22))
    beak.closeSubpath()
    p.setBrush(QColor(238, 172, 76, 235))
    p.drawPath(beak)
    tip = QPainterPath(QPointF(x + body_w * 0.44, top + body_h * 0.145))
    tip.lineTo(QPointF(x + body_w * 0.58, top + body_h * 0.17))
    tip.lineTo(QPointF(x + body_w * 0.44, top + body_h * 0.195))
    tip.closeSubpath()
    p.setBrush(QColor(186, 118, 44, 225))
    p.drawPath(tip)

    p.setBrush(QColor(250, 252, 255, 235))
    p.drawEllipse(QPointF(x + body_w * 0.16, top + body_h * 0.10),
                  size * 0.11, size * 0.11)
    p.setBrush(QColor(16, 22, 34, 240))
    p.drawEllipse(QPointF(x + body_w * 0.175, top + body_h * 0.10),
                  size * 0.055, size * 0.055)
    p.setBrush(QColor(255, 255, 255, 220))
    p.drawEllipse(QPointF(x + body_w * 0.155, top + body_h * 0.085),
                  size * 0.022, size * 0.022)
    p.restore()


def _icicles_rich(p, w, y, seed=181):
    """
    Ice that refracts: a bright core, a cool rim, and a drip forming.

    Clear ice is brightest along its middle where light travels the
    length of it, not at its edges. Lighting it that way is the whole
    difference between an icicle and a grey triangle.
    """
    rng = random.Random(seed)
    x = 6
    while x < w:
        width = rng.uniform(5, 13)
        length = rng.uniform(10, 38)
        lean = rng.uniform(-1.6, 1.6)
        tip = QPointF(x + width * 0.5 + lean, y + length)

        spike = QPainterPath(QPointF(x, y))
        spike.quadTo(QPointF(x + width * 0.10, y + length * 0.72), tip)
        spike.quadTo(QPointF(x + width * 0.90, y + length * 0.72),
                     QPointF(x + width, y))
        spike.closeSubpath()

        # Body: cool at the edges, pale down the middle.
        across = QLinearGradient(x, 0, x + width, 0)
        across.setColorAt(0.0, QColor(150, 186, 220, 70))
        across.setColorAt(0.38, QColor(238, 250, 255, 110))
        across.setColorAt(0.62, QColor(214, 238, 252, 96))
        across.setColorAt(1.0, QColor(142, 178, 214, 72))
        p.setPen(Qt.NoPen)
        p.setBrush(across)
        p.drawPath(spike)

        # The lit core, a sliver down the length.
        core = QPainterPath(QPointF(x + width * 0.38, y))
        core.quadTo(QPointF(x + width * 0.40, y + length * 0.7), tip)
        core.quadTo(QPointF(x + width * 0.58, y + length * 0.7),
                    QPointF(x + width * 0.60, y))
        core.closeSubpath()
        p.setBrush(QColor(255, 255, 255, 72))
        p.drawPath(core)

        # A drip gathering at the point, which is what makes ice read as
        # cold rather than as glass.
        if rng.random() < 0.45:
            p.setBrush(QColor(226, 244, 255, 130))
            p.drawEllipse(QPointF(tip.x(), tip.y() + width * 0.18),
                          width * 0.15, width * 0.21)
            p.setBrush(QColor(255, 255, 255, 170))
            p.drawEllipse(QPointF(tip.x() - width * 0.05,
                                  tip.y() + width * 0.12),
                          width * 0.05, width * 0.06)

        x += width + rng.uniform(12, 46)


def _flake_rich(p, x, y, size, alpha):
    """
    A six-armed flake for the nearest snow, instead of a dot.

    Only worth drawing on the closest few: at two pixels the arms are
    invisible and it is just a more expensive dot.
    """
    pen = QPen(QColor(255, 255, 255, alpha))
    pen.setWidthF(max(0.6, size * 0.22))
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    for i in range(3):
        angle = math.radians(i * 60)
        p.drawLine(QPointF(x - math.cos(angle) * size,
                           y - math.sin(angle) * size),
                   QPointF(x + math.cos(angle) * size,
                           y + math.sin(angle) * size))
    for i in range(6):
        angle = math.radians(i * 60)
        mid = QPointF(x + math.cos(angle) * size * 0.6,
                      y + math.sin(angle) * size * 0.6)
        for side in (-1, 1):
            barb = angle + side * math.radians(55)
            p.drawLine(mid, QPointF(mid.x() + math.cos(barb) * size * 0.3,
                                    mid.y() + math.sin(barb) * size * 0.3))


def _aurora(p, w, h, phase):
    """
    Curtains of light across the upper sky.

    Built from the same nested ribbons as the aero swooshes: an aurora
    has no edge anywhere, so a filled shape with a gradient along it
    would betray itself at the sides. Colour shifts along each curtain
    rather than across it - green low, violet at the fringes - which is
    how the real thing separates.

    Drawn through a scaled buffer, so the step at each band's own edge
    is interpolated away rather than paid for with more bands.

    Enhanced only. It is an addition rather than a better version of
    something, so the plain theme stays as it was.
    """
    def paint(q, bw, bh, scale):
        for band in range(3):
            drift = math.sin(phase * 0.12 + band * 2.1) * (26 / scale)
            top = bh * (0.06 + band * 0.05)
            sag = bh * (0.16 + band * 0.05)

            p0 = QPointF(-80 / scale, top + sag * 0.5 + drift)
            p1 = QPointF(bw * 0.30, top - sag * 0.35 + drift)
            p2 = QPointF(bw * 0.70, top + sag * 0.9 + drift)
            p3 = QPointF(bw + 80 / scale, top + drift)

            widest = bh * (0.16 + band * 0.03)
            layers = 7
            for layer in range(layers):
                outer = 1.0 - layer / layers
                alpha = int(6 * (1.0 - outer * 0.4))

                def half(t, outer=outer, widest=widest):
                    # Ragged along its length, the way a curtain hangs,
                    # and tapered to nothing at both ends.
                    ripple = 0.72 + 0.28 * math.sin(
                        t * 9 + phase * 0.4 + band)
                    return (widest * outer * ripple
                            * math.sin(math.pi * t) ** 0.6)

                tint = ((126, 226, 168), (108, 210, 190),
                        (150, 176, 236))[band]
                q.setPen(Qt.NoPen)
                q.setBrush(QColor(*tint, max(1, alpha)))
                q.drawPath(_ribbon(p0, p1, p2, p3, half, steps=28))

            def spine(t, widest=widest):
                return max(0.4, widest * 0.06
                           * math.sin(math.pi * t) ** 0.8)

            q.setBrush(QColor(214, 255, 232, 16))
            q.drawPath(_ribbon(p0, p1, p2, p3, spine, steps=28))

    _through_buffer(p, w, h, paint)


def _shafts_rich(p, w, h, phase, seed=103):
    """
    Sunlight through water: nested bands, drawn small and scaled up.

    The bands remove the hard sides a single filled wedge would have,
    but each band keeps an edge of its own, and across a beam this wide
    twelve of them left visible steps - measured at three to fifteen
    levels of brightness, which reads as faint coloured wedges against
    the water. `_through_buffer` interpolates them away and costs less
    than drawing at full size.

    The random draws mirror the plain shafts - same seed, same order,
    same ranges - so every beam sits where it always has.
    """
    def paint(q, bw, bh, scale):
        rng = random.Random(3)
        for i in range(5):
            base = rng.uniform(0.05, 0.95) * bw
            width = rng.uniform(60, 140) / scale
            lean = rng.uniform(-0.35, 0.35)
            drift = math.sin(phase * 0.25 + i * 1.3) * (26 / scale)

            top_x = base + drift
            spread = width * 3.1
            shimmer = 1.0 + math.sin(phase * 0.6 + i * 2.1) * 0.08

            p0 = QPointF(top_x, -20 / scale)
            p1 = QPointF(top_x + lean * bh * 0.34, bh * 0.34)
            p2 = QPointF(top_x + lean * bh * 0.70, bh * 0.70)
            p3 = QPointF(top_x + lean * bh, bh + 20 / scale)

            wob = random.Random(1000 + i)
            for layer in range(12):
                step = 1.0 - layer / 12
                outer = step * (1.0 + wob.uniform(-0.10, 0.10))
                strength = (1.0 - step * 0.42) * 0.8

                def half(t, outer=outer, spread=spread, shimmer=shimmer):
                    # Narrow where it enters the water, spreading as it
                    # sinks - the opposite of a ribbon, which tapers at
                    # both ends.
                    return spread * outer * shimmer * (0.34 + 0.66 * t)

                fade = QLinearGradient(0, 0, 0, bh)
                fade.setColorAt(0.0, QColor(178, 236, 250,
                                            max(1, int(9 * strength))))
                fade.setColorAt(0.45, QColor(150, 218, 238,
                                             max(1, int(5 * strength))))
                fade.setColorAt(1.0, QColor(120, 190, 214, 0))
                q.setPen(Qt.NoPen)
                q.setBrush(fade)
                q.drawPath(_ribbon(p0, p1, p2, p3, half, steps=24))

            def core(t, spread=spread, shimmer=shimmer):
                return max(0.4, spread * 0.05 * shimmer
                           * (0.34 + 0.66 * t))

            thread = QLinearGradient(0, 0, 0, bh)
            thread.setColorAt(0.0, QColor(226, 250, 255, 21))
            thread.setColorAt(0.6, QColor(200, 238, 250, 8))
            thread.setColorAt(1.0, QColor(180, 224, 240, 0))
            q.setBrush(thread)
            q.drawPath(_ribbon(p0, p1, p2, p3, core, steps=24))

    _through_buffer(p, w, h, paint)


# ---- registries --------------------------------------------------------
#
# Every registry lives here, at the end, because each one names things
# defined above it. Three separate themes have been added by appending
# their code to this file, and all three broke a registry that sat
# higher up - so the rule is now explicit: definitions above, registries
# below.

PAINTERS = {"halloween": halloween, "starfield": starfield,
            "underwater": underwater, "kawaii": kawaii,
            "cryptic": cryptic, "aero": aero,
            "desert": desert, "arctic": arctic}


# Which extra stylesheet belongs to which theme. A registry rather than a
# chain of ifs, so adding a theme is one entry in one place.
SHEETS = {
    "halloween": HALLOWEEN_QSS,
    "starfield": STARFIELD_QSS,
    "underwater": UNDERWATER_QSS,
    "kawaii": KAWAII_QSS,
    "cryptic": CRYPTIC_QSS,
    "aero": AERO_QSS,
    "desert": DESERT_QSS,
    "arctic": ARCTIC_QSS,
}


def style_sheet(name):
    """
    Extra stylesheet for a theme, appended after the base one.

    A theme cannot paint on controls, so reshaping them here is the only
    way it can reach them. Returns an empty string for plain themes.
    """
    return SHEETS.get(canonical(name), "")
