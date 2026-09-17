"""
Style presets: the suffix appended to every prompt, saved by name.

Two kinds live in one list. Built-ins ship with the app and cannot be
edited or removed; the user's own sit alongside them and can be. They are
kept in one list rather than two because the person choosing one does not
care where it came from - they care what it looks like.
"""

import json
import threading
from pathlib import Path

# Shipped with the app. Deliberately sparse for now: the shape is here so
# a proper set can be dropped in without touching anything else.
BUILT_IN = [
    {
        "name": "Detailed",
        "suffix": "highly detailed, dramatic lighting",
        "note": "The original default.",
    },
    {
        "name": "None",
        "suffix": "",
        "note": "Send prompts exactly as they are.",
    },
]


class StylePresets:
    """The built-in styles, plus whatever the user has made."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._custom = self._load()

    def _load(self):
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # A damaged file costs presets, not the app.
            return []
        if not isinstance(raw, list):
            return []
        out = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if name:
                out.append({
                    "name": name,
                    "suffix": str(item.get("suffix", "")),
                    "note": str(item.get("note", "")),
                })
        return out

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._custom, indent=1),
                           encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass

    # ---- reading -------------------------------------------------------

    def all(self):
        """Built-ins first, then the user's own, each tagged with which."""
        out = [dict(p, built_in=True) for p in BUILT_IN]
        with self._lock:
            out += [dict(p, built_in=False) for p in self._custom]
        return out

    def custom(self):
        with self._lock:
            return [dict(p) for p in self._custom]

    def find(self, name):
        for preset in self.all():
            if preset["name"].lower() == (name or "").strip().lower():
                return preset
        return None

    def suffix_for(self, name):
        preset = self.find(name)
        return preset["suffix"] if preset else None

    def is_built_in(self, name):
        preset = self.find(name)
        return bool(preset and preset["built_in"])

    # ---- writing -------------------------------------------------------

    def validate(self, name, original=None):
        """
        Returns an error message, or "" if the name is usable.

        Checked here rather than in the dialog so the rule is the same
        wherever a preset is made.
        """
        name = (name or "").strip()
        if not name:
            return "A name is needed."
        if len(name) > 40:
            return "That name is too long."
        if original and name.lower() == original.lower():
            return ""
        if self.find(name):
            if self.is_built_in(name):
                return f'"{name}" is a built-in style.'
            return f'A style called "{name}" already exists.'
        return ""

    def save(self, name, suffix, note="", original=None):
        """Add a preset, or rename and update one. Returns (ok, message)."""
        name = " ".join((name or "").split())
        problem = self.validate(name, original)
        if problem:
            return False, problem

        entry = {"name": name, "suffix": " ".join((suffix or "").split()),
                 "note": (note or "").strip()}
        with self._lock:
            if original:
                for i, preset in enumerate(self._custom):
                    if preset["name"].lower() == original.lower():
                        self._custom[i] = entry
                        break
                else:
                    self._custom.append(entry)
            else:
                self._custom.append(entry)
            self._save()
        return True, name

    def remove(self, name):
        """Built-ins cannot be removed; they are not the user's to lose."""
        if self.is_built_in(name):
            return False
        with self._lock:
            for i, preset in enumerate(self._custom):
                if preset["name"].lower() == (name or "").lower():
                    del self._custom[i]
                    self._save()
                    return True
        return False

    def __len__(self):
        return len(BUILT_IN) + len(self._custom)
