"""
The expanded image viewer.

Opens from the thumbnail it was launched from and returns to it, so the
picture appears to grow out of the grid rather than replacing it. That
continuity is the whole point: a lightbox that fades in from nowhere
loses the connection between what was clicked and what is now shown.
"""

from pathlib import Path

from PySide6.QtCore import (
    QAbstractAnimation, QEasingCurve, QParallelAnimationGroup, QPoint,
    QPointF, QPropertyAnimation, QRect, Qt, Signal,
)
from PySide6.QtGui import (
    QColor, QKeySequence, QPainter, QPainterPath, QPen, QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from . import theme


class MarkButton(QPushButton):
    """
    A button that draws its own arrow or cross.

    Drawn rather than typed: a font glyph is whatever size and weight the
    font decided, and on a control this small that is usually too light
    with no way to say otherwise. Drawing it also means it looks the same
    on any machine, whatever fonts happen to be installed.
    """

    def __init__(self, mark, parent=None):
        super().__init__(parent)
        self.mark = mark            # "left", "right" or "close"
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        # The frame, hover and disabled states still come from the
        # stylesheet; only the mark itself is painted here.
        super().paintEvent(event)

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        span = min(self.width(), self.height())
        cx, cy = self.width() / 2, self.height() / 2

        ink = (QColor(226, 234, 244) if self.isEnabled()
               else QColor(110, 122, 138))
        pen = QPen(ink)
        pen.setWidthF(max(1.5, span * 0.12))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)

        if self.mark == "close":
            arm = span * 0.30
            p.drawLine(QPointF(cx - arm, cy - arm),
                       QPointF(cx + arm, cy + arm))
            p.drawLine(QPointF(cx + arm, cy - arm),
                       QPointF(cx - arm, cy + arm))
        else:
            arm = span * 0.34
            facing = -1 if self.mark == "left" else 1
            path = QPainterPath(QPointF(cx - facing * arm * 0.5, cy - arm))
            path.lineTo(QPointF(cx + facing * arm * 0.5, cy))
            path.lineTo(QPointF(cx - facing * arm * 0.5, cy + arm))
            p.drawPath(path)
        p.end()


class ImageViewer(QWidget):
    """A picture filling the gallery, with its own controls."""

    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("viewer")
        # A plain QWidget ignores a stylesheet background unless told to
        # honour it, so the dimmed backdrop was never painting at all and
        # the gallery showed straight through around the picture.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.hide()

        self._paths = []
        self._index = 0
        self._censored = set()
        self._revealed = set()
        self._home = QRect()
        self._anim = None
        self._slide = None

        self.frame = QLabel(self)
        self.frame.setAlignment(Qt.AlignCenter)
        self.frame.setObjectName("viewerImage")

        self.hint = QLabel("Censored - click to reveal", self)
        self.hint.setObjectName("viewerHint")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.hide()

        self.prev_btn = MarkButton("left", self)
        self.prev_btn.setObjectName("viewerNav")
        self.prev_btn.setToolTip("Previous image")
        self.prev_btn.clicked.connect(lambda: self.step(-1))
        self.next_btn = MarkButton("right", self)
        self.next_btn.setObjectName("viewerNav")
        self.next_btn.setToolTip("Next image")
        self.next_btn.clicked.connect(lambda: self.step(1))
        self.close_btn = MarkButton("close", self)
        self.close_btn.setObjectName("viewerClose")
        self.close_btn.setToolTip("Close (Esc)")
        self.close_btn.clicked.connect(self.collapse)

        self.caption = QLabel("", self)
        self.caption.setObjectName("viewerCaption")
        self.caption.setAlignment(Qt.AlignCenter)

        for key in ("Esc",):
            QShortcut(QKeySequence(key), self, activated=self.collapse)
        QShortcut(QKeySequence(Qt.Key_Left), self,
                  activated=lambda: self.step(-1))
        QShortcut(QKeySequence(Qt.Key_Right), self,
                  activated=lambda: self.step(1))

    # ---- opening and closing -------------------------------------------

    def open_at(self, paths, index, start_rect, censored, captions=None):
        """
        Show `paths[index]`, growing out of `start_rect`.

        The rectangle is where the thumbnail sits, in this widget's own
        coordinates, so the animation can begin exactly where the user
        clicked.
        """
        self._paths = list(paths)
        self._index = max(0, min(index, len(self._paths) - 1))
        self._censored = set(censored or ())
        self._revealed = set()
        self._captions = captions or {}
        self._home = QRect(start_rect)

        # The caller decides where this goes - it covers the gallery,
        # not the whole window, and its parent is the window so that it
        # can sit above the decoration. Taking the parent's rect here
        # threw that away and swallowed the sidebar.
        self.show()
        self.raise_()
        self.setFocus(Qt.OtherFocusReason)
        self._render()

        # Grow from the thumbnail to full size.
        self.frame.setGeometry(self._home)
        grow = QPropertyAnimation(self.frame, b"geometry", self)
        grow.setDuration(240)
        grow.setStartValue(self._home)
        grow.setEndValue(self._stage())
        grow.setEasingCurve(QEasingCurve.OutCubic)

        fade = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(fade)
        wash = QPropertyAnimation(fade, b"opacity", self)
        wash.setDuration(200)
        wash.setStartValue(0.0)
        wash.setEndValue(1.0)

        group = QParallelAnimationGroup(self)
        group.addAnimation(grow)
        group.addAnimation(wash)
        group.finished.connect(self._settle)
        self._anim = group
        group.start(QAbstractAnimation.DeleteWhenStopped)

    def collapse(self):
        """Shrink back to the thumbnail it came from."""
        if not self.isVisible():
            return
        for widget in (self.prev_btn, self.next_btn, self.close_btn,
                       self.hint, self.caption):
            widget.hide()

        shrink = QPropertyAnimation(self.frame, b"geometry", self)
        shrink.setDuration(210)
        shrink.setStartValue(self.frame.geometry())
        shrink.setEndValue(self._home)
        shrink.setEasingCurve(QEasingCurve.InCubic)

        fade = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(fade)
        wash = QPropertyAnimation(fade, b"opacity", self)
        wash.setDuration(200)
        wash.setStartValue(1.0)
        wash.setEndValue(0.0)

        group = QParallelAnimationGroup(self)
        group.addAnimation(shrink)
        group.addAnimation(wash)
        group.finished.connect(self._finish_close)
        self._anim = group
        group.start(QAbstractAnimation.DeleteWhenStopped)

    def _finish_close(self):
        self.setGraphicsEffect(None)
        self.hide()
        self.closed.emit()

    def _settle(self):
        self.setGraphicsEffect(None)
        self._place_controls()
        for widget in (self.close_btn, self.caption):
            widget.show()
        self._sync_nav()

    # ---- layout --------------------------------------------------------

    def _stage(self):
        """The rectangle the picture fills, with room for the controls."""
        margin = 26
        return QRect(margin, margin,
                     max(40, self.width() - margin * 2),
                     max(40, self.height() - margin * 2 - 26))

    def _place_controls(self):
        """
        Put the controls on the picture, not on the stage around it.

        The frame fills the stage, but the picture is letterboxed inside
        it and its shape depends entirely on the image: a portrait one
        leaves wide bars either side. Anchoring to the stage leaves the
        arrows floating out in the backdrop, disconnected from the thing
        they act on. Anchoring to the picture means they sit on its
        edges whatever its proportions.
        """
        stage = self._stage()
        self.frame.setGeometry(stage)

        # Derived after the frame is placed, since it is measured from
        # the frame's geometry and the pixmap inside it.
        rect = self.picture_rect()
        if rect.isEmpty():
            rect = stage
        self.hint.setGeometry(rect)

        size = 58
        close = 40
        # A small picture cannot carry full-size controls on its edges,
        # so they shrink rather than swamping it.
        if rect.width() < size * 3:
            size = max(28, rect.width() // 3)
        if min(rect.width(), rect.height()) < close * 3:
            close = max(22, min(rect.width(), rect.height()) // 3)

        middle = rect.top() + rect.height() // 2 - size // 2
        self.prev_btn.setGeometry(rect.left() + 10, middle, size, size)
        self.next_btn.setGeometry(rect.right() - size - 10, middle,
                                  size, size)

        # Inset from the corner rather than hard against it, so it reads
        # as sitting on the picture rather than hanging off the edge.
        self.close_btn.setGeometry(rect.right() - close - 22,
                                   rect.top() + 20, close, close)

        self.caption.setGeometry(stage.left(), stage.bottom() + 2,
                                 stage.width(), 24)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.isVisible():
            self._place_controls()

    def _sync_nav(self):
        many = len(self._paths) > 1
        self.prev_btn.setVisible(many)
        self.next_btn.setVisible(many)
        self.prev_btn.setEnabled(self._index > 0)
        self.next_btn.setEnabled(self._index < len(self._paths) - 1)

    # ---- what is showing -----------------------------------------------

    def current(self):
        if not self._paths:
            return None
        return self._paths[self._index]

    def _pixmap_for(self, path, box):
        pm = QPixmap(str(path))
        if pm.isNull():
            return pm
        return pm.scaled(box.size(), Qt.KeepAspectRatio,
                         Qt.SmoothTransformation)

    def _render(self):
        """Draw the current image, blurred if it is still censored."""
        path = self.current()
        if path is None:
            return
        stage = self._stage()
        pm = self._pixmap_for(path, stage)
        hidden = (path.name in self._censored
                  and path.name not in self._revealed)
        if hidden and not pm.isNull():
            # The same shrink-and-grow as the thumbnail: the detail is
            # genuinely discarded rather than covered over.
            small = pm.scaled(max(4, pm.width() // 40),
                              max(4, pm.height() // 40),
                              Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            pm = small.scaled(pm.size(), Qt.IgnoreAspectRatio,
                              Qt.SmoothTransformation)
        self.frame.setPixmap(pm)
        self.hint.setVisible(hidden)
        self.caption.setText(
            self._captions.get(path.name, path.name)
            + (f"    {self._index + 1} of {len(self._paths)}"
               if len(self._paths) > 1 else ""))

    def picture_rect(self):
        """
        Where the picture actually is, inside the frame.

        The frame fills the stage, but the image is letterboxed within
        it, so the bars either side belong to the backdrop rather than
        to the picture.
        """
        pixmap = self.frame.pixmap()
        if pixmap is None or pixmap.isNull():
            return QRect()
        geometry = self.frame.geometry()
        pw, ph = pixmap.width(), pixmap.height()
        if not pw or not ph:
            return QRect()
        scale = min(geometry.width() / pw, geometry.height() / ph)
        w, h = pw * scale, ph * scale
        return QRect(int(geometry.x() + (geometry.width() - w) / 2),
                     int(geometry.y() + (geometry.height() - h) / 2),
                     int(w), int(h))

    def mousePressEvent(self, event):
        """
        Click the picture to reveal it if censored; click anywhere else
        to close.

        Clicking away is how every image viewer behaves, and the
        backdrop is dimmed precisely to say it is not part of what you
        are looking at. The buttons are children and take their own
        clicks, so they never reach this.
        """
        path = self.current()
        if path is None:
            self.collapse()
            return

        if not self.picture_rect().contains(event.position().toPoint()):
            self.collapse()
            return

        if (path.name in self._censored
                and path.name not in self._revealed):
            self._revealed.add(path.name)
            self._reveal()
            return
        super().mousePressEvent(event)

    def _reveal(self):
        """
        Cross-fade from the blur to the picture.

        A second label holding the sharp image is faded in over the top,
        rather than swapping the pixmap: an instant swap after a
        deliberate click reads as a glitch, and the fade is what makes it
        feel like something being uncovered.
        """
        stage = self._stage()
        sharp = QLabel(self)
        sharp.setAlignment(Qt.AlignCenter)
        sharp.setObjectName("viewerImage")
        sharp.setGeometry(stage)
        sharp.setPixmap(self._pixmap_for(self.current(), stage))
        sharp.show()
        sharp.raise_()
        self.hint.hide()

        effect = QGraphicsOpacityEffect(sharp)
        sharp.setGraphicsEffect(effect)
        fade = QPropertyAnimation(effect, b"opacity", self)
        fade.setDuration(420)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)

        def done():
            self._render()
            sharp.deleteLater()
            self.close_btn.raise_()
            self._sync_nav()

        fade.finished.connect(done)
        self._reveal_anim = fade
        fade.start(QAbstractAnimation.DeleteWhenStopped)

    # ---- moving between images ------------------------------------------

    def _sliding(self):
        """
        Is a slide still playing?

        Guarded rather than tested directly: the animation is set to
        delete itself when it stops, so the Python reference outlives the
        C++ object and asking it anything raises.
        """
        if self._slide is None:
            return False
        try:
            return self._slide.state() == QAbstractAnimation.Running
        except RuntimeError:
            self._slide = None
            return False

    def step(self, direction):
        """
        Slide to the neighbouring image.

        The outgoing picture leaves the way the incoming one arrives, so
        the pair reads as a strip being moved rather than two unrelated
        fades. Stops at the ends rather than wrapping: silently looping
        back to the first image makes it impossible to tell where the set
        ends.
        """
        if not self._paths:
            return False
        target = self._index + direction
        if not 0 <= target < len(self._paths):
            return False
        if self._sliding():
            return False

        stage = self._stage()
        leaving = QLabel(self)
        leaving.setAlignment(Qt.AlignCenter)
        leaving.setObjectName("viewerImage")
        leaving.setGeometry(stage)
        leaving.setPixmap(self.frame.pixmap())
        leaving.show()

        self._index = target
        self._render()

        offset = stage.width() + 24
        start = QRect(stage)
        start.moveLeft(stage.left() + offset * direction)
        self.frame.setGeometry(start)

        incoming = QPropertyAnimation(self.frame, b"geometry", self)
        incoming.setDuration(230)
        incoming.setStartValue(start)
        incoming.setEndValue(stage)
        incoming.setEasingCurve(QEasingCurve.OutCubic)

        gone = QRect(stage)
        gone.moveLeft(stage.left() - offset * direction)
        outgoing = QPropertyAnimation(leaving, b"geometry", self)
        outgoing.setDuration(230)
        outgoing.setStartValue(stage)
        outgoing.setEndValue(gone)
        outgoing.setEasingCurve(QEasingCurve.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(incoming)
        group.addAnimation(outgoing)
        group.finished.connect(leaving.deleteLater)
        group.finished.connect(self._place_controls)
        self._slide = group
        group.start(QAbstractAnimation.DeleteWhenStopped)
        self._sync_nav()
        return True

    def set_home(self, rect):
        """Where to shrink back to, if the grid has moved underneath."""
        self._home = QRect(rect)

    def keyPressEvent(self, event):
        # Handled here as well as by the shortcuts, so the keys work
        # whichever child happens to hold focus.
        if event.key() == Qt.Key_Escape:
            self.collapse()
        elif event.key() == Qt.Key_Left:
            self.step(-1)
        elif event.key() == Qt.Key_Right:
            self.step(1)
        else:
            super().keyPressEvent(event)
