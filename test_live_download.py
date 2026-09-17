"""
Checks the real download endpoints, briefly.

Local tests prove the logic; this proves the actual servers behave the way
the logic assumes. Each download is started, cancelled after a few seconds,
then resumed - which is exactly what happens on a flaky connection. Only a
few megabytes move.
"""
import threading
import time
from pathlib import Path

from avcore import setup

tmp = Path("_livetest")
tmp.mkdir(exist_ok=True)
ok = True


def probe(name, url, dest):
    global ok
    print(f"\n=== {name} ===")
    stop = threading.Event()
    seen = []

    dl = setup.Downloader(
        on_progress=lambda **kw: seen.append(kw),
        cancel=stop.is_set,
    )
    # Stop after a few seconds, however fast the connection is.
    threading.Timer(6.0, stop.set).start()
    try:
        dl.fetch(url, dest, label=name)
        print("   finished before the timer, which is fine")
    except setup.SetupCancelled:
        pass
    except Exception as exc:
        print(f"   *** FAILED: {exc}")
        ok = False
        return

    part = dest.with_suffix(dest.suffix + ".part")
    first = part.stat().st_size if part.exists() else 0
    total = max((p.get("total") or 0) for p in seen) if seen else 0
    speed = max((p.get("speed") or 0) for p in seen) if seen else 0
    print(f"   got {setup.human(first)} of {setup.human(total)} "
          f"at up to {setup.human(speed)}/s")

    if first <= 0:
        print("   *** FAILED: nothing downloaded")
        ok = False
        return
    if total < 100_000_000:
        print(f"   *** FAILED: reported total looks wrong ({total})")
        ok = False
        return

    # Resume: the second attempt must pick up rather than start over.
    stop2 = threading.Event()
    seen2 = []
    dl2 = setup.Downloader(on_progress=lambda **kw: seen2.append(kw),
                           cancel=stop2.is_set)
    threading.Timer(5.0, stop2.set).start()
    try:
        dl2.fetch(url, dest, label=name)
    except setup.SetupCancelled:
        pass
    except Exception as exc:
        print(f"   *** FAILED on resume: {exc}")
        ok = False
        return

    second = part.stat().st_size if part.exists() else 0
    started_at = min((p.get("done") or 0) for p in seen2) if seen2 else 0
    print(f"   resumed from {setup.human(started_at)}, now "
          f"{setup.human(second)}")

    if second <= first:
        print("   *** FAILED: resume did not add anything")
        ok = False
    elif started_at < first * 0.9:
        print("   *** FAILED: it restarted instead of resuming")
        ok = False
    else:
        print("   server honoured Range: resume works")


url, size = setup.comfy_asset_url()
print(f"ComfyUI asset resolved: {url.rsplit('/', 1)[-1]} "
      f"({setup.human(size)})")
probe("ComfyUI", url, tmp / "comfy.7z")
probe("Image model", setup.MODEL_URL, tmp / "model.safetensors")

import shutil
shutil.rmtree(tmp, ignore_errors=True)
print("\nlive endpoints behave as expected" if ok
      else "\nsomething is wrong with the live downloads")
raise SystemExit(0 if ok else 1)
