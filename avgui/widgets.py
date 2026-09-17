"""Small reusable widgets: the tally light and the image preview."""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QSize, QRectF, Signal
from PySide6.QtGui import (
    QColor, QCursor, QFont, QFontMetrics, QPainter, QPen, QPixmap,
)
from PySide6.QtWidgets import (
    QCheckBox, QLabel, QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)

from . import theme


class TallyLight(QWidget):
    """
    A broadcast tally lamp. Dark when idle, red when listening, amber while
    the GPU works. It pulses only while working, because motion that means
    'something is happening right now' is worth the attention it takes.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 14)
        self._state = "idle"
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set_state(self, state):
        if state == self._state:
            return
        self._state = state
        if state == "working":
            self._timer.start(60)
        else:
            self._timer.stop()
            self._phase = 0.0
        self.update()

    def _tick(self):
        self._phase = (self._phase + 0.09) % 1.0
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        if self._state == "live":
            colour = QColor(theme.TALLY)
        elif self._state == "working":
            colour = QColor(theme.WORKING)
            # Triangle wave: never fully dark, so it reads as a pulse
            # rather than a blink.
            t = abs(self._phase * 2 - 1)
            colour.setAlpha(int(140 + 115 * t))
        else:
            colour = QColor(theme.EDGE)

        if self._state in ("live", "working"):
            glow = QColor(colour)
            glow.setAlpha(60)
            p.setBrush(glow)
            p.setPen(Qt.NoPen)
            p.drawEllipse(0, 0, 14, 14)

        p.setBrush(colour)
        p.setPen(Qt.NoPen)
        p.drawEllipse(3, 3, 8, 8)
        p.end()


class ImagePreview(QLabel):
    """
    Shows the current overlay image, scaled to fit and letterboxed.

    Rescaling happens from the original pixmap on every resize, never from
    an already-scaled copy, which would compound softness each time the
    window moved.

    Both size hints are fixed, and the size policy ignores the contents.
    A QLabel normally reports hints based on whatever pixmap it holds,
    and this one replaces its pixmap on every resize - so the layout
    asked the label how big it wanted to be, the answer changed, the
    layout resized it, and round again. In a splitter that feedback is
    visible as the divider jumping about under the hand once an image is
    on screen, and it got worse the larger the picture was.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("preview")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(320, 180)
        # Ignored rather than Expanding: it still takes all the room
        # going, but the pixmap inside it never gets a say in how much
        # that is.
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._source = None
        self._path = None
        self.setText("Nothing on the overlay yet")

    def set_image(self, path):
        if not path:
            return
        path = Path(path)
        if self._path and Path(self._path) == path:
            return
        pm = QPixmap(str(path))
        if pm.isNull():
            return
        self._source = pm
        self._path = str(path)
        self._redraw()

    def clear_image(self):
        self._source = None
        self._path = None
        self.setPixmap(QPixmap())
        self.setText("Nothing on the overlay yet")

    def _redraw(self):
        if self._source is None:
            return
        target = self.size() * self.devicePixelRatio()
        scaled = self._source.scaled(
            target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        scaled.setDevicePixelRatio(self.devicePixelRatio())
        self.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._redraw()

    def sizeHint(self):
        return QSize(720, 405)

    def minimumSizeHint(self):
        """
        A fixed floor, whatever is being shown.

        Inherited from QLabel this tracks the pixmap, which is how a
        1920-wide image ended up demanding 927px of a panel that was
        happy with 320 a moment earlier.
        """
        return QSize(320, 180)


class LevelMeter(QWidget):
    """
    A live audio level bar.

    Without this, a muted output and a silent room look identical - the
    app just sits there saying "Recording" either way. The gate threshold
    is drawn as a notch so it is obvious whether what is coming in will
    actually clear it.

    The bar rises instantly and falls slowly, the way audio meters
    normally behave: a peak that vanished in 50ms would never be seen.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(6)
        self.setMinimumWidth(60)
        self._level = 0.0        # 0..1
        self._peak = 0.0
        self._gate = 0.0
        self._active = False
        self._decay = QTimer(self)
        self._decay.timeout.connect(self._fall)

    def set_gate(self, rms_threshold, ceiling=6000.0):
        self._gate = max(0.0, min(1.0, rms_threshold / ceiling))
        self.update()

    def set_level(self, rms, ceiling=6000.0):
        value = max(0.0, min(1.0, rms / ceiling))
        self._level = max(self._level, value)
        self._peak = max(self._peak, value)
        self._active = True
        if not self._decay.isActive():
            self._decay.start(40)
        self.update()

    def stop(self):
        self._active = False
        self._level = 0.0
        self._peak = 0.0
        self._decay.stop()
        self.update()

    def _fall(self):
        self._level *= 0.82
        self._peak *= 0.96
        if self._level < 0.005:
            self._level = 0.0
            self._decay.stop()
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.EDGE))
        p.drawRoundedRect(QRectF(0, 0, w, h), r, r)

        if self._level > 0:
            # Amber below the gate, green above it: colour says whether
            # this clip will be used, not just that sound is present.
            over = self._level >= self._gate
            colour = QColor(theme.OK if over else theme.WORKING)
            p.setBrush(colour)
            p.drawRoundedRect(QRectF(0, 0, max(h, w * self._level), h), r, r)

        if self._gate > 0:
            x = w * self._gate
            p.setPen(QColor(theme.TEXT))
            p.setOpacity(0.5)
            p.drawLine(int(x), 0, int(x), h)
        p.end()

class HoverCaption(QLabel):
    """
    A thumbnail that reveals the prompt behind it on hover.

    The tint is what makes the text legible: generated images are busy and
    unpredictable, so light text alone would vanish against a pale one.
    Darkening first means the caption reads over anything.

    Painting rather than a tooltip, because a tooltip appears somewhere
    else on screen after a delay, and the point here is to connect the
    words to the picture you are looking at.
    """

    cog_clicked = Signal()
    expand_clicked = Signal()

    def __init__(self, size, parent=None):
        super().__init__(parent)
        self.setObjectName("preview")
        self.setFixedSize(size)
        self.setAlignment(Qt.AlignCenter)
        self.setMouseTracking(True)
        self._caption = ""
        self._detail = ""
        self._hover = False
        self._fade = 0.0
        self._favourite = False
        self._menu_open = False
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._step)

        # The cog lives in the corner of the image and appears with the
        # caption, so the options belong to the image being looked at.
        self.cog = QToolButton(self)
        self.cog.setObjectName("cogButton")
        self.cog.setText("\u2699")
        self.cog.setCursor(Qt.PointingHandCursor)
        self.cog.setToolTip("More options for this image")
        self.cog.setFixedSize(24, 24)
        self.cog.clicked.connect(self.cog_clicked.emit)

        # Beside the cog: the two hover controls are a pair, one for
        # changing the image and one for looking at it.
        self.expand = QToolButton(self)
        self.expand.setObjectName("cogButton")
        self.expand.setText("\u2921")
        self.expand.setCursor(Qt.PointingHandCursor)
        self.expand.setToolTip("Expand this image")
        self.expand.hide()
        self.expand.clicked.connect(self.expand_clicked.emit)
        self.cog.hide()
        self.cog.move(size.width() - 30, size.height() - 30)
        self.expand.setFixedSize(24, 24)
        self.expand.move(size.width() - 58, size.height() - 30)

    def set_caption(self, text, detail=""):
        self._caption = (text or "").strip()
        self._detail = (detail or "").strip()

    def set_favourite(self, value):
        """A favourite is outlined all the time, not only on hover."""
        self._favourite = bool(value)
        self.update()

    def set_menu_open(self, value):
        """
        Hold the reveal open while the menu is showing.

        Opening a menu moves the pointer off the thumbnail, which would
        otherwise fade the caption and the cog out from under it.
        """
        self._menu_open = bool(value)
        if not value and not self._under_pointer():
            self._hover = False
            self._anim.start(16)
        self._sync_cog()

    def _under_pointer(self):
        return self.rect().contains(self.mapFromGlobal(QCursor.pos()))

    def _sync_cog(self):
        showing = bool(self._hover or self._menu_open)
        self.cog.setVisible(showing)
        self.expand.setVisible(showing)
        if showing:
            self.cog.raise_()
            self.expand.raise_()

    def enterEvent(self, event):
        super().enterEvent(event)
        if self._caption:
            self._hover = True
            self._anim.start(16)
        self._sync_cog()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        # Moving onto the cog counts as still being on the thumbnail: the
        # cog is a child widget, so Qt reports a leave for the parent.
        if self._menu_open or self._under_pointer():
            return
        if self.expand.underMouse():
            return
        self._hover = False
        self._anim.start(16)
        self._sync_cog()

    def _step(self):
        # A short fade rather than a hard switch: moving the mouse across
        # a grid of these would otherwise flash.
        target = 1.0 if self._hover else 0.0
        self._fade += (target - self._fade) * 0.35
        if abs(target - self._fade) < 0.02:
            self._fade = target
            self._anim.stop()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        if self._favourite:
            # Drawn regardless of hover: the point of a favourite is that
            # you can see which ones they are while scanning the grid.
            pen = QPen(QColor(theme.FAVOURITE))
            pen.setWidth(3)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(self.rect().adjusted(1, 1, -2, -2))

        if self._fade <= 0.01 or not self._caption:
            p.end()
            return

        rect = self.rect()

        tint = QColor(theme.BG)
        # Heavy enough that light text reads over a pale image, light
        # enough that you can still tell which image you are reading
        # about - that association is the whole point.
        tint.setAlpha(int(198 * self._fade))
        p.fillRect(rect, tint)

        inner = rect.adjusted(9, 8, -9, -8)
        p.setOpacity(self._fade)

        font = QFont(self.font())
        font.setPointSizeF(max(7.5, font.pointSizeF() - 0.5))
        p.setFont(font)
        metrics = QFontMetrics(font)

        if self._detail:
            detail_h = metrics.height() + 2
            p.setPen(QColor(theme.MUTED))
            p.drawText(
                QRectF(inner.left(), inner.bottom() - detail_h,
                       inner.width(), detail_h),
                Qt.AlignLeft | Qt.AlignBottom, self._detail)
            inner = inner.adjusted(0, 0, 0, -detail_h - 2)

        p.setPen(QColor(theme.TEXT))
        # Elided at the end rather than scrolled: the first words are the
        # ones that identify the image.
        text = self._elide(self._caption, metrics, inner)
        p.drawText(QRectF(inner), Qt.AlignLeft | Qt.AlignTop
                   | Qt.TextWordWrap, text)
        p.end()

    @staticmethod
    def _elide(text, metrics, rect):
        """Trim to what fits, ending on a word."""
        lines = max(1, rect.height() // max(1, metrics.height()))
        budget = int(lines * rect.width() * 0.92)
        if metrics.horizontalAdvance(text) <= budget:
            return text
        words = text.split()
        out = []
        used = 0
        space = metrics.horizontalAdvance(" ")
        for word in words:
            w = metrics.horizontalAdvance(word) + space
            if used + w > budget - metrics.horizontalAdvance("...."):
                break
            out.append(word)
            used += w
        return " ".join(out) + ("..." if out else text[:40] + "...")


class CollapsibleBox(QWidget):
    """
    A titled section that can be folded away.

    The header keeps showing how many items are inside while collapsed,
    so folding it does not hide whether there is anything in there - which
    would just mean opening it again to check.
    """

    toggled = Signal(bool)

    def __init__(self, title, expanded=True, parent=None):
        super().__init__(parent)
        self._title = title

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self.header = QToolButton()
        self.header.setObjectName("collapseHeader")
        self.header.setCheckable(True)
        self.header.setChecked(expanded)
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.header.setArrowType(Qt.DownArrow if expanded
                                 else Qt.RightArrow)
        self.header.clicked.connect(self._flip)
        outer.addWidget(self.header)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(4)
        outer.addWidget(self.body)

        self._count = 0
        self._refresh_title()
        self.body.setVisible(expanded)

    def add_widget(self, widget):
        self.body_layout.addWidget(widget)

    def set_count(self, count):
        self._count = int(count)
        self._refresh_title()

    def _refresh_title(self):
        suffix = f"  ({self._count})" if self._count else ""
        self.header.setText(f"{self._title}{suffix}")

    def _flip(self):
        expanded = self.header.isChecked()
        self.header.setArrowType(Qt.DownArrow if expanded
                                 else Qt.RightArrow)
        self.body.setVisible(expanded)
        self.toggled.emit(expanded)

    def is_expanded(self):
        return self.header.isChecked()

    def set_expanded(self, value):
        self.header.setChecked(bool(value))
        self._flip()


class TriStateFilter(QCheckBox):
    """
    A filter toggle with three states, driven by which button is clicked.

    Neutral means "do not care". Left click moves towards including,
    right click towards excluding, and clicking the button that put it in
    its current state returns it to neutral:

        neutral  --left-->  include   --left-->   neutral
        neutral  --right--> exclude   --right-->  neutral
        include  --right--> exclude
        exclude  --left-->  include

    A plain checkbox can only say "only these"; the third state is what
    lets it also say "anything but these", which otherwise needs a second
    control for the same idea.
    """

    NEUTRAL = "neutral"
    INCLUDE = "include"
    EXCLUDE = "exclude"

    state_changed = Signal(str)

    def __init__(self, label, noun="favourites", parent=None):
        super().__init__(label, parent)
        self._noun = noun
        self._state = self.NEUTRAL
        # Clicks are handled here, so Qt's own two-state toggling is not
        # wanted - it would fight with the third state.
        self.setTristate(False)
        self.setFocusPolicy(Qt.StrongFocus)
        self._apply()

    def state(self):
        return self._state

    def set_state(self, value):
        if value not in (self.NEUTRAL, self.INCLUDE, self.EXCLUDE):
            return
        if value == self._state:
            return
        self._state = value
        self._apply()
        self.state_changed.emit(value)

    def _apply(self):
        """Push the state into the stylesheet and the tooltip."""
        self.setProperty("filterState", self._state)
        # A dynamic property does not restyle on its own.
        self.style().unpolish(self)
        self.style().polish(self)

        super().setChecked(self._state == self.INCLUDE)
        noun = self._noun
        if self._state == self.INCLUDE:
            tip = (f"Showing only {noun}.\n"
                   f"Left click to stop filtering.\n"
                   f"Right click to hide {noun} instead.")
        elif self._state == self.EXCLUDE:
            tip = (f"Hiding {noun}.\n"
                   f"Right click to stop filtering.\n"
                   f"Left click to show only {noun} instead.")
        else:
            tip = (f"Not filtering by {noun}.\n"
                   f"Left click to show only {noun}.\n"
                   f"Right click to hide {noun}.")
        self.setToolTip(tip)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.set_state(self.NEUTRAL if self._state == self.INCLUDE
                           else self.INCLUDE)
            event.accept()
            return
        if event.button() == Qt.RightButton:
            self.set_state(self.NEUTRAL if self._state == self.EXCLUDE
                           else self.EXCLUDE)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # Swallowed so the base class cannot toggle on release as well.
        event.accept()

    def keyPressEvent(self, event):
        # Space matches a left click, for anyone working without a mouse.
        if event.key() in (Qt.Key_Space, Qt.Key_Select):
            self.set_state(self.NEUTRAL if self._state == self.INCLUDE
                           else self.INCLUDE)
            event.accept()
            return
        super().keyPressEvent(event)
