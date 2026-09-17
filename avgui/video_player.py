"""
Playing a clip inside the app.

Built with the controls a person expects of any video - play and pause,
a bar that can be dragged to move about, a mute and a volume. The clips
this app makes are silent, because nothing that generates sound fits a
12GB card, but the sound controls are here rather than left out: they
cost little, and a player without them is the wrong shape if an audio
pass is ever added.
"""

from PySide6.QtCore import Qt, QUrl, Signal

# Imported here rather than inside the function that needs it. The
# packager follows imports it can see, and a function-level import left
# QtMultimediaWidgets out of the build entirely - video worked from
# source and failed once packaged, which is the worst way round.
try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget

    MULTIMEDIA = True
except ImportError:          # pragma: no cover - depends on the build
    QAudioOutput = QMediaPlayer = QVideoWidget = None
    MULTIMEDIA = False

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSlider, QVBoxLayout,
    QWidget,
)


def _clock(milliseconds):
    """Milliseconds as m:ss, which is how people read a short clip."""
    seconds = max(0, int(milliseconds // 1000))
    return f"{seconds // 60}:{seconds % 60:02d}"


class VideoPlayer(QWidget):
    """A clip with transport controls."""

    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("videoPlayer")
        self._ready = False
        self._scrubbing = False
        self._player = None
        self._audio = None
        self._surface = None

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)

        self._stage = QWidget()
        self._stage.setObjectName("videoStage")
        self._stage.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        stage_layout = QVBoxLayout(self._stage)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        self._message = QLabel("")
        self._message.setAlignment(Qt.AlignCenter)
        self._message.setObjectName("fieldLabel")
        stage_layout.addWidget(self._message)
        column.addWidget(self._stage, 1)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.play_btn = QPushButton("Pause")
        self.play_btn.setFixedWidth(74)
        self.play_btn.clicked.connect(self.toggle)
        row.addWidget(self.play_btn)

        self.elapsed = QLabel("0:00")
        self.elapsed.setObjectName("fieldLabel")
        row.addWidget(self.elapsed)

        self.bar = QSlider(Qt.Horizontal)
        self.bar.setRange(0, 0)
        # Pressing anywhere on the groove jumps there. Qt's default is
        # to step by a page, which on a two-second clip does nothing
        # anybody wants.
        self.bar.sliderPressed.connect(self._grab)
        self.bar.sliderReleased.connect(self._release)
        self.bar.sliderMoved.connect(self._scrub)
        row.addWidget(self.bar, 1)

        self.total = QLabel("0:00")
        self.total.setObjectName("fieldLabel")
        row.addWidget(self.total)

        self.mute_btn = QPushButton("Mute")
        self.mute_btn.setFixedWidth(64)
        self.mute_btn.clicked.connect(self.toggle_mute)
        row.addWidget(self.mute_btn)

        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(80)
        self.volume.setFixedWidth(90)
        self.volume.valueChanged.connect(self._set_volume)
        row.addWidget(self.volume)

        column.addLayout(row)
        self._build_player()

    # ---- setting up ------------------------------------------------------

    def _build_player(self):
        """
        Qt Multimedia, if it is there.

        Absent, the player says so and everything else in the gallery
        carries on working - the same rule the theme sounds follow.
        """
        if not MULTIMEDIA:
            self._message.setText(
                "Video playback is unavailable in this build.")
            for widget in (self.play_btn, self.bar, self.mute_btn,
                           self.volume):
                widget.setEnabled(False)
            return

        self._surface = QVideoWidget()
        self._surface.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._stage.layout().addWidget(self._surface)
        self._message.hide()

        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._audio.setVolume(0.8)
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._surface)

        self._player.positionChanged.connect(self._moved)
        self._player.durationChanged.connect(self._lasts)
        self._player.playbackStateChanged.connect(self._state_changed)
        self._player.errorOccurred.connect(self._trouble)
        self._ready = True

    # ---- what it is showing ---------------------------------------------

    def play_file(self, path):
        """Start a clip. Loops, because these are two seconds long."""
        if not self._ready:
            return False
        self._player.setLoops(QMediaPlayer.Infinite)
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._player.play()
        return True

    def stop(self):
        """
        Stop and let go of the file.

        Letting go matters: Windows keeps a handle on a file being
        played, and deleting a clip from the gallery while the player
        still holds it fails with a permission error that looks like
        the app being broken.
        """
        if not self._ready:
            return
        self._player.stop()
        self._player.setSource(QUrl())

    # ---- transport -------------------------------------------------------

    def toggle(self):
        if not self._ready:
            return
        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def toggle_mute(self):
        if not self._ready:
            return
        self._audio.setMuted(not self._audio.isMuted())
        self.mute_btn.setText("Unmute" if self._audio.isMuted() else "Mute")

    def _set_volume(self, value):
        if self._ready:
            self._audio.setVolume(value / 100)
            if value and self._audio.isMuted():
                # Reaching for the volume means wanting to hear it.
                self._audio.setMuted(False)
                self.mute_btn.setText("Mute")

    # ---- the bar ---------------------------------------------------------

    def _grab(self):
        self._scrubbing = True

    def _release(self):
        self._scrubbing = False
        if self._ready:
            self._player.setPosition(self.bar.value())

    def _scrub(self, value):
        """
        Move while dragging, not only on release.

        On a clip this short, waiting for the release to see anything
        makes the bar feel broken.
        """
        if self._ready:
            self._player.setPosition(value)
            self.elapsed.setText(_clock(value))

    def _moved(self, position):
        if not self._scrubbing:
            self.bar.setValue(position)
        self.elapsed.setText(_clock(position))

    def _lasts(self, duration):
        self.bar.setRange(0, duration)
        self.total.setText(_clock(duration))

    def _state_changed(self, state):
        playing = state == QMediaPlayer.PlayingState
        self.play_btn.setText("Pause" if playing else "Play")

    def _trouble(self, _error, text):
        self._message.setText(text or "That clip could not be played.")
        self._message.show()
        self.failed.emit(text or "playback failed")
