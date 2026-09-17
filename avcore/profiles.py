"""
Named sets of preferences.

A profile is somewhere to keep "how I like it for streaming" or "how I
like it for messing about", so the two are a click apart rather than
twenty adjustments apart.

Deliberately not a copy of everything. Three kinds of setting are left
out, because carrying them would do harm rather than good:

- where ComfyUI and the folders are. Those describe this machine, not a
  preference, and restoring a stale path could send the app looking for
  an install that is not there.
- the Civitai API key. It is a credential; copying it between files
  that get shared or backed up is how credentials leak.
- which model was installed. That is a fact about the disk, not a taste.
"""

import copy
import json
from pathlib import Path

from .config import DATA_DIR, DEFAULTS

PROFILES_FILE = DATA_DIR / "profiles.json"

# Kept out of profiles, for the reasons in the docstring above.
EXCLUDED = (
    "paths.",
    "comfyui.path",
    "models.",
)


def _flatten(node, prefix=""):
    """Settings as dotted keys, which is how they are addressed."""
    flat = {}
    for key, value in (node or {}).items():
        dotted = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, dotted + "."))
        else:
            flat[dotted] = value
    return flat


def portable_keys():
    """Every setting a profile is allowed to carry."""
    return [key for key in sorted(_flatten(DEFAULTS))
            if not key.startswith(EXCLUDED)]


def capture(settings):
    """What the settings look like now, as a profile would store it."""
    return {key: settings.get(key) for key in portable_keys()}


def _read():
    try:
        data = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(data):
    PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def names():
    """Saved profiles, in the order a person would expect to read them."""
    return sorted(_read(), key=str.lower)


def exists(name):
    return (name or "").strip() in _read()


def save(name, settings):
    """
    Store the current settings under a name.

    Overwrites an existing profile of the same name - the caller asks
    first, because doing it silently is how someone loses the setup they
    spent an evening on.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("A profile needs a name.")
    data = _read()
    data[name] = capture(settings)
    _write(data)
    return name


def apply(name, settings):
    """
    Put a saved profile into the settings.

    Only keys the profile actually carries are touched, so anything
    added to the app since the profile was saved keeps its current
    value rather than reverting to a default the profile never knew
    about.
    """
    stored = _read().get((name or "").strip())
    if stored is None:
        raise KeyError(name)
    allowed = set(portable_keys())
    applied = 0
    for key, value in stored.items():
        if key in allowed:
            settings.set(key, value)
            applied += 1
    settings.save()
    return applied


def delete(name):
    data = _read()
    if data.pop((name or "").strip(), None) is None:
        return False
    _write(data)
    return True


def reset_to_defaults(settings):
    """
    Put the preferences back to how the app ships.

    Installation paths are kept. "Reset settings" should not be able to
    lose track of a ten gigabyte ComfyUI install and start downloading
    it again - that is a far bigger consequence than the button
    promises.
    """
    defaults = _flatten(copy.deepcopy(DEFAULTS))
    changed = 0
    for key, value in defaults.items():
        if key.startswith(("paths.", "comfyui.path")):
            continue
        if settings.get(key) != value:
            settings.set(key, value)
            changed += 1
    settings.save()
    return changed
