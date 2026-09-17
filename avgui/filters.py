"""
Filtering the gallery.

Kept apart from the panel so the matching rules can be tested on their own
rather than through a grid of widgets.
"""

import time

# label -> how many days back, or None for no limit
DATE_RANGES = [
    ("Any time", None),
    ("Today", "today"),
    ("Yesterday", "yesterday"),
    ("Past 3 days", 3),
    ("Past week", 7),
    ("Past month", 30),
    ("Past year", 365),
]

SOURCES = [
    ("Anything", "any"),
    ("Heard", "heard"),
    ("Typed", "typed"),
]


def fuzzy(needle, haystack):
    """
    A forgiving match.

    Every whitespace-separated word has to appear somewhere, in any order,
    so "stone bridge" finds "a bridge of old stone". Failing that, the
    whole needle is tried as a subsequence, which tolerates a dropped
    letter or an abbreviation like "lghths" for "lighthouse".
    """
    needle = (needle or "").strip().lower()
    if not needle:
        return True
    hay = (haystack or "").lower()
    if not hay:
        return False

    words = needle.split()
    if all(word in hay for word in words):
        return True

    # Subsequence: the characters in order, gaps allowed.
    position = 0
    for char in needle.replace(" ", ""):
        position = hay.find(char, position)
        if position < 0:
            return False
        position += 1
    return True


def _day_start(offset_days=0):
    now = time.localtime()
    midnight = time.mktime((now.tm_year, now.tm_mon, now.tm_mday,
                            0, 0, 0, 0, 0, -1))
    return midnight - offset_days * 86400


def in_range(mtime, choice):
    """Is a timestamp inside the chosen window?"""
    if choice is None:
        return True
    if choice == "today":
        return mtime >= _day_start()
    if choice == "yesterday":
        return _day_start(1) <= mtime < _day_start()
    try:
        days = int(choice)
    except (TypeError, ValueError):
        return True
    # Counted from the start of the day, so "past 3 days" means three
    # calendar days rather than exactly 72 hours ago to the second.
    return mtime >= _day_start(days - 1)


class Filters:
    """What the gallery is currently showing."""

    def __init__(self):
        self.date = None
        self.name = ""
        self.prompt = ""
        self.source = "any"
        self.kind = "any"
        # "any", "only" or "hide". Kept apart from `source` rather than
        # being one of its options: favourite is not a kind of image, it
        # is a mark on one, so it has to combine with the rest - "heard,
        # and favourited" or "heard, but not favourited".
        self.favourites = "any"
        # Same three states as favourites, for the same reason: censored
        # is a mark on an image, not a kind of one.
        self.censored = "any"
        # Which model made the image. Empty means any; otherwise it is
        # a key from the catalogue's own history.
        self.model = ""

    def active(self):
        return bool(self.date or self.name or self.prompt
                    or self.source != "any" or self.kind != "any"
                    or self.favourites != "any"
                    or self.censored != "any"
                    or bool(self.model))

    def clear(self):
        self.__init__()

    def matches(self, path, entry, favourite, censored=False):
        """
        Decide whether one image belongs in the list.

        `entry` is its catalogue record, which may be missing for images
        made before the catalogue existed - those simply have no prompt to
        match against.
        """
        if self.kind == "video":
            # One entry covering every clip format, because nobody
            # filters by container.
            if path.suffix.lower() not in (".webm", ".mp4"):
                return False
        elif self.kind != "any" and path.suffix.lower() != self.kind:
            return False

        if self.favourites == "only" and not favourite:
            return False
        if self.favourites == "hide" and favourite:
            return False

        if self.censored == "only" and not censored:
            return False
        if self.censored == "hide" and censored:
            return False

        if self.model:
            from avcore.catalog import model_key

            made_by = model_key((entry or {}).get("backend"),
                                (entry or {}).get("model"))
            if made_by != self.model:
                return False


        if self.source in ("heard", "typed"):
            if not entry or entry.get("source") != (
                    "live" if self.source == "heard" else "manual"):
                return False

        if self.name and not fuzzy(self.name, path.name):
            return False

        if self.prompt:
            text = (entry or {}).get("prompt") or ""
            if not fuzzy(self.prompt, text):
                return False

        if self.date is not None:
            try:
                if not in_range(path.stat().st_mtime, self.date):
                    return False
            except OSError:
                return False
        return True
