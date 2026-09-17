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
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel

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

print("\n=== the two layouts ComfyUI comes in ===")
# A git clone keeps models under <root>/models. The portable build -
# which is what setup installs - buries them under
# <root>/ComfyUI_windows_portable/ComfyUI/models. Assuming the first
# meant downloads on a portable install landed somewhere ComfyUI never
# reads: models arrived, and then simply were not there. It was
# invisible on a cloned install, which is why it reached somebody else
# before it was noticed.
from avcore.setup import checkpoints_dir as _ckdir

shapes = tmp / "shapes"

clone = shapes / "clone"
(clone / "models" / "checkpoints").mkdir(parents=True)
(clone / "main.py").write_text("#")
(clone / ".venv" / "Scripts").mkdir(parents=True)
(clone / ".venv" / "Scripts" / "python.exe").write_bytes(b"x")

portable = shapes / "portable"
inner = portable / "ComfyUI_windows_portable" / "ComfyUI"
(inner / "models" / "checkpoints").mkdir(parents=True)
(inner / "main.py").write_text("#")
embedded = portable / "ComfyUI_windows_portable" / "python_embeded"
embedded.mkdir(parents=True)
(embedded / "python.exe").write_bytes(b"x")

sc = Settings.load(path=tmp / "clone.json")
sc.set("comfyui.path", str(clone))
check("a clone keeps models at the root",
      _ckdir(sc) == clone / "models" / "checkpoints", str(_ckdir(sc)))

sp = Settings.load(path=tmp / "portable.json")
sp.set("comfyui.path", str(portable))
check("a portable build keeps them further in",
      _ckdir(sp) == inner / "models" / "checkpoints", str(_ckdir(sp)))
check("which is not what a naive guess would give",
      _ckdir(sp) != portable / "models" / "checkpoints",
      "the guess is why downloads vanished")

print("\n  the model browser asks rather than assumes:")
browser_source = Path("avgui/model_browser.py").read_text(encoding="utf-8")
check("it uses the locator",
      "checkpoints_dir" in browser_source)
check("and does not build the path by hand",
      'base / "models" / "checkpoints"' not in browser_source,
      "that line only worked on one of the two layouts")

print("\n  ComfyUI is told not to open its own page:")
launcher = Path("avcore/comfy_launcher.py").read_text(encoding="utf-8")
check("the flag is passed", "--disable-auto-launch" in launcher)
check("alongside the standalone flag that turns it on",
      "--windows-standalone-build" in launcher,
      "which is why only portable installs popped up a browser tab")

print("\n  models stranded by the old guess can be rescued:")
from avcore.setup import adopt_strays, stray_checkpoints

wrong = portable / "models" / "checkpoints"
wrong.mkdir(parents=True, exist_ok=True)
(wrong / "stranded.safetensors").write_bytes(b"0" * 600_000_000)
(wrong / "notes.txt").write_text("not a model")

strays = stray_checkpoints(sp)
check("they are found", [path.name for path in strays]
      == ["stranded.safetensors"], str([p.name for p in strays]))
check("and other files are left alone",
      all(path.suffix == ".safetensors" for path in strays))

moved, skipped, failed = adopt_strays(sp)
check("they are moved into place", moved == 1, f"moved={moved}")
check("nothing failed", failed == 0)
check("the file is where ComfyUI reads",
      (_ckdir(sp) / "stranded.safetensors").exists())
check("and no longer in the old folder",
      not (wrong / "stranded.safetensors").exists(),
      "moved rather than copied - nobody wants two of six gigabytes")
check("nothing is left stranded", stray_checkpoints(sp) == [])

print("\n  and it does not trample anything already there:")
(wrong / "stranded.safetensors").write_bytes(b"0" * 600_000_000)
moved, skipped, failed = adopt_strays(sp)
check("a name already in use is skipped", skipped == 1 and moved == 0,
      f"moved={moved} skipped={skipped}")
check("the stray is left where it is for the person to judge",
      (wrong / "stranded.safetensors").exists())

print("\n  a clone install has no stray folder to worry about:")
check("nothing is reported", stray_checkpoints(sc) == [],
      "the two paths are the same there")

print("\n=== animating a still is opt-in ===")
# Another 8.9GB and a card that can hold it. Plenty of people want
# neither, so nothing is fetched and the menu entry stays hidden until
# somebody asks.
from avcore.setup import VIDEO_MODEL, video_file, video_installed
from avcore.video import LENGTHS, SIZES, plan, shape_for

vid = tmp / "videocheck" / "ComfyUI"
(vid / "models" / "checkpoints").mkdir(parents=True, exist_ok=True)
(vid / "main.py").write_text("#")
(vid / ".venv" / "Scripts").mkdir(parents=True, exist_ok=True)
(vid / ".venv" / "Scripts" / "python.exe").write_bytes(b"x")

sv = Settings.load(path=tmp / "video.json")
sv.set("comfyui.path", str(vid))
sv.save()

check("it is not installed to begin with", not video_installed(sv))

partial = video_file(sv)
partial.write_bytes(b"0" * 1000)
check("and a stub of a file does not count as installed",
      not video_installed(sv),
      "a part-finished 8.9GB download would otherwise look ready")
partial.unlink()

print("\n  the lengths offered are the ones that worked:")
check("four of them", len(LENGTHS) == 4, str(len(LENGTHS)))
check("every one has a measured estimate",
      all(estimate > 60 for _f, _s, _l, estimate in LENGTHS))
check("longer clips are made smaller",
      all(SIZES["landscape"][i][0] > SIZES["landscape"][i + 1][0]
          for i in range(len(SIZES["landscape"]) - 1)),
      "asking for 10s at full size takes ComfyUI down, not just longer")

widest = plan(25, "landscape")
longest = plan(100, "landscape")
check("the shortest is the biggest picture",
      widest[0] * widest[1] > longest[0] * longest[1],
      f"{widest[0]}x{widest[1]} against {longest[0]}x{longest[1]}")
check("and they cost about the same",
      abs(widest[3] - longest[3]) < 90,
      f"{widest[3]}s against {longest[3]}s")

print("\n  the shape follows the picture:")
check("a wide one is landscape", shape_for(1920, 1080) == "landscape")
check("a tall one is portrait", shape_for(768, 1344) == "portrait")
check("a square one is square", shape_for(1024, 1024) == "square")
check("every shape covers every length",
      all(len(sizes) == len(LENGTHS) for sizes in SIZES.values()))

print("\n  what the dialog tells somebody:")
from avgui.dialogs import ConfirmAnimate

dialog = ConfirmAnimate("a_picture.png", "landscape")
words = " ".join(l.text() for l in dialog.findChildren(QLabel))
check("that there is no sound", "no sound" in words)
check("that a prompt cannot steer it", "prompt cannot steer" in words,
      "this model takes the picture and nothing else")
check("that live generation waits its turn",
      "queued" in words and "one job at a time" in words,
      "the thing somebody would otherwise discover mid-stream")
check("and how long the chosen option takes",
      "to make" in dialog.detail.text(), dialog.detail.text())
check("it hands back the choice", dialog.choice()[0] in
      [frames for frames, _s, _l, _e in LENGTHS])
dialog.reject()

print("\n  pressing Install actually opens something:")
# Nothing exercised this button before, which is how 0.1.7 shipped with
# a handler that raised ImportError on its first line. Qt swallows an
# exception inside a slot, so the button simply did nothing at all.
#
# The dialog is stood in for rather than shown: exec() blocks until
# somebody answers it, and a test suite has nobody to answer.
import avgui.setup_panel as _panel_module
from avgui.setup_panel import SetupPanel

engv = Engine(sv)
panelv = SetupPanel(engv)
_app.processEvents()

check("the row offers Install when nothing is there",
      panelv.video_btn.text() == "Install", panelv.video_btn.text())
check("and it is pressable", panelv.video_btn.isEnabled())

asked = []


class _Stub:
    """Stands in for the confirmation, and declines."""

    def __init__(self, *args, **kwargs):
        asked.append(args[0] if args else "?")

    def exec(self):
        from PySide6.QtWidgets import QDialog

        return QDialog.Rejected


_real = _panel_module.ConfirmInstall
_panel_module.ConfirmInstall = _Stub
try:
    panelv._toggle_video()
    raised = ""
except Exception as exc:
    raised = f"{type(exc).__name__}: {exc}"
finally:
    _panel_module.ConfirmInstall = _real

check("the handler runs without raising", not raised,
      raised or "clean - it used to raise ImportError here")
check("and it asks before downloading 8.9 GB", len(asked) == 1,
      f"{len(asked)} confirmations")
check("naming what it would install",
      asked and "Animate" in str(asked[0]), str(asked[:1]))
check("there is a bar for the download", hasattr(panelv, "video_bar"))
check("nothing was fetched after declining",
      not video_installed(sv), "declining must mean declining")

engv.shutdown()
panelv.deleteLater()

bad = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed")
if bad:
    print("FAILURES:")
    for n in bad:
        print(f"  - {n}")
    raise SystemExit(1)
print("setup logic works")
