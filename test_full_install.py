"""
Full-scale install test: downloads ComfyUI and a model for real, proves
they work, then removes everything.

This is the one thing the mocked tests cannot cover - whether 8.3 GB of
real archive actually extracts and runs. Everything lands in a temp folder
and is deleted at the end, including on failure.
"""
import shutil
import sys
import time
from pathlib import Path

from avcore import setup as avsetup
from avcore.config import Settings

ROOT = Path("_fullinstall").resolve()
ok = True
last_line = [0.0]


def note(msg):
    print(f"  {msg}", flush=True)


def progress(**kw):
    # One line every few seconds; a progress bar makes no sense in a log.
    now = time.time()
    if now - last_line[0] < 3:
        return
    last_line[0] = now
    label = kw.get("label", "")
    done, total = kw.get("done", 0), kw.get("total", 0)
    speed = kw.get("speed") or 0
    if total:
        pct = 100 * done / total
        extra = f" at {avsetup.human(speed)}/s" if speed else ""
        note(f"{label}: {pct:.0f}%  "
             f"({avsetup.human(done)} of {avsetup.human(total)}){extra}")


def main():
    global ok
    shutil.rmtree(ROOT, ignore_errors=True)
    ROOT.mkdir(parents=True)

    free = avsetup.free_space(ROOT)
    print(f"free space before: {avsetup.human(free)}")
    if free < avsetup.REQUIRED_FREE_BYTES:
        print("not enough room; skipping")
        return False

    s = Settings.load(path=ROOT / "settings.json")
    s.set("comfyui.path", str(ROOT))
    s.set("comfyui.url", "http://127.0.0.1:8199")   # avoid a running instance

    print("\n=== installing for real ===")
    started = time.time()
    inst = avsetup.Installer(
        s, on_progress=progress,
        on_step=lambda k, t: print(f"\n[{k}] {t}", flush=True))
    report = inst.run(root=ROOT)
    print(f"\ninstall took {(time.time() - started) / 60:.1f} minutes")

    def check(name, cond, detail=""):
        global ok
        ok = ok and bool(cond)
        print(f"  {'PASS' if cond else '*** FAIL ***':<14} {name}"
              + (f"  [{detail}]" if detail else ""))

    print("\n=== what landed on disk ===")
    check("reports ready", report["ready"])
    info = avsetup.find_comfy(ROOT)
    check("install detected", info is not None)
    if not info:
        return False
    check("embedded python present", info["python"].exists())
    check("main.py present", info["main"].exists())
    models = avsetup.checkpoints_in(info["models"])
    check("model present", bool(models),
          f"{models[0].name} "
          f"({avsetup.human(models[0].stat().st_size)})" if models else "")
    check("archive cleaned up", not list(ROOT.glob("*.7z")))
    size = sum(f.stat().st_size for f in ROOT.rglob("*") if f.is_file())
    print(f"  installed size: {avsetup.human(size)}")
    return info, s


def verify_runs(info, s):
    """Start the downloaded ComfyUI and render one image with it."""
    global ok
    from avcore.comfy_launcher import ComfyLauncher
    from avcore.images import ComfyBackend

    print("\n=== does the downloaded ComfyUI actually run? ===")
    launcher = ComfyLauncher(s)
    started = launcher.start(wait=420, on_progress=note)
    if not started:
        print(f"  *** FAILED to start: {launcher.error}")
        ok = False
        return launcher

    backend = ComfyBackend(s)
    print(f"  checkpoints it can see: {backend.list_checkpoints()}")
    s.set("image.width", 1024)
    s.set("image.height", 576)
    s.set("comfyui.steps", 12)
    dest = ROOT / "proof.png"
    t = time.time()
    try:
        backend.generate("a lone red sailboat on a calm green sea", dest)
        size = dest.stat().st_size
        print(f"  PASS           rendered in {time.time() - t:.1f}s "
              f"({avsetup.human(size)})")
    except Exception as exc:
        print(f"  *** FAILED to render: {exc}")
        ok = False
    return launcher


launcher = None
try:
    result = main()
    if result:
        info, s = result
        launcher = verify_runs(info, s)
finally:
    print("\n=== cleaning up ===")
    if launcher:
        launcher.stop()
        time.sleep(3)
    # Uses the long-path aware remove, because a full install contains
    # paths a plain rmtree cannot even see, let alone delete.
    removed = avsetup.remove_tree(ROOT)
    print(f"  temp folder removed: {removed}")
    if not removed:
        # Leaving 10 GB behind is a failure in its own right, so it is
        # reported as one rather than printed and ignored.
        ok = False
        print(f"  *** LEFT BEHIND at {ROOT} - delete this manually")
    print(f"  free space after: {avsetup.human(avsetup.free_space('.'))}")

print("\nfull install works end to end" if ok else "\nsomething failed")
sys.exit(0 if ok else 1)
