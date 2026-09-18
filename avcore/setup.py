"""
First-run setup: works out what is missing and fetches it.

A fresh machine has none of this, and the pieces are large - ComfyUI
portable is about 1.8 GB and an SDXL checkpoint about 6.6 GB - so they are
downloaded rather than bundled. The portable build carries its own Python
and CUDA-enabled PyTorch, which means nothing has to be preinstalled.

Everything here reports progress and can be cancelled, and downloads
resume, because a 6.6 GB transfer will not always survive in one go.
"""

import json
import struct
import os
import shutil
import stat
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

COMFY_RELEASE_API = (
    "https://api.github.com/repos/comfyanonymous/ComfyUI/releases/latest"
)
COMFY_ASSET = "ComfyUI_windows_portable_nvidia.7z"

# What setup can fetch, and what each costs. Official releases only:
# unambiguous provenance, no login, and they will still be there in a
# year - a community checkpoint can be withdrawn by its author, which is
# a poor thing to discover during first-run setup. Anything else can be
# added afterwards from Get more models.
#
# The sizes are measured, not estimated. There is deliberately no "~1 GB"
# or "~2 GB" choice: the smallest official checkpoint is four gigabytes,
# and the 2 GB files people have seen are community fp16 conversions,
# which belong in the catalogue rather than in setup.
TIERS = {
    "sd15": {
        "label": "Stable Diffusion 1.5",
        "note": "About 4.3 GB. Faster, lighter on the graphics card, and "
                "fine for most things.",
        "name": "v1-5-pruned-emaonly.safetensors",
        "url": ("https://huggingface.co/stable-diffusion-v1-5"
                "/stable-diffusion-v1-5/resolve/main"
                "/v1-5-pruned-emaonly.safetensors"),
        "bytes": 4_265_146_304,
        "min_bytes": 3_500_000_000,
    },
    "sdxl": {
        "label": "Stable Diffusion XL",
        "note": "About 6.9 GB. Better images, slower, and wants more "
                "video memory.",
        "name": "sd_xl_base_1.0.safetensors",
        "url": ("https://huggingface.co/stabilityai"
                "/stable-diffusion-xl-base-1.0/resolve/main"
                "/sd_xl_base_1.0.safetensors"),
        "bytes": 6_938_078_334,
        "min_bytes": 6_000_000_000,
    },
}

DEFAULT_TIER = "sdxl"

# Animating a still is an extra rather than part of the app. It is
# another 8.9GB, it needs a card that can hold it, and plenty of people
# will never want it - so nothing is fetched and the menu entry stays
# hidden until somebody asks for it.
VIDEO_MODEL = {
    "label": "Animate images (video)",
    "note": "About 9.6 GB. Turns a gallery picture into a short clip. "
            "Needs an NVIDIA card with 12 GB or more.",
    "name": "svd_xt.safetensors",
    "url": ("https://huggingface.co/stabilityai"
            "/stable-video-diffusion-img2vid-xt/resolve/main"
            "/svd_xt.safetensors"),
    "bytes": 9_556_534_000,
    "min_bytes": 8_000_000_000,
}


def video_file(settings=None, root=None):
    """Where the video model would live."""
    return checkpoints_dir(settings, root) / VIDEO_MODEL["name"]


def video_installed(settings=None, root=None):
    """
    Is the video model there and whole?

    Size-checked like the others: a part-finished 8.9GB download under
    the right name would otherwise look installed and then fail in the
    middle of a job.
    """
    path = video_file(settings, root)
    try:
        return path.exists() and path.stat().st_size >= VIDEO_MODEL["min_bytes"]
    except OSError:
        return False


def tier(settings=None):
    """Which model setup should fetch."""
    chosen = ""
    if settings is not None:
        chosen = (settings.get("models.tier") or "").strip()
    return TIERS.get(chosen, TIERS[DEFAULT_TIER])


# Any checkpoint smaller than this is a stub or a truncated download
# rather than a model. Used to decide whether one is really installed,
# so it is deliberately far below the smallest real file.
PLAUSIBLE_MODEL_BYTES = 500_000_000

# Archive + extracted copy + model, with room to spare.
REQUIRED_FREE_BYTES = 22 * 1024**3


def long_path(p):
    """
    Return a path Windows will accept regardless of length.

    Windows caps paths at 260 characters unless an application opts out,
    and LongPathsEnabled is off by default. The ComfyUI portable build
    contains PyTorch, whose licence folder nests far past that limit -
    torch...dist-info\\licenses\\third_party\\kineto\\libkineto\\third_party
    \\dynolog\\third_party\\prometheus-cpp\\3rdparty\\civetweb\\examples
    \\rest\\cJSON is on its own about 210 characters. Without this prefix
    extraction dies partway through on a normal machine.
    """
    p = Path(p).resolve()
    if os.name != "nt":
        return str(p)
    text = str(p)
    if text.startswith("\\\\?\\"):
        return text
    return "\\\\?\\" + text


def remove_tree(path):
    """
    Delete a folder completely.

    Two things defeat a plain rmtree here. Paths inside the ComfyUI build
    run past Windows' length limit, and some files - git pack files in
    particular - are marked read-only, which rmtree skips silently when
    ignore_errors is set. So the read-only bit is cleared and the delete
    retried rather than the failure being swallowed.
    """
    target = Path(path)
    if not target.exists():
        return True

    def on_error(func, failed, exc_info):
        try:
            os.chmod(failed, stat.S_IWRITE)
            func(failed)
        except OSError:
            pass

    for _ in range(4):
        try:
            if sys.version_info >= (3, 12):
                shutil.rmtree(long_path(target),
                              onexc=lambda f, p, e: on_error(f, p, e))
            else:
                shutil.rmtree(long_path(target), onerror=on_error)
        except OSError:
            pass
        if not target.exists():
            return True
        time.sleep(2)      # Windows can hold handles briefly after use
    return not target.exists()


def seven_zip_exe():
    """
    Locate the bundled 7-Zip extractor.

    py7zr cannot open the ComfyUI archive: it is built with the BCJ2
    filter, which py7zr does not implement and raises on. 7zr.exe is the
    official standalone extractor, is public domain, and is under 600 KB,
    so it ships with the app rather than being a dependency.
    """
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent.parent
    bundled = base / "tools" / "7zr.exe"
    if bundled.exists():
        return bundled
    for name in ("7zr", "7z"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def default_root():
    """Where the heavy files go, unless the user picks somewhere else."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "WispWasp"


def has_nvidia_gpu():
    """
    True when an NVIDIA GPU appears to be present.

    Checked with nvidia-smi because it ships with the driver; its absence
    usually means no driver, which is the thing that actually matters.
    """
    exe = shutil.which("nvidia-smi")
    if not exe:
        # Driver installs put it here even when it is not on PATH.
        fallback = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        fallback = fallback / "System32" / "nvidia-smi.exe"
        if not fallback.exists():
            return False, "No NVIDIA driver found"
        exe = str(fallback)
    try:
        out = subprocess.run(
            [exe, "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if out.returncode != 0:
            return False, "NVIDIA driver did not respond"
        line = (out.stdout or "").strip().splitlines()
        return (True, line[0].strip()) if line else (True, "NVIDIA GPU")
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)


def free_space(path):
    p = Path(path)
    while not p.exists() and p.parent != p:
        p = p.parent
    try:
        return shutil.disk_usage(str(p)).free
    except OSError:
        return 0


def find_comfy(root):
    """
    Locate an installed ComfyUI under root.

    The portable archive unpacks to ComfyUI_windows_portable containing
    python_embeded and ComfyUI, but people also point this at an existing
    install, so both shapes are accepted.
    """
    root = Path(root)
    candidates = [root / "ComfyUI_windows_portable", root]
    for base in candidates:
        main = base / "ComfyUI" / "main.py"
        python = base / "python_embeded" / "python.exe"
        if main.exists() and python.exists():
            return {"base": base, "main": main, "python": python,
                    "models": base / "ComfyUI" / "models" / "checkpoints",
                    "portable": True}
    # A plain git clone, which keeps its dependencies in its own venv.
    if (root / "main.py").exists():
        return {"base": root, "main": root / "main.py",
                "python": _venv_python(root),
                "models": root / "models" / "checkpoints", "portable": False}
    return None


def _venv_python(root):
    """
    Find the Python a cloned ComfyUI was set up with.

    A git clone keeps its dependencies in its own virtual environment, and
    torch is installed only there. Falling back to whatever "python" means
    on PATH launches an interpreter without torch, which exits instantly -
    so ComfyUI appears never to start, with nothing saying why.
    """
    root = Path(root)
    for rel in (".venv", "venv", "env", ".env"):
        candidate = root / rel / "Scripts" / "python.exe"
        if candidate.exists():
            return candidate
    return None


def checkpoints_in(folder):
    folder = Path(folder)
    if not folder.exists():
        return []
    return sorted(
        p for p in folder.glob("*.safetensors")
        if p.stat().st_size > PLAUSIBLE_MODEL_BYTES
    )


def candidate_roots(settings=None):
    """
    Places an existing ComfyUI might already be.

    Someone who already runs ComfyUI should not be asked to download
    another eight gigabytes of it, so the configured path is tried first
    and then the usual spots.
    """
    roots = []
    if settings is not None:
        configured = (settings.get("comfyui.path") or "").strip()
        if configured:
            roots.append(Path(configured))
    roots.append(default_root())
    home = Path.home()
    roots += [
        home / "ComfyUI",
        home / "Documents" / "ComfyUI",
        home / "Desktop" / "ComfyUI",
        Path("C:/ComfyUI"),
        Path("D:/ComfyUI"),
    ]
    seen, out = set(), []
    for r in roots:
        key = str(r).lower()
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def locate(settings):
    """
    Find ComfyUI. Returns (root, info or None).

    A path the user has actually chosen is honoured exactly - probing
    elsewhere would quietly install to, or report, somewhere they did not
    pick. Only an unset path triggers a search of the usual locations.
    """
    configured = (settings.get("comfyui.path") or "").strip()
    if configured:
        root = Path(configured)
        return root, find_comfy(root)

    for root in candidate_roots(None):
        info = find_comfy(root)
        if info:
            return root, info
    return default_root(), None


def check(settings):
    """
    Report what is present and what is missing.

    Returns a dict the UI can render directly, rather than raising, because
    every one of these is a normal state on a fresh machine.
    """
    root, comfy = locate(settings)
    gpu_ok, gpu_name = has_nvidia_gpu()
    models = checkpoints_in(comfy["models"]) if comfy else []

    return {
        "root": root,
        "gpu_ok": gpu_ok,
        "gpu_name": gpu_name,
        "comfy": comfy,
        "comfy_ok": comfy is not None,
        "models": models,
        "model_ok": bool(models),
        "free_bytes": free_space(root),
        "space_ok": free_space(root) >= REQUIRED_FREE_BYTES,
        "ready": bool(comfy) and bool(models),
    }


def human(n):
    """
    A size, in the units the rest of the world uses.

    Decimal, not binary. HuggingFace, Civitai and every download page
    count a gigabyte as 1000^3, so dividing by 1024^3 and writing "GB"
    made a 6.9 GB checkpoint appear as 6.5 GB and a 9.6 GB model as 8.9.
    Nothing was miscounted; the label was the wrong unit, which is worse
    than a rounding error because it looks like the app disagreeing with
    the page it is downloading from.
    """
    step = 1000.0
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < step or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= step
    return f"{n:.1f} GB"


# One gigabyte, as a download page means it. Used wherever a size is
# shown to somebody, so the app and the source they got the file from
# agree with each other.
GB = 1_000_000_000


class SetupCancelled(Exception):
    """Raised when the user stops a download or extraction."""


class Downloader:
    """
    Fetches a large file, resuming where it left off.

    A 6.6 GB transfer will sometimes be interrupted, and starting over each
    time is not acceptable, so bytes go to a .part file and a Range request
    picks up from its length.
    """

    def __init__(self, on_progress=None, cancel=None):
        self.on_progress = on_progress or (lambda **kw: None)
        self.cancel = cancel or (lambda: False)

    def _check(self):
        if self.cancel():
            raise SetupCancelled()

    def fetch(self, url, dest, label="", expect_min=0):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_suffix(dest.suffix + ".part")

        if dest.exists() and dest.stat().st_size >= expect_min:
            self.on_progress(label=label, done=dest.stat().st_size,
                             total=dest.stat().st_size, note="already here")
            return dest

        have = part.stat().st_size if part.exists() else 0
        req = urllib.request.Request(url, headers={
            "User-Agent": "WispWasp-Setup",
        })
        if have:
            req.add_header("Range", f"bytes={have}-")

        try:
            resp = urllib.request.urlopen(req, timeout=60)
        except Exception as exc:
            raise RuntimeError(f"Could not start the download: {exc}") from exc

        # A server that ignores the Range header answers 200 with the whole
        # file, in which case the partial data has to be discarded rather
        # than appended to - that would corrupt it silently.
        resuming = resp.status == 206
        if have and not resuming:
            have = 0
            part.unlink(missing_ok=True)

        total = int(resp.headers.get("Content-Length") or 0) + have
        mode = "ab" if resuming else "wb"
        started = time.time()
        done = have

        with open(part, mode) as fh:
            while True:
                self._check()
                chunk = resp.read(1024 * 512)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                elapsed = max(0.001, time.time() - started)
                speed = (done - have) / elapsed
                self.on_progress(label=label, done=done, total=total,
                                 speed=speed)
        resp.close()

        if expect_min and done < expect_min:
            raise RuntimeError(
                f"{label} downloaded only {human(done)}, which is short of "
                f"the expected size. The file was left in place so it can "
                f"resume.")

        part.replace(dest)
        self.on_progress(label=label, done=done, total=done, note="done")
        return dest


def comfy_asset_url():
    """Find the NVIDIA portable build in the latest ComfyUI release."""
    req = urllib.request.Request(
        COMFY_RELEASE_API, headers={"User-Agent": "WispWasp-Setup"})
    import json
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for asset in data.get("assets", []):
        if asset.get("name") == COMFY_ASSET:
            return asset["browser_download_url"], asset.get("size", 0)
    # The exact filename has changed before, so fall back to any nvidia
    # portable build rather than failing outright.
    for asset in data.get("assets", []):
        name = asset.get("name", "").lower()
        if "portable" in name and "nvidia" in name and name.endswith(".7z"):
            return asset["browser_download_url"], asset.get("size", 0)
    raise RuntimeError(
        "No Windows NVIDIA build was found in the latest ComfyUI release.")


class Installer:
    """
    Runs the setup steps in order, reporting progress as it goes.

    Designed to be run on a worker thread: every step checks the cancel
    callback, and anything already finished is skipped, so stopping and
    starting again resumes rather than repeating work.
    """

    def __init__(self, settings, on_progress=None, on_step=None,
                 cancel=None):
        self.s = settings
        self.on_progress = on_progress or (lambda **kw: None)
        self.on_step = on_step or (lambda *a, **k: None)
        self.cancel = cancel or (lambda: False)
        self.dl = Downloader(on_progress=self.on_progress, cancel=self.cancel)

    def _check(self):
        if self.cancel():
            raise SetupCancelled()

    def run(self, root=None, get_comfy=True, get_model=True):
        root = Path(root or self.s.get("comfyui.path") or default_root())
        root.mkdir(parents=True, exist_ok=True)

        if free_space(root) < REQUIRED_FREE_BYTES:
            raise RuntimeError(
                f"Not enough disk space on that drive. About "
                f"{human(REQUIRED_FREE_BYTES)} is needed and "
                f"{human(free_space(root))} is free.")

        if get_comfy and not find_comfy(root):
            self.on_step("comfy", "Fetching ComfyUI")
            self._install_comfy(root)

        comfy = find_comfy(root)
        if comfy is None:
            raise RuntimeError(
                "ComfyUI did not appear where it was expected after "
                f"extraction. Look in {root}.")

        if get_model and not checkpoints_in(comfy["models"]):
            self.on_step("model", "Fetching the image model")
            self._install_model(comfy)

        self.on_step("save", "Saving settings")
        self.s.set("comfyui.path", str(root))
        self.s.set("comfyui.autostart", True)
        self.s.save()
        self.on_step("done", "Ready")
        return check(self.s)

    def _install_comfy(self, root):
        url, size = comfy_asset_url()
        archive = root / COMFY_ASSET
        self.dl.fetch(url, archive, label="ComfyUI",
                      expect_min=int(size * 0.98) if size else 0)

        self._check()
        self.on_step("extract", "Unpacking ComfyUI")
        self._extract(archive, root)

        # The archive is over a gigabyte and serves no purpose once
        # unpacked, so it goes rather than sitting there forever.
        try:
            archive.unlink()
        except OSError:
            pass

    def _extract(self, archive, dest):
        """
        Unpack with 7zr.exe.

        It handles both things that defeated the pure-Python route: the
        BCJ2 filter this archive is built with, and paths past Windows'
        260 character limit.
        """
        exe = seven_zip_exe()
        if exe is None:
            raise RuntimeError(
                "The 7-Zip extractor is missing from this build, so the "
                "ComfyUI download cannot be unpacked. Reinstalling "
                "WispWasp should restore it.")

        dest.mkdir(parents=True, exist_ok=True)
        cmd = [str(exe), "x", str(archive), f"-o{dest}", "-y",
               "-bsp1",     # progress to stdout
               "-bso0"]     # without the file-by-file listing

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        self.on_progress(label="Unpacking", done=0, total=100)
        tail = b""
        last = 0.0
        try:
            while True:
                if self.cancel():
                    proc.terminate()
                    raise SetupCancelled()
                chunk = proc.stdout.read(64)
                if not chunk:
                    break
                tail += chunk
                # Progress is written with carriage returns rather than
                # newlines, so both are treated as line breaks.
                parts = tail.replace(b"\r", b"\n").split(b"\n")
                tail = parts[-1]
                for part in parts[:-1]:
                    text = part.decode("utf-8", "ignore").strip()
                    if "%" not in text:
                        continue
                    digits = text.split("%")[0].strip().split()
                    if digits and digits[-1].isdigit():
                        if time.time() - last > 0.4:
                            last = time.time()
                            self.on_progress(label="Unpacking",
                                             done=int(digits[-1]), total=100)
        finally:
            try:
                proc.stdout.close()
            except OSError:
                pass
            code = proc.wait()

        if code != 0:
            raise RuntimeError(
                f"Unpacking failed (7-Zip exit code {code}). The download "
                f"may be damaged; deleting it and running setup again "
                f"fetches a fresh copy.")
        self.on_progress(label="Unpacking", done=100, total=100)

    def _install_model(self, comfy):
        folder = Path(comfy["models"])
        folder.mkdir(parents=True, exist_ok=True)
        picked = tier(self.s)
        self.dl.fetch(picked["url"], folder / picked["name"],
                      label="Image model",
                      expect_min=picked["min_bytes"])


def checkpoints_dir(settings=None, root=None):
    """
    Where ComfyUI keeps its checkpoints.

    Asks the locator rather than assuming a layout: the portable archive
    unpacks one way, a git clone another, and people point this at an
    existing install of either shape. Guessing the portable path here
    reported models as missing on a perfectly good install.
    """
    if root is not None:
        info = find_comfy(root)
        if info:
            return info["models"]
        return _guess_checkpoints(Path(root))

    if settings is None:
        return _guess_checkpoints(default_root())

    where, info = locate(settings)
    if info:
        return info["models"]
    return _guess_checkpoints(Path(where))


def _guess_checkpoints(root):
    """
    Where checkpoints would go, before anything is installed.

    The configured path is sometimes the ComfyUI folder itself and
    sometimes the place ComfyUI will be put, and the two want different
    answers. A models folder already sitting there settles it; without
    one, assume ComfyUI has yet to arrive.
    """
    root = Path(root)
    if (root / "models").exists() or root.name.lower() == "comfyui":
        return root / "models" / "checkpoints"
    return root / "ComfyUI" / "models" / "checkpoints"


def tier_file(key, settings=None, root=None):
    """The path a given tier's model would occupy."""
    spec = TIERS.get(key)
    if spec is None:
        return None
    return checkpoints_dir(settings, root) / spec["name"]


_family_cache = {}


def family_of(path):
    """
    Which family a checkpoint belongs to: "sd15", "sdxl" or None.

    Read from the safetensors header rather than guessed from the name.
    People rename models, and almost nobody's SDXL checkpoint is called
    sd_xl_base_1.0 - judging by filename reported a folder full of
    perfectly good models as empty.

    SDXL carries two text encoders under conditioner.embedders; SD 1.5
    has a single cond_stage_model. That difference is in the weights, so
    it cannot be wrong about a renamed file.

    Cached against size and modification time, since this runs for every
    checkpoint each time the Setup page refreshes.
    """
    path = Path(path)
    try:
        stat = path.stat()
    except OSError:
        return None
    token = (str(path), stat.st_size, stat.st_mtime_ns)
    if token in _family_cache:
        return _family_cache[token]

    family = None
    try:
        with path.open("rb") as handle:
            length = struct.unpack("<Q", handle.read(8))[0]
            if 0 < length < 100_000_000:
                header = json.loads(handle.read(length).decode("utf-8"))
                keys = header.keys()
                if any(k.startswith("conditioner.embedders.1")
                       for k in keys):
                    family = "sdxl"
                elif any(k.startswith("cond_stage_model") for k in keys):
                    family = "sd15"
    except (OSError, ValueError, struct.error, UnicodeDecodeError):
        family = None

    _family_cache[token] = family
    return family


def models_for_tier(key, settings=None, root=None):
    """
    Every installed checkpoint that would satisfy this option.

    The official file first if it is there, then anything else of the
    same family, so "have I got an SDXL model" is answered by the models
    themselves rather than by one particular filename.
    """
    spec = TIERS.get(key)
    if spec is None:
        return []
    folder = checkpoints_dir(settings, root)
    if not folder.exists():
        return []

    official = folder / spec["name"]
    found = []
    if official.exists() and official.stat().st_size >= spec["min_bytes"]:
        found.append(official)
    for path in sorted(folder.glob("*.safetensors")):
        if path == official or path.stat().st_size < PLAUSIBLE_MODEL_BYTES:
            continue
        if family_of(path) == key:
            found.append(path)
    return found


def tier_installed(key, settings=None, root=None):
    """
    Is that tier's model really there?

    Size-checked rather than merely present: a part-finished download
    left behind under the right name would otherwise look installed and
    then fail to load.
    """
    return bool(models_for_tier(key, settings, root))


def stray_checkpoints(settings=None):
    """
    Models sitting where ComfyUI will never look for them.

    Downloads used to be written to <root>/models/checkpoints, which is
    right for a cloned ComfyUI and wrong for the portable build, where
    the real folder is further in. Anyone who downloaded a model on a
    portable install before that was fixed has gigabytes stranded in a
    folder nothing reads, so they can be found and moved rather than
    left to be discovered by hand.
    """
    configured = ""
    if settings is not None:
        configured = (settings.get("comfyui.path") or "").strip()
    root = Path(configured) if configured else default_root()

    guessed = root / "models" / "checkpoints"
    real = checkpoints_dir(settings)
    if guessed == real or not guessed.exists():
        return []
    return [path for path in sorted(guessed.glob("*.safetensors"))
            if path.stat().st_size > PLAUSIBLE_MODEL_BYTES]


def adopt_strays(settings=None):
    """
    Move stranded models into the folder ComfyUI reads.

    Moved rather than copied - they are the same file and nobody wants
    two copies of six gigabytes - and skipped rather than overwritten if
    something of that name is already there.

    Returns (moved, skipped, failed).
    """
    target = checkpoints_dir(settings)
    target.mkdir(parents=True, exist_ok=True)
    moved = skipped = failed = 0
    for path in stray_checkpoints(settings):
        destination = target / path.name
        if destination.exists():
            skipped += 1
            continue
        try:
            path.replace(destination)
            moved += 1
        except OSError:
            # Usually a different drive, where replace cannot work.
            try:
                shutil.move(str(path), str(destination))
                moved += 1
            except (OSError, shutil.Error):
                failed += 1
    return moved, skipped, failed


def installed_tiers(settings=None, root=None):
    """Which of the offered models are on disk."""
    return [key for key in TIERS
            if tier_installed(key, settings, root)]
