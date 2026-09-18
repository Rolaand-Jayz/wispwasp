"""
The About page.

What somebody wants when they open this is usually one of four things:
which version am I on, what changed, something is broken and where do I
say so, and where did my files go. So it answers those four and stops -
a page of credits nobody asked for would bury them.
"""

import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout,
    QWidget,
)

from avcore.version import (
    AUTHOR, CHANGES, ISSUES_PAGE, RELEASES_PAGE, SOURCE_PAGE, __version__,
)


class UpdateLook(QThread):
    """The update check, off the interface thread as everywhere else."""

    answered = Signal(object)
    failed = Signal(str)

    def run(self):
        from avcore.updates import UpdateError, check

        try:
            self.answered.emit(check())
        except UpdateError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:                       # pragma: no cover
            self.failed.emit(f"The check failed: {exc}")


class AboutPanel(QWidget):
    """Version, what changed, and where to go when something is wrong."""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.s = engine.s
        self._worker = None
        self._build()

    # ---- building --------------------------------------------------------

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        self.form = QVBoxLayout(holder)
        self.form.setContentsMargins(24, 20, 24, 20)
        self.form.setSpacing(8)
        scroll.setWidget(holder)
        outer.addWidget(scroll)

        self._title_section()
        self._update_section()
        self._changes_section()
        self._folders_section()
        self._help_section()
        self.form.addStretch(1)

    def _heading(self, text):
        label = QLabel(text)
        label.setObjectName("sectionHeading")
        return label

    def _hint(self, text):
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        label.setWordWrap(True)
        return label

    def _title_section(self):
        name = QLabel("WispWasp")
        name.setObjectName("dialogTitle")
        self.form.addWidget(name)

        self.form.addWidget(self._hint(
            f"Version {__version__}   -   made by {AUTHOR}, with love."))
        self.form.addWidget(self._hint(
            "Listens to what your computer is playing and turns it into "
            "pictures on an overlay for OBS."))
        self.form.addSpacing(8)

    def _update_section(self):
        row = QHBoxLayout()
        row.setSpacing(10)

        self.update_note = QLabel(f"You are on {__version__}.")
        self.update_note.setObjectName("fieldLabel")
        self.update_note.setWordWrap(True)
        row.addWidget(self.update_note, 1)

        self.get_btn = QPushButton("Get it")
        self.get_btn.clicked.connect(
            lambda: webbrowser.open(RELEASES_PAGE))
        self.get_btn.hide()
        row.addWidget(self.get_btn)

        self.check_btn = QPushButton("Check for updates")
        self.check_btn.clicked.connect(self.check_updates)
        row.addWidget(self.check_btn)
        self.form.addLayout(row)
        self.form.addSpacing(10)

    def _changes_section(self):
        self.form.addWidget(self._heading(f"New in {__version__}"))
        for line in CHANGES:
            entry = QLabel(f"-   {line}")
            entry.setObjectName("fieldLabel")
            entry.setWordWrap(True)
            self.form.addWidget(entry)
        self.form.addSpacing(10)

    def _folders_section(self):
        """
        Where things are kept.

        The most common question after "is it broken" is "where did my
        pictures go", and the answer is a folder nobody would guess.
        """
        self.form.addWidget(self._heading("Where things are kept"))

        from avcore.config import DATA_DIR

        places = [
            ("Images", self.s.dir_for("paths.overlay_dir", "output")),
            ("Settings and profiles", Path(DATA_DIR)),
        ]
        try:
            from avcore.setup import checkpoints_dir

            places.append(("Models", checkpoints_dir(self.s)))

            from avcore.setup import loras_dir

            places.append(("LoRAs", loras_dir(self.s)))
        except Exception:
            pass

        for label, folder in places:
            row = QHBoxLayout()
            row.setSpacing(10)
            caption = QLabel(label)
            caption.setMinimumWidth(150)
            row.addWidget(caption)
            path = QLabel(str(folder))
            path.setObjectName("fieldLabel")
            path.setTextInteractionFlags(Qt.TextSelectableByMouse)
            row.addWidget(path, 1)
            open_btn = QPushButton("Open")
            open_btn.clicked.connect(
                lambda _c=False, where=folder: self._open(where))
            row.addWidget(open_btn)
            self.form.addLayout(row)

        self.form.addSpacing(10)

    def _help_section(self):
        self.form.addWidget(self._heading("Something wrong?"))
        self.form.addWidget(self._hint(
            "Bug reports are welcome, and the more ordinary the better - "
            "if something looked odd, that is worth saying. Mentioning "
            "the version above and what you were doing at the time "
            "usually makes it findable."))

        row = QHBoxLayout()
        row.setSpacing(10)
        report = QPushButton("Report a bug")
        report.setObjectName("primaryButton")
        report.clicked.connect(lambda: webbrowser.open(ISSUES_PAGE))
        row.addWidget(report)

        source = QPushButton("Source code")
        source.clicked.connect(lambda: webbrowser.open(SOURCE_PAGE))
        row.addWidget(source)

        releases = QPushButton("All releases")
        releases.setToolTip("Older versions, if you need to go back")
        releases.clicked.connect(lambda: webbrowser.open(RELEASES_PAGE))
        row.addWidget(releases)
        row.addStretch(1)
        self.form.addLayout(row)

        self.form.addSpacing(6)
        self.form.addWidget(self._hint(
            "Images are generated by ComfyUI on this machine, or by "
            "Pollinations online. Models come from Civitai and Hugging "
            "Face, each under its own licence."))

    # ---- doing things ----------------------------------------------------

    def _open(self, folder):
        """Show a folder, making it first if it is not there yet."""
        folder = Path(folder)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            webbrowser.open(folder.as_uri())
        except Exception as exc:
            self.update_note.setText(f"Could not open {folder}: {exc}")

    def check_updates(self):
        if self._worker is not None and self._worker.isRunning():
            return
        self.check_btn.setEnabled(False)
        self.update_note.setText("Checking...")

        self._worker = UpdateLook(self)
        self._worker.answered.connect(self._answered)
        self._worker.failed.connect(self._failed)
        self._worker.finished.connect(
            lambda: self.check_btn.setEnabled(True))
        self._worker.start()

    def _answered(self, found):
        from avcore.updates import describe

        self.update_note.setText(describe(found))
        self.get_btn.setVisible(bool(found))
        if found:
            self.get_btn.setText(f"Get {found['version']}")

    def _failed(self, message):
        self.update_note.setText(message)
        self.get_btn.hide()
