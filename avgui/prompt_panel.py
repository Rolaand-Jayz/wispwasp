"""Prompt panel: the unhurried counterpart to the always-visible strip."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel,
    QListWidget,
    QListWidgetItem, QMenu, QPlainTextEdit, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)

from . import theme
from .dialogs import ConfirmUnfavourite
from .widgets import CollapsibleBox, ImagePreview


class PromptPanel(QWidget):
    """
    The unhurried version of the prompt strip: room to write, per-run
    overrides, and a history you can click to reuse.
    """

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        # Only caches of what was last drawn, so the lists are not rebuilt
        # on every state update. The prompts themselves live in the engine.
        self._typed_key = None
        self._fav_key = None
        # Caches of what the style picker last drew, plus a guard so
        # refilling it does not look like the user choosing.
        self._style_names = None
        self._style_current = None
        self._filling_styles = False
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(10)

        self.box = QPlainTextEdit()
        self.box.setPlaceholderText(
            "Describe the image you want, then press Ctrl+Enter")
        self.box.setMinimumHeight(110)
        outer.addWidget(self.box)

        # Ctrl+Enter fires; plain Enter makes a new line, because this box
        # is for writing something longer than the strip allows.
        fire = QShortcut(QKeySequence("Ctrl+Return"), self.box)
        fire.activated.connect(self._fire)

        # Two rows rather than one. A single row of controls sets a large
        # minimum width on the whole panel, which in the split layout stops
        # the splitter honouring any size you drag it to.
        controls = QHBoxLayout()
        controls.setSpacing(8)

        controls.addWidget(self._label("How many"))
        self.amount = QSpinBox()
        self.amount.setRange(1, 50)
        self.amount.setValue(int(self.engine.s.get("image.amount", 1)))
        self.amount.setFixedWidth(74)
        controls.addWidget(self.amount)
        controls.addStretch(1)

        self.clear_btn = QPushButton("Clear overlay")
        self.clear_btn.setToolTip(
            "Take the image off the overlay. The file is kept, and stays "
            "in the gallery.")
        self.clear_btn.clicked.connect(self.engine.clear_overlay)
        self.clear_btn.setEnabled(False)
        controls.addWidget(self.clear_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.engine.cancel_current)
        self.cancel_btn.setEnabled(False)
        controls.addWidget(self.cancel_btn)

        self.go_btn = QPushButton("Generate")
        self.go_btn.setObjectName("primaryButton")
        self.go_btn.clicked.connect(self._fire)
        controls.addWidget(self.go_btn)
        outer.addLayout(controls)

        toggles = QHBoxLayout()
        toggles.setSpacing(14)
        self.use_suffix = QCheckBox("Apply the saved style")
        self.use_suffix.setChecked(True)
        self.use_suffix.setToolTip(
            f"Adds: {self.engine.s.get('image.style_suffix') or '(none)'}")
        toggles.addWidget(self.use_suffix)

        # Right beside the tick that decides whether a style is applied,
        # because "whether" and "which" are the same decision and asking
        # them in two different places would be strange.
        self.style_pick = QComboBox()
        self.style_pick.setMinimumWidth(150)
        self.style_pick.setToolTip("Which style is added to every prompt")
        self.style_pick.currentIndexChanged.connect(self._pick_style)
        toggles.addWidget(self.style_pick)

        self.to_overlay = QCheckBox("Show on overlay")
        self.to_overlay.setChecked(
            bool(self.engine.s.get("image.manual_auto_push", True)))
        toggles.addWidget(self.to_overlay)
        toggles.addStretch(1)
        outer.addLayout(toggles)

        self.status = QLabel("")
        self.status.setObjectName("fieldLabel")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

        self.push_btn = QPushButton("Put the last image on the overlay")
        self.push_btn.clicked.connect(self.engine.push_pending)
        self.push_btn.hide()
        outer.addWidget(self.push_btn)

        # Favourites first: a kept prompt is one you meant to come back
        # to, whereas the recent list is just what happened to go through.
        self.fav_box = CollapsibleBox(
            "Favourite prompts",
            expanded=bool(self.engine.s.get("ui.favourites_open", True)))
        self.fav_box.toggled.connect(self._remember_fold)
        self.favourites = QListWidget()
        self.favourites.setObjectName("feedList")
        self.favourites.setMaximumHeight(140)
        # A long prompt should clip, not add a scrollbar that eats a whole
        # row out of an already short list.
        self.favourites.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.favourites.setTextElideMode(Qt.ElideRight)
        self.favourites.setToolTip(
            "Double-click to load it back in, right-click to remove it")
        self.favourites.itemDoubleClicked.connect(self._reuse)
        self.favourites.setContextMenuPolicy(Qt.CustomContextMenu)
        self.favourites.customContextMenuRequested.connect(self._fav_menu)
        self.fav_box.add_widget(self.favourites)
        outer.addWidget(self.fav_box)

        outer.addWidget(self._label("Earlier prompts"))
        self.history = QListWidget()
        self.history.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history.setTextElideMode(Qt.ElideRight)
        self.history.setToolTip("Double-click to load a prompt back in")
        self.history.itemDoubleClicked.connect(self._reuse)
        outer.addWidget(self.history, 1)

        self.preview = ImagePreview()
        self.preview.setMinimumHeight(160)
        outer.addWidget(self.preview, 1)

    def set_preview_visible(self, visible):
        """
        The split layout puts the live preview right next to this panel, so
        showing the same image twice there just wastes the width.
        """
        self.preview.setVisible(visible)

    @staticmethod
    def _label(text):
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl

    # ---- actions -------------------------------------------------------

    def _fire(self):
        text = self.box.toPlainText().strip()
        if not text:
            self.status.setText("Write a prompt first.")
            return

        base = text
        suffix = ""
        if self.use_suffix.isChecked():
            suffix = self.engine.s.get("image.style_suffix", "") or ""
            if suffix:
                text = f"{base}, {suffix}"

        ok = self.engine.queue_manual(
            text,
            amount=self.amount.value(),
            auto_push=self.to_overlay.isChecked(),
            base=base,
            suffix=suffix,
        )
        if not ok:
            self.status.setText("That prompt was empty after trimming.")
            return

        self.box.clear()
        self.status.setText("Queued.")

    def _remember_fold(self, expanded):
        """The fold state is a preference, so it outlives the session."""
        self.engine.s.set("ui.favourites_open", bool(expanded))
        self.engine.s.save()

    def _fav_menu(self, point):
        item = self.favourites.itemAt(point)
        if item is None:
            return
        prompt = item.text()
        menu = QMenu(self)
        menu.addAction("Copy prompt",
                       lambda: QApplication.clipboard().setText(prompt))
        menu.addAction("Use this prompt", lambda: self._load(prompt))
        menu.addSeparator()
        remove = QAction("Remove from favourites", menu)
        remove.triggered.connect(lambda: self._remove_favourite(prompt))
        menu.addAction(remove)
        menu.exec(self.favourites.mapToGlobal(point))

    def _remove_favourite(self, prompt):
        # Same confirmation as anywhere else something is given up.
        if ConfirmUnfavourite(prompt, self).exec() == QDialog.Accepted:
            self.engine.unfavourite_prompt(prompt)

    def _load(self, prompt):
        self.box.setPlainText(prompt)
        self.box.setFocus()

    def _reuse(self, item):
        self._load(item.text())

    # ---- state ---------------------------------------------------------

    def on_state(self, s):
        busy = bool(s.get("busy"))
        self.cancel_btn.setEnabled(busy)
        self.go_btn.setEnabled(not busy or s.get("queued", 0) < 5)

        parts = []
        if s.get("status"):
            parts.append(s["status"])
        if s.get("queued"):
            parts.append(f"{s['queued']} waiting")
        self.status.setText("   ".join(parts))

        if s.get("error"):
            self.status.setText(s["error"])

        self.push_btn.setVisible(bool(s.get("pending_manual")))
        self.clear_btn.setEnabled(bool(s.get("image")))
        self._render_typed(s.get("typed") or [])
        self._render_favourites(s.get("favourites") or [])
        self._render_styles(s.get("styles") or [], s.get("style_name") or "")

        shown = s.get("pending_manual") or s.get("image")
        if shown:
            self.preview.set_image(shown)
        else:
            self.preview.clear_image()

    def _render_typed(self, typed):
        """
        Redraw the list of prompts entered by hand.

        Driven by the engine rather than by what this panel happened to
        send: the prompt strip in the hybrid layout goes straight to the
        engine, and a list owned by this panel never saw those at all.
        """
        if typed == self._typed_key:
            return
        self._typed_key = list(typed)

        self.history.clear()
        for prompt in typed:
            self.history.addItem(prompt)

    def _render_favourites(self, favourites):
        """Redraw the kept prompts, and keep the header count honest."""
        if favourites == self._fav_key:
            return
        self._fav_key = list(favourites)

        self.favourites.clear()
        for prompt in favourites:
            self.favourites.addItem(prompt)
        self.fav_box.set_count(len(favourites))

        if not favourites:
            placeholder = QListWidgetItem(
                "Right-click a prompt in the history to keep it here")
            placeholder.setForeground(QColor(theme.MUTED))
            # Not selectable: it is a hint, not something to act on.
            placeholder.setFlags(Qt.NoItemFlags)
            self.favourites.addItem(placeholder)

    def _pick_style(self, _index):
        """Choose a style. The engine tells every other panel."""
        if self._filling_styles:
            return
        name = self.style_pick.currentData()
        if name:
            self.engine.set_style(name)

    def _render_styles(self, styles, current):
        """
        Redraw the picker from the shared list.

        Rebuilt only when something actually differs, because this runs on
        every state update and refilling a combo would close it under the
        user's cursor mid-choice.
        """
        # Compared on the text as well as the names: editing a style
        # changes what every prompt gets without its name moving, and a
        # name-only comparison would leave this showing the old suffix.
        key = [(p["name"], p["suffix"]) for p in styles]
        if key == self._style_names and current == self._style_current:
            return
        self._style_names = list(key)
        self._style_current = current

        self._filling_styles = True
        self.style_pick.clear()
        for preset in styles:
            label = preset["name"]
            self.style_pick.addItem(label, preset["name"])
            self.style_pick.setItemData(
                self.style_pick.count() - 1,
                preset["suffix"] or "Nothing is added.", Qt.ToolTipRole)
        index = self.style_pick.findData(current)
        self.style_pick.setCurrentIndex(index if index >= 0 else 0)
        self._filling_styles = False

        suffix = ""
        for preset in styles:
            if preset["name"] == current:
                suffix = preset["suffix"]
                break
        self.use_suffix.setToolTip(f"Adds: {suffix or '(none)'}")
