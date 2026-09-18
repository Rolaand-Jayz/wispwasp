"""Image generation backends. ComfyUI is local; Pollinations is a fallback."""

import time
import urllib.parse

import requests


class GenerationError(RuntimeError):
    """Raised when a backend can't produce an image."""


def _was_interrupted(messages):
    """Did this job stop because somebody stopped it?"""
    for entry in messages or []:
        if isinstance(entry, (list, tuple)) and entry:
            if entry[0] == "execution_interrupted":
                return True
    return False


def _why(messages):
    """
    A readable reason out of ComfyUI's status log.

    The log is a list of pairs carrying node ids, timestamps and cache
    details. Printing the whole thing into the window told nobody
    anything; the useful parts are the exception and which node raised
    it.
    """
    for entry in messages or []:
        if not (isinstance(entry, (list, tuple)) and len(entry) > 1):
            continue
        if entry[0] != "execution_error":
            continue
        detail = entry[1] if isinstance(entry[1], dict) else {}
        reason = (detail.get("exception_message") or "").strip()
        node = (detail.get("node_type") or "").strip()
        if reason and node:
            return f"{reason} (in {node})"
        if reason:
            return reason
    # Nothing recognisable: say so rather than dumping the structure.
    return "ComfyUI reported an error but gave no reason."


class ComfyBackend:
    """Talks to a running ComfyUI instance over its HTTP API."""

    def __init__(self, settings):
        self.s = settings
        self._checkpoint = None
        self._checkpoint_for = None

    @property
    def url(self):
        return self.s.get("comfyui.url", "http://127.0.0.1:8188").rstrip("/")

    def is_up(self, timeout=4):
        try:
            requests.get(f"{self.url}/system_stats",
                         timeout=timeout).raise_for_status()
            return True
        except requests.RequestException:
            return False

    def list_checkpoints(self):
        try:
            # A short connect timeout, a longer read one. This runs on
            # the UI thread whenever ComfyUI comes or goes, and ComfyUI
            # is on this machine: if it does not accept a connection
            # within a couple of seconds it is not going to. Thirty
            # seconds here froze the whole window whenever ComfyUI was
            # stopped, wedged, or had left its port bound behind it.
            r = requests.get(
                f"{self.url}/object_info/CheckpointLoaderSimple",
                timeout=(2.5, 10))
            r.raise_for_status()
        except requests.RequestException as exc:
            # The raw urllib3 text - HTTPConnectionPool, Max retries,
            # WinError 10061 - says nothing a person can act on. What
            # matters is that ComfyUI is not running.
            raise GenerationError(self._unreachable(exc)) from exc
        node = r.json()["CheckpointLoaderSimple"]["input"]["required"]
        return list(node["ckpt_name"][0])

    def _unreachable(self, exc):
        if isinstance(exc, requests.ConnectionError):
            return (f"ComfyUI is not running at {self.url}. It should start "
                    f"by itself within a minute; if it does not, check "
                    f"Setup, or start ComfyUI yourself.")
        return f"ComfyUI did not respond: {exc}"

    def checkpoint(self):
        """
        Resolve which checkpoint to use.

        The answer is cached, but against the setting it came from. It
        used to be cached outright, so changing the model in Settings or
        pressing Use in Setup changed nothing until the app was
        restarted - the old model kept generating and the new choice
        looked as though it had been ignored.
        """
        from .safety import is_on

        # Keyed on safe mode as well as the setting. With "first found"
        # the setting is blank either way, so a checkpoint resolved
        # before the tick went on would have been handed back after it -
        # the cache remembering exactly the answer that is no longer
        # allowed.
        wanted = (self.s.get("comfyui.checkpoint") or "").strip()
        token = (wanted, is_on(self.s))
        if self._checkpoint and self._checkpoint_for == token:
            return self._checkpoint

        names = self.list_checkpoints()
        if not names:
            raise GenerationError(
                "No models installed. Put a .safetensors file in ComfyUI's "
                "models\\checkpoints folder and restart it."
            )

        # Safe mode filters the pickers, but "first found" never went
        # through one - it asked ComfyUI for everything it had and took
        # the first, which on this machine was an adult model that the
        # lists were deliberately hiding. Filtering here closes that,
        # because every path to a checkpoint comes through this method.
        from .safety import is_on

        if is_on(self.s):
            from .setup import looks_adult

            allowed = [n for n in names if not looks_adult(n)]
            if not allowed:
                raise GenerationError(
                    "Safe mode is on and every installed model is "
                    "flagged as adult. Install another model, or turn "
                    "safe mode off in Settings."
                )
            names = allowed

        if wanted:
            q = wanted.lower()
            exact = [n for n in names if n.lower() == q]
            partial = [n for n in names if q in n.lower()]
            # Falls back to the first allowed name rather than the first
            # of everything: a model chosen before safe mode was turned
            # on should not keep being used after it.
            self._checkpoint = (exact or partial or names)[0]
        else:
            self._checkpoint = names[0]
        self._checkpoint_for = token
        return self._checkpoint

    def set_checkpoint(self, name):
        self._checkpoint = name
        # Set by hand rather than resolved, so it is pinned until the
        # setting itself changes.
        from .safety import is_on

        self._checkpoint_for = (
            (self.s.get("comfyui.checkpoint") or "").strip(),
            is_on(self.s))

    def _workflow(self, prompt, width, height, seed):
        graph = {
            "1": {"class_type": "CheckpointLoaderSimple",
                  "inputs": {"ckpt_name": self.checkpoint()}},
            "2": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": prompt, "clip": ["1", 1]}},
            "3": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": self._negative(),
                             "clip": ["1", 1]}},
            "4": {"class_type": "EmptyLatentImage",
                  "inputs": {"width": width, "height": height,
                             "batch_size": 1}},
            "5": {"class_type": "KSampler",
                  "inputs": {"seed": seed,
                             "steps": int(self.s.get("comfyui.steps", 20)),
                             "cfg": float(self.s.get("comfyui.cfg", 6.5)),
                             "sampler_name": self.s.get("comfyui.sampler",
                                                        "dpmpp_2m"),
                             "scheduler": self.s.get("comfyui.scheduler",
                                                     "karras"),
                             "denoise": 1.0,
                             "model": ["1", 0], "positive": ["2", 0],
                             "negative": ["3", 0], "latent_image": ["4", 0]}},
            "6": {"class_type": "VAEDecode",
                  "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
            "7": {"class_type": "SaveImage",
                  "inputs": {"images": ["6", 0],
                             "filename_prefix": "WispWasp"}},
        }
        graph = self._with_loras(graph)
        if self._cutting():
            graph.update(self._cutout_nodes())
        return graph

    def chosen_loras(self):
        """
        The LoRAs that are switched on, in the order they are listed.

        Order matters: each one is applied on top of the last, and two
        that pull in different directions give a different picture
        depending on which goes first.

        Anything no longer on disk is skipped rather than passed to
        ComfyUI, which would fail the whole job over a file somebody
        deleted months ago.
        """
        from .models import installed
        from .setup import loras_dir

        chosen = self.s.get("comfyui.loras") or []
        if not isinstance(chosen, list):
            return []

        try:
            present = {path.name for path in installed(loras_dir(self.s))}
        except Exception:
            present = set()

        live = []
        for entry in chosen:
            if not isinstance(entry, dict) or not entry.get("on"):
                continue
            name = (entry.get("name") or "").strip()
            if not name or name not in present:
                continue
            try:
                strength = float(entry.get("strength", 1.0))
            except (TypeError, ValueError):
                strength = 1.0
            live.append((name, max(-4.0, min(4.0, strength))))
        return live

    def _with_loras(self, graph):
        """
        Chain a LoraLoader for each one, between the checkpoint and
        everything that uses it.

        Both the model and the text encoder have to come through the
        chain: a LoRA that changes only the model and not the CLIP
        produces something that half-remembers the style it was asked
        for, which is worse than not applying it at all.
        """
        loras = self.chosen_loras()
        if not loras:
            return graph

        model_from = ["1", 0]
        clip_from = ["1", 1]
        for index, (name, strength) in enumerate(loras):
            node = f"2{index}"
            graph[node] = {
                "class_type": "LoraLoader",
                "inputs": {
                    "lora_name": name,
                    "strength_model": strength,
                    "strength_clip": strength,
                    "model": model_from,
                    "clip": clip_from,
                },
            }
            model_from = [node, 0]
            clip_from = [node, 1]

        # Everything downstream now reads from the end of the chain.
        graph["2"]["inputs"]["clip"] = clip_from
        graph["3"]["inputs"]["clip"] = clip_from
        graph["5"]["inputs"]["model"] = model_from
        return graph

    def _trim(self, path):
        """
        Crop a cut-out down to what is actually in it.

        The model puts the subject wherever it likes in the frame, and a
        rubber duck occupying two percent of a 768 square is a sticker
        that is almost entirely nothing. On the overlay, where the
        picture is shown whole rather than cropped to fill, that empty
        margin is what decides how small the subject looks.

        Left alone if the picture is nearly all subject already, so the
        common case costs nothing.
        """
        from PySide6.QtGui import QImage

        picture = QImage(str(path))
        if picture.isNull() or not picture.hasAlphaChannel():
            return path

        # Sampled rather than exhaustive: every fourth pixel is plenty to
        # find an edge, and a full scan of a large image is slow enough
        # to notice in a twenty second cycle.
        step = 4
        left, top = picture.width(), picture.height()
        right = bottom = 0
        for y in range(0, picture.height(), step):
            for x in range(0, picture.width(), step):
                if picture.pixelColor(x, y).alpha() > 24:
                    left = min(left, x)
                    right = max(right, x)
                    top = min(top, y)
                    bottom = max(bottom, y)

        if right <= left or bottom <= top:
            return path            # nothing survived the cut

        pad = max(8, int(min(picture.width(), picture.height()) * 0.02))
        left = max(0, left - pad)
        top = max(0, top - pad)
        right = min(picture.width() - 1, right + pad)
        bottom = min(picture.height() - 1, bottom + pad)

        width = right - left + 1
        height = bottom - top + 1
        if width >= picture.width() * 0.9 and height >= picture.height() * 0.9:
            return path            # already fills the frame

        picture.copy(left, top, width, height).save(str(path), "PNG")
        return path

    def _negative(self):
        """
        The negative prompt, with the safety terms while safe mode is on.

        Added here rather than written into the setting, so turning safe
        mode off gives back exactly the negative prompt somebody chose
        rather than one this app has edited behind them.
        """
        from .safety import is_on, negative_with_safety

        written = self.s.get("image.negative_prompt", "")
        return negative_with_safety(written) if is_on(self.s) else written

    def _cutting(self):
        """
        Should the background be removed from this image?

        Both the setting and the model have to be there. Asking for a
        cut-out without the model would fail the whole job, and losing
        the picture because of a decoration would be the wrong trade.
        """
        from .setup import cutout_installed

        if not self.s.get("image.cutout", False):
            return False
        return cutout_installed(self.s)

    def _cutout_nodes(self):
        """
        Four nodes that turn the picture into a sticker.

        The mask is inverted on the way through: RemoveBackground marks
        the background rather than the subject, so joining it straight
        onto the image gives a transparent teapot in an opaque room.
        """
        from .setup import CUTOUT_MODEL

        return {
            "8": {"class_type": "LoadBackgroundRemovalModel",
                  "inputs": {"bg_removal_name": CUTOUT_MODEL["name"]}},
            "9": {"class_type": "RemoveBackground",
                  "inputs": {"bg_removal_model": ["8", 0],
                             "image": ["6", 0]}},
            "10": {"class_type": "InvertMask",
                   "inputs": {"mask": ["9", 0]}},
            "11": {"class_type": "JoinImageWithAlpha",
                   "inputs": {"image": ["6", 0], "alpha": ["10", 0]}},
            # Replaces node 7 rather than adding beside it, so only the
            # cut-out version is written.
            "7": {"class_type": "SaveImage",
                  "inputs": {"images": ["11", 0],
                             "filename_prefix": "WispWasp"}},
        }

    def generate(self, prompt, dest, seed=None, cancel=None):
        """Render one image to `dest`. Returns the path."""
        width = int(self.s.get("image.width", 1344))
        height = int(self.s.get("image.height", 768))
        seed = seed if seed is not None else int(time.time() * 1000) % 2**31
        timeout = int(self.s.get("comfyui.timeout", 180))

        wf = self._workflow(prompt, width, height, seed)
        try:
            r = requests.post(f"{self.url}/prompt", json={"prompt": wf},
                              timeout=30)
        except requests.RequestException as exc:
            raise GenerationError(f"ComfyUI is not reachable: {exc}") from exc

        if r.status_code == 400:
            raise GenerationError(f"ComfyUI rejected the job: {r.text[:300]}")
        r.raise_for_status()
        pid = r.json()["prompt_id"]

        return self._await_result(pid, dest, timeout, cancel)

    def _await_result(self, pid, dest, timeout, cancel=None):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if cancel and cancel():
                self.interrupt()
                raise GenerationError("cancelled")
            time.sleep(0.4)

            try:
                h = requests.get(f"{self.url}/history/{pid}", timeout=30)
                h.raise_for_status()
                hist = h.json().get(pid)
            except requests.RequestException as exc:
                raise GenerationError(f"lost contact: {exc}") from exc

            if not hist:
                continue

            status = hist.get("status", {})
            if status.get("status_str") == "error":
                msgs = status.get("messages", [])
                if _was_interrupted(msgs):
                    # Stopping a job is not a fault. ComfyUI files it
                    # under "error" either way, and the cancel flag has
                    # usually been cleared by the time this reads the
                    # history, so the interruption has to be recognised
                    # here or a deliberate Cancel is reported as a
                    # failure - with a page of internal status dumped
                    # into the window.
                    raise GenerationError("cancelled")
                raise GenerationError(f"render failed: {_why(msgs)}")

            for node in hist.get("outputs", {}).values():
                for img in node.get("images", []):
                    return self._download(img, dest)

        raise GenerationError(f"no image after {timeout}s")

    def _download(self, img, dest):
        v = requests.get(
            f"{self.url}/view",
            params={"filename": img["filename"],
                    "subfolder": img.get("subfolder", ""),
                    "type": img.get("type", "output")},
            timeout=60)
        v.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(v.content)
        if self._cutting():
            # Only cut-outs have a margin worth removing, and only they
            # are shown whole rather than cropped to fill.
            self._trim(dest)
        return dest

    def interrupt(self):
        """Ask ComfyUI to abandon the job it's working on."""
        try:
            requests.post(f"{self.url}/interrupt", timeout=10)
        except requests.RequestException:
            pass

    @property
    def extension(self):
        return "png"


class PollinationsBackend:
    """
    Fallback only. Pollinations removed nologo, negative_prompt and enhance
    from their API on 2026-06-10, so images come back watermarked and the
    negative prompt is ignored. It also rate-limits hard under ~30s spacing.
    """

    def __init__(self, settings):
        self.s = settings

    def is_up(self, timeout=4):
        return True

    def list_checkpoints(self):
        return []

    def checkpoint(self):
        return "pollinations"

    def generate(self, prompt, dest, seed=None, cancel=None):
        w = int(self.s.get("image.width", 1024))
        h = int(self.s.get("image.height", 576))
        seed = seed if seed is not None else int(time.time())
        url = (f"https://image.pollinations.ai/prompt/"
               f"{urllib.parse.quote(prompt)}"
               f"?width={w}&height={h}&seed={seed}")

        last = None
        for wait in (0, 6, 14):
            if cancel and cancel():
                raise GenerationError("cancelled")
            if wait:
                time.sleep(wait)
            try:
                r = requests.get(url, timeout=180)
            except requests.RequestException as exc:
                last = str(exc)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                last = f"HTTP {r.status_code}"
                continue
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            return dest

        raise GenerationError(f"Pollinations unavailable ({last})")

    def interrupt(self):
        pass

    @property
    def extension(self):
        return "jpg"


def make_backend(settings):
    """Build the backend named in settings."""
    name = (settings.get("image.backend") or "comfyui").lower()
    if name == "pollinations":
        return PollinationsBackend(settings)
    return ComfyBackend(settings)
