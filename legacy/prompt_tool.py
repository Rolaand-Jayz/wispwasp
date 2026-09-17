"""
Type a prompt, get an image on your Desktop. Then choose whether to roll
another one from the same prompt.

Needs ComfyUI running. PROMPT.bat starts it for you.
"""

import importlib.util
import time
import winreg
from datetime import datetime
from pathlib import Path

# Reuse the config and ComfyUI backend from listener.py. Importing it is safe:
# the audio worker only starts under __main__.
_spec = importlib.util.spec_from_file_location(
    "L", Path(__file__).parent / "listener.py")
L = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(L)


def desktop_dir():
    """Real Desktop path, honouring OneDrive redirection."""
    try:
        key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            return Path(winreg.QueryValueEx(k, "Desktop")[0])
    except OSError:
        return Path.home() / "Desktop"


SAVE_DIR = desktop_dir()
use_suffix = True
amount = 1          # images generated per prompt entry


def next_path():
    base = SAVE_DIR / f"ai_{datetime.now():%Y%m%d_%H%M%S}"
    p = base.with_suffix(".png")
    n = 2
    while p.exists():
        p = Path(f"{base}_{n}.png")
        n += 1
    return p


def render(prompt, idx=None, total=None):
    full = prompt
    if use_suffix and L.STYLE_SUFFIX:
        full = f"{prompt}, {L.STYLE_SUFFIX}"

    tag = f"[{idx}/{total}] " if total and total > 1 else ""
    dest = next_path()
    t = time.time()
    try:
        L.generate_comfyui(full, dest)
    except KeyboardInterrupt:
        print("\n  stopped\n")
        raise
    except Exception as exc:
        print(f"  {tag}failed: {exc}")
        return False
    w, h = L.IMAGE_SIZE
    print(f"  {tag}saved {dest.name}  ({w}x{h}, "
          f"{dest.stat().st_size // 1024} KB, {time.time() - t:.1f}s)")
    return True


def render_batch(prompt):
    """Render `amount` images from one prompt. Ctrl+C stops the run."""
    t = time.time()
    done = 0
    try:
        for i in range(1, amount + 1):
            if render(prompt, i, amount):
                done += 1
    except KeyboardInterrupt:
        pass
    if amount > 1:
        print(f"  {done}/{amount} in {time.time() - t:.1f}s total")


def list_checkpoints():
    """All checkpoints ComfyUI can see."""
    r = L.requests.get(
        f"{L.COMFY_URL}/object_info/CheckpointLoaderSimple", timeout=30)
    r.raise_for_status()
    return r.json()["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]


def switch_model(query):
    """Pick a checkpoint by partial name. Blank query just lists them."""
    try:
        names = list_checkpoints()
    except L.requests.RequestException as exc:
        print(f"  could not reach ComfyUI: {exc}\n")
        return

    if not names:
        print("  no checkpoints installed\n")
        return

    if not query:
        print()
        for n in names:
            mark = "*" if n == L._comfy_ckpt else " "
            print(f"   {mark} {n}")
        print("\n  /model <part of a name> to switch\n")
        return

    q = query.lower()
    hits = [n for n in names if q in n.lower()]

    if not hits:
        print(f"  nothing matches '{query}'. Available:")
        for n in names:
            print(f"     {n}")
        print()
        return
    elif len(hits) > 1:
        # An exact filename match wins over being a substring of others.
        exact = [n for n in hits if n.lower() == q or Path(n).stem.lower() == q]
        if len(exact) == 1:
            hits = exact
        else:
            print(f"  '{query}' matches several - be more specific:")
            for n in hits:
                print(f"     {n}")
            print()
            return

    L._comfy_ckpt = hits[0]
    print(f"  model = {hits[0]}")
    print("  (first render will be slower while it loads)\n")


def show_help():
    w, h = L.IMAGE_SIZE
    print(f"""
  Commands:
    /amount 5          images per prompt (now {amount})
    /model jug         switch checkpoint by partial name (/model to list)
    /size 1024x576     change resolution (now {w}x{h})
    /steps 12          change sampling steps (now {L.COMFY_STEPS})
    /cfg 6.5           change prompt adherence (now {L.COMFY_CFG})
    /suffix            toggle the style suffix (now {'on' if use_suffix else 'off'})
    /neg <text>        set the negative prompt
    /show              show current settings
    /help              this list
    /quit              exit

  Anything else is treated as a prompt.
""")


def show_settings():
    w, h = L.IMAGE_SIZE
    print(f"""
  checkpoint : {L._comfy_ckpt or '(not loaded yet)'}
  size       : {w}x{h}
  amount     : {amount} per prompt
  steps      : {L.COMFY_STEPS}   cfg: {L.COMFY_CFG}
  sampler    : {L.COMFY_SAMPLER} / {L.COMFY_SCHEDULER}
  suffix     : {'on - ' + L.STYLE_SUFFIX if use_suffix else 'off'}
  negative   : {L.NEGATIVE_PROMPT.strip() or '(none)'}
  saving to  : {SAVE_DIR}
""")


def handle_command(line):
    """Returns True if the line was a command."""
    global use_suffix, amount
    if not line.startswith("/"):
        return False

    parts = line.split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("/quit", "/exit", "/q"):
        raise SystemExit
    elif cmd == "/help":
        show_help()
    elif cmd == "/show":
        show_settings()
    elif cmd == "/suffix":
        use_suffix = not use_suffix
        print(f"  style suffix {'on' if use_suffix else 'off'}\n")
    elif cmd == "/neg":
        L.NEGATIVE_PROMPT = arg
        print(f"  negative prompt set to: {arg or '(none)'}\n")
    elif cmd == "/amount":
        try:
            val = int(arg)
            if not 1 <= val <= 50:
                raise ValueError
            amount = val
            print(f"  amount = {amount} image{'s' if amount > 1 else ''} "
                  f"per prompt\n")
        except ValueError:
            print("  usage: /amount 5   (1-50)\n")
    elif cmd == "/model":
        switch_model(arg)
    elif cmd == "/cfg":
        try:
            val = float(arg)
            if not 0.0 <= val <= 30.0:
                raise ValueError
            L.COMFY_CFG = val
            print(f"  cfg = {L.COMFY_CFG}\n")
        except ValueError:
            print("  usage: /cfg 6.5   (0-30; SDXL likes 5-8, Turbo 1-2)\n")
    elif cmd == "/steps":
        try:
            L.COMFY_STEPS = max(1, int(arg))
            print(f"  steps = {L.COMFY_STEPS}\n")
        except ValueError:
            print("  usage: /steps 12\n")
    elif cmd == "/size":
        try:
            w, h = (int(x) for x in arg.lower().replace(" ", "").split("x"))
            L.IMAGE_SIZE = (w - w % 8, h - h % 8)
            print(f"  size = {L.IMAGE_SIZE[0]}x{L.IMAGE_SIZE[1]}\n")
        except (ValueError, TypeError):
            print("  usage: /size 1024x576\n")
    else:
        print(f"  unknown command {cmd} - try /help\n")
    return True


def main():
    print("\n  Manual image prompt")
    print("  -------------------")
    try:
        print(f"  model: {L.comfy_checkpoint()}")
    except L.requests.RequestException:
        print(f"  ERROR: ComfyUI is not responding at {L.COMFY_URL}.")
        print("  Close this window and start PROMPT.bat, which launches it.")
        input("\n  Press Enter to close")
        return
    except Exception as exc:
        print(f"  ERROR: {exc}")
        input("\n  Press Enter to close")
        return
    print(f"  saving to: {SAVE_DIR}")
    print("  /help for commands, /quit to exit\n")

    while True:
        try:
            line = input("  prompt> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        try:
            if handle_command(line):
                continue
        except SystemExit:
            break

        render_batch(line)

        # Offer repeats of the same prompt until they decline.
        while True:
            try:
                again = input("  Another with the same prompt? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return
            if again in ("y", "yes"):
                render_batch(line)
            else:
                print()
                break


if __name__ == "__main__":
    main()
