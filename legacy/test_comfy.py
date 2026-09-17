"""Verifies the ComfyUI backend end to end, without the audio pipeline."""
import sys
import time
from pathlib import Path

sys.argv = ["test"]
import importlib.util

spec = importlib.util.spec_from_file_location("L", "listener.py")
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)

print("checkpoint folder contents:")
try:
    ck = L.comfy_checkpoint()
    print("  resolved checkpoint:", ck)
except Exception as e:
    print("  ERROR:", e)
    raise SystemExit(1)

dest = Path("output/comfy_test.png")
dest.parent.mkdir(exist_ok=True)
t = time.time()
try:
    L.generate_comfyui("a red barn in a green field, wide shot", dest)
    print(f"OK - rendered in {time.time()-t:.1f}s -> {dest} "
          f"({dest.stat().st_size//1024} KB)")
except Exception as e:
    print(f"FAILED after {time.time()-t:.1f}s: {e}")
