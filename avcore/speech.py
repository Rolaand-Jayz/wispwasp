"""Speech to text, plus turning a transcript into a usable image prompt."""

import re
import wave

import numpy as np
from faster_whisper import WhisperModel

# Whisper wants 16 kHz mono float32 in the range -1..1.
WHISPER_RATE = 16000


def read_wav(path):
    """
    Load a WAV file as the float32 array Whisper expects.

    Reading it here rather than handing over a filename means faster-whisper
    never has to decode anything, so the app does not depend on a full media
    stack just to open a file it wrote itself.
    """
    with wave.open(str(path), "rb") as w:
        channels = w.getnchannels()
        width = w.getsampwidth()
        rate = w.getframerate()
        frames = w.readframes(w.getnframes())

    if width == 2:
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
        audio /= 32768.0
    elif width == 4:
        audio = np.frombuffer(frames, dtype=np.int32).astype(np.float32)
        audio /= 2147483648.0
    elif width == 1:
        # 8-bit WAV is unsigned, centred on 128.
        audio = np.frombuffer(frames, dtype=np.uint8).astype(np.float32)
        audio = (audio - 128.0) / 128.0
    else:
        raise ValueError(f"unsupported sample width: {width} bytes")

    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)

    if rate != WHISPER_RATE:
        # Linear resample. The source is a local loopback capture at a
        # known rate, so there is no need for a polyphase filter here.
        count = int(round(len(audio) * WHISPER_RATE / rate))
        if count > 0:
            audio = np.interp(
                np.linspace(0, len(audio) - 1, count, dtype=np.float64),
                np.arange(len(audio), dtype=np.float64),
                audio,
            ).astype(np.float32)

    return np.ascontiguousarray(audio, dtype=np.float32)


# Whisper reliably invents these when fed silence or music.
HALLUCINATIONS = {
    "you", "thank you", "thanks for watching", "thank you for watching",
    "bye", "bye bye", "subscribe", "please subscribe", "okay", "so",
    "thanks", "the end", "music", "applause", "outro", "intro",
    "thank you very much", "thanks for listening",
}

# Anything shorter than this can't be judged for repetition reliably.
_REPEAT_MIN_WORDS = 8
_REPEAT_RATIO = 0.35


def looks_repetitive(text):
    """Catch Whisper's stuck-loop output, e.g. 'we are, we are, we are...'."""
    words = text.lower().split()
    if len(words) < _REPEAT_MIN_WORDS:
        return False
    return len(set(words)) / len(words) < _REPEAT_RATIO


def is_junk(text, min_words=3):
    """
    True when a transcript isn't worth generating from.

    Returns (junk, reason) so the UI can say why a cycle was skipped.
    """
    bare = re.sub(r"[^\w\s']", "", text.lower()).strip()
    if not bare:
        return True, "nothing said"
    if bare in HALLUCINATIONS:
        return True, "filler phrase"
    if len(bare.split()) < min_words:
        return True, "too short"
    if looks_repetitive(bare):
        return True, "repetition loop"
    return False, ""


def build_prompt(text, style_suffix="", max_chars=400, min_words=3):
    """
    Turn a transcript into a prompt, verbatim.

    The speech is passed through untouched apart from whitespace tidying and
    the length cap - no filler stripping, no reordering. Returns None when
    the transcript is junk.
    """
    prompt = " ".join((text or "").split())
    if not prompt:
        return None

    junk, _reason = is_junk(prompt, min_words)
    if junk:
        return None

    if len(prompt) > max_chars:
        prompt = prompt[:max_chars].rsplit(" ", 1)[0]

    if style_suffix:
        prompt = f"{prompt}, {style_suffix}"
    return prompt


class Transcriber:
    """Wraps faster-whisper with the settings that made it accurate."""

    def __init__(self, model="small.en", cpu_threads=4, beam_size=5):
        self.model_name = model
        self.beam_size = beam_size
        self.model = WhisperModel(
            model, device="cpu", compute_type="int8", cpu_threads=cpu_threads
        )

    def transcribe(self, path):
        # Decoded here rather than by faster-whisper, so a media stack is
        # never involved in reading our own recording.
        audio = read_wav(path)
        segments, _info = self.model.transcribe(
            audio,
            beam_size=self.beam_size,
            language="en",
            temperature=0.0,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300),
            condition_on_previous_text=False,
        )
        return " ".join(s.text.strip() for s in segments).strip()
