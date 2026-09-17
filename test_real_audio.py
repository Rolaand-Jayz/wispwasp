"""
End-to-end test of the one path that has never run for real.

Windows SAPI speaks a known sentence through the default output device.
The loopback recorder captures it, faster-whisper transcribes it, and the
result is compared against what was said. This covers WASAPI loopback
capture, model loading, transcription accuracy and prompt building - none
of which the fake-backed tests touch.
"""
import subprocess
import sys
import threading
import time
from pathlib import Path

from avcore.audio import Recorder, list_devices
from avcore.config import Settings
from avcore.speech import Transcriber, build_prompt, is_junk

SENTENCE = (
    "the old stone lighthouse stands above a cold grey sea while three "
    "fishing boats return to the harbour before the storm arrives"
)

PS = f'''
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = 0
$s.Volume = 100
Start-Sleep -Milliseconds 900
$s.Speak("{SENTENCE}")
'''


def speak():
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", PS],
                   capture_output=True)


s = Settings.load()
print("devices:")
for d in list_devices():
    print(f"   {d['name'][:50]}", "(default)" if d.get("is_default") else "")

print("\nloading the speech model (first run is slow)...")
t = time.time()
tr = Transcriber(model=s.get("speech.model", "small.en"),
                 cpu_threads=int(s.get("speech.cpu_threads", 4)),
                 beam_size=int(s.get("speech.beam_size", 5)))
print(f"   loaded in {time.time() - t:.1f}s")

rec = Recorder(s.get("audio.device_name"))
clip = Path("_realaudio.wav")

print("\nspeaking and recording at the same time...")
voice = threading.Thread(target=speak, daemon=True)
voice.start()

t = time.time()
rms = rec.record(clip, 12)
print(f"   recorded 12s in {time.time() - t:.1f}s, level {rms}")
voice.join(timeout=5)

if rms is None:
    print("\nFAILED: nothing was recorded")
    sys.exit(1)
if rms < int(s.get("audio.silence_rms", 250)):
    print(f"\nFAILED: level {rms} is below the silence gate - the loopback "
          "device captured nothing. Is the default output the one playing?")
    sys.exit(1)

print("\ntranscribing...")
t = time.time()
text = tr.transcribe(clip)
took = time.time() - t
print(f"   done in {took:.1f}s")
print(f"\n   said:  {SENTENCE}")
print(f"   heard: {text}")

# Word overlap is the fair measure here. Whisper gets punctuation and the
# odd word wrong on synthetic speech, and demanding an exact match would
# fail for reasons that do not matter.
said = set(SENTENCE.lower().split())
heard = set(text.lower().replace(",", "").replace(".", "").split())
hit = said & heard
ratio = len(hit) / len(said) if said else 0
print(f"\n   matched {len(hit)}/{len(said)} words ({ratio:.0%})")
missed = said - heard
if missed:
    print(f"   missed: {sorted(missed)}")

junk, reason = is_junk(text, int(s.get("speech.min_words", 3)))
print(f"   junk filter: {'REJECTED - ' + reason if junk else 'accepted'}")

prompt = build_prompt(
    text,
    style_suffix=s.get("image.style_suffix", ""),
    max_chars=int(s.get("speech.max_prompt_chars", 400)),
    min_words=int(s.get("speech.min_words", 3)),
)
print(f"\n   prompt: {prompt}")

clip.unlink(missing_ok=True)

ok = True
if ratio < 0.6:
    print("\nFAILED: too many words missed to call this working")
    ok = False
if junk:
    print("\nFAILED: real speech was rejected as junk")
    ok = False
if prompt is None:
    print("\nFAILED: no prompt was built from real speech")
    ok = False
if text.strip() and text.strip() not in (prompt or ""):
    print("\nFAILED: the prompt is not verbatim")
    ok = False

print("\nreal audio path works end to end" if ok else "\nreal audio path is broken")
sys.exit(0 if ok else 1)
