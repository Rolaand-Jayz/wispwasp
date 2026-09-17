"""
The panels. None of them store state: each redraws from the snapshot handed
to it by on_state(), so the window can tear them down and rebuild them in a
different layout without losing anything.
"""

from PySide6.QtCore import Qt, QRectF, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFontMetrics, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox,
    QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMenu, QPushButton, QSpinBox, QSplitter, QStyle,
    QStyledItemDelegate, QVBoxLayout, QWidget,
)

from . import theme
from .dialogs import ConfirmUnfavourite
from .quick_settings import QuickSettings
from .widgets import ImagePreview, LevelMeter, TallyLight

WORKING_MODES = ("recording", "transcribing", "generating", "loading")

# Looked up when a row is drawn rather than captured here: the palette
# can change while the app is running, and a dict built at import would
# keep handing out the old colours.
from .theme import kind_colour as KIND_COLOUR


def _swatch(colour):
    """A small colour dot, used to mark menu actions."""
    pm = QPixmap(10, 10)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(colour))
    p.setPen(Qt.NoPen)
    p.drawEllipse(1, 1, 8, 8)
    p.end()
    return QIcon(pm)


class KindBarDelegate(QStyledItemDelegate):
    """
    Draws a history row: colour bar, time, prompt, and the style dimmed.

    A bar rather than coloured text, because the transcripts are the thing
    being read and tinting them would make some entries harder to read for
    a reason unrelated to their content. The appended style is dimmed
    instead, since it is the same on every entry and is not what
    distinguishes one from another.

    Painted rather than left to Qt so the two-tone text is possible at
    all - a list item carries one colour.
    """

    BAR_WIDTH = 3
    GAP = 7

    def paint(self, painter, option, index):
        data = index.data(Qt.UserRole + 2) or {}
        colour = index.data(Qt.UserRole + 1)

        painter.save()
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor(theme.PANEL_HI))
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(option.rect, QColor(theme.PANEL_HI))

        r = option.rect
        if colour:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(colour))
            painter.drawRect(r.left() + 2, r.top() + 1,
                             self.BAR_WIDTH, r.height() - 2)

        metrics = QFontMetrics(option.font)
        x = r.left() + self.BAR_WIDTH + self.GAP
        top, height = r.top(), r.height()
        skipped = bool(data.get("skipped"))

        def draw(text, pen):
            nonlocal x
            if not text or x >= r.right():
                return
            painter.setPen(QColor(pen))
            width = min(metrics.horizontalAdvance(text), r.right() - x)
            painter.drawText(QRectF(x, top, width, height),
                             Qt.AlignVCenter | Qt.AlignLeft, text)
            x += width

        draw(data.get("at", "") + "   ", theme.MUTED)
        draw(data.get("base") or data.get("text") or "(silence)",
             theme.MUTED if skipped else theme.TEXT)
        suffix = data.get("suffix")
        if suffix and not skipped:
            draw(", " + suffix, theme.DISABLED)
        if skipped:
            draw(f"   - skipped, {data['skipped']}", theme.MUTED)
        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setWidth(size.width() + self.BAR_WIDTH + self.GAP)
        return size


def _backend_and_model(settings):
    """A short name for whatever is set to generate right now."""
    from avcore.catalog import model_label

    backend = (settings.get("image.backend", "comfyui") or "comfyui")
    if backend != "comfyui":
        return model_label(backend, "")

    chosen = (settings.get("comfyui.checkpoint") or "").strip()
    if chosen:
        return model_label(backend, chosen, short=True)

    # Nothing pinned: whichever ComfyUI picks first. Saying so beats
    # showing nothing, and beats pretending to know which one.
    return "first model found"


def _listen_summary(s):
    """
    Account for every listen that did not become an image.

    The gap between the two numbers mixes things that mean quite
    different things - audio too quiet to bother with is the app working
    as intended, a render that failed is not - so the reasons are listed
    rather than left to be guessed at.
    """
    listens = s.get("cycles") or 0
    made = s.get("generated") or 0
    if not listens:
        return ""

    lines = [f"{listens} listens, {made} became images."]
    skips = s.get("skips") or {}
    failures = s.get("failures") or 0

    if skips:
        parts = ", ".join(
            f"{count} {reason}"
            for reason, count in sorted(skips.items(),
                                        key=lambda kv: -kv[1]))
        lines.append(f"Skipped: {parts}.")
    if failures:
        lines.append(
            f"Failed: {failures}. These are worth looking at - the "
            f"skips above are not.")

    accounted = sum(skips.values()) + failures
    leftover = listens - made - accounted
    if leftover > 0:
        lines.append(f"{leftover} unaccounted for.")

    stopped = s.get("cancelled") or 0
    if stopped:
        lines.append(
            f"{stopped} stopped by hand, which count as neither.")
    return "\n".join(lines)


class LivePanel(QWidget):
    """
    What's on air right now: status, the image, what was heard, and a prompt
    strip that stays reachable without leaving the view.
    """

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._history_key = None
        self._style_names = None
        self._style_current = None
        self._filling_styles = False
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- status bar ------------------------------------------------
        bar = QWidget()
        bar.setObjectName("statusBar")
        bar.setFixedHeight(46)
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 0, 12, 0)
        row.setSpacing(10)

        self.tally = TallyLight()
        self.status = QLabel("Not started")
        self.status.setObjectName("statusText")
        self.meter = LevelMeter()
        self.meter.setFixedWidth(84)
        self.meter.setToolTip(
            "Live input level. The notch is the silence threshold - "
            "anything below it is discarded.")
        self.detail = QLabel("")
        self.detail.setObjectName("statusDetail")

        self.capture_btn = QPushButton("Capture")
        self.capture_btn.setToolTip(
            "Record straight away instead of waiting for the next cycle")
        self.capture_btn.clicked.connect(self.engine.capture_now)

        self.repeat_btn = QPushButton("Repeat")
        self.repeat_btn.setToolTip("Generate the last prompt again")
        self.repeat_btn.clicked.connect(self.engine.repeat_last)
        self.repeat_btn.setEnabled(False)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setToolTip(
            "Take the image off the overlay. The file is kept, and stays "
            "in the gallery.")
        self.clear_btn.clicked.connect(self.engine.clear_overlay)
        self.clear_btn.setEnabled(False)

        self.listen_btn = QPushButton("Start listening")
        self.listen_btn.setObjectName("primaryButton")
        self.listen_btn.clicked.connect(self._toggle_listen)
        self.stop_btn = QPushButton("Cancel")
        self.stop_btn.setToolTip("Abandon the clip or render in progress")
        self.stop_btn.clicked.connect(self.engine.cancel_current)
        self.stop_btn.setEnabled(False)

        row.addWidget(self.tally)
        row.addWidget(self.status)
        row.addWidget(self.meter)
        row.addStretch(1)
        row.addWidget(self.detail)
        row.addSpacing(8)
        row.addWidget(self.capture_btn)
        row.addWidget(self.repeat_btn)
        row.addWidget(self.clear_btn)
        row.addWidget(self.stop_btn)
        row.addWidget(self.listen_btn)
        outer.addWidget(bar)

        # --- image + caption feed --------------------------------------
        body = QVBoxLayout()
        body.setContentsMargins(14, 14, 14, 10)
        body.setSpacing(10)

        self.preview = ImagePreview()

        # A list rather than a single line. Seeing only the newest
        # transcript made it impossible to tell whether a bad image came
        # from a mishearing or from the prompt itself.
        self.heard = QListWidget()
        self.heard.setObjectName("feedList")
        self.heard.setMinimumHeight(52)
        self.heard.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.heard.setToolTip("Double-click an entry to generate it again")
        self.heard.itemDoubleClicked.connect(self._reuse_history)
        self.heard.setItemDelegate(KindBarDelegate(self.heard))
        self.heard.setContextMenuPolicy(Qt.CustomContextMenu)
        self.heard.customContextMenuRequested.connect(self._history_menu)

        # Draggable, because how much history is worth seeing depends on
        # what you are doing: two lines while watching the image, twenty
        # when working out why a prompt came out wrong.
        self.split = QSplitter(Qt.Vertical)
        self.split.setObjectName("liveSplit")
        self.split.setChildrenCollapsible(False)
        self.split.addWidget(self.preview)
        self.split.addWidget(self.heard)
        # The preview still takes most of the height, but the strip
        # above the prompt box grew by a row when the style and overlay
        # choices moved in, and the transcript list paid for it - it
        # came out below the two entries it is meant to show. A slightly
        # smaller share for the preview puts that back.
        self.split.setStretchFactor(0, 7)
        self.split.setStretchFactor(1, 2)
        self.split.splitterMoved.connect(self._remember_split)
        body.addWidget(self.split, 1)

        self.error = QLabel("")
        self.error.setObjectName("errorText")
        self.error.setWordWrap(True)
        self.error.hide()
        body.addWidget(self.error)

        outer.addLayout(body, 1)
        self._restore_split()

        # --- prompt strip ----------------------------------------------
        # The point of the hybrid layout: always visible, never a detour.
        strip = QWidget()
        strip.setObjectName("promptStrip")
        stack = QVBoxLayout(strip)
        stack.setContentsMargins(14, 8, 14, 10)
        stack.setSpacing(6)

        # Directly above the prompt box, which is where the eye already
        # is when deciding what to make. In the side bar these competed
        # for width with everything else, worst of all in the split
        # layout.
        self.quick = QuickSettings(self.engine.s, self.engine,
                                   compact=True)
        stack.addWidget(self.quick)

        # The same three decisions the Prompt page offers. Typing here
        # was otherwise a lesser version of typing there: no way to say
        # whether the saved style applies, which one, or whether the
        # result should go straight to the overlay.
        choices = QHBoxLayout()
        choices.setContentsMargins(0, 0, 0, 0)
        choices.setSpacing(12)

        self.use_suffix = QCheckBox("Apply the saved style")
        self.use_suffix.setChecked(True)
        choices.addWidget(self.use_suffix)

        # Beside the tick that decides whether a style applies, because
        # "whether" and "which" are one decision.
        self.style_pick = QComboBox()
        self.style_pick.setMinimumWidth(140)
        self.style_pick.setMaximumWidth(200)
        self.style_pick.setToolTip(
            "Which style is added to every prompt")
        self.style_pick.currentIndexChanged.connect(self._pick_style)
        choices.addWidget(self.style_pick)

        self.to_overlay = QCheckBox("Show on overlay")
        self.to_overlay.setChecked(
            bool(self.engine.s.get("image.manual_auto_push", True)))
        self.to_overlay.toggled.connect(
            lambda on: self._save_auto_push(on))
        choices.addWidget(self.to_overlay)
        choices.addStretch(1)
        stack.addLayout(choices)

        srow = QHBoxLayout()
        srow.setContentsMargins(0, 0, 0, 0)
        srow.setSpacing(8)

        self.prompt_box = QLineEdit()
        self.prompt_box.setPlaceholderText(
            "Type a prompt to take over the overlay")
        self.prompt_box.returnPressed.connect(self._fire_prompt)

        self.amount = QSpinBox()
        self.amount.setRange(1, 50)
        self.amount.setValue(1)
        self.amount.setFixedWidth(72)
        self.amount.setToolTip("How many images to render from this prompt")

        self.make_btn = QPushButton("Generate")
        self.make_btn.clicked.connect(self._fire_prompt)

        self.push_btn = QPushButton("Push to overlay")
        self.push_btn.clicked.connect(self.engine.push_pending)
        self.push_btn.hide()

        srow.addWidget(self.prompt_box, 1)
        srow.addWidget(self.amount)
        srow.addWidget(self.make_btn)
        srow.addWidget(self.push_btn)
        stack.addLayout(srow)
        self.strip = strip
        outer.addWidget(strip)

    def set_strip_visible(self, visible):
        """
        Hybrid keeps the strip; the other layouts give prompting its own
        space and hide it. Hiding rather than destroying means the widgets
        survive a layout switch untouched.
        """
        self.strip.setVisible(visible)

    # ---- actions ------------------------------------------------------

    def _toggle_listen(self):
        self.engine.toggle_listening()

    def _fire_prompt(self):
        text = self.prompt_box.text().strip()
        if not text:
            return

        # Built the same way the Prompt page builds it, so the same
        # typing gives the same picture wherever it was typed.
        base = text
        suffix = ""
        if self.use_suffix.isChecked():
            suffix = self.engine.s.get("image.style_suffix", "") or ""
            if suffix:
                text = f"{base}, {suffix}"

        if self.engine.queue_manual(
                text,
                amount=self.amount.value(),
                auto_push=self.to_overlay.isChecked(),
                base=base,
                suffix=suffix):
            self.prompt_box.clear()

    def _save_auto_push(self, on):
        """Remember the overlay choice, as the Prompt page does."""
        self.engine.s.set("image.manual_auto_push", bool(on))
        self.engine.s.save()

    def _pick_style(self, _index):
        """
        Choose which saved style is applied.

        The engine holds the choice and tells every other panel, so this
        picker and the one on the Prompt page are two views of one
        decision rather than two decisions.
        """
        if getattr(self, "_filling_styles", False):
            return
        name = self.style_pick.currentData()
        if name:
            self.engine.set_style(name)

    def _render_styles(self, styles, current):
        """
        Redraw the picker from the shared list.

        Rebuilt only when something differs: this runs on every state
        update, and refilling a combo would close it under the hand of
        anyone reading it.
        """
        # A style is a preset - a name and the text it adds - not just a
        # name. Compared on both, because editing a style changes what
        # every prompt gets without its name moving, and comparing names
        # alone would leave this showing the old suffix.
        key = [(preset["name"], preset["suffix"]) for preset in styles]
        if key == getattr(self, "_style_names", None) \
                and current == getattr(self, "_style_current", None):
            return
        self._style_names = list(key)
        self._style_current = current

        self._filling_styles = True
        try:
            self.style_pick.clear()
            for preset in styles:
                self.style_pick.addItem(preset["name"], preset["name"])
                self.style_pick.setItemData(
                    self.style_pick.count() - 1,
                    preset["suffix"] or "Nothing is added.",
                    Qt.ToolTipRole)
            index = self.style_pick.findData(current)
            self.style_pick.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self._filling_styles = False

        suffix = self.engine.s.get("image.style_suffix", "") or ""
        self.use_suffix.setToolTip(f"Adds: {suffix or '(none)'}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_status_bar()

    def _fit_status_bar(self):
        """
        Drop the least important things first as the panel narrows.

        The split layout gives this panel about 420px, which is not enough
        for a meter, three counters and four buttons. Without this the
        labels truncate to nonsense like "oture n" instead of anything
        reorganising itself.
        """
        w = self.width()
        self._listening_wide = w >= 620
        self.detail.setVisible(w >= 700)
        self.meter.setVisible(w >= 540)
        self.repeat_btn.setVisible(w >= 470)
        self.capture_btn.setVisible(w >= 400)
        # Clear survives narrower than the rest: it is the one that gets
        # reached for in a hurry, when something is on screen that should
        # not be.
        self.clear_btn.setVisible(w >= 330)
        # The primary button keeps its full wording only when there is room
        # for it; "Listen" and "Stop" are unambiguous next to the tally.
        listening = self.listen_btn.text().startswith("Stop")
        self._set_listen_text(listening)

    def _model_label(self):
        engine = getattr(self, "engine", None)
        settings = getattr(engine, "s", None)
        if settings is None:
            return ""
        return _backend_and_model(settings)

    def _set_listen_text(self, listening):
        if getattr(self, "_listening_wide", True):
            self.listen_btn.setText(
                "Stop listening" if listening else "Start listening")
        else:
            self.listen_btn.setText("Stop" if listening else "Listen")

    def _remember_split(self, *_args):
        """Store where the divider was left, as a preference."""
        sizes = self.split.sizes()
        if sum(sizes) <= 0:
            return
        self.engine.s.set("ui.live_split", list(sizes))
        self.engine.s.save()

    def _restore_split(self):
        """
        Put the divider back where it was left, or pick a sensible start.

        Applied after Qt has laid the splitter out. Setting sizes while it
        is still zero-height normalises them against no space and silently
        discards them - the same trap the layout splitter fell into.

        Without an explicit default the preview's size hint wins and the
        history collapses to its minimum, which would be less than the
        fixed height this replaced.
        """
        saved = self.engine.s.get("ui.live_split")
        valid = isinstance(saved, list) and len(saved) == 2

        def apply_sizes():
            try:
                total = self.split.height()
                if total <= 0:
                    return
                if valid:
                    self.split.setSizes([int(v) for v in saved])
                else:
                    history = max(96, int(total * 0.22))
                    self.split.setSizes([total - history, history])
            except (RuntimeError, TypeError, ValueError):
                pass

        QTimer.singleShot(0, apply_sizes)

    def _history_menu(self, point):
        """
        Right-click options for a history entry.

        Only offered on entries that produced a prompt - a skipped one has
        nothing to copy or keep, and a menu full of dead options is worse
        than no menu.
        """
        item = self.heard.itemAt(point)
        if item is None:
            return
        data = item.data(Qt.UserRole + 2) or {}
        if data.get("skipped") or not data.get("base"):
            return

        base = data["base"]
        # The style it was made with, falling back to whatever is set now,
        # so "with style" always means something.
        suffix = data.get("suffix") or self.engine.s.get(
            "image.style_suffix", "")
        styled = f"{base}, {suffix}" if suffix else base

        menu = QMenu(self)
        menu.addAction("Copy prompt",
                       lambda: self._copy(base))
        with_style = menu.addAction("Copy prompt with style",
                                    lambda: self._copy(styled))
        with_style.setEnabled(bool(suffix))

        menu.addSeparator()
        self._add_favourite_action(menu, "prompt", base)
        if suffix:
            self._add_favourite_action(menu, "prompt with style", styled)

        menu.exec(self.heard.mapToGlobal(point))

    def _add_favourite_action(self, menu, label, prompt):
        """One favourite entry, which toggles and says which way it goes."""
        kept = self.engine.is_favourite_prompt(prompt)
        action = QAction(
            f"{'Unfavourite' if kept else 'Favourite'} {label}", menu)
        # Blue, matching the favourite outline in the gallery, so the
        # colour means the same thing in both places.
        action.setIcon(_swatch(theme.FAVOURITE))
        action.triggered.connect(lambda: self._toggle_prompt(prompt))
        menu.addAction(action)

    def _copy(self, text):
        QApplication.clipboard().setText(text)

    def _toggle_prompt(self, prompt):
        if not self.engine.is_favourite_prompt(prompt):
            self.engine.favourite_prompt(prompt)
            return
        # Removing is the destructive direction, so it is confirmed the
        # same way deleting an image is.
        if ConfirmUnfavourite(prompt, self).exec() == QDialog.Accepted:
            self.engine.unfavourite_prompt(prompt)

    def _reuse_history(self, item):
        """Double-clicking a past transcript renders it again."""
        prompt = item.data(Qt.UserRole)
        if prompt:
            self.engine.queue_manual(prompt)

    def on_level(self, rms):
        self.meter.set_level(rms)

    # ---- state --------------------------------------------------------

    def on_state(self, s):
        mode = s.get("mode", "idle")
        listening = s.get("listening", False)

        if mode in WORKING_MODES:
            self.tally.set_state("working")
        elif listening:
            self.tally.set_state("live")
        else:
            self.tally.set_state("idle")

        if mode != "recording":
            self.meter.stop()
        self.meter.set_gate(float(self.engine.s.get("audio.silence_rms", 250)))

        status = s.get("status") or "Idle"
        # The countdown lives in the status line rather than as another
        # widget: it answers "is it broken or just waiting", which is the
        # same question the status text answers.
        left = s.get("next_in")
        if left is not None and listening and mode == "idle":
            status = f"Next capture in {left}s"
        self.status.setText(status)

        self._set_listen_text(listening)
        self.stop_btn.setEnabled(bool(s.get("busy")))
        self.repeat_btn.setEnabled(bool(s.get("can_repeat")))
        self.capture_btn.setEnabled(not s.get("busy"))
        self.clear_btn.setEnabled(bool(s.get("image")))

        bits = []
        if s.get("queued"):
            bits.append(f"{s['queued']} queued")
        # What is actually making the pictures. It is in the side bar
        # too, but this is the line people watch while working, and
        # "why does this look different" is usually answered by the
        # model having changed.
        making = self._model_label()
        if making:
            bits.append(making)

        self._render_styles(s.get("styles") or [],
                            s.get("style_name") or "")

        listens = s.get("cycles") or 0
        made = s.get("generated") or 0
        if listens:
            # "Cycles" only meant something to whoever designed it, and
            # the bare pair of numbers never said why they differed.
            bits.append(f"{made} images from {listens} listens")
        elif made:
            bits.append(f"{made} images")
        self.detail.setText("   ".join(bits))
        self.detail.setToolTip(_listen_summary(s))

        img = s.get("image")
        if img:
            self.preview.set_image(img)
        else:
            # The preview mirrors the overlay, so clearing one clears the
            # other. Showing a stale image here would be misleading about
            # what is on stream.
            self.preview.clear_image()

        self._render_history(s.get("history") or [])

        err = s.get("error") or ""
        self.error.setText(err)
        self.error.setVisible(bool(err))

        self.push_btn.setVisible(bool(s.get("pending_manual")))

    def _render_history(self, history):
        """
        Redraw the transcript list.

        Rebuilt only when the newest entry changes, since this runs on
        every state update and refilling a list widget several times a
        second would fight with the user's scrolling.
        """
        newest = history[0]["at"] + history[0]["text"][:20] if history else ""
        if newest == self._history_key:
            return
        self._history_key = newest

        self.heard.clear()
        if not history:
            item = QListWidgetItem("Waiting for audio")
            item.setForeground(QColor(theme.MUTED))
            self.heard.addItem(item)
            return

        for entry in history[:40]:
            # The delegate paints from the entry itself, so the text on
            # the item is only what a screen reader or a copy would get.
            base = entry.get("base") or entry.get("text") or "(silence)"
            suffix = entry.get("suffix") or ""
            label = f"{entry['at']}   {base}"
            if suffix and not entry.get("skipped"):
                label += f", {suffix}"
            if entry.get("skipped"):
                label += f"   - skipped, {entry['skipped']}"

            item = QListWidgetItem(label)
            kind = entry.get("kind") or (
                "skipped" if entry.get("skipped") else "heard")
            item.setData(Qt.UserRole + 1, KIND_COLOUR(kind))
            item.setData(Qt.UserRole + 2, entry)
            if entry.get("prompt"):
                item.setData(Qt.UserRole, entry["prompt"])
                item.setToolTip(entry["prompt"])
            self.heard.addItem(item)
