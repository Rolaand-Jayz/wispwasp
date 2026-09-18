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
    QSizePolicy,
    QPushButton,
    QCheckBox,
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
        self._has_cutout = False

        if compact:
            # Ignored horizontally, not merely minimum-zero. A layout
            # asks a widget with a layout of its own for its minimum
            # size hint and honours that, so setting the minimum to
            # zero changed nothing: the strip still reported the 631px
            # its children wanted and held the whole panel open at that
            # width - which meant it could never get narrow enough for
            # _fit to start hiding things. Ignored is the same trick the
            # image preview needed, for the same reason.
            self.setMinimumWidth(0)
            self.setSizePolicy(QSizePolicy.Ignored,
                               QSizePolicy.Preferred)
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
        # Shorter wording in the strip: the family picker moved in
        # beside it, and "ComfyUI (this PC)" was being cut off mid-word,
        # which is worse than saying less.
        if compact:
            self.backend.addItem("ComfyUI", "comfyui")
            self.backend.addItem("Online", "pollinations")
            self.backend.setToolTip(
                "ComfyUI runs on this PC; Online uses Pollinations")
        else:
            self.backend.addItem("ComfyUI (this PC)", "comfyui")
            self.backend.addItem("Pollinations (online)", "pollinations")
        self.backend.currentIndexChanged.connect(
            lambda _i: self._write("image.backend",
                                   self.backend.currentData()))
        self.backend.setMaximumWidth(140 if not compact else 104)
        column.addWidget(self.backend)

        # Which half of Stable Diffusion is in use. It decides what can
        # be listed below it, and what a LoRA has to be to work, so it
        # belongs in front of the model rather than buried in Setup.
        self.family = QComboBox()
        self.family.addItem("SD 1.5", "sd15")
        self.family.addItem("SDXL", "sdxl")
        self.family.setToolTip(
            "Which kind of model to use. The list below shows only "
            "the ones that match.")
        self.family.currentIndexChanged.connect(
            lambda _i: self._pick_family())
        column.addWidget(self.family)

        self.model = QComboBox()
        self.model.setToolTip("Which checkpoint generates the image")
        self.model.currentIndexChanged.connect(
            lambda _i: self._write("comfyui.checkpoint",
                                   self.model.currentData() or ""))
        self.family.setMaximumWidth(110 if not compact else 96)
        self.model.setMaximumWidth(140 if not compact else 175)
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

        # A per-picture decision, so it sits with the other per-picture
        # decisions rather than in Settings. Disabled until the model is
        # installed: a tick that does nothing is worse than one that is
        # not offered at all.
        # A button rather than a row of ticks: there can be any number
        # of LoRAs, and the strip cannot grow. The popup holds the same
        # controls as Settings, so switching one off mid-stream is one
        # click from where the pictures are being made.
        self.loras_btn = QPushButton("LoRAs")
        self.loras_btn.setMaximumWidth(140 if not compact else 110)
        self.loras_btn.clicked.connect(self._open_loras)
        column.addWidget(self.loras_btn)

        # First among the ticks, because it changes what the others do.
        # Always shown, whatever the backend: Pollinations can produce
        # the same things and is checked the same way.
        self.safe = QCheckBox("Safe mode")
        self.safe.setToolTip(
            "Steer away from explicit images, refuse prompts that ask "
            "for them, hide adult models, blur anything the check is "
            "unsure about, and keep flagged pictures off the overlay")
        self.safe.toggled.connect(
            lambda on: self._write("safety.safe_mode", bool(on)))
        column.addWidget(self.safe)

        self.cutout = QCheckBox("Cut out")
        self.cutout.setToolTip(
            "Remove the background, so the picture floats on your scene "
            "instead of covering it")
        self.cutout.toggled.connect(
            lambda on: self._write("image.cutout", bool(on)))
        column.addWidget(self.cutout)

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

            tier = self.s.get("models.tier") or "sd15"
            index = self.family.findData(tier)
            self.family.setCurrentIndex(index if index >= 0 else 0)

            self._fill_models()

            width = int(self.s.get("image.width", 1344) or 1344)
            height = int(self.s.get("image.height", 768) or 768)
            self._fill_sizes(width, height)

            from avgui.lora_chooser import active_count, on_disk

            installed_loras = len(on_disk(self.s))
            live = active_count(self.s)
            self.loras_btn.setEnabled(bool(installed_loras))
            self.loras_btn.setText(
                f"LoRAs ({live})" if live else "LoRAs")
            self.loras_btn.setToolTip(
                f"{live} of {installed_loras} applied"
                if installed_loras else
                "None installed yet - Settings has a LoRAs button")

            from avcore.setup import cutout_installed

            # Hidden rather than greyed out. An extra nobody has opted
            # into should not occupy space in the bar at all: a tick
            # that cannot be ticked is a question the app has no
            # business asking.
            self.safe.setChecked(bool(self.s.get("safety.safe_mode", False)))

            self._has_cutout = cutout_installed(self.s)
            self.cutout.setChecked(
                self._has_cutout and bool(self.s.get("image.cutout", False)))
            if not self._has_cutout and self.s.get("image.cutout"):
                # The model has been removed since it was switched on.
                # Left alone, every picture would keep asking for a
                # cut-out that silently does not happen.
                self.s.set("image.cutout", False)
                self.s.save()

            self.steps.setValue(int(self.s.get("comfyui.steps", 20) or 20))
            self.cfg.setValue(float(self.s.get("comfyui.cfg", 7.0) or 7.0))
        finally:
            self._loading = False
        self._sync_visibility()

    def _fill_models(self):
        """
        The checkpoints of the chosen family, read from disk.

        Filtered by what the weights say rather than by what the file is
        called: an SDXL model listed under SD 1.5 loads and then fails
        at the first step, and nobody renames their downloads to help.

        Read from disk rather than asked of ComfyUI: this runs whenever
        the panel is shown, and a request to a program that may not be
        running would block the window.
        """
        from avcore.setup import models_for_tier

        tier = self.s.get("models.tier") or "sd15"
        current = (self.s.get("comfyui.checkpoint") or "").strip()
        self.model.clear()
        names = [path.name for path in models_for_tier(tier, self.s)]
        if names:
            self.model.addItem(
                "First found" if self.compact else "First one found", "")
            for name in names:
                # The extension is noise in a list this narrow.
                label = name.rsplit(".", 1)[0]
                self.model.addItem(label, name)
        else:
            label = "SDXL" if (self.s.get("models.tier") == "sdxl") \
                else "SD 1.5"
            self.model.addItem(f"No {label} models installed", "")

        index = self.model.findData(current)
        self.model.setCurrentIndex(index if index >= 0 else 0)
        self.model.setEnabled(bool(names))

    def _pick_family(self):
        """
        Switch between SD 1.5 and SDXL.

        The chosen model is cleared when it belongs to the other family,
        rather than left pointing at something that cannot be loaded.
        Blank means "first one found", which is the right answer while
        somebody decides.
        """
        if self._loading:
            return
        tier = self.family.currentData() or "sd15"
        self.s.set("models.tier", tier)

        from avcore.setup import models_for_tier

        allowed = {path.name for path in models_for_tier(tier, self.s)}
        if (self.s.get("comfyui.checkpoint") or "") not in allowed:
            self.s.set("comfyui.checkpoint", "")
        self.s.save()

        self.refresh()
        self._after_change("models.tier")

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

    def _open_loras(self):
        """A small window of the same controls, beside the prompt box."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout

        from .lora_chooser import LoraChooser

        box = QDialog(self)
        box.setWindowTitle("LoRAs")
        box.setMinimumWidth(360)
        column = QVBoxLayout(box)
        column.setContentsMargins(16, 14, 16, 14)

        chooser = LoraChooser(self.s, compact=True)
        chooser.changed.connect(self.refresh)
        chooser.changed.connect(self.changed.emit)
        column.addWidget(chooser)

        # Finding out you have none, and being able to do something
        # about it, belong in the same window. Otherwise the popup's
        # only message to somebody with an empty folder is "go
        # elsewhere".
        row = QHBoxLayout()
        row.setSpacing(8)

        more = QPushButton("Get more")
        more.setToolTip("Browse and download LoRAs from Civitai")
        more.clicked.connect(lambda: self._get_loras(chooser))
        row.addWidget(more)
        row.addStretch(1)

        close = QPushButton("Done")
        close.setObjectName("confirmButton")
        close.clicked.connect(box.accept)
        row.addWidget(close)
        column.addLayout(row)

        box.exec()
        self.refresh()

    def _get_loras(self, chooser):
        """
        The same browser Settings opens, from here.

        The list behind it is rebuilt when the browser closes rather
        than while it is open: a LoRA that has just arrived should be
        tickable straight away, without closing the popup and opening
        it again.
        """
        from .model_browser import ModelBrowser

        ModelBrowser(self.s, kind="LORA", parent=self).exec()
        chooser.reload()
        self.refresh()

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.compact:
            self._fit(event.size().width())

    def _fit(self, width):
        """
        Drop controls, least useful first, when the strip is squeezed.

        The split layout gives each panel whatever is left after the
        other, and a strip that refuses to narrow holds its whole panel
        open - which is how the prompt side came out wider than the live
        side by default.

        Guidance goes first, then steps, then the size: all three are
        set once and rarely touched, while the backend and the model
        decide what every picture is.
        """
        local = (self.backend.currentData() or "comfyui") == "comfyui"

        # Two separate questions: whether the backend can use a control
        # at all, and whether there is room for it. Conflating them hid
        # the size box for Pollinations, which does use it.
        for widget, needed in ((self.cfg, 620), (self.steps, 520),
                               (self.model, 340)):
            widget.setVisible(local and width >= needed)
        self.family.setVisible(local and width >= 300)
        self.loras_btn.setVisible(local and width >= 250)
        self.size.setVisible(width >= 430)
        self.cutout.setVisible(
            local and getattr(self, "_has_cutout", False) and width >= 200)
        # Last to go: a safety control that vanishes when the window is
        # narrow is a safety control nobody can rely on.
        self.safe.setVisible(width >= 170)

    def _sync_visibility(self):
        """
        Hide what the chosen backend cannot use.

        Pollinations takes a prompt and a size; steps, guidance and the
        checkpoint mean nothing there, and leaving them on screen invites
        fiddling with controls that do nothing.
        """
        local = (self.backend.currentData() or "comfyui") == "comfyui"
        hidden = [self.family, self.model, self.steps, self.cfg,
                  self.loras_btn]
        if not self.compact:
            hidden += [self.steps_label, self.cfg_label]
        for widget in hidden:
            widget.setVisible(local)
        # Two conditions for the tick: the backend can use it, and the
        # model somebody opted into is actually installed.
        self.cutout.setVisible(local and getattr(self, "_has_cutout", False))
        if self.compact and local:
            # Re-apply the width rules, so switching backend cannot
            # bring back a control the strip has no room for.
            self._fit(self.width())
        self.note.setText(
            "" if local else
            ("Online" if self.compact else
             "Pollinations makes the image online. Size still applies."))
