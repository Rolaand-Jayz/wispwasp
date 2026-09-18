"""
Choosing which LoRAs apply, and how strongly.

One widget, used in two places: the Settings page, where there is room
to explain, and a small popup from the prompt strip, where there is not.
Both edit the same setting, so a LoRA switched off mid-stream stays off
when Settings is next opened.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)


def stored(settings):
    """The saved list, cleaned up enough to trust."""
    entries = settings.get("comfyui.loras") or []
    if not isinstance(entries, list):
        return []
    clean = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("name") or "").strip()
        if not name:
            continue
        try:
            strength = float(entry.get("strength", 1.0))
        except (TypeError, ValueError):
            strength = 1.0
        clean.append({"name": name, "strength": strength,
                      "on": bool(entry.get("on"))})
    return clean


def on_disk(settings):
    """Every LoRA installed, by filename."""
    from avcore.models import installed
    from avcore.setup import loras_dir

    try:
        return [path.name for path in installed(loras_dir(settings))]
    except Exception:
        return []


def current_family(settings):
    """Which family the model in use belongs to, or None."""
    from avcore.setup import checkpoints_dir, family_of

    name = (settings.get("comfyui.checkpoint") or "").strip()
    folder = checkpoints_dir(settings)
    try:
        if name:
            return family_of(folder / name)
        from avcore.models import installed

        for path in installed(folder):
            found = family_of(path)
            if found:
                return found
    except Exception:
        pass
    return None


def verdict(settings, name):
    """
    Whether a LoRA will do anything, and what to say if not.

    Returns (usable, note). Two ways to be useless, and both are silent:
    a LoRA for another architecture entirely, which ComfyUI loads while
    matching none of its weights, and one for the other half of Stable
    Diffusion, which does the same. Neither raises anything - the
    picture simply comes out unchanged.
    """
    from avcore.setup import lora_family, loras_dir

    family = lora_family(loras_dir(settings) / name)
    if family is None:
        return False, "Not compatible with Stable Diffusion"

    mine = current_family(settings)
    if mine and family != mine:
        wanted = "SDXL" if family == "sdxl" else "SD 1.5"
        using = "SDXL" if mine == "sdxl" else "SD 1.5"
        return False, f"Needs {wanted} - your model is {using}"

    return True, "SDXL" if family == "sdxl" else "SD 1.5"


def merged(settings):
    """
    What is installed, carrying over what was chosen.

    Driven by the folder rather than by the setting: a LoRA deleted from
    disk should stop appearing, and one dropped in by hand should turn
    up without anybody having to tell the app about it.
    """
    saved = {entry["name"]: entry for entry in stored(settings)}
    rows = []
    for name in on_disk(settings):
        entry = saved.get(name)
        rows.append({
            "name": name,
            "strength": entry["strength"] if entry else 1.0,
            "on": bool(entry["on"]) if entry else False,
        })
    return rows


def active_count(settings):
    """How many are switched on and still present."""
    return sum(1 for row in merged(settings) if row["on"])


class LoraChooser(QWidget):
    """A row per installed LoRA: on or off, and how strongly."""

    changed = Signal()

    def __init__(self, settings, compact=False, parent=None):
        super().__init__(parent)
        self.s = settings
        self.compact = compact
        self._rows = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        self.note = QLabel("")
        self.note.setObjectName("fieldLabel")
        self.note.setWordWrap(True)
        outer.addWidget(self.note)

        holder = QWidget()
        self.list = QVBoxLayout(holder)
        self.list.setContentsMargins(0, 0, 0, 0)
        self.list.setSpacing(4)

        if compact:
            # The popup can hold a lot of LoRAs; the strip cannot grow.
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.NoFrame)
            area.setWidget(holder)
            area.setMaximumHeight(240)
            outer.addWidget(area)
        else:
            outer.addWidget(holder)

        self.reload()

    # ---- building the rows ----------------------------------------------

    def reload(self):
        """Rebuild from what is on disk and what was chosen."""
        while self.list.count():
            item = self.list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows = []

        rows = merged(self.s)
        if not rows:
            self.note.setText(
                "No LoRAs installed. Settings has a LoRAs button that "
                "fetches them from Civitai.")
            return

        self.note.setText(
            "Applied on top of the model, in this order."
            if not self.compact else "")

        for row in rows:
            self.list.addWidget(self._row(row))

    def _row(self, row):
        holder = QWidget()
        line = QHBoxLayout(holder)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(8)

        usable, note = verdict(self.s, row["name"])

        tick = QCheckBox(row["name"].rsplit(".", 1)[0])
        tick.setChecked(row["on"] and usable)
        tick.setToolTip(row["name"])
        tick.setEnabled(usable)
        tick.toggled.connect(self._save)
        line.addWidget(tick, 1)

        # The reason, beside the name. Red only when it would not work,
        # so the colour means something rather than decorating every
        # row.
        badge = QLabel(note)
        badge.setObjectName("fieldLabel")
        if not usable:
            badge.setStyleSheet("color: #e06c6c;")
            badge.setToolTip(
                "ComfyUI will load it and match none of its weights, so "
                "the picture comes out unchanged - with no error to tell "
                "you why.")
        line.addWidget(badge)

        strength = QDoubleSpinBox()
        strength.setRange(-4.0, 4.0)
        strength.setSingleStep(0.05)
        strength.setDecimals(2)
        strength.setValue(row["strength"])
        strength.setFixedWidth(84)
        strength.setToolTip(
            "How strongly it applies. 1 is what the maker intended; "
            "lower is subtler, and above 1 usually goes strange.")
        strength.setEnabled(usable)
        strength.valueChanged.connect(self._save)
        line.addWidget(strength)

        self._rows.append((row["name"], tick, strength))
        return holder

    # ---- saving ----------------------------------------------------------

    def _save(self, *_args):
        entries = [{"name": name,
                    "strength": round(strength.value(), 2),
                    "on": tick.isChecked()}
                   for name, tick, strength in self._rows]
        self.s.set("comfyui.loras", entries)
        self.s.save()
        self.changed.emit()
