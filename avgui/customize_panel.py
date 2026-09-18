"""
Customize panel: the look of the interface.

Sits under Settings as a sub-page. Settings is about what the app does;
this is about how it appears, which is a different question and a
different frame of mind.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QFrame, QHBoxLayout,
    QLabel, QListWidget,
    QListWidgetItem, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from . import theme
from .dialogs import ConfirmUnfavourite, StyleEditor
from .themes import option_label, options_for, theme_names

# Starting points, so nobody has to open a colour wheel to get somewhere
# reasonable. Each pair is (main, accent).
PRESETS = [
    ("Wasp", "#E0392B", "#4C9BE8"),
    ("Cyan drift", "#2BB6C4", "#7C5CE0"),
    ("Violet", "#7C5CE0", "#E08A2B"),
    ("Ember", "#E0742B", "#4FB286"),
    ("Moss", "#4FB286", "#E0C04A"),
    ("Rose", "#D8456F", "#4C9BE8"),
]


class Swatch(QFrame):
    """A colour block that opens a picker when clicked."""

    picked = Signal(str)

    def __init__(self, colour, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 28)
        self.setCursor(Qt.PointingHandCursor)
        self.setFrameShape(QFrame.NoFrame)
        self._colour = colour
        self._paint()

    def colour(self):
        return self._colour

    def set_colour(self, colour):
        self._colour = colour
        self._paint()

    def _paint(self):
        self.setStyleSheet(
            f"background: {self._colour};"
            f"border: 1px solid {theme.EDGE}; border-radius: 3px;")
        self.setToolTip(f"{self._colour}  -  click to choose another")

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        chosen = QColorDialog.getColor(
            QColor(self._colour), self, "Choose a colour")
        if chosen.isValid():
            self.set_colour(chosen.name().upper())
            self.picked.emit(self._colour)


class KeyCatcher(QPushButton):
    """
    Shows a shortcut, and records a new one when clicked.

    Listening rather than typing: asking somebody to write "Space" is
    asking them to know what Qt calls the key they just pressed. Click,
    press, done.
    """

    captured = Signal(str)

    def __init__(self, key="", parent=None):
        super().__init__(parent)
        self._key = key
        self._listening = False
        self.setCheckable(True)
        self.clicked.connect(self._start)
        self._show()

    def key(self):
        return self._key

    def set_key(self, key):
        self._key = key or ""
        self._show()

    def _show(self):
        if self._listening:
            self.setText("press a key...")
        else:
            self.setText(self._key or "none")

    def _start(self):
        self._listening = True
        self.setChecked(True)
        self.grabKeyboard()
        self._show()

    def _stop(self):
        self._listening = False
        self.setChecked(False)
        self.releaseKeyboard()
        self._show()

    def keyPressEvent(self, event):
        if not self._listening:
            super().keyPressEvent(event)
            return

        key = event.key()
        if key in (Qt.Key_Escape,):
            # Escape means "changed my mind", not "bind Escape".
            self._stop()
            return
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return          # a modifier on its own is not a shortcut

        from .hotkeys import normalise

        chosen = normalise(QKeySequence(key).toString())
        self._stop()
        if chosen:
            self._key = chosen
            self._show()
            self.captured.emit(chosen)

    def focusOutEvent(self, event):
        if self._listening:
            self._stop()
        super().focusOutEvent(event)

class CustomizePanel(QWidget):
    """
    Colours now; presets and decorative themes are marked out for later.

    Changes apply as they are made rather than waiting for an Apply
    button: a colour is judged by looking at it, and a preview that
    needed confirming would be no preview at all.
    """

    palette_changed = Signal()
    decor_changed = Signal()

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.s = engine.s
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        self.form = QVBoxLayout(inner)
        self.form.setContentsMargins(18, 14, 18, 18)
        self.form.setSpacing(10)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        self._colour_section()
        self._hotkey_section()
        self._decor_section()
        self._styles_section()
        self.form.addStretch(1)

    # ---- colours -------------------------------------------------------

    def _heading(self, text):
        label = QLabel(text)
        label.setStyleSheet(
            "font-size: 14px; font-weight: 600; padding-top: 6px;")
        return label

    def _hint(self, text):
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        label.setWordWrap(True)
        return label

    def _colour_section(self):
        self.form.addWidget(self._heading("Colours"))
        self.form.addWidget(self._hint(
            "Two colours carry the interface. Everything else is derived "
            "from them, so you only choose twice."))

        self.main_swatch = Swatch(
            self.s.get("ui.theme_main") or theme.DEFAULT_MAIN)
        self.main_swatch.picked.connect(
            lambda c: self._set_colour(main=c))
        self.form.addLayout(self._colour_row(
            "Main", self.main_swatch,
            "Buttons that do something, and the marker beside the open "
            "page."))

        self.accent_swatch = Swatch(
            self.s.get("ui.theme_accent") or theme.DEFAULT_ACCENT)
        self.accent_swatch.picked.connect(
            lambda c: self._set_colour(accent=c))
        self.form.addLayout(self._colour_row(
            "Accent", self.accent_swatch,
            "Favourites, selected text, and the flash that asks for your "
            "attention."))

        self.form.addWidget(self._hint(
            "The tally light stays red and the working light stays amber "
            "whatever you pick. Those report what the app is doing, and a "
            "status that can be recoloured can mislead."))

        self.form.addWidget(self._heading("Starting points"))
        grid = QHBoxLayout()
        grid.setSpacing(8)
        for name, main, accent in PRESETS:
            button = QPushButton(name)
            button.setToolTip(f"Main {main}, accent {accent}")
            button.clicked.connect(
                lambda _c, m=main, a=accent: self._use_preset(m, a))
            grid.addWidget(button)
        grid.addStretch(1)
        self.form.addLayout(grid)

        reset = QPushButton("Back to the original colours")
        reset.clicked.connect(
            lambda: self._use_preset(theme.DEFAULT_MAIN,
                                     theme.DEFAULT_ACCENT))
        self.form.addWidget(reset, 0, Qt.AlignLeft)

    def _hotkey_section(self):
        """
        One row per action, each showing the key it answers to.

        Here rather than in Settings proper because this is decoration
        of a sort - how the app is driven rather than what it does - and
        because Settings holds its changes until Apply, while a shortcut
        is easier to judge by trying it straight away.
        """
        from avgui.hotkeys import ACTIONS

        self.form.addWidget(self._heading("Shortcuts"))
        self.form.addWidget(self._hint(
            "Single keys, while the Live or Prompt page is showing. They "
            "do nothing while you are typing into a box, so you can "
            "still write a prompt containing the letter C."))

        self.key_buttons = {}
        for name, label, _default in ACTIONS:
            row = QHBoxLayout()
            row.setSpacing(10)

            caption = QLabel(label)
            caption.setMinimumWidth(190)
            row.addWidget(caption)

            catcher = KeyCatcher(self._current_key(name))
            catcher.setMinimumWidth(110)
            catcher.captured.connect(
                lambda key, which=name: self._set_key(which, key))
            row.addWidget(catcher)

            clear = QPushButton("None")
            clear.setToolTip("Turn this shortcut off")
            clear.clicked.connect(
                lambda _checked=False, which=name: self._set_key(which, ""))
            row.addWidget(clear)
            row.addStretch(1)

            self.key_buttons[name] = catcher
            self.form.addLayout(row)

        self.key_note = QLabel("")
        self.key_note.setObjectName("fieldLabel")
        self.key_note.setWordWrap(True)
        self.form.addWidget(self.key_note)

        reset = QPushButton("Reset shortcuts")
        reset.clicked.connect(self._reset_keys)
        holder = QHBoxLayout()
        holder.addWidget(reset)
        holder.addStretch(1)
        self.form.addLayout(holder)

    def _current_key(self, name):
        from avgui.hotkeys import DEFAULTS, normalise

        stored = self.engine.s.get(f"hotkeys.{name}")
        if stored is None:
            stored = DEFAULTS.get(name, "")
        return normalise(stored)

    def _set_key(self, name, key):
        """
        Bind a key, refusing one that is already taken.

        Refusing rather than silently stealing it: two actions on one
        key means one of them stops working, and finding out which by
        experiment is nobody's idea of a good time.
        """
        from avgui.hotkeys import ACTIONS, normalise

        key = normalise(key)
        if key:
            for other, label, _default in ACTIONS:
                if other != name and self._current_key(other) == key:
                    self.key_note.setText(
                        f"{key} is already used for \"{label}\". Give "
                        f"that one a different key first.")
                    self.key_buttons[name].set_key(self._current_key(name))
                    return

        self.engine.s.set(f"hotkeys.{name}", key)
        self.engine.s.save()
        self.key_buttons[name].set_key(key)
        self.key_note.setText(
            f"Shortcut set to {key}." if key
            else "That shortcut is off.")
        self._tell_window()

    def _reset_keys(self):
        from avgui.hotkeys import DEFAULTS

        for name, default in DEFAULTS.items():
            self.engine.s.set(f"hotkeys.{name}", default)
            if name in self.key_buttons:
                self.key_buttons[name].set_key(default)
        self.engine.s.save()
        self.key_note.setText("Back to the original keys.")
        self._tell_window()

    def _tell_window(self):
        """The window holds the only copy that matters; it re-reads."""
        window = self.window()
        hotkeys = getattr(window, "hotkeys", None)
        if hotkeys is not None:
            hotkeys.reload()

    def _colour_row(self, label, swatch, description):
        row = QHBoxLayout()
        row.setSpacing(10)
        name = QLabel(label)
        name.setFixedWidth(64)
        row.addWidget(name)
        row.addWidget(swatch)
        note = self._hint(description)
        row.addWidget(note, 1)
        return row

    def _use_preset(self, main, accent):
        self.main_swatch.set_colour(main)
        self.accent_swatch.set_colour(accent)
        self._set_colour(main=main, accent=accent)

    def _set_colour(self, main=None, accent=None):
        if main:
            self.s.set("ui.theme_main", main)
        if accent:
            self.s.set("ui.theme_accent", accent)
        self.s.save()
        self.palette_changed.emit()

    def on_state(self, snapshot):
        """
        Follow the shared style list.

        The picker in the Prompt panel writes through the engine, so this
        list has to notice - otherwise the two would disagree about which
        style is in use until one of them was rebuilt.
        """
        if not hasattr(self, "style_list"):
            return
        names = [p["name"] for p in (snapshot.get("styles") or [])]
        current = snapshot.get("style_name") or ""
        shown = [self.style_list.item(i).data(Qt.UserRole)
                 for i in range(self.style_list.count())]
        if names != shown or current != self._selected_style():
            self._reload_styles(select=current)

    # ---- style presets -------------------------------------------------

    def _styles_section(self):
        self.form.addWidget(self._heading("Prompt styles"))
        self.form.addWidget(self._hint(
            "A style is added to the end of every prompt. Pick one here "
            "and it becomes the saved style used by live capture and by "
            "the prompt box."))

        self.style_list = QListWidget()
        self.style_list.setObjectName("feedList")
        self.style_list.setMinimumHeight(150)
        self.style_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.style_list.itemSelectionChanged.connect(self._style_selected)
        self.style_list.itemDoubleClicked.connect(
            lambda _i: self._edit_style())
        self.form.addWidget(self.style_list)

        row = QHBoxLayout()
        row.setSpacing(8)
        make = QPushButton("Create your own")
        make.setObjectName("primaryButton")
        make.clicked.connect(self._new_style)
        row.addWidget(make)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_style)
        self.edit_btn.setEnabled(False)
        row.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_style)
        self.delete_btn.setEnabled(False)
        row.addWidget(self.delete_btn)
        row.addStretch(1)
        self.form.addLayout(row)

        self.style_note = self._hint("")
        self.form.addWidget(self.style_note)
        self._reload_styles()

    def _reload_styles(self, select=None):
        """Redraw the list, keeping or moving the selection."""
        wanted = select or self.s.get("image.style_name") or ""
        self.style_list.blockSignals(True)
        self.style_list.clear()
        for preset in self.engine.styles.all():
            label = preset["name"]
            if preset["built_in"]:
                label += "   (built in)"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, preset["name"])
            item.setToolTip(preset["suffix"] or "No style is added.")
            if preset["built_in"]:
                item.setForeground(QColor(theme.MUTED))
            self.style_list.addItem(item)
            if preset["name"].lower() == wanted.lower():
                self.style_list.setCurrentItem(item)
        self.style_list.blockSignals(False)
        self._style_selected()

    def _selected_style(self):
        item = self.style_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _style_selected(self):
        name = self._selected_style()
        built_in = self.engine.styles.is_built_in(name) if name else True
        self.edit_btn.setEnabled(bool(name) and not built_in)
        self.delete_btn.setEnabled(bool(name) and not built_in)

        if not name:
            self.style_note.setText("")
            return
        # Routed through the engine rather than written here, so every
        # panel showing styles hears about it.
        preset = self.engine.styles.find(name)
        if name != (self.s.get("image.style_name") or ""):
            self.engine.set_style(name)
        shown = (preset["suffix"] if preset and preset["suffix"]
                 else "nothing is added")
        self.style_note.setText(f"Every prompt gets: {shown}")
        if built_in:
            self.style_note.setText(
                self.style_note.text()
                + "    Built-in styles cannot be edited or deleted.")

    def _new_style(self):
        dialog = StyleEditor(self.engine.styles, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.engine.refresh_styles()
            self._reload_styles(select=dialog.saved_name)

    def _edit_style(self):
        name = self._selected_style()
        if not name or self.engine.styles.is_built_in(name):
            return
        preset = self.engine.styles.find(name)
        dialog = StyleEditor(self.engine.styles, original=preset,
                             parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.engine.refresh_styles()
            self._reload_styles(select=dialog.saved_name)

    def _delete_style(self):
        name = self._selected_style()
        if not name or self.engine.styles.is_built_in(name):
            return
        if ConfirmUnfavourite(
                f'Style "{name}"', self).exec() != QDialog.Accepted:
            return
        self.engine.styles.remove(name)
        self.engine.refresh_styles()
        self._reload_styles()

    # ---- decorative themes ---------------------------------------------

    def _decor_section(self):
        self.form.addWidget(self._heading("Decorative theme"))
        self.form.addWidget(self._hint(
            "Decoration is painted over the interface. Generated images, "
            "controls and text are never covered - it fills what is left "
            "and moves out of the way when panels resize."))

        row = QHBoxLayout()
        row.setSpacing(10)
        label = QLabel("Theme")
        label.setFixedWidth(64)
        row.addWidget(label)
        self.decor_pick = QComboBox()
        for key, name, note in theme_names():
            self.decor_pick.addItem(name, key)
            self.decor_pick.setItemData(self.decor_pick.count() - 1,
                                        note, Qt.ToolTipRole)
        want = self.s.get("ui.decor_theme", "none") or "none"
        index = self.decor_pick.findData(want)
        self.decor_pick.setCurrentIndex(index if index >= 0 else 0)
        self.decor_pick.currentIndexChanged.connect(self._pick_decor)
        row.addWidget(self.decor_pick)
        row.addStretch(1)
        self.form.addLayout(row)

        self.fancy = QCheckBox("Fancy")
        self.fancy.setChecked(bool(self.s.get("ui.decor_animate", True)))
        self.fancy.setToolTip(
            "Animates the decoration - candle flames, swinging spiders. "
            "Turn it off to keep the decoration perfectly still.")
        self.fancy.toggled.connect(self._toggle_fancy)
        self.form.addWidget(self.fancy)

        self.enhance = QCheckBox("Enhance visuals")
        self.enhance.setChecked(
            bool(self.s.get("ui.decor_enhanced", False)))
        self.enhance.setToolTip(
            "Richer artwork: shaded, jointed and highlighted instead of "
            "the plainer original shapes. Off by default - both sets are "
            "kept, and the plain one is lighter to draw.")
        self.enhance.toggled.connect(self._toggle_enhance)
        self.form.addWidget(self.enhance)

        self.spooky = QCheckBox("Spooky sounds")
        self.spooky.setChecked(bool(self.s.get("ui.decor_sounds", False)))
        self.spooky.setToolTip(
            "Occasional sound effects while this theme is on. Off by "
            "default - the app is meant to be safe to leave running on "
            "a broadcast.")
        self.spooky.toggled.connect(self._toggle_spooky)
        self.form.addWidget(self.spooky)

        self.decor_note = self._hint("")
        self.form.addWidget(self.decor_note)
        self._sync_decor_controls()

    def _sync_decor_controls(self):
        """
        Show only the options the chosen theme actually offers.

        Hidden rather than disabled: a greyed-out "Spooky sounds" with no
        theme applied invites the question "spooky sounds for what?", and
        the answer is nothing. A theme that brings no options shows none,
        and the section is just a picker.
        """
        name = self.decor_pick.currentData() or "none"
        offered = options_for(name)

        self.fancy.setVisible("animate" in offered)
        self.enhance.setVisible("enhance" in offered)
        self.spooky.setVisible("sounds" in offered)
        # Relabelled per theme, so the wording matches what it decorates.
        if "animate" in offered:
            self.fancy.setText(option_label(name, "animate"))
        if "enhance" in offered:
            self.enhance.setText(option_label(name, "enhance"))
        if "sounds" in offered:
            self.spooky.setText(option_label(name, "sounds"))

        if not offered:
            # Cleared rather than merely hidden: stale text that happens
            # to be invisible is one styling change away from showing.
            self.decor_note.setText(
                "This theme has no options of its own."
                if name != "none" else "")
            self.decor_note.setVisible(name != "none")
            return

        self.decor_note.setVisible(True)
        if "sounds" in offered and self.spooky.isChecked():
            self.decor_note.setText(
                "Sounds are on. They will play at a low volume while the "
                "app is open.")
        elif "sounds" in offered:
            self.decor_note.setText(
                "Silent. Sounds stay off until asked for."
                + ("" if self.enhance.isChecked()
                   else "  Enhanced visuals are off too."))
        else:
            self.decor_note.setText("")
            self.decor_note.setVisible(False)

    def _pick_decor(self, _index):
        name = self.decor_pick.currentData() or "none"
        self.s.set("ui.decor_theme", name)
        self.s.save()
        self._sync_decor_controls()
        self.decor_changed.emit()

    def _toggle_fancy(self, value):
        self.s.set("ui.decor_animate", bool(value))
        self.s.save()
        self.decor_changed.emit()

    def _toggle_enhance(self, value):
        self.s.set("ui.decor_enhanced", bool(value))
        self.s.save()
        self._sync_decor_controls()
        self.decor_changed.emit()

    def _toggle_spooky(self, value):
        self.s.set("ui.decor_sounds", bool(value))
        self.s.save()
        self._sync_decor_controls()
        self.decor_changed.emit()
