"""
The handful of settings people change most, kept within reach.

Lives in the side bar beside Live and Prompt, because changing the model
or the size is part of working, not part of configuring. Everything here
writes immediately: there is no Apply, and none of these needs one - the
next image simply uses the new value.

It is the same settings underneath, so this and the Settings page cannot
disagree; whichever one is changed, the other is told to re-read.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QSpinBox,
    QVBoxLayout, QWidget,
)

# Sizes worth offering. Anything else is still reachable in Settings -
# this is a shortcut, not a replacement.
SIZES = [
    ("512 x 512", 512, 512),
    ("768 x 768", 768, 768),
    ("1024 x 1024", 1024, 1024),
    ("1344 x 768", 1344, 768),
    ("1920 x 1080", 1920, 1080),
]


class QuickSettings(QWidget):
    """The few controls worth having beside the picture."""

    changed = Signal()

    def __init__(self, settings, engine=None, parent=None, compact=False):
        """
        `compact` lays the controls out in a row.

        The row goes above the prompt box, where the eye already is when
        deciding what to make. A column of the same controls in the side
        bar competed for width with everything else, particularly in the
        split layout.
        """
        super().__init__(parent)
        self.s = settings
        self.engine = engine
        self.compact = compact
        self._loading = False

        if compact:
            column = QHBoxLayout(self)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(6)
        else:
            column = QVBoxLayout(self)
            column.setContentsMargins(0, 6, 0, 0)
            column.setSpacing(4)
            # The side bar is narrow, and a spin box that runs past its
            # edge loses its arrows.
            self.setMaximumWidth(148)

        heading = QLabel("Quick settings")
        heading.setObjectName("sectionLabel")
        if not compact:
            column.addWidget(heading)

        self.backend = QComboBox()
        self.backend.addItem("ComfyUI (this PC)", "comfyui")
        self.backend.addItem("Pollinations (online)", "pollinations")
        self.backend.currentIndexChanged.connect(
            lambda _i: self._write("image.backend",
                                   self.backend.currentData()))
        self.backend.setMaximumWidth(140 if not compact else 170)
        column.addWidget(self.backend)

        self.model = QComboBox()
        self.model.setToolTip("Which checkpoint generates the image")
        self.model.currentIndexChanged.connect(
            lambda _i: self._write("comfyui.checkpoint",
                                   self.model.currentData() or ""))
        self.model.setMaximumWidth(140 if not compact else 190)
        column.addWidget(self.model)

        self.size = QComboBox()
        self.size.setToolTip("Size of the generated image")
        self.size.currentIndexChanged.connect(self._write_size)
        self.size.setMaximumWidth(140 if not compact else 130)
        column.addWidget(self.size)

        self.steps_label = QLabel("Steps")
        self.steps_label.setObjectName("sectionLabel")
        if not compact:
            column.addWidget(self.steps_label)
        self.steps = QSpinBox()
        self.steps.setRange(1, 100)
        self.steps.setToolTip("More steps, slower and usually cleaner")
        if compact:
            self.steps.setPrefix("Steps ")
        self.steps.valueChanged.connect(
            lambda v: self._write("comfyui.steps", v))
        self.steps.setMaximumWidth(140 if not compact else 112)
        column.addWidget(self.steps)

        self.cfg_label = QLabel("Guidance")
        self.cfg_label.setObjectName("sectionLabel")
        if not compact:
            column.addWidget(self.cfg_label)
        self.cfg = QDoubleSpinBox()
        self.cfg.setRange(0.0, 30.0)
        self.cfg.setSingleStep(0.5)
        self.cfg.setToolTip("How closely the image follows the prompt")
        if compact:
            self.cfg.setPrefix("Guidance ")
        self.cfg.valueChanged.connect(
            lambda v: self._write("comfyui.cfg", v))
        self.cfg.setMaximumWidth(140 if not compact else 136)
        column.addWidget(self.cfg)

        if compact:
            # A combo sizes itself to its longest entry, and a spin box
            # to its prefix plus its widest value. Left alone, this row
            # demanded 756px and helped hold the Live panel open - which
            # in the split layout is width the divider cannot give back.
            # Each control is told the least it can live with; the text
            # elides rather than the panel refusing to narrow.
            for box in (self.backend, self.model, self.size):
                box.setMinimumContentsLength(6)
                box.setSizeAdjustPolicy(
                    QComboBox.AdjustToMinimumContentsLengthWithIcon)
                box.setMinimumWidth(70)
            self.steps.setMinimumWidth(64)
            self.cfg.setMinimumWidth(70)

        self.note = QLabel("")
        self.note.setObjectName("sectionLabel")
        self.note.setWordWrap(not compact)
        column.addWidget(self.note)
        if compact:
            # Nothing stretches: the row sits above a prompt box that
            # should keep the width.
            column.addStretch(1)

        self.refresh()

    # ---- reading the settings -------------------------------------------

    def refresh(self):
        """
        Re-read everything from the settings.

        Called when this panel is shown and whenever the Settings page
        changes something, so the two can never drift apart.
        """
        self._loading = True
        try:
            backend = (self.s.get("image.backend", "comfyui")
                       or "comfyui")
            index = self.backend.findData(backend)
            self.backend.setCurrentIndex(index if index >= 0 else 0)

            self._fill_models()

            width = int(self.s.get("image.width", 1344) or 1344)
            height = int(self.s.get("image.height", 768) or 768)
            self._fill_sizes(width, height)

            self.steps.setValue(int(self.s.get("comfyui.steps", 20) or 20))
            self.cfg.setValue(float(self.s.get("comfyui.cfg", 7.0) or 7.0))
        finally:
            self._loading = False
        self._sync_visibility()

    def _fill_models(self):
        """
        The checkpoints ComfyUI can actually load.

        Read from disk rather than asked of ComfyUI: this runs whenever
        the panel is shown, and a request to a program that may not be
        running would block the window.
        """
        from avcore.models import installed
        from avcore.setup import checkpoints_dir

        current = (self.s.get("comfyui.checkpoint") or "").strip()
        self.model.clear()
        names = [path.name for path in installed(checkpoints_dir(self.s))]
        if names:
            self.model.addItem("First one found", "")
            for name in names:
                # The extension is noise in a list this narrow.
                label = name.rsplit(".", 1)[0]
                self.model.addItem(label, name)
        else:
            self.model.addItem("No models installed", "")

        index = self.model.findData(current)
        self.model.setCurrentIndex(index if index >= 0 else 0)
        self.model.setEnabled(bool(names))

    def _fill_sizes(self, width, height):
        self.size.clear()
        for label, w, h in SIZES:
            self.size.addItem(label, (w, h))
        # Whatever is set, even if it is not one of the offered sizes -
        # someone who chose 1152x896 in Settings should not have it
        # silently changed by opening this panel.
        if not any(w == width and h == height for _l, w, h in SIZES):
            self.size.insertItem(0, f"{width} x {height}", (width, height))
            self.size.setCurrentIndex(0)
            return
        for i in range(self.size.count()):
            if self.size.itemData(i) == (width, height):
                self.size.setCurrentIndex(i)
                return

    # ---- writing --------------------------------------------------------

    def _write(self, key, value):
        if self._loading:
            return
        self.s.set(key, value)
        self.s.save()
        self._sync_visibility()
        self._after_change(key)

    def _write_size(self, _index):
        if self._loading:
            return
        chosen = self.size.currentData()
        if not chosen:
            return
        width, height = chosen
        self.s.set("image.width", width)
        self.s.set("image.height", height)
        self.s.save()
        self._after_change("image.width")

    def _after_change(self, key):
        # The same follow-ups the Settings page runs, so a change made
        # here behaves identically to one made there.
        engine = self.engine
        if engine is not None and key == "image.backend":
            sync = getattr(engine, "_sync_backend", None)
            if sync:
                sync()
        self.changed.emit()

    def _sync_visibility(self):
        """
        Hide what the chosen backend cannot use.

        Pollinations takes a prompt and a size; steps, guidance and the
        checkpoint mean nothing there, and leaving them on screen invites
        fiddling with controls that do nothing.
        """
        local = (self.backend.currentData() or "comfyui") == "comfyui"
        hidden = [self.model, self.steps, self.cfg]
        if not self.compact:
            hidden += [self.steps_label, self.cfg_label]
        for widget in hidden:
            widget.setVisible(local)
        self.note.setText(
            "" if local else
            ("Online" if self.compact else
             "Pollinations makes the image online. Size still applies."))
