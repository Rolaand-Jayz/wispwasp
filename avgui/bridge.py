"""
Marshals engine callbacks onto the Qt main thread.

The engine notifies listeners from its worker thread. Touching a widget from
that thread is undefined behaviour in Qt - it usually looks fine and then
crashes under load. Emitting a signal is the documented way across: Qt
queues it to the receiving object's thread. Every panel connects here and
never subscribes to the engine directly.
"""

from PySide6.QtCore import QObject, Signal


class EngineBridge(QObject):
    changed = Signal(dict)
    level = Signal(float)

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        # Bound methods, kept so they can be unsubscribed on close.
        self._forward = self._on_engine_state
        self._forward_level = self._on_engine_level
        engine.add_listener(self._forward)
        engine.add_level_listener(self._forward_level)

    def _on_engine_state(self, snapshot):
        # Called on the worker thread. Emitting is the only safe move here:
        # the connection is queued because sender and receiver differ.
        self.changed.emit(snapshot)

    def _on_engine_level(self, rms):
        # Same rule, higher rate: this arrives about twenty times a second
        # from the recording thread.
        self.level.emit(rms)

    def detach(self):
        self.engine.remove_listener(self._forward)
        self.engine.remove_level_listener(self._forward_level)
