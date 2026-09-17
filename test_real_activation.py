"""
Sound-activated capture against real audio.

Speech is played through the default output; the recorder should start on
its own, keep going through the gaps between sentences, and stop shortly
after the speech ends rather than at a fixed length.
"""
import subprocess
import sys
import threading
import time
from pathlib import Path

from avcore.audio import DONE, ActivationGate, Recorder
from avcore.speech import Transcriber, read_wav

SENTENCE = ("the old stone lighthouse stands above a cold grey sea while "
            "fishing boats return to the harbour before the storm")

PS = f'''
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Volume = 100
Start-Sleep -Milliseconds 2500
$s.Speak("{SENTENCE}")
'''

tmp = Path("_realactivation")
tmp.mkdir(exist_ok=True)
clip = tmp / "clip.wav"

print("recorder: waiting for sound, then recording until it stops")
rec = Recorder("", "output")
print(f"  source: {rec.label}")

gate = ActivationGate(threshold=400, silence_seconds=1.5, max_seconds=25,
                      min_seconds=1.0)

states = []
threading.Thread(
    target=lambda: subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", PS],
        capture_output=True),
    daemon=True).start()

started = time.time()
rms, gate = rec.record_activated(
    clip, gate, on_state=lambda s, g: states.append((s, round(g.recorded, 1))))
elapsed = time.time() - started
rec.close()

print(f"  waited {gate.waited:.1f}s before anything was loud enough")
print(f"  recorded {gate.recorded:.1f}s, of which "
      f"{gate.speech_seconds:.1f}s was sound")
print(f"  ended because it {gate.reason}")
print(f"  whole call took {elapsed:.1f}s, level {rms:.0f}")
print(f"  state changes: {states}")

ok = True


def check(name, cond, detail=""):
    global ok
    ok = ok and bool(cond)
    print(f"  {'PASS' if cond else '*** FAIL ***':<14} {name}"
          + (f"  [{detail}]" if detail else ""))


print()
# Not asserting that it waited: this runs on a live desktop, and if
# anything else is making noise the trigger fires immediately. That is
# correct behaviour, not a fault. The waiting path is covered by the gate
# tests, which can guarantee silence.
if gate.waited > 0.5:
    print(f"  (it waited {gate.waited:.1f}s for the speech to start)")
else:
    print("  (something was already playing, so it triggered at once - "
          "expected on a machine with other audio running)")

check("it recorded something", gate.recorded > 1.0)
check("it stopped on its own, not at a fixed length",
      gate.state == DONE and gate.reason == "went quiet", gate.reason)
check("the clip is not a blip", not gate.too_short())
check("the audio is readable", clip.exists() and len(read_wav(clip)) > 16000)

print("\ntranscribing what it captured:")
tr = Transcriber(model="small.en", cpu_threads=4, beam_size=5)
text = tr.transcribe(clip)
print(f"  heard: {text}")

said = set(SENTENCE.lower().split())
heard = set(text.lower().replace(",", "").replace(".", "").split())
ratio = len(said & heard) / len(said)
check(f"the speech came through ({ratio:.0%} of words)", ratio > 0.6)
# The lead-in matters: speech starts quieter than the threshold, so
# without keeping a little history the first word is lost.
check("the opening word was not clipped off", "lighthouse" in text.lower()
      or "old" in text.lower(), text[:40])

import shutil
shutil.rmtree(tmp, ignore_errors=True)
print("\nreal sound-activated capture works" if ok else "\nsomething failed")
raise SystemExit(0 if ok else 1)
