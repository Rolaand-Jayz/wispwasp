"""
Keyboard shortcuts for the things people do repeatedly.

Kept apart from the panels that own the actions. A shortcut has to know
three things the panels do not: which page is showing, whether somebody
is typing, and what key the person chose - and putting that logic in
both the Live and Prompt panels would mean two copies of it.

Nothing here is a global hotkey. These only fire while the app has focus
and one of the two working pages is open; the app has no business
intercepting keys from whatever else is on the machine.
"""

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QAbstractSpinBox, QComboBox, QLineEdit, QPlainTextEdit, QTextEdit,
)

# What can be bound, in the order the Customize panel lists them.
ACTIONS = [
    ("listen", "Start or stop listening", "Space"),
    ("capture", "Capture now", "V"),
    ("repeat", "Repeat the last prompt", "R"),
    ("cancel", "Cancel what is running", "C"),
    ("clear", "Clear the overlay", "X"),
]

DEFAULTS = {name: key for name, _label, key in ACTIONS}


def normalise(text):
    """
    A key as Qt would write it, or "" if it is not usable.

    Round-tripped through QKeySequence so that whatever a person pressed
    is stored in the same form it will be compared in - "space" typed by
    hand and Space captured from a keypress have to end up identical.
    """
    text = (text or "").strip()
    if not text:
        return ""
    sequence = QKeySequence(text)
    if sequence.isEmpty():
        return ""
    return sequence.toString()


def describes_typing(widget):
    """
    Is this widget one somebody types into?

    Checked by behaviour rather than by name: a spin box is not a line
    edit, but pressing X in one is still typing. Anything that accepts
    text gets to keep its keystrokes.
    """
    if widget is None:
        return False
    if isinstance(widget, (QLineEdit, QPlainTextEdit, QTextEdit,
                           QAbstractSpinBox)):
        return True
    if isinstance(widget, QComboBox) and widget.isEditable():
        return True
    # A spin box holds its line edit as a child, and that is what
    # actually has focus.
    parent = widget.parentWidget()
    if isinstance(parent, (QAbstractSpinBox, QComboBox)):
        return True
    return False


class Hotkeys(QObject):
    """Watches for key presses and runs the matching action."""

    def __init__(self, window, settings, parent=None):
        super().__init__(parent or window)
        self.win = window
        self.s = settings
        self._actions = {}
        self.reload()

    # ---- what is bound ---------------------------------------------------

    def reload(self):
        """Re-read the bindings from the settings."""
        self._keys = {}
        for name, _label, fallback in ACTIONS:
            chosen = self.s.get(f"hotkeys.{name}")
            key = normalise(chosen if chosen is not None else fallback)
            if key:
                self._keys[key] = name

    def bind(self, name, handler):
        """Say what to run for one action."""
        self._actions[name] = handler

    def binding(self, name):
        """The key currently bound to an action."""
        for key, bound in self._keys.items():
            if bound == name:
                return key
        return ""

    def clashes_with(self, key, name):
        """Which other action already uses this key, if any."""
        held = self._keys.get(normalise(key))
        return held if held and held != name else ""

    # ---- catching the key ------------------------------------------------

    def eventFilter(self, watched, event):
        if event.type() != QEvent.KeyPress:
            return False
        if not self._should_fire():
            return False

        widget = self.win.focusWidget()
        if describes_typing(widget):
            return False

        # Modified presses are left alone: Ctrl+C is a copy, whatever X
        # is bound to, and stealing it would be rude.
        modifiers = event.modifiers()
        if modifiers & (Qt.ControlModifier | Qt.AltModifier
                        | Qt.MetaModifier):
            return False

        pressed = QKeySequence(event.key()).toString()
        name = self._keys.get(pressed)
        if not name:
            return False

        handler = self._actions.get(name)
        if handler is None:
            return False
        handler()
        return True          # swallowed, so it does not also scroll a list

    def _should_fire(self):
        """
        Only on the two pages that generate anything.

        The gallery has its own keys - arrows step through the viewer -
        and Setup and Settings are full of fields. A shortcut firing
        there would be a surprise at best.
        """
        current = getattr(self.win, "current_panel", None)
        if callable(current):
            current = current()
        return current in ("live", "prompt")
