"""
Tests for first-run setup detection and the downloader.

The multi-gigabyte downloads are not exercised here. Resume, range
handling and short-file detection are tested against a local server, which
covers the logic without moving 8 GB.
"""
import http.server
import shutil
import threading
from pathlib import Path

from avcore import setup
from avcore.config import Settings

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  {'PASS' if cond else '*** FAIL ***':<14} {name}"
          + (f"  [{detail}]" if detail else ""))


tmp = Path("_setuptest")
shutil.rmtree(tmp, ignore_errors=True)
# Tolerates a leftover: Windows will not delete a folder a live
# window still has open, so the cleanup at the end can fail.
tmp.mkdir(parents=True, exist_ok=True)

print("=== hardware and space checks ===")
gpu_ok, gpu_name = setup.has_nvidia_gpu()
check("detects the NVIDIA GPU", gpu_ok, gpu_name)
check("reports free space", setup.free_space(tmp) > 0,
      setup.human(setup.free_space(tmp)))

print("\n=== finding an existing install ===")
check("nothing found in an empty folder", setup.find_comfy(tmp) is None)

# The shape the portable archive unpacks into.
port = tmp / "ComfyUI_windows_portable"
(port / "ComfyUI" / "models" / "checkpoints").mkdir(parents=True)
(port / "python_embeded").mkdir(parents=True)
(port / "ComfyUI" / "main.py").write_text("x")
(port / "python_embeded" / "python.exe").write_text("x")
found = setup.find_comfy(tmp)
check("finds a portable install", found is not None)
check("marks it portable", found and found["portable"] is True)
check("points at the checkpoints folder",
      found and found["models"].name == "checkpoints")

# A real install on this machine, which is a git clone rather than portable.
real = setup.find_comfy(Path.home() / "ComfyUI")
check("finds the real ComfyUI on this machine", real is not None,
      str(real["base"]) if real else "not found")
check("recognises it as a non-portable clone",
      real is not None and real["portable"] is False)

print("\n=== checkpoint detection ignores stubs ===")
ck = found["models"]
(ck / "tiny.safetensors").write_bytes(b"0" * 1000)
check("a tiny file is not mistaken for a model",
      len(setup.checkpoints_in(ck)) == 0)
(ck / "real.safetensors").write_bytes(
    b"0" * (setup.PLAUSIBLE_MODEL_BYTES * 2))
check("a plausible file counts", len(setup.checkpoints_in(ck)) == 1)

print("\n=== the overall report ===")
s = Settings.load()
s.set("comfyui.path", str(tmp))
rep = setup.check(s)
check("reports comfy present", rep["comfy_ok"])
check("reports model present", rep["model_ok"])
check("reports ready", rep["ready"])

s.set("comfyui.path", str(tmp / "nothing-here"))
rep = setup.check(s)
check("an empty folder is reported not ready", rep["ready"] is False)
check("and says comfy is missing", rep["comfy_ok"] is False)

print("\n=== a chosen path is honoured, not overridden ===")
# There is a real ComfyUI on this machine. Choosing an empty folder must
# report that folder, not quietly fall back to the one found elsewhere -
# otherwise picking a different drive would silently do nothing.
chosen = tmp / "my-drive" / "ComfyUI"
s.set("comfyui.path", str(chosen))
rep = setup.check(s)
check("reports the folder the user picked", rep["root"] == chosen,
      str(rep["root"]))
check("does not claim an install that is elsewhere",
      rep["comfy_ok"] is False)

print("\n=== an unset path searches the usual places ===")
s.set("comfyui.path", "")
rep = setup.check(s)
real_exists = (Path.home() / "ComfyUI" / "main.py").exists()
check("finds an existing install when nothing is configured",
      rep["comfy_ok"] == real_exists,
      str(rep["root"]))


# ---- a local server, to test resume without moving gigabytes ----------
PAYLOAD = bytes((i * 7) % 251 for i in range(900_000))
serve_dir = tmp / "srv"
serve_dir.mkdir(parents=True, exist_ok=True)
(serve_dir / "blob.bin").write_bytes(PAYLOAD)


class Handler(http.server.SimpleHTTPRequestHandler):
    ignore_range = False

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(serve_dir), **kw)

    def log_message(self, *a):
        pass

    def do_GET(self):
        rng = self.headers.get("Range")
        if rng and not Handler.ignore_range:
            start = int(rng.split("=")[1].split("-")[0])
            body = PAYLOAD[start:]
            self.send_response(206)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Range",
                             f"bytes {start}-{len(PAYLOAD)-1}/{len(PAYLOAD)}")
            self.end_headers()
            self.wfile.write(body)
            return
        # Either no range asked for, or a server that ignores it.
        self.send_response(200)
        self.send_header("Content-Length", str(len(PAYLOAD)))
        self.end_headers()
        self.wfile.write(PAYLOAD)


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8489), Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:8489/blob.bin"

print("\n=== downloading ===")
seen = []
dl = setup.Downloader(on_progress=lambda **kw: seen.append(kw))
dest = tmp / "got.bin"
dl.fetch(URL, dest, label="blob")
check("file downloads intact", dest.read_bytes() == PAYLOAD)
check("progress was reported", len(seen) > 1, f"{len(seen)} updates")
check("progress reported a total",
      any(p.get("total") == len(PAYLOAD) for p in seen))

print("\n=== resuming a partial download ===")
dest2 = tmp / "resume.bin"
part = dest2.with_suffix(dest2.suffix + ".part")
part.write_bytes(PAYLOAD[:400_000])      # pretend an interrupted transfer
seen.clear()
dl.fetch(URL, dest2, label="blob")
check("resumed file is correct", dest2.read_bytes() == PAYLOAD)
# Only the remainder should have come over the wire.
transferred = max(p.get("done", 0) for p in seen) - 400_000
check("only the missing part was fetched", transferred < 520_000,
      f"{transferred} bytes")

print("\n=== a server that ignores Range must not corrupt the file ===")
# This is the dangerous case: appending a full response onto partial data
# would produce a file that is the right shape but wrong content.
Handler.ignore_range = True
dest3 = tmp / "norange.bin"
part3 = dest3.with_suffix(dest3.suffix + ".part")
part3.write_bytes(PAYLOAD[:400_000])
dl.fetch(URL, dest3, label="blob")
check("partial data was discarded, not appended",
      dest3.read_bytes() == PAYLOAD,
      f"{dest3.stat().st_size} bytes vs {len(PAYLOAD)}")
Handler.ignore_range = False

print("\n=== a short file is rejected ===")
dest4 = tmp / "short.bin"
try:
    dl.fetch(URL, dest4, label="blob", expect_min=len(PAYLOAD) * 2)
    check("short download raises", False)
except RuntimeError as exc:
    check("short download raises", True, str(exc)[:48])
check("and the partial file is kept for resuming",
      dest4.with_suffix(".bin.part").exists())

print("\n=== cancelling ===")
stop = {"v": False}
dl2 = setup.Downloader(
    on_progress=lambda **kw: stop.__setitem__("v", True),
    cancel=lambda: stop["v"])
try:
    dl2.fetch(URL, tmp / "cancelled.bin", label="blob")
    check("cancel stops the download", False)
except setup.SetupCancelled:
    check("cancel stops the download", True)

print("\n=== already-present files are skipped ===")
seen.clear()
dl.fetch(URL, dest, label="blob", expect_min=len(PAYLOAD))
check("existing complete file is not re-fetched",
      any(p.get("note") == "already here" for p in seen))

srv.shutdown()
shutil.rmtree(tmp, ignore_errors=True)

print("\n=== choosing how images get made ===")
from avcore.setup import DEFAULT_TIER, TIERS, tier

check("there is an online option and local ones",
      len(TIERS) >= 2, str(list(TIERS)))
check("every tier names a real file",
      all(spec["name"].endswith(".safetensors")
          for spec in TIERS.values()))
check("and says what it costs",
      all(spec["bytes"] > 1_000_000_000 for spec in TIERS.values()))
check("and how to recognise a truncated one",
      all(0 < spec["min_bytes"] < spec["bytes"]
          for spec in TIERS.values()),
      "the bar has to sit below the real size")

# The sizes are measured from the hosts, not guessed. If one of these
# drifts far from reality the choice offered stops being honest.
sd15 = TIERS["sd15"]["bytes"] / 1_073_741_824
sdxl = TIERS["sdxl"]["bytes"] / 1_073_741_824
check("the smaller option really is smaller", sd15 < sdxl,
      f"{sd15:.1f} GB vs {sdxl:.1f} GB")
check("no tier claims to be tiny", sd15 > 3,
      "the smallest official checkpoint is about four gigabytes")

print("\n  an unset choice keeps the old behaviour:")
blank = Settings.load(path=tmp / "blank.json")
check("it falls back to the default",
      tier(blank)["name"] == TIERS[DEFAULT_TIER]["name"],
      "an existing install must not change model on upgrade")

print("\n  a chosen tier is what gets fetched:")
picked = Settings.load(path=tmp / "picked.json")
picked.set("models.tier", "sd15")
check("the choice is followed", tier(picked)["name"].startswith("v1-5"),
      tier(picked)["name"])
picked.set("models.tier", "nonsense")
check("and nonsense falls back rather than failing",
      tier(picked)["name"] == TIERS[DEFAULT_TIER]["name"])

print("\n=== recognising models already on disk ===")
# Judged by the weights, not the filename. Almost nobody's SDXL
# checkpoint is called sd_xl_base_1.0, and judging by name reported a
# folder full of perfectly good models as empty.
import json as _json
import struct as _struct

from avcore.setup import (
    family_of, models_for_tier, tier_file, tier_installed,
)


def fake_checkpoint(path, family):
    """A file with a real safetensors header and nothing else."""
    if family == "sdxl":
        keys = {"conditioner.embedders.1.model.ln_final.weight":
                {"dtype": "F16", "shape": [1280], "data_offsets": [0, 2]},
                "model.diffusion_model.out.0.weight":
                {"dtype": "F16", "shape": [320], "data_offsets": [0, 2]}}
    else:
        keys = {"cond_stage_model.transformer.text_model.final_layer_norm"
                ".weight":
                {"dtype": "F16", "shape": [768], "data_offsets": [0, 2]},
                "model.diffusion_model.out.0.weight":
                {"dtype": "F16", "shape": [320], "data_offsets": [0, 2]}}
    header = _json.dumps(keys).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(_struct.pack("<Q", len(header)))
        handle.write(header)
        handle.write(b"0" * 600_000_000)


shelf = tmp / "recognise" / "ComfyUI"
(shelf / "models" / "checkpoints").mkdir(parents=True, exist_ok=True)
(shelf / "main.py").write_text("#")
(shelf / ".venv" / "Scripts").mkdir(parents=True, exist_ok=True)
(shelf / ".venv" / "Scripts" / "python.exe").write_bytes(b"x")

sr = Settings.load(path=tmp / "recognise.json")
sr.set("comfyui.path", str(shelf))
sr.save()

check("an empty folder has nothing installed",
      not tier_installed("sdxl", sr) and not tier_installed("sd15", sr))

store = shelf / "models" / "checkpoints"
fake_checkpoint(store / "somebodys_favourite_xl.safetensors", "sdxl")
check("a renamed SDXL model is still recognised",
      tier_installed("sdxl", sr),
      "the family is read from the weights")
check("and does not count as SD 1.5", not tier_installed("sd15", sr))
check("the file is named back",
      models_for_tier("sdxl", sr)[0].name.endswith("_xl.safetensors"))

fake_checkpoint(store / "some_15_mix.safetensors", "sd15")
check("an SD 1.5 model is recognised too", tier_installed("sd15", sr))
check("each option finds only its own family",
      len(models_for_tier("sdxl", sr)) == 1
      and len(models_for_tier("sd15", sr)) == 1)

print("\n  what setup fetched is told apart from what was already there:")
check("the official file is absent",
      not tier_file("sdxl", sr).exists(),
      "so removal is not offered for somebody else's model")

(store / "notes.txt").write_text("not a model")
check("non-models are ignored", len(models_for_tier("sd15", sr)) == 1)

garbage = store / "broken.safetensors"
garbage.write_bytes(b"\x00" * 600_000_000)
check("an unreadable header does not raise",
      family_of(garbage) is None, "it is simply not recognised")
check("and does not appear as either family",
      len(models_for_tier("sd15", sr)) == 1
      and len(models_for_tier("sdxl", sr)) == 1)

print("\n=== the faults that made this unstable ===")
# Five separate bugs, all of the same shape: a choice made in one place
# ignored in another. Each is pinned here because the symptom - "it
# keeps switching back", "it generates with the wrong thing" - is
# miserable to diagnose from the outside.
from PySide6.QtWidgets import QApplication

from avcore.engine import Engine
from avcore.images import ComfyBackend
from avgui import theme
from avgui.settings_panel import SettingsPanel
from avgui.setup_panel import SetupPanel

_app = QApplication.instance() or QApplication([])
theme.apply_to(_app, None)


def _pump(seconds=0.35):
    import time as _t
    end = _t.time() + seconds
    while _t.time() < end:
        _app.processEvents()
        _t.sleep(0.01)


bench = tmp / "faults" / "ComfyUI"
(bench / "models" / "checkpoints").mkdir(parents=True, exist_ok=True)
(bench / "main.py").write_text("#")
(bench / ".venv" / "Scripts").mkdir(parents=True, exist_ok=True)
(bench / ".venv" / "Scripts" / "python.exe").write_bytes(b"x")
fake_checkpoint(bench / "models" / "checkpoints" / "mine_xl.safetensors",
                "sdxl")
fake_checkpoint(bench / "models" / "checkpoints" / "mine_15.safetensors",
                "sd15")

sf = Settings.load(path=tmp / "faults.json")
sf.set("comfyui.path", str(bench))
sf.set("image.backend", "comfyui")
sf.save()
engf = Engine(sf)
setup = SetupPanel(engf)
setup.show()
_pump()

print("\n  choosing a model sticks:")
setup.how.button(2).click()          # Stable Diffusion XL
_pump()
picked = setup.how.checkedId()
setup.refresh()                       # what the two-second timer does
_pump()
check("the tick stays where it was put",
      setup.how.checkedId() == picked == 2,
      "it used to be dragged back to the first installed option")
check("and the checkpoint is a file that exists",
      (bench / "models" / "checkpoints"
       / sf.get("comfyui.checkpoint")).exists(),
      sf.get("comfyui.checkpoint"))

print("\n  refreshing does not rewrite the choice:")
sf.set("image.backend", "comfyui")
sf.save()
for _ in range(3):
    setup.refresh()
    setup._recheck_models()
    _pump(0.15)
check("a refresh leaves the backend alone",
      sf.get("image.backend") == "comfyui",
      "it used to flip to Pollinations every couple of seconds")

print("\n  the engine follows the backend setting without a restart:")
sf.set("image.backend", "pollinations")
sf.save()
first = type(engf._sync_backend()).__name__
sf.set("image.backend", "comfyui")
sf.save()
second = type(engf._sync_backend()).__name__
check("switching changes what generates", first != second,
      f"{first} -> {second}")
check("and it settles on the right one", second == "ComfyBackend")
again = engf._sync_backend()
check("an unchanged setting is not rebuilt each time",
      engf._sync_backend() is again)

print("\n  the backend follows the model setting without a restart:")
backend = ComfyBackend(sf)
backend.list_checkpoints = lambda: ["mine_xl.safetensors",
                                    "mine_15.safetensors"]
sf.set("comfyui.checkpoint", "mine_15.safetensors")
one = backend.checkpoint()
sf.set("comfyui.checkpoint", "mine_xl.safetensors")
two = backend.checkpoint()
check("changing the model changes what is loaded", one != two,
      f"{one} -> {two}")
check("and it is the one asked for", two == "mine_xl.safetensors")

print("\n  the Settings model row offers files that exist:")
panel = SettingsPanel(engf)
_pump()
offered = [panel.model_pick.itemData(i)
           for i in range(panel.model_pick.count())]
check("every option names a real file",
      all((bench / "models" / "checkpoints" / name).exists()
          for name in offered if name),
      str(offered))

engf.shutdown()
setup.close()
panel.close()
_pump(0.2)

print("\n=== checking for a newer build ===")
# It only ever finds out and offers a link. Downloading and running an
# installer on somebody else's machine is a different level of
# responsibility, and without code signing this app has no business
# taking it - so there is nothing here that fetches or executes.
import io as _io
import json as _json
import urllib.error as _urlerror

from avcore import updates as _updates
# Deliberately not importing `check` by name: this suite has its own
# check() helper, and the import would shadow it and break every
# assertion in the file.
from avcore.updates import UpdateError, describe
from avcore.version import __version__


class _Answer(_io.BytesIO):
    def __init__(self, payload, status=200):
        super().__init__(_json.dumps(payload).encode("utf-8"))
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()
        return False


def _serving(payload):
    return lambda request, timeout=None: _Answer(payload)


newer = {"version": "9.9.9", "page": "https://example/releases",
         "notes": "things", "size": 82_395_802}
found = _updates.check(url="https://example/latest.json",
                       opener=_serving(newer))
check("a newer build is reported", found is not None)
check("with its version", found["version"] == "9.9.9")
check("and where to get it", found["page"] == "https://example/releases")
check("described for a person",
       "9.9.9 is available" in describe(found), describe(found))
check("including the size", "79 MB" in describe(found), describe(found))

same = {"version": __version__, "page": "https://example/releases"}
check("the current version is not offered as an update",
       _updates.check(url="https://example/x",
                      opener=_serving(same)) is None)
check("and says so plainly",
       "latest version" in describe(None), describe(None))

older = {"version": "0.0.1", "page": "https://example/releases"}
check("an older one is not offered either",
       _updates.check(url="https://example/x",
                      opener=_serving(older)) is None)

print("\n  when the answer is unusable:")
junk = {"version": "not-a-version"}
check("nonsense does not become an update",
       _updates.check(url="https://example/x",
                      opener=_serving(junk)) is None,
       "it sorts low rather than raising")

try:
    _updates.check(url="https://example/x",
                   opener=_serving({"nothing": True}))
    check("a manifest without a version is refused", False)
except UpdateError as exc:
    check("a manifest without a version is refused",
           "not readable" in str(exc))


def _refuses(request, timeout=None):
    raise _urlerror.HTTPError(request.full_url, 503, "Unavailable", {}, None)


try:
    _updates.check(url="https://example/x", opener=_refuses)
    check("a server fault is reported plainly", False)
except UpdateError as exc:
    check("a server fault is reported plainly", "503" in str(exc))

try:
    # A build with no manifest configured at all. An empty url is not
    # enough now that one is set - it falls back to it - so the constant
    # itself is taken away for this one check.
    _was = _updates.UPDATE_MANIFEST
    _updates.UPDATE_MANIFEST = ""
    _updates.check(opener=_serving(newer))
    check("no configured source is refused", False)
except UpdateError as exc:
    check("no configured source is refused",
          "No update source" in str(exc),
          "so a build with none simply does not offer the check")
finally:
    _updates.UPDATE_MANIFEST = _was

print("\n  nothing here downloads anything:")
source = Path("avcore/updates.py").read_text(encoding="utf-8")
check("no subprocess", "subprocess" not in source)
check("nothing is executed", "Popen" not in source and "startfile" not in source)
check("and no installer is fetched",
       ".exe" not in source,
       "the person opens the page and decides")

bad = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed")
if bad:
    print("FAILURES:")
    for n in bad:
        print(f"  - {n}")
    raise SystemExit(1)
print("setup logic works")
