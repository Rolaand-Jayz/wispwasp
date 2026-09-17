"""
The version number, which does something if you poke it.

Kept apart from the theme sounds: those are opt-in and follow a theme,
while this is a joke attached to a particular label. It also has to
refuse to overlap with itself, which the theme effects do not.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel


class VersionLabel(QLabel):
    """
    Shows the version, and plays a clip when clicked.

    One at a time: the clip is twelve seconds of somebody shouting, and
    half a dozen overlapping copies is unpleasant rather than funny. A
    click while it is already playing does nothing at all - not queued,
    not restarted - because the joke is the surprise, and spamming it
    into a wall of noise spoils it.
    """

    clicked = Signal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._effect = None
        self._failed = False
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.play()
            self.clicked.emit()
        super().mousePressEvent(event)

    def is_playing(self):
        effect = self._effect
        if effect is None:
            return False
        try:
            return bool(effect.isPlaying())
        except RuntimeError:
            # The effect was destroyed under us; treat that as silence.
            self._effect = None
            return False

    def play(self):
        """
        Play the clip, unless it is already playing.

        Returns True when it actually started, so a test can tell the
        difference between "played" and "ignored because it was busy".
        """
        if self._failed or self.is_playing():
            return False

        if self._effect is None:
            self._effect = self._load()
            if self._effect is None:
                return False

        self._effect.play()
        return True

    def _load(self):
        """
        Build the player once, and never complain if it cannot be.

        Sound is a nicety here more than anywhere else in the app: a
        missing file or a missing QtMultimedia should cost a joke, not
        raise anything in front of somebody.
        """
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QSoundEffect

            from .assets import asset
        except ImportError:
            self._failed = True
            return None

        path = asset("well_do_it_live.wav")
        if path is None or not path.exists():
            self._failed = True
            return None

        effect = QSoundEffect(self)
        effect.setSource(QUrl.fromLocalFile(str(path)))
        effect.setVolume(0.7)
        return effect
