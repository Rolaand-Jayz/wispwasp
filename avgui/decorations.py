"""
Decorative themes: a layer painted over the window.

The layer is a child of the main window, transparent to the mouse, sitting
above the panels. Three rules govern what it may cover, and they are the
whole design:

  - generated artwork always wins
  - controls and text always win
  - decoration fills whatever is left

Everything else is a painter that fills a region. Adding a theme means
adding one function, not touching the layer.
"""

import math
import random

from PySide6.QtCore import QPoint, QRect, QRectF, QPointF, Qt, QTimer
from PySide6.QtGui import (
    QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient,
    QRegion, QTransform,
)
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QLabel, QLineEdit, QListWidget, QPlainTextEdit,
    QPushButton, QSpinBox, QToolButton, QWidget,
)

# Anything the decoration must not cover. Text is on the list for the
# same reason buttons are: a web over a heading makes the words lose.
PROTECTED = (QPushButton, QToolButton, QLineEdit, QPlainTextEdit,
             QComboBox, QListWidget, QCheckBox, QSpinBox, QLabel)

# How often the exclusion geometry is re-measured. Walking the widget
# tree every frame would be wasteful; panels do not move that often, and
# a splitter drag is caught within a fifth of a second.
GEOMETRY_MS = 200
FRAME_MS = 70          # about 14 fps, enough for a flame

# The enhanced artwork briefly ran at a slower pace, back when the
# underwater shafts cost 57ms a frame. Drawing that work through a
# scaled buffer halved it, and the slower rate turned out to read as lag
# in its own right - fewer frames of a moving thing looks like the app
# struggling, whatever the thread is actually doing. Both sets run at
# the same rate again.
RICH_FRAME_MS = FRAME_MS


class DecorationLayer(QWidget):
    """Paints the current theme over the window."""

    def __init__(self, window, parent=None):
        super().__init__(parent or window)
        self.win = window
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._painter_fn = None
        self._animated = False
        self._rich = False
        self._phase = 0.0
        self._clip = None
        self._safe = None

        self._frames = QTimer(self)
        self._frames.timeout.connect(self._tick)
        self._geometry = QTimer(self)
        self._geometry.timeout.connect(self._remeasure)
        self.hide()

    # ---- what is showing ----------------------------------------------

    def set_theme(self, name):
        from .themes import painter_for
        self._painter_fn = painter_for(name)
        active = self._painter_fn is not None
        self.setVisible(active)
        if active:
            self.raise_()
            self._remeasure()
            self._geometry.start(GEOMETRY_MS)
        else:
            self._geometry.stop()
            self._frames.stop()
        self._sync_animation()
        self.update()

    def set_enhanced(self, value):
        """Swap between the plain and the enhanced artwork."""
        value = bool(value)
        if value != self._rich:
            self._rich = value
            self._sync_animation()
            self.update()

    def set_animated(self, value):
        self._animated = bool(value)
        self._sync_animation()
        self.update()

    def _sync_animation(self):
        wants = self._animated and self._painter_fn is not None
        interval = RICH_FRAME_MS if self._rich else FRAME_MS
        if wants:
            # Restarted rather than left alone when the pace changes, or
            # turning the enhanced artwork on would keep the old rate
            # until something else happened to restart the timer.
            if (not self._frames.isActive()
                    or self._frames.interval() != interval):
                self._frames.start(interval)
        elif self._frames.isActive():
            self._frames.stop()

    def _tick(self):
        self._phase += self._frames.interval() / 1000.0
        self.update()

    # ---- where it may paint --------------------------------------------

    def refresh(self):
        """
        Re-measure from scratch, after the window was rearranged.

        Switching layout builds a new central widget, which Qt stacks
        above this one, and destroys the panels the cached regions were
        measured from. Both have to be redone or the decoration ends up
        underneath the interface with a stale idea of where things are.
        """
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self._clip = None
        self._safe = None
        if self.isVisible():
            self.raise_()
            self._remeasure()
        self.update()

    def _remeasure(self):
        """
        Work out the two paintable regions.

        Two, not one: a tint or a candle glow may cross a label without
        harm, but nothing at all may cross the artwork. Patterned things
        use the tighter region, placed things use the looser one.

        Cached rather than computed per frame: this walks the whole widget
        tree, which is fine a few times a second and wasteful fourteen
        times a second.
        """
        if not self.isVisible():
            return
        artwork_free = QRegion(self.rect())

        for preview in self._artwork_widgets():
            rect = self._artwork_rect(preview)
            if rect is not None:
                artwork_free = artwork_free.subtracted(QRegion(rect))

        # The viewer is not cut out of the decoration: it sits above it
        # instead. Cutting a hole stopped the effects dead wherever it
        # opened, so they vanished and popped back as it closed. Sitting
        # above means its dimmed backdrop falls over the decoration too,
        # which is what it should do - everything behind the picture
        # goes quiet together.

        patterned = QRegion(artwork_free)
        for kind in PROTECTED:
            for widget in self.win.findChildren(kind):
                if not widget.isVisible():
                    continue
                if widget.width() < 4 or widget.height() < 4:
                    continue
                pad = 2 if isinstance(widget, QLabel) else 3
                top_left = widget.mapTo(self.win, QPoint(0, 0))
                patterned = patterned.subtracted(QRegion(QRect(
                    top_left.x() - pad, top_left.y() - pad,
                    widget.width() + pad * 2, widget.height() + pad * 2)))

        if patterned != self._clip or artwork_free != self._safe:
            self._clip = patterned
            self._safe = artwork_free
            self.update()

    def _artwork_widgets(self):
        """
        Everything showing a generated picture, wherever it lives.

        Not just the live preview: a gallery thumbnail is the same
        image, and so is the expanded viewer. Decoration washing over
        them tints the very thing the app exists to show, which is the
        one thing the rules have always said it may not do.
        """
        found = []
        for panel in (getattr(self.win, "live", None),
                      getattr(self.win, "prompt", None)):
            preview = getattr(panel, "preview", None) if panel else None
            if preview is not None:
                found.append(preview)

        gallery = getattr(self.win, "gallery", None)
        if gallery is not None:
            from .widgets import HoverCaption
            found.extend(gallery.findChildren(HoverCaption))

        return [widget for widget in found if widget is not None]

    def _artwork_rect(self, preview):
        """
        Where the picture is, not where its container is.

        A preview is wider than the image inside it, so excluding the
        widget would leave bare strips either side of the artwork.
        """
        if preview is None or not preview.isVisible():
            return None
        pixmap = preview.pixmap()
        if pixmap is None or pixmap.isNull():
            return None
        w, h = preview.width(), preview.height()
        if not pixmap.width() or not pixmap.height():
            return None
        scale = min(w / pixmap.width(), h / pixmap.height())
        draw_w, draw_h = pixmap.width() * scale, pixmap.height() * scale
        top_left = preview.mapTo(self.win, QPoint(0, 0))
        return QRect(int(top_left.x() + (w - draw_w) / 2),
                     int(top_left.y() + (h - draw_h) / 2),
                     int(draw_w), int(draw_h))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._clip = None
        self._safe = None
        self._remeasure()

    def paintEvent(self, _event):
        if self._painter_fn is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        whole = QRegion(self.rect())
        clip = self._clip if self._clip is not None else whole
        safe = self._safe if self._safe is not None else whole
        self._painter_fn(p, self.width(), self.height(), self.win,
                         clip, safe,
                         self._phase if self._animated else 0.0,
                         self._rich)
        p.end()
