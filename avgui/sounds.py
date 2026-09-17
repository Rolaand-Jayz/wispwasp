"""
Theme sounds.

Opt-in and silent unless asked for. The effects are generated into the
data folder the first time they are needed rather than shipped: a handful
of short atmospheric noises are cheaper to synthesise than to carry, and
it keeps the installer from growing for a feature most people leave off.
"""

import math
import struct
import wave

RATE = 22050


def _write(path, samples):
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(b"".join(
            struct.pack("<h", max(-32767, min(32767, int(s * 32767))))
            for s in samples))


def _envelope(i, total, attack=0.1, release=0.6):
    """Fade in and out so nothing clicks at the edges."""
    a = int(total * attack) or 1
    r = int(total * release) or 1
    if i < a:
        return i / a
    if i > total - r:
        return max(0.0, (total - i) / r)
    return 1.0


def _creak(total=int(RATE * 0.9)):
    """A door-like creak: a low tone wobbling upward, plus grain."""
    import random
    rng = random.Random(4)
    out = []
    phase = 0.0
    for i in range(total):
        t = i / total
        freq = 90 + 120 * t + math.sin(t * 26) * 14
        phase += 2 * math.pi * freq / RATE
        tone = math.sin(phase) * 0.28 + math.sin(phase * 2) * 0.09
        grain = rng.uniform(-1, 1) * 0.05 * (1 - t)
        out.append((tone + grain) * _envelope(i, total, 0.06, 0.5))
    return out


def _whoosh(total=int(RATE * 0.55)):
    """Filtered noise sweeping past: a bat, or a gust."""
    import random
    rng = random.Random(9)
    out = []
    last = 0.0
    for i in range(total):
        t = i / total
        noise = rng.uniform(-1, 1)
        # A one-pole filter that opens then closes, so it sweeps.
        cutoff = 0.05 + 0.5 * math.sin(math.pi * t)
        last += (noise - last) * cutoff
        out.append(last * 0.5 * _envelope(i, total, 0.2, 0.6))
    return out


def _chime(total=int(RATE * 1.1)):
    """A soft minor third, for something having finished."""
    out = []
    for i in range(total):
        t = i / RATE
        a = math.sin(2 * math.pi * 494 * t) * 0.22
        b = math.sin(2 * math.pi * 587 * t) * 0.16
        c = math.sin(2 * math.pi * 988 * t) * 0.07
        decay = math.exp(-t * 3.4)
        out.append((a + b + c) * decay * _envelope(i, total, 0.02, 0.35))
    return out


def _latch(total=int(RATE * 0.35)):
    """A short wooden clack: a latch dropping, for something stopping."""
    import random
    rng = random.Random(21)
    out = []
    for i in range(total):
        t = i / total
        thud = math.sin(2 * math.pi * 140 * (i / RATE)) * 0.5
        knock = rng.uniform(-1, 1) * 0.35 * math.exp(-t * 26)
        out.append((thud * math.exp(-t * 12) + knock)
                   * _envelope(i, total, 0.01, 0.55))
    return out


def _rustle(total=int(RATE * 0.22)):
    """
    A brief papery rustle.

    Deliberately the quietest and shortest of the set: it plays on every
    panel change, and anything with character would wear out within a
    minute of normal use.
    """
    import random
    rng = random.Random(33)
    out = []
    last = 0.0
    for i in range(total):
        t = i / total
        last += (rng.uniform(-1, 1) - last) * 0.42
        out.append(last * 0.30 * math.sin(math.pi * t)
                   * _envelope(i, total, 0.15, 0.6))
    return out


def _wisp(total=int(RATE * 1.5)):
    """
    The logo's easter egg: a rising figure that thins into nothing.

    Only ever heard on purpose, so it can afford to be the one sound with
    real character.
    """
    out = []
    for i in range(total):
        t = i / RATE
        span = total / RATE
        glide = 420 + 560 * (i / total) ** 1.6
        wobble = math.sin(2 * math.pi * 5.5 * t) * 18
        body = math.sin(2 * math.pi * (glide + wobble) * t) * 0.26
        shimmer = math.sin(2 * math.pi * (glide * 2.02) * t) * 0.09
        breath = math.exp(-((t - span * 0.35) ** 2) / (2 * 0.16 ** 2))
        out.append((body + shimmer) * breath
                   * _envelope(i, total, 0.08, 0.45))
    return out


def ensure_sounds(folder):
    """
    Make sure the effect files exist. Returns {name: path}.

    Generating on demand means a first play is slightly late; they are a
    few tenths of a second of audio each, so it is not worth a background
    thread to hide.
    """
    folder.mkdir(parents=True, exist_ok=True)
    made = {}
    for name, build in EFFECTS.items():
        path = folder / f"{name}.wav"
        if not path.exists():
            try:
                _write(path, build())
            except OSError:
                continue
        made[name] = path
    return made


class ThemeSounds:
    """
    Plays the theme's effects, when they are switched on.

    Holds one player per effect: creating one per play leaks handles, and
    reusing a single player cuts a sound off when the next one starts.
    """

    def __init__(self, folder):
        self.folder = folder
        self.enabled = False
        self.theme = ""
        self._players = {}
        self._error = ""

    def set_enabled(self, value):
        self.enabled = bool(value)
        if self.enabled:
            self._load()

    def set_theme(self, name):
        """Which theme's sound set to use."""
        self.theme = (name or "").strip().lower()

    def play_event(self, event):
        """
        Play whatever the current theme uses for this moment.

        Callers name the event, never the effect: that is what lets a
        theme swap its whole palette of sounds without a single caller
        changing.
        """
        if not self.enabled:
            return False
        from .themes import canonical
        name = EVENTS.get(canonical(self.theme), {}).get(event)
        if name is None:
            return False
        return self.play(name)

    def _load(self):
        if self._players or self._error:
            return
        try:
            from PySide6.QtMultimedia import QSoundEffect
            from PySide6.QtCore import QUrl
        except ImportError as exc:
            # Qt Multimedia is not always present. Sound is a nicety, so
            # its absence must never stop the app.
            self._error = f"Sound is unavailable: {exc}"
            return
        for name, path in ensure_sounds(self.folder).items():
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(str(path)))
            effect.setVolume(VOLUME.get(name, 0.3))
            self._players[name] = effect

    def play(self, name):
        if not self.enabled:
            return False
        self._load()
        effect = self._players.get(name)
        if effect is None:
            return False
        effect.play()
        return True

    @property
    def error(self):
        return self._error


def _shimmer(total=int(RATE * 1.0)):
    """Airy rising tone: the starfield's equivalent of a door opening."""
    out = []
    for i in range(total):
        t = i / RATE
        span = total / RATE
        glide = 520 + 340 * (i / total)
        a = math.sin(2 * math.pi * glide * t) * 0.16
        b = math.sin(2 * math.pi * glide * 1.5 * t) * 0.09
        c = math.sin(2 * math.pi * glide * 2.01 * t) * 0.05
        swell = math.sin(math.pi * (t / span)) ** 1.4
        out.append((a + b + c) * swell * _envelope(i, total, 0.12, 0.5))
    return out


def _hush(total=int(RATE * 0.9)):
    """The same figure falling away, for stopping."""
    out = []
    for i in range(total):
        t = i / RATE
        span = total / RATE
        glide = 620 - 260 * (i / total)
        a = math.sin(2 * math.pi * glide * t) * 0.15
        b = math.sin(2 * math.pi * glide * 1.5 * t) * 0.07
        out.append((a + b) * math.exp(-t * 2.6)
                   * _envelope(i, total, 0.08, 0.55))
    return out


def _sparkle(total=int(RATE * 1.2)):
    """
    A small cluster of bells, for something finishing.

    Struck at slightly different moments rather than together, which is
    what keeps it from sounding like a single detuned tone.
    """
    out = [0.0] * total
    for index, (freq, delay, level) in enumerate((
            (1318, 0.00, 0.16), (1760, 0.06, 0.12),
            (2093, 0.13, 0.09), (2637, 0.21, 0.06))):
        start = int(delay * RATE)
        for i in range(start, total):
            t = (i - start) / RATE
            out[i] += (math.sin(2 * math.pi * freq * t) * level
                       * math.exp(-t * 4.2))
    return [s * _envelope(i, total, 0.01, 0.4) for i, s in enumerate(out)]


def _blip(total=int(RATE * 0.16)):
    """
    The quietest one: a soft tick for changing page.

    Kept almost featureless on purpose - it plays constantly, and
    anything with character wears out within a minute.
    """
    out = []
    for i in range(total):
        t = i / RATE
        tone = math.sin(2 * math.pi * 880 * t) * 0.16
        out.append(tone * math.exp(-t * 26)
                   * _envelope(i, total, 0.05, 0.6))
    return out


def _aurora(total=int(RATE * 1.8)):
    """The starfield easter egg: a slow swell with a shifting overtone."""
    out = []
    for i in range(total):
        t = i / RATE
        span = total / RATE
        drift = math.sin(2 * math.pi * 0.6 * t) * 26
        base = math.sin(2 * math.pi * (196 + drift) * t) * 0.16
        fifth = math.sin(2 * math.pi * (294 + drift * 1.4) * t) * 0.11
        air = math.sin(2 * math.pi * (784 + drift * 3) * t) * 0.05
        swell = math.sin(math.pi * (t / span)) ** 1.2
        out.append((base + fifth + air) * swell
                   * _envelope(i, total, 0.14, 0.45))
    return out


def _surge(total=int(RATE * 1.0)):
    """Water moving in: filtered noise swelling, over a low body."""
    import random
    rng = random.Random(41)
    out = []
    last = 0.0
    for i in range(total):
        t = i / total
        last += (rng.uniform(-1, 1) - last) * (0.04 + 0.22 * t)
        body = math.sin(2 * math.pi * (70 + 60 * t) * (i / RATE)) * 0.14
        out.append((last * 0.34 + body) * math.sin(math.pi * t) ** 0.8
                   * _envelope(i, total, 0.1, 0.5))
    return out


def _sink(total=int(RATE * 0.9)):
    """The same movement withdrawing, for stopping."""
    import random
    rng = random.Random(43)
    out = []
    last = 0.0
    for i in range(total):
        t = i / total
        last += (rng.uniform(-1, 1) - last) * (0.26 - 0.2 * t)
        body = math.sin(2 * math.pi * (130 - 70 * t) * (i / RATE)) * 0.13
        out.append((last * 0.30 + body) * math.exp(-t * 2.4)
                   * _envelope(i, total, 0.05, 0.55))
    return out


def _sonar(total=int(RATE * 1.4)):
    """
    A ping with two soft echoes.

    The echoes are what place it underwater; the same tone alone is just
    a beep.
    """
    out = [0.0] * total
    for delay, level in ((0.0, 0.20), (0.34, 0.09), (0.66, 0.04)):
        start = int(delay * RATE)
        for i in range(start, total):
            t = (i - start) / RATE
            out[i] += (math.sin(2 * math.pi * 720 * t) * level
                       * math.exp(-t * 7.0))
            out[i] += (math.sin(2 * math.pi * 1080 * t) * level * 0.4
                       * math.exp(-t * 9.0))
    return [s * _envelope(i, total, 0.01, 0.35) for i, s in enumerate(out)]


def _bloop(total=int(RATE * 0.18)):
    """One bubble: the page-change sound, gone before it is noticed."""
    out = []
    for i in range(total):
        t = i / RATE
        # The quick downward glide is what makes it a bloop and not a
        # click.
        freq = 640 - 380 * (i / total)
        out.append(math.sin(2 * math.pi * freq * t) * 0.18
                   * math.exp(-t * 15) * _envelope(i, total, 0.08, 0.6))
    return out


def _whale(total=int(RATE * 2.4)):
    """The easter egg: a long call with a slow bend."""
    out = []
    for i in range(total):
        t = i / RATE
        span = total / RATE
        bend = math.sin(math.pi * (t / span)) ** 1.6
        freq = 150 + 120 * bend + math.sin(2 * math.pi * 0.4 * t) * 14
        a = math.sin(2 * math.pi * freq * t) * 0.18
        b = math.sin(2 * math.pi * freq * 2.01 * t) * 0.07
        c = math.sin(2 * math.pi * freq * 3.02 * t) * 0.03
        out.append((a + b + c) * bend * _envelope(i, total, 0.16, 0.4))
    return out


def _twinkle(total=int(RATE * 0.9)):
    """A bright rising figure, for starting."""
    out = []
    for i in range(total):
        t = i / RATE
        span = total / RATE
        step = int((i / total) * 4)
        freq = (1046, 1318, 1568, 2093)[min(step, 3)]
        tone = math.sin(2 * math.pi * freq * t) * 0.15
        shine = math.sin(2 * math.pi * freq * 2.0 * t) * 0.05
        out.append((tone + shine) * math.sin(math.pi * (t / span)) ** 0.7
                   * _envelope(i, total, 0.04, 0.4))
    return out


def _settle(total=int(RATE * 0.8)):
    """The same figure coming back down, for stopping."""
    out = []
    for i in range(total):
        t = i / RATE
        step = int((i / total) * 4)
        freq = (2093, 1568, 1318, 1046)[min(step, 3)]
        tone = math.sin(2 * math.pi * freq * t) * 0.14
        out.append(tone * math.exp(-t * 2.2)
                   * _envelope(i, total, 0.03, 0.45))
    return out


def _pip(total=int(RATE * 0.14)):
    """
    A tiny bright tick for changing page.

    Short and high: at this length the ear registers it as punctuation
    rather than as a note, which is what something heard constantly
    should be.
    """
    out = []
    for i in range(total):
        t = i / RATE
        out.append(math.sin(2 * math.pi * 1760 * t) * 0.15
                   * math.exp(-t * 30) * _envelope(i, total, 0.06, 0.6))
    return out


def _flutter(total=int(RATE * 1.6)):
    """The easter egg: a little ascending run, then a shimmer."""
    out = [0.0] * total
    notes = ((1046, 0.00), (1318, 0.11), (1568, 0.22), (2093, 0.33))
    for freq, delay in notes:
        start = int(delay * RATE)
        for i in range(start, total):
            t = (i - start) / RATE
            out[i] += (math.sin(2 * math.pi * freq * t) * 0.11
                       * math.exp(-t * 3.4))
    for i in range(total):
        t = i / RATE
        out[i] += (math.sin(2 * math.pi * 2637 * t) * 0.03
                   * math.exp(-t * 1.6)
                   * (0.5 + 0.5 * math.sin(2 * math.pi * 6 * t)))
    return [s * _envelope(i, total, 0.02, 0.4) for i, s in enumerate(out)]


def _drone(total=int(RATE * 1.3)):
    """A low swell with a fifth above it, for starting."""
    out = []
    for i in range(total):
        t = i / RATE
        span = total / RATE
        wobble = math.sin(2 * math.pi * 0.7 * t) * 2.5
        low = math.sin(2 * math.pi * (98 + wobble) * t) * 0.17
        fifth = math.sin(2 * math.pi * (147 + wobble) * t) * 0.09
        air = math.sin(2 * math.pi * 294 * t) * 0.03
        swell = math.sin(math.pi * (t / span)) ** 0.9
        out.append((low + fifth + air) * swell
                   * _envelope(i, total, 0.14, 0.45))
    return out


def _seal(total=int(RATE * 0.7)):
    """A dull stone knock, for stopping."""
    import random
    rng = random.Random(83)
    out = []
    for i in range(total):
        t = i / total
        body = math.sin(2 * math.pi * 116 * (i / RATE)) * 0.34
        grit = rng.uniform(-1, 1) * 0.22 * math.exp(-t * 30)
        out.append((body * math.exp(-t * 9) + grit)
                   * _envelope(i, total, 0.01, 0.5))
    return out


def _cipher(total=int(RATE * 0.15)):
    """A dry tick for changing page: a mark being made."""
    import random
    rng = random.Random(89)
    out = []
    for i in range(total):
        t = i / total
        out.append(rng.uniform(-1, 1) * 0.16 * math.exp(-t * 34)
                   * _envelope(i, total, 0.04, 0.6))
    return out


def _reveal(total=int(RATE * 1.5)):
    """
    Something unlocking: a low note, then a bright one above it.

    The gap between the two is what makes it read as a consequence
    rather than as a chord.
    """
    out = [0.0] * total
    for freq, delay, level, decay in ((174, 0.0, 0.16, 3.0),
                                      (523, 0.18, 0.12, 3.6),
                                      (784, 0.30, 0.07, 4.2)):
        start = int(delay * RATE)
        for i in range(start, total):
            t = (i - start) / RATE
            out[i] += (math.sin(2 * math.pi * freq * t) * level
                       * math.exp(-t * decay))
    return [s * _envelope(i, total, 0.02, 0.38) for i, s in enumerate(out)]


def _whisper(total=int(RATE * 2.0)):
    """The easter egg: breath with a voice half-buried in it."""
    import random
    rng = random.Random(97)
    out = []
    last = 0.0
    for i in range(total):
        t = i / RATE
        span = total / RATE
        last += (rng.uniform(-1, 1) - last) * 0.16
        voice = math.sin(2 * math.pi * (128 + math.sin(t * 3) * 18) * t)
        shape = math.sin(math.pi * (t / span)) ** 1.3
        out.append((last * 0.22 + voice * 0.05) * shape
                   * _envelope(i, total, 0.12, 0.45))
    return out


def _gloss(total=int(RATE * 1.0)):
    """A clean glassy swell, for starting."""
    out = []
    for i in range(total):
        t = i / RATE
        span = total / RATE
        glide = 660 + 180 * (i / total)
        a = math.sin(2 * math.pi * glide * t) * 0.13
        b = math.sin(2 * math.pi * glide * 1.5 * t) * 0.07
        c = math.sin(2 * math.pi * glide * 3.0 * t) * 0.03
        out.append((a + b + c) * math.sin(math.pi * (t / span)) ** 0.8
                   * _envelope(i, total, 0.08, 0.45))
    return out


def _dim(total=int(RATE * 0.85)):
    """The same gloss withdrawing, for stopping."""
    out = []
    for i in range(total):
        t = i / RATE
        glide = 760 - 220 * (i / total)
        a = math.sin(2 * math.pi * glide * t) * 0.13
        b = math.sin(2 * math.pi * glide * 1.5 * t) * 0.05
        out.append((a + b) * math.exp(-t * 2.6)
                   * _envelope(i, total, 0.05, 0.5))
    return out


def _droplet(total=int(RATE * 0.2)):
    """
    A single drop landing: the page-change sound.

    The pitch rises rather than falls, which is what a drop into water
    actually does and what separates it from a plain click.
    """
    out = []
    for i in range(total):
        t = i / RATE
        freq = 700 + 900 * (i / total) ** 2
        out.append(math.sin(2 * math.pi * freq * t) * 0.15
                   * math.exp(-t * 20) * _envelope(i, total, 0.05, 0.6))
    return out


def _gleam(total=int(RATE * 1.3)):
    """A bright rising sparkle over a soft pad, for a finished image."""
    out = [0.0] * total
    for freq, delay, level in ((1568, 0.0, 0.12), (2093, 0.09, 0.10),
                               (2637, 0.18, 0.07), (3136, 0.27, 0.04)):
        start = int(delay * RATE)
        for i in range(start, total):
            t = (i - start) / RATE
            out[i] += (math.sin(2 * math.pi * freq * t) * level
                       * math.exp(-t * 4.6))
    for i in range(total):
        t = i / RATE
        out[i] += math.sin(2 * math.pi * 523 * t) * 0.05 * math.exp(-t * 2.2)
    return [s * _envelope(i, total, 0.02, 0.38) for i, s in enumerate(out)]


def _breeze(total=int(RATE * 1.9)):
    """The easter egg: air moving past, with a bright tail."""
    import random
    rng = random.Random(113)
    out = []
    last = 0.0
    for i in range(total):
        t = i / total
        last += (rng.uniform(-1, 1) - last) * (0.06 + 0.3 * t)
        sheen = math.sin(2 * math.pi * (900 + 600 * t) * (i / RATE)) * 0.05 * t
        out.append((last * 0.3 + sheen) * math.sin(math.pi * t) ** 0.9
                   * _envelope(i, total, 0.1, 0.45))
    return out


def _gust(total=int(RATE * 1.2)):
    """Wind rising: filtered noise that opens out, for starting."""
    import random
    rng = random.Random(151)
    out = []
    last = 0.0
    for i in range(total):
        t = i / total
        last += (rng.uniform(-1, 1) - last) * (0.05 + 0.30 * t)
        body = math.sin(2 * math.pi * (86 + 40 * t) * (i / RATE)) * 0.08
        out.append((last * 0.36 + body) * math.sin(math.pi * t) ** 0.8
                   * _envelope(i, total, 0.12, 0.48))
    return out


def _lull(total=int(RATE * 1.0)):
    """The wind dropping away, for stopping."""
    import random
    rng = random.Random(157)
    out = []
    last = 0.0
    for i in range(total):
        t = i / total
        last += (rng.uniform(-1, 1) - last) * (0.30 - 0.24 * t)
        out.append(last * 0.30 * math.exp(-t * 2.2)
                   * _envelope(i, total, 0.06, 0.5))
    return out


def _grit(total=int(RATE * 0.16)):
    """
    Sand shifting: the page-change tick.

    Pure noise with a fast decay - no pitch at all, because anything
    tonal would sound like an instrument rather than a surface.
    """
    import random
    rng = random.Random(163)
    out = []
    last = 0.0
    for i in range(total):
        t = i / total
        last += (rng.uniform(-1, 1) - last) * 0.55
        out.append(last * 0.20 * math.exp(-t * 22)
                   * _envelope(i, total, 0.05, 0.6))
    return out


def _gong(total=int(RATE * 1.8)):
    """
    A struck bell, far off, for a finished image.

    Detuned partials rather than exact harmonics: a real strike is never
    perfectly in tune with itself, and the slight beating is what makes
    it sound like metal instead of a sine wave.
    """
    out = [0.0] * total
    for freq, level, decay in ((196, 0.15, 1.6), (293.5, 0.09, 2.0),
                               (392, 0.06, 2.6), (588.7, 0.035, 3.2)):
        for i in range(total):
            t = i / RATE
            out[i] += (math.sin(2 * math.pi * freq * t) * level
                       * math.exp(-t * decay))
    return [s * _envelope(i, total, 0.01, 0.42) for i, s in enumerate(out)]


def _flute(total=int(RATE * 2.1)):
    """The easter egg: a breathy reed line that bends."""
    import random
    rng = random.Random(167)
    out = []
    last = 0.0
    steps = (392, 440, 466, 440, 392, 349)
    for i in range(total):
        t = i / RATE
        span = total / RATE
        step = min(len(steps) - 1, int((i / total) * len(steps)))
        freq = steps[step] + math.sin(2 * math.pi * 5 * t) * 5
        tone = math.sin(2 * math.pi * freq * t) * 0.14
        last += (rng.uniform(-1, 1) - last) * 0.4
        breath = last * 0.05
        out.append((tone + breath) * math.sin(math.pi * (t / span)) ** 0.6
                   * _envelope(i, total, 0.1, 0.4))
    return out


def _frostfall(total=int(RATE * 1.1)):
    """A cold swell with a high glassy edge, for starting."""
    out = []
    for i in range(total):
        t = i / RATE
        span = total / RATE
        low = math.sin(2 * math.pi * (140 + 50 * (i / total)) * t) * 0.10
        ring = math.sin(2 * math.pi * 1244 * t) * 0.05
        shine = math.sin(2 * math.pi * 1864 * t) * 0.025
        out.append((low + ring + shine)
                   * math.sin(math.pi * (t / span)) ** 0.8
                   * _envelope(i, total, 0.1, 0.45))
    return out


def _thaw(total=int(RATE * 0.9)):
    """The same cold tone settling, for stopping."""
    out = []
    for i in range(total):
        t = i / RATE
        low = math.sin(2 * math.pi * (190 - 70 * (i / total)) * t) * 0.12
        ring = math.sin(2 * math.pi * 932 * t) * 0.04
        out.append((low + ring) * math.exp(-t * 2.4)
                   * _envelope(i, total, 0.05, 0.5))
    return out


def _crunch(total=int(RATE * 0.14)):
    """
    A footstep in snow: the page tick.

    Noise shaped by a very fast decay - compacting snow has no pitch at
    all, and any tone would turn it into an instrument.
    """
    import random
    rng = random.Random(211)
    out = []
    last = 0.0
    for i in range(total):
        t = i / total
        last += (rng.uniform(-1, 1) - last) * 0.62
        out.append(last * 0.20 * math.exp(-t * 26)
                   * _envelope(i, total, 0.04, 0.6))
    return out


def _chime_ice(total=int(RATE * 1.4)):
    """
    Ice struck: bright, glassy, with a long thin tail.

    High partials and almost no fundamental, which is what separates
    something brittle from something metal.
    """
    out = [0.0] * total
    for freq, level, decay in ((1568, 0.11, 2.4), (2093, 0.08, 2.9),
                               (2637, 0.05, 3.4), (3520, 0.03, 4.0)):
        for i in range(total):
            t = i / RATE
            out[i] += (math.sin(2 * math.pi * freq * t) * level
                       * math.exp(-t * decay))
    return [s * _envelope(i, total, 0.01, 0.4) for i, s in enumerate(out)]


def _call(total=int(RATE * 1.5)):
    """The easter egg: a short braying call, with a rasp in it."""
    import random
    rng = random.Random(223)
    out = []
    last = 0.0
    for i in range(total):
        t = i / RATE
        span = total / RATE
        warble = math.sin(2 * math.pi * 7 * t) * 30
        freq = 420 + warble + 90 * math.sin(math.pi * (t / span))
        tone = math.sin(2 * math.pi * freq * t) * 0.13
        last += (rng.uniform(-1, 1) - last) * 0.5
        out.append((tone + last * 0.04)
                   * math.sin(math.pi * (t / span)) ** 0.5
                   * _envelope(i, total, 0.06, 0.4))
    return out


EFFECTS = {"creak": _creak, "whoosh": _whoosh, "chime": _chime,
           "latch": _latch, "rustle": _rustle, "wisp": _wisp,
           "shimmer": _shimmer, "hush": _hush, "sparkle": _sparkle,
           "blip": _blip, "aurora": _aurora,
           "surge": _surge, "sink": _sink, "sonar": _sonar,
           "bloop": _bloop, "whale": _whale,
           "twinkle": _twinkle, "settle": _settle, "pip": _pip,
           "flutter": _flutter,
           "drone": _drone, "seal": _seal, "cipher": _cipher,
           "reveal": _reveal, "whisper": _whisper,
           "gloss": _gloss, "dim": _dim, "droplet": _droplet,
           "gleam": _gleam, "breeze": _breeze,
           "gust": _gust, "lull": _lull, "grit": _grit,
           "gong": _gong, "flute": _flute,
           "frostfall": _frostfall, "thaw": _thaw, "crunch": _crunch,
           "chime_ice": _chime_ice, "call": _call}

# What each theme plays for a given moment. The window asks for the
# event - "listening started" - and the theme decides what that sounds
# like, so a door creak never turns up in a starfield.
EVENTS = {
    "halloween": {
        "listen_start": "creak",
        "listen_stop": "latch",
        "cleared": "whoosh",
        "image": "chime",
        "page": "rustle",
        "rare": "creak",
        "egg": "wisp",
    },
    "starfield": {
        "listen_start": "shimmer",
        "listen_stop": "hush",
        "cleared": "whoosh",
        "image": "sparkle",
        "page": "blip",
        "rare": "shimmer",
        "egg": "aurora",
    },
    "underwater": {
        "listen_start": "surge",
        "listen_stop": "sink",
        "cleared": "whoosh",
        "image": "sonar",
        "page": "bloop",
        "rare": "sonar",
        "egg": "whale",
    },
    "kawaii": {
        "listen_start": "twinkle",
        "listen_stop": "settle",
        "cleared": "whoosh",
        "image": "sparkle",
        "page": "pip",
        "rare": "twinkle",
        "egg": "flutter",
    },
    "cryptic": {
        "listen_start": "drone",
        "listen_stop": "seal",
        "cleared": "whoosh",
        "image": "reveal",
        "page": "cipher",
        "rare": "whisper",
        "egg": "whisper",
    },
    "aero": {
        "listen_start": "gloss",
        "listen_stop": "dim",
        "cleared": "whoosh",
        "image": "gleam",
        "page": "droplet",
        "rare": "breeze",
        "egg": "breeze",
    },
    "desert": {
        "listen_start": "gust",
        "listen_stop": "lull",
        "cleared": "whoosh",
        "image": "gong",
        "page": "grit",
        "rare": "flute",
        "egg": "flute",
    },
    "arctic": {
        "listen_start": "frostfall",
        "listen_stop": "thaw",
        "cleared": "whoosh",
        "image": "chime_ice",
        "page": "crunch",
        "rare": "call",
        "egg": "call",
    },
}

# How loud each one is. Frequent sounds are quiet; the rare ones may
# speak up. A panel change that announced itself at full volume would be
# unbearable after ten minutes.
VOLUME = {"creak": 0.30, "whoosh": 0.26, "chime": 0.28,
          "latch": 0.24, "rustle": 0.11, "wisp": 0.34,
          "shimmer": 0.26, "hush": 0.24, "sparkle": 0.24,
          "blip": 0.09, "aurora": 0.30,
          "surge": 0.26, "sink": 0.24, "sonar": 0.22,
          "bloop": 0.10, "whale": 0.30,
          "twinkle": 0.24, "settle": 0.22, "pip": 0.08,
          "flutter": 0.28,
          "drone": 0.26, "seal": 0.24, "cipher": 0.09,
          "reveal": 0.24, "whisper": 0.28,
          "gloss": 0.24, "dim": 0.22, "droplet": 0.09,
          "gleam": 0.22, "breeze": 0.26,
          "gust": 0.26, "lull": 0.24, "grit": 0.09,
          "gong": 0.26, "flute": 0.26,
          "frostfall": 0.25, "thaw": 0.23, "crunch": 0.09,
          "chime_ice": 0.22, "call": 0.26}
