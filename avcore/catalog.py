"""
Remembers which prompt made which image.

The gallery reads files off disk, and a filename is just a timestamp - so
without this there is nothing anywhere that connects an image to the words
that produced it once the app closes.

One index file rather than a sidecar per image: manual images are saved
wherever the user chooses, often the Desktop, and scattering .json files
through someone's Desktop to support a tooltip is not a fair trade.
Filenames carry a timestamp to the millisecond, so they are unique across
both folders.
"""

import json
import threading
import time
from pathlib import Path

MAX_ENTRIES = 2000


# Images from before the model was recorded need a key that is not the
# empty string, because empty already means "any model" to the filter.
# Sharing one value made choosing "Not recorded" quietly do nothing.
UNRECORDED = "\x00unrecorded"


def has_transparency(path):
    """
    Does this PNG carry an alpha channel?

    Read from the header rather than by decoding the picture: the
    gallery asks this of every file each time a filter changes, and
    loading a few hundred full-size images to find out would make
    scrolling crawl.

    A PNG's IHDR is always the first chunk, and its colour type says
    whether there is alpha - 4 is grey with alpha, 6 is colour with
    alpha. This reports what the file can hold rather than whether any
    pixel is actually see-through, which is the same thing in practice
    here: only cut-outs are written with an alpha channel at all.
    """
    path = Path(path)
    if path.suffix.lower() not in (".png", ".webp"):
        return False
    try:
        with path.open("rb") as handle:
            head = handle.read(26)
    except OSError:
        return False

    if head[:8] != b"\x89PNG\r\n\x1a\n":
        # WEBP and anything else: not worth opening, and nothing this
        # app writes puts alpha in them.
        return False
    if head[12:16] != b"IHDR":
        return False
    return head[25] in (4, 6)


def model_key(backend, model):
    """
    One value identifying what made an image, for matching and filtering.

    A local model is its filename; online work has no checkpoint, so the
    backend name stands in. Images from before this was recorded get an
    empty key, which is a real answer rather than a missing one.
    """
    backend = (backend or "").strip().lower()
    model = (model or "").strip()
    if model:
        return model
    if backend and backend != "comfyui":
        return backend
    return UNRECORDED


def model_label(backend, model, short=False):
    """
    A readable name for whatever made an image.

    Pollinations has no checkpoint to name, so saying "Pollinations" is
    the whole truth there. A local model is named by its file, with the
    extension dropped - nobody thinks of their model as ending in
    .safetensors.
    """
    backend = (backend or "").strip().lower()
    model = (model or "").strip()

    if backend == "svd":
        # Named properly rather than capitalised: "Svd" reads like a
        # typo, and the checkpoint is what someone would recognise.
        stem = model.rsplit(".", 1)[0] if "." in model else model
        if short:
            return stem or "Stable Video Diffusion"
        return (f"Stable Video Diffusion - {stem}" if stem
                else "Stable Video Diffusion")

    if backend and backend != "comfyui":
        return backend.capitalize()

    if not model:
        return "" if short else "model not recorded"

    stem = model.rsplit(".", 1)[0] if "." in model else model
    return stem if short else f"ComfyUI - {stem}"


class Catalog:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self):
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (json.JSONDecodeError, OSError):
            # A damaged index costs tooltips, not images, so it is not
            # worth refusing to start over.
            return {}

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._data, indent=1),
                           encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass

    def record(self, paths, prompt, source="live", transcript="",
               backend="", model="", seconds=None):
        """
        Note the prompt behind one image.

        `paths` may be several: a manual image exists both where the user
        asked for it and as a copy in the overlay folder, and either may
        be the one the gallery shows.
        """
        if not prompt:
            return
        if isinstance(paths, (str, Path)):
            paths = [paths]

        entry = {
            "prompt": prompt,
            "source": source,
            "transcript": transcript or "",
            "at": time.time(),
            # What made it. Recorded at the moment of generation because
            # the setting can change afterwards, and then nothing on
            # disk would say what any older picture came from.
            "backend": backend or "",
            "model": model or "",
        }
        if seconds:
            # Only clips have a length. Written down now because reading
            # it back would mean decoding video, and the packaged build
            # has nothing to decode with.
            entry["seconds"] = float(seconds)
        with self._lock:
            for p in paths:
                if not p:
                    continue
                name = Path(p).name
                # Carry a favourite across, so re-recording an image
                # cannot silently un-protect it.
                keep = self._data.get(name, {}).get("favourite")
                self._data[name] = dict(entry)
                if keep:
                    self._data[name]["favourite"] = True
            if len(self._data) > MAX_ENTRIES:
                # Oldest first, so the index cannot grow without bound -
                # but never a favourite, since dropping its entry would
                # quietly un-protect an image the user asked to keep.
                ordered = sorted(
                    (kv for kv in self._data.items()
                     if not kv[1].get("favourite")),
                    key=lambda kv: kv[1].get("at", 0))
                excess = len(self._data) - MAX_ENTRIES
                for name, _ in ordered[:excess]:
                    self._data.pop(name, None)
            self._save()

    def lookup(self, path):
        """The entry for an image, or None if it predates the catalogue."""
        with self._lock:
            return self._data.get(Path(path).name)

    def set_favourite(self, path, value=True):
        """
        Mark an image as kept.

        An entry is created even for an image with no recorded prompt, so
        anything in the gallery can be favourited - including images made
        before the catalogue existed.
        """
        name = Path(path).name
        with self._lock:
            entry = self._data.setdefault(name, {
                "prompt": "", "source": "", "transcript": "",
                "at": time.time(),
            })
            if value:
                entry["favourite"] = True
            else:
                entry.pop("favourite", None)
                # An entry with nothing left in it is just clutter.
                if not entry.get("prompt"):
                    self._data.pop(name, None)
            self._save()

    def set_censored(self, path, value=True):
        """
        Mark an image as censored: shown blurred until revealed.

        Kept in the same place as the favourite flag and behaving the same
        way, because to the user they are two marks on an image rather
        than two different systems. An entry is created even for an image
        with no recorded prompt, so anything in the gallery can be marked.
        """
        name = Path(path).name
        with self._lock:
            entry = self._data.setdefault(name, {
                "prompt": "", "source": "", "transcript": "",
                "at": time.time(),
            })
            if value:
                entry["censored"] = True
            else:
                entry.pop("censored", None)
                # An entry holding nothing but a cleared flag is clutter.
                if not entry.get("prompt") and not entry.get("favourite"):
                    self._data.pop(name, None)
            self._save()

    def is_censored(self, path):
        entry = self.lookup(path)
        return bool(entry and entry.get("censored"))

    def models_used(self):
        """
        Every model that appears in the history, newest use first.

        Taken from the images themselves rather than from what is
        installed: someone may have deleted a model, or be looking at
        pictures made on another machine, and the question here is
        "what made these", not "what could I run now".
        """
        seen = {}
        with self._lock:
            for entry in self._data.values():
                if not entry.get("prompt"):
                    continue
                key = model_key(entry.get("backend"), entry.get("model"))
                label = model_label(entry.get("backend"),
                                    entry.get("model"), short=True)
                at = entry.get("at") or 0
                if key not in seen or at > seen[key][1]:
                    seen[key] = (label or "Not recorded", at)
        return [(key, label) for key, (label, _at)
                in sorted(seen.items(), key=lambda kv: -kv[1][1])]

    def censored(self):
        """Every censored filename."""
        with self._lock:
            return {name for name, entry in self._data.items()
                    if entry.get("censored")}

    def is_favourite(self, path):
        with self._lock:
            entry = self._data.get(Path(path).name)
            return bool(entry and entry.get("favourite"))

    def favourites(self):
        with self._lock:
            return {name for name, e in self._data.items()
                    if e.get("favourite")}

    def rename(self, old_path, new_path):
        """
        Move an entry to a new filename.

        Everything recorded about an image - its prompt and whether it is
        a favourite - is keyed by filename, so a rename that did not carry
        the entry across would silently lose both.
        """
        old_name = Path(old_path).name
        new_name = Path(new_path).name
        if old_name == new_name:
            return False
        with self._lock:
            entry = self._data.pop(old_name, None)
            if entry is None:
                return False
            self._data[new_name] = entry
            self._save()
        return True

    def forget(self, path):
        with self._lock:
            if self._data.pop(Path(path).name, None) is not None:
                self._save()

    def __len__(self):
        with self._lock:
            return len(self._data)


class PromptStore:
    """
    Prompts the user has chosen to keep.

    Separate from the image catalogue: that one is keyed by filename and
    an entry dies with its file, whereas a kept prompt outlives any
    particular image made from it. Order is preserved, newest first,
    because this is a list somebody reads rather than a set.
    """

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._items = self._load()

    def _load(self):
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Losing kept prompts is bad, but refusing to start is worse.
            return []
        if isinstance(raw, list):
            return [str(x) for x in raw if str(x).strip()]
        return []

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._items, indent=1),
                           encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass

    @staticmethod
    def _clean(prompt):
        return " ".join((prompt or "").split())

    def add(self, prompt):
        prompt = self._clean(prompt)
        if not prompt:
            return False
        with self._lock:
            if prompt in self._items:
                return False
            self._items.insert(0, prompt)
            self._save()
        return True

    def remove(self, prompt):
        prompt = self._clean(prompt)
        with self._lock:
            if prompt not in self._items:
                return False
            self._items.remove(prompt)
            self._save()
        return True

    def has(self, prompt):
        with self._lock:
            return self._clean(prompt) in self._items

    def all(self):
        with self._lock:
            return list(self._items)

    def __len__(self):
        return len(self._items)
