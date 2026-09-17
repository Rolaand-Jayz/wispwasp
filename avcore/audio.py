"""System audio capture. Enumerates capture sources and records clips."""

import wave

import numpy as np
import pyaudiowpatch as pyaudio

# What a source is. "output" listens in on something playing through a
# speaker or headset; "input" is a microphone or line in.
OUTPUT = "output"
INPUT = "input"

# What the gate is doing, moment to moment.
WAITING = "waiting"      # armed, nothing loud enough yet
RECORDING = "recording"  # capturing
DONE = "done"            # finished, for one of the reasons below


class ActivationGate:
    """
    Decides when a sound-triggered clip starts and stops.

    Kept apart from the recorders because both the ordinary one and the
    per-application one need identical behaviour, and because a state
    machine driven by a level is far easier to test on its own than
    through a live audio stream.

    It waits for something above the threshold, records while sound
    continues, and ends the clip once it has been quiet for long enough -
    or when the maximum length is reached, so a noisy room cannot record
    forever.
    """

    def __init__(self, threshold, silence_seconds=2.0, max_seconds=30.0,
                 min_seconds=1.0):
        self.threshold = float(threshold)
        self.silence_seconds = float(silence_seconds)
        self.max_seconds = float(max_seconds)
        self.min_seconds = float(min_seconds)

        self.state = WAITING
        self.reason = ""
        self.recorded = 0.0      # seconds captured so far
        self.quiet_for = 0.0     # seconds below the threshold
        self.waited = 0.0        # seconds spent waiting for a sound

    def feed(self, rms, dt):
        """Advance by one chunk. Returns the current state."""
        loud = rms >= self.threshold

        if self.state == WAITING:
            self.waited += dt
            if loud:
                self.state = RECORDING
                self.recorded = dt
                self.quiet_for = 0.0
            return self.state

        if self.state == RECORDING:
            self.recorded += dt
            self.quiet_for = 0.0 if loud else self.quiet_for + dt

            if self.recorded >= self.max_seconds:
                self.state = DONE
                self.reason = "reached the maximum length"
            elif (self.quiet_for >= self.silence_seconds
                  and self.recorded >= self.min_seconds):
                self.state = DONE
                self.reason = "went quiet"
        return self.state

    @property
    def speech_seconds(self):
        """Length without the trailing silence that ended it."""
        return max(0.0, self.recorded - self.quiet_for)

    def too_short(self):
        """
        True when what was captured is not worth transcribing.

        A door closing or a mouse click clears the threshold briefly; a
        minimum length keeps those from becoming prompts.
        """
        return self.speech_seconds < self.min_seconds



def list_devices(kind=None):
    """
    Every device that can be captured from.

    Returns dicts: index, name, kind, rate, channels, is_default. `kind`
    filters to OUTPUT or INPUT; the default returns both, outputs first,
    since listening in on playback is the usual case.
    """
    pa = pyaudio.PyAudio()
    try:
        wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_out = pa.get_device_info_by_index(
            wasapi["defaultOutputDevice"])["name"]
        try:
            default_in = pa.get_device_info_by_index(
                wasapi["defaultInputDevice"])["name"]
        except Exception:
            default_in = ""

        outputs, inputs = [], []
        for i in range(pa.get_device_count()):
            d = pa.get_device_info_by_index(i)
            if d["maxInputChannels"] < 1:
                continue
            if d["hostApi"] != wasapi["index"]:
                continue
            loopback = bool(d.get("isLoopbackDevice"))
            entry = {
                "index": d["index"],
                "name": d["name"],
                "kind": OUTPUT if loopback else INPUT,
                "rate": int(d["defaultSampleRate"]),
                "channels": d["maxInputChannels"],
                "is_default": (default_out in d["name"] if loopback
                               else d["name"] == default_in),
            }
            (outputs if loopback else inputs).append(entry)

        both = outputs + inputs
        if kind:
            return [d for d in both if d["kind"] == kind]
        return both
    finally:
        pa.terminate()


def resolve_device(pa, wanted="", kind=OUTPUT):
    """
    Find a capture device.

    `wanted` is matched as a case-insensitive substring; blank falls back
    to the current Windows default for that kind. A microphone and a
    loopback device can share a name - "Razer Kraken V4 X" is both - so
    the kind is matched first, which is why it is stored alongside the
    name rather than being guessed from it.
    """
    devices = []
    wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
    for i in range(pa.get_device_count()):
        d = pa.get_device_info_by_index(i)
        if d["maxInputChannels"] < 1 or d["hostApi"] != wasapi["index"]:
            continue
        is_loop = bool(d.get("isLoopbackDevice"))
        if (kind == OUTPUT) == is_loop:
            devices.append(d)

    if not devices:
        if kind == OUTPUT:
            raise RuntimeError(
                "No loopback devices found. PyAudioWPatch must be installed "
                "instead of plain PyAudio."
            )
        raise RuntimeError("No microphones or line inputs were found.")

    if wanted:
        q = wanted.lower()
        for d in devices:
            if q in d["name"].lower():
                return d
        # Fall through to the default rather than failing outright, so a
        # renamed or unplugged device doesn't stop the app from starting.
        print(f"[audio] '{wanted}' not found; using the default {kind}")

    if kind == OUTPUT:
        default_name = pa.get_device_info_by_index(
            wasapi["defaultOutputDevice"])["name"]
    else:
        try:
            default_name = pa.get_device_info_by_index(
                wasapi["defaultInputDevice"])["name"]
        except Exception:
            default_name = ""
    for d in devices:
        if default_name and default_name in d["name"]:
            return d
    return devices[0]


class Recorder:
    """Holds a PyAudio instance and records fixed-length clips from it."""

    def __init__(self, device_name="", kind=OUTPUT):
        self.pa = pyaudio.PyAudio()
        self.kind = kind or OUTPUT
        self.device = resolve_device(self.pa, device_name, self.kind)

    @property
    def name(self):
        return self.device["name"]

    @property
    def label(self):
        """Name with the kind spelled out, for the status line."""
        what = "microphone" if self.kind == INPUT else "output"
        return f"{self.device['name']}  ({what})"

    def record(self, path, seconds, cancel=None, on_level=None):
        """
        Record `seconds` of audio to `path` (WAV). Returns the RMS level.

        `cancel` may be a callable returning True to abort early, so the GUI
        can stop mid-clip instead of waiting out the full window.

        `on_level` is called with the RMS of each chunk as it arrives. That
        is what lets the window show a live meter, so a muted device looks
        different from a silent one rather than both looking like nothing
        happening.
        """
        rate = int(self.device["defaultSampleRate"])
        channels = self.device["maxInputChannels"]
        chunk = 1024

        stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            input=True,
            input_device_index=self.device["index"],
            frames_per_buffer=chunk,
        )
        frames = []
        # Report roughly 20 times a second rather than per chunk, which at
        # 48 kHz would be about 47 callbacks a second for no visible gain.
        every = max(1, int(rate / chunk / 20))
        try:
            for i in range(int(rate / chunk * seconds)):
                if cancel and cancel():
                    break
                buf = stream.read(chunk, exception_on_overflow=False)
                frames.append(buf)
                if on_level and i % every == 0:
                    block = np.frombuffer(buf, dtype=np.int16)
                    if block.size:
                        block = block.astype(np.float32)
                        on_level(float(np.sqrt(np.mean(block * block))))
        finally:
            stream.stop_stream()
            stream.close()

        data = b"".join(frames)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(self.pa.get_sample_size(pyaudio.paInt16))
            wf.setframerate(rate)
            wf.writeframes(data)

        # audioop was removed in Python 3.13, so RMS is computed with numpy.
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        if samples.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples * samples)))

    def record_activated(self, path, gate, cancel=None, on_level=None,
                         on_state=None):
        """
        Record when sound starts, and stop when it stops.

        `gate` is an ActivationGate deciding the boundaries. Returns
        (rms, gate) so the caller can see why the clip ended and whether
        it was long enough to bother with.

        Audio from just before the trigger is kept: speech almost always
        begins quieter than the threshold, and without a little history
        the first word is clipped off every time.
        """
        rate = int(self.device["defaultSampleRate"])
        channels = self.device["maxInputChannels"]
        chunk = 1024
        dt = chunk / rate
        lead_chunks = max(1, int(0.35 / dt))

        stream = self.pa.open(
            format=pyaudio.paInt16, channels=channels, rate=rate,
            input=True, input_device_index=self.device["index"],
            frames_per_buffer=chunk,
        )

        from collections import deque
        lead = deque(maxlen=lead_chunks)
        frames = []
        last_state = None
        try:
            while True:
                if cancel and cancel():
                    break
                buf = stream.read(chunk, exception_on_overflow=False)
                block = np.frombuffer(buf, dtype=np.int16)
                rms = 0.0
                if block.size:
                    b = block.astype(np.float32)
                    rms = float(np.sqrt(np.mean(b * b)))
                if on_level:
                    on_level(rms)

                state = gate.feed(rms, dt)
                if state != last_state:
                    last_state = state
                    if on_state:
                        on_state(state, gate)

                if state == WAITING:
                    lead.append(buf)
                    continue
                if not frames:
                    frames.extend(lead)      # the run-up to the trigger
                frames.append(buf)
                if state == DONE:
                    break
        finally:
            stream.stop_stream()
            stream.close()

        data = b"".join(frames)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(self.pa.get_sample_size(pyaudio.paInt16))
            wf.setframerate(rate)
            wf.writeframes(data)

        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        rms = (float(np.sqrt(np.mean(samples * samples)))
               if samples.size else 0.0)
        return rms, gate

    def close(self):
        try:
            self.pa.terminate()
        except Exception:
            pass
