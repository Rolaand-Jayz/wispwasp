"""
Stubs for --demo: exercises the whole UI with no GPU, audio or ComfyUI.

Images are written with a tiny stdlib PNG encoder rather than Pillow, so
demo mode has no dependency of its own.
"""

import math
import random
import struct
import time
import zlib


def write_png(path, width, height, rgb):
    """Minimal solid-colour PNG. Enough to prove the preview pipeline."""
    r, g, b = rgb
    raw = b"".join(
        b"\x00" + bytes([r, g, b]) * width for _ in range(height))

    def chunk(tag, data):
        body = tag + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR",
                 struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6))
    png += chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


LINES = [
    "so the thing about the boss fight is you have to bait the second phase",
    "chat is saying the audio is quiet again, is it quiet",
    "I genuinely did not know you could climb that wall",
    "we are going to run it back one more time and then call it",
    "somebody clip that, that was ridiculous",
]


class DemoBackend:
    extension = "png"

    def generate(self, prompt, dest, seed=None, cancel=None):
        # Roughly a real render, and interruptible so Cancel is testable.
        for _ in range(24):
            if cancel and cancel():
                from avcore.images import GenerationError
                raise GenerationError("cancelled")
            time.sleep(0.1)
        hue = (abs(hash(prompt)) % 360) / 360.0
        rgb = tuple(int(90 + 120 * abs(((hue * 3 + o) % 1.0) * 2 - 1))
                    for o in (0.0, 0.33, 0.66))
        write_png(dest, 640, 360, rgb)
        return dest

    def interrupt(self):
        pass

    def is_up(self, timeout=4):
        return True

    def list_checkpoints(self):
        return ["demo_model.safetensors"]

    def checkpoint(self):
        return "demo_model.safetensors"


class DemoRecorder:
    name = "Demo output (loopback)"

    # Signature mirrors the real Recorder, on_level included - demo mode
    # should exercise the level meter too, not just the happy path.
    def record(self, path, seconds, cancel=None, on_level=None):
        steps = int(seconds * 20)
        for i in range(steps):
            if cancel and cancel():
                return None
            if on_level:
                # A plausible speech envelope rather than a flat line, so
                # the meter looks like audio instead of a static bar.
                phase = i / max(1, steps)
                wobble = abs(math.sin(phase * 9)) * 0.7 + 0.3
                on_level(900 + 4200 * wobble * random.uniform(0.7, 1.0))
            time.sleep(0.05)
        return 5000


class DemoTranscriber:
    def transcribe(self, path):
        # Occasionally return junk so the skip path gets exercised too.
        if random.random() < 0.25:
            return random.choice(["Thank you.", "we are, we are, we are"])
        return random.choice(LINES)


def install_stubs(engine, autostart=False):
    engine._backend = DemoBackend()
    engine._recorder = DemoRecorder()
    engine._transcriber = DemoTranscriber()
    engine._ensure_ready = lambda: None
    engine.s.set("audio.record_seconds", 3)
    engine.s.set("audio.cycle_seconds", 6)
    if autostart:
        engine.start_listening()
