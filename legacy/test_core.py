"""Checks config round-tripping and audio device enumeration."""
import json
from pathlib import Path

from avcore.config import DEFAULTS, Settings
from avcore import audio

print("=== config ===")
tmp = Path("_test_settings.json")
tmp.unlink(missing_ok=True)

s = Settings.load(tmp)
print(f"  defaults loaded, width={s.get('image.width')}")
assert s.get("image.width") == 1344
assert s.get("nope.missing", "fallback") == "fallback"

s.set("image.width", 1024)
s.set("audio.device_name", "Kraken")
s.save()
print(f"  saved to {tmp.name}")

s2 = Settings.load(tmp)
assert s2.get("image.width") == 1024, "width did not persist"
assert s2.get("audio.device_name") == "Kraken"
assert s2.get("comfyui.steps") == DEFAULTS["comfyui"]["steps"]
print("  round-trip OK, untouched keys kept their defaults")

# A partial file must still gain every default key.
tmp.write_text(json.dumps({"image": {"width": 512}}), encoding="utf-8")
s3 = Settings.load(tmp)
assert s3.get("image.width") == 512
assert s3.get("image.height") == 768, "missing key not backfilled"
assert s3.get("server.port") == 8420
print("  partial file backfilled with defaults")

# A corrupt file must not crash the app.
tmp.write_text("{ this is not json", encoding="utf-8")
s4 = Settings.load(tmp)
assert s4.get("image.width") == 1344
print("  corrupt file fell back to defaults")
tmp.unlink(missing_ok=True)

print("\n=== audio devices ===")
for d in audio.list_devices():
    mark = "*" if d["is_default"] else " "
    print(f"  {mark} [{d['index']:>3}] {d['name'][:46]:<46} "
          f"{d['rate']}Hz {d['channels']}ch")

print("\n=== device resolution ===")
import pyaudiowpatch as pyaudio
pa = pyaudio.PyAudio()
try:
    for q in ("", "Kraken", "PRO X", "does-not-exist"):
        d = audio.resolve_device(pa, q)
        print(f"  {q or '(default)':<16} -> {d['name'][:44]}")
finally:
    pa.terminate()

print("\nall checks passed")
