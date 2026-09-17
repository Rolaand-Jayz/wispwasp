"""Times a render at several resolutions so we can pick one."""
import importlib.util
import time
from pathlib import Path

spec = importlib.util.spec_from_file_location("L", "listener.py")
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)

PROMPT = ("a burning cathedral at dusk, wide establishing shot, "
          "dramatic lighting, high detail")

SIZES = [(384, 216), (1024, 576), (1152, 648), (1344, 768)]
out = Path("output")
out.mkdir(exist_ok=True)

print(f"checkpoint: {L.comfy_checkpoint()}")
print(f"steps={L.COMFY_STEPS} cfg={L.COMFY_CFG} "
      f"sampler={L.COMFY_SAMPLER}/{L.COMFY_SCHEDULER}\n")
print(f"{'size':>12} {'seconds':>9} {'KB':>7}")
print("-" * 31)

for w, h in SIZES:
    L.IMAGE_SIZE = (w, h)
    dest = out / f"bench_{w}x{h}.png"
    t = time.time()
    try:
        L.generate_comfyui(PROMPT, dest)
        el = time.time() - t
        print(f"{w}x{h:<7} {el:>9.1f} {dest.stat().st_size // 1024:>7}")
    except Exception as e:
        print(f"{w}x{h:<7} {'FAILED':>9}  {str(e)[:40]}")
