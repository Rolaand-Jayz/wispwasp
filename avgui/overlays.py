"""
Overlays that sit on top of the window: the vignette and the change bar.

Both are children of the main window rather than of any panel, so they
can appear over whatever is showing and survive a layout switch.
"""

from PySide6.QtCore import (
    Property, QAbstractAnimation, QEasingCurve, QPoint, QPropertyAnimation,
    QRect, QSequentialAnimationGroup, Qt, Signal,
)
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget,
)

from . import theme


class Vignette(QWidget):
    """
    A coloured glow around the inside edge of the window.

    Used to say "not yet" when navigation is refused. It draws only near
    the border and is transparent to the mouse, so it can flash over a
    live interface without interrupting anything.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.hide()
        self._strength = 0.0
        self._colour = QColor(theme.FAVOURITE)

        self._anim = QSequentialAnimationGroup(self)
        rise = QPropertyAnimation(self, b"strength", self)
        rise.setDuration(160)
        rise.setStartValue(0.0)
        rise.setEndValue(1.0)
        rise.setEasingCurve(QEasingCurve.OutCubic)
        fall = QPropertyAnimation(self, b"strength", self)
        fall.setDuration(420)
        fall.setStartValue(1.0)
        fall.setEndValue(0.0)
        fall.setEasingCurve(QEasingCurve.InCubic)
        self._anim.addAnimation(rise)
        self._anim.addAnimation(fall)
        self._anim.finished.connect(self.hide)

    def get_strength(self):
        return self._strength

    def set_strength(self, value):
        self._strength = float(value)
        self.update()

    strength = Property(float, get_strength, set_strength)

    def flash(self, colour=None):
        """One quick pulse. Restarting mid-flash is fine."""
        self._colour = QColor(colour or theme.FAVOURITE)
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.raise_()
        self.show()
        self._anim.stop()
        self._anim.start()

    def paintEvent(self, _event):
        if self._strength <= 0.01:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        depth = max(48, min(rect.width(), rect.height()) // 6)

        base = QColor(self._colour)
        base.setAlphaF(min(1.0, 0.55 * self._strength))
        clear = QColor(self._colour)
        clear.setAlpha(0)

        # Four edge gradients rather than one radial: a radial over a wide
        # window washes the middle of the screen, which is where the user
        # is trying to look.
        edges = (
            (QRect(0, 0, rect.width(), depth), 0, 0, 0, depth),
            (QRect(0, rect.height() - depth, rect.width(), depth),
             0, depth, 0, 0),
            (QRect(0, 0, depth, rect.height()), 0, 0, depth, 0),
            (QRect(rect.width() - depth, 0, depth, rect.height()),
             depth, 0, 0, 0),
        )
        for area, x1, y1, x2, y2 in edges:
            grad = QLinearGradient(area.x() + x1, area.y() + y1,
                                   area.x() + x2, area.y() + y2)
            grad.setColorAt(0.0, base)
            grad.setColorAt(1.0, clear)
            p.fillRect(area, grad)
        p.end()


class ChangeBar(QFrame):
    """
    The unapplied-changes bar: slides up from the bottom of the window.

    Anchored to the window rather than to the Settings panel so it stays
    put while the panel scrolls, and so it can still be seen if the user
    is trying to navigate away from it.
    """

    applied = Signal()
    cancelled = Signal()

    HEIGHT = 56

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("changeBar")
        self.setFixedHeight(self.HEIGHT)
        self.hide()

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 12, 0)
        row.setSpacing(10)

        self.label = QLabel("Unapplied changes")
        self.label.setObjectName("changeBarText")
        row.addWidget(self.label)
        row.addStretch(1)

        self.cancel_btn = QPushButton("Cancel changes")
        self.cancel_btn.setObjectName("denyButton")
        self.cancel_btn.clicked.connect(lambda: self._finish(False))
        row.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Apply changes")
        self.apply_btn.setObjectName("confirmButton")
        self.apply_btn.clicked.connect(lambda: self._finish(True))
        row.addWidget(self.apply_btn)

        # Offset 0 turns a drop shadow into an even glow. Red to begin
        # with, so it never flickers green before a decision is made.
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setOffset(0, 0)
        self._glow.setBlurRadius(0)
        self._glow.setColor(QColor(theme.DANGER))
        self.setGraphicsEffect(self._glow)

        self._slide = QPropertyAnimation(self, b"pos", self)
        self._slide.setDuration(260)
        self._shake = None
        self._glow_anim = None
        self._showing = False
        self._confirming = False

    # ---- placement -----------------------------------------------------

    def _resting(self):
        parent = self.parentWidget()
        margin = 18
        width = min(560, parent.width() - margin * 2)
        x = (parent.width() - width) // 2
        self.resize(width, self.HEIGHT)
        return QPoint(x, parent.height() - self.HEIGHT - margin)

    def _hidden(self):
        parent = self.parentWidget()
        return QPoint(self._resting().x(), parent.height() + 8)

    def reposition(self):
        """Keep it anchored when the window is resized."""
        if not self.parentWidget():
            return
        self.move(self._resting() if self._showing else self._hidden())

    # ---- showing and hiding --------------------------------------------

    # Resting glow while changes are outstanding, and the brighter peak
    # used to confirm a decision.
    IDLE_GLOW = 26
    PEAK_GLOW = 46

    def slide_in(self):
        if self._showing:
            return
        self._showing = True
        self.show()
        self.raise_()
        # Red from the moment it appears: something is unresolved, and it
        # stays that way until the green button is actually pressed.
        self._set_glow(theme.DANGER, self.IDLE_GLOW, duration=220)
        self._slide.stop()
        self._slide.setStartValue(self._hidden())
        self._slide.setEndValue(self._resting())
        self._slide.setEasingCurve(QEasingCurve.OutCubic)
        self._slide.start()

    def _set_glow(self, colour, radius, duration=200):
        """Ease the glow to a colour and strength."""
        self._glow.setColor(QColor(colour))
        anim = QPropertyAnimation(self._glow, b"blurRadius", self)
        anim.setDuration(duration)
        anim.setStartValue(self._glow.blurRadius())
        anim.setEndValue(radius)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        self._glow_anim = anim
        anim.start(QAbstractAnimation.DeleteWhenStopped)

    def slide_out(self):
        """
        Put it away.

        Used both when the user decides and when they undo their own
        edits: if every value is back where it started there is nothing to
        apply, and leaving the bar up would be asking about nothing.
        """
        if not self._showing:
            return
        self._showing = False
        self._slide.stop()
        self._slide.setStartValue(self.pos())
        self._slide.setEndValue(self._hidden())
        self._slide.setEasingCurve(QEasingCurve.InCubic)
        self._slide.start()
        self._slide.finished.connect(self._maybe_hide)

    def _maybe_hide(self):
        if not self._showing:
            self.hide()
            self._glow.setBlurRadius(0)
            self._confirming = False

    def is_showing(self):
        return self._showing

    # ---- attention and confirmation ------------------------------------

    def shake(self):
        """
        A quick tremble, for when navigation was refused.

        Short and small on purpose: it should read as "this thing, here",
        not as an error state.
        """
        if not self._showing:
            return
        home = self._resting()
        self.move(home)

        group = QSequentialAnimationGroup(self)
        offsets = (11, -9, 7, -5, 3, 0)
        previous = home
        for offset in offsets:
            step = QPropertyAnimation(self, b"pos", group)
            step.setDuration(55)
            step.setStartValue(previous)
            previous = QPoint(home.x() + offset, home.y())
            step.setEndValue(previous)
            group.addAnimation(step)
        self._shake = group
        group.start(QAbstractAnimation.DeleteWhenStopped)

    def confirm(self, accepted):
        """
        Flare, then fade away.

        Green only if Apply was pressed. Cancelling keeps the red it has
        been wearing all along, so the colour that leaves the screen is
        the colour of what happened - not merely "you pressed something".
        """
        colour = theme.OK if accepted else theme.DANGER
        self._glow.setColor(QColor(colour))

        group = QSequentialAnimationGroup(self)
        rise = QPropertyAnimation(self._glow, b"blurRadius", group)
        rise.setDuration(150)
        rise.setStartValue(self._glow.blurRadius())
        rise.setEndValue(self.PEAK_GLOW)
        rise.setEasingCurve(QEasingCurve.OutCubic)
        hold = QPropertyAnimation(self._glow, b"blurRadius", group)
        hold.setDuration(220)
        hold.setStartValue(self.PEAK_GLOW)
        hold.setEndValue(self.PEAK_GLOW - 14)
        group.addAnimation(rise)
        group.addAnimation(hold)
        group.finished.connect(self.slide_out)
        self._glow_anim = group
        group.start(QAbstractAnimation.DeleteWhenStopped)

    def _finish(self, accepted):
        # The confirmation animation owns the exit from here on. Applying
        # clears the pending changes, which would otherwise slide the bar
        # away instantly and the glow would never be seen.
        self._confirming = True
        (self.applied if accepted else self.cancelled).emit()
        self.confirm(accepted)

    def is_confirming(self):
        """True while the confirmation animation is playing itself out."""
        return self._confirming


class SubNavItem(QWidget):
    """
    A nav entry that unrolls beneath its parent page.

    Hidden until its parent is the open page, then it slides down and
    glows briefly in the accent colour. The glow is what stops it reading
    as a layout jump: something arrived, and it says so.

    The height is animated rather than the position, so the entries below
    move out of the way instead of being covered.
    """

    clicked = Signal()

    def __init__(self, label, height=34, parent=None):
        super().__init__(parent)
        self._full_height = height
        self.setMaximumHeight(0)
        self.setMinimumHeight(0)

        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)

        self.button = QPushButton(label)
        self.button.setObjectName("navSubButton")
        self.button.setCheckable(True)
        self.button.setFixedHeight(height)
        self.button.clicked.connect(lambda: self.clicked.emit())
        box.addWidget(self.button)

        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setOffset(0, 0)
        self._glow.setBlurRadius(0)
        self._glow.setColor(QColor(theme.ACCENT))
        self.button.setGraphicsEffect(self._glow)

        self._slide = QPropertyAnimation(self, b"maximumHeight", self)
        self._slide.setDuration(220)
        self._shown = False

    def is_open(self):
        return self._shown

    def set_checked(self, value):
        self.button.setChecked(bool(value))

    def reveal(self):
        if self._shown:
            return
        self._shown = True
        self._slide.stop()
        self._slide.setStartValue(self.maximumHeight())
        self._slide.setEndValue(self._full_height)
        self._slide.setEasingCurve(QEasingCurve.OutCubic)
        self._slide.start()
        self._flare()

    def conceal(self):
        if not self._shown:
            return
        self._shown = False
        self._slide.stop()
        self._slide.setStartValue(self.maximumHeight())
        self._slide.setEndValue(0)
        self._slide.setEasingCurve(QEasingCurve.InCubic)
        self._slide.start()

    def _flare(self):
        """A short glow, timed to land as the slide finishes."""
        self._glow.setColor(QColor(theme.ACCENT))
        group = QSequentialAnimationGroup(self)
        rise = QPropertyAnimation(self._glow, b"blurRadius", group)
        rise.setDuration(200)
        rise.setStartValue(0)
        rise.setEndValue(22)
        rise.setEasingCurve(QEasingCurve.OutCubic)
        fall = QPropertyAnimation(self._glow, b"blurRadius", group)
        fall.setDuration(520)
        fall.setStartValue(22)
        fall.setEndValue(0)
        fall.setEasingCurve(QEasingCurve.InCubic)
        group.addAnimation(rise)
        group.addAnimation(fall)
        self._flare_anim = group
        group.start(QAbstractAnimation.DeleteWhenStopped)
