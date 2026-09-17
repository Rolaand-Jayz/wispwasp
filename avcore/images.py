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
        wanted = (self.s.get("comfyui.checkpoint") or "").strip()
        if self._checkpoint and self._checkpoint_for == wanted:
            return self._checkpoint

        names = self.list_checkpoints()
        if not names:
            raise GenerationError(
                "No models installed. Put a .safetensors file in ComfyUI's "
                "models\\checkpoints folder and restart it."
            )

        if wanted:
            q = wanted.lower()
            exact = [n for n in names if n.lower() == q]
            partial = [n for n in names if q in n.lower()]
            self._checkpoint = (exact or partial or names)[0]
        else:
            self._checkpoint = names[0]
        self._checkpoint_for = wanted
        return self._checkpoint

    def set_checkpoint(self, name):
        self._checkpoint = name
        # Set by hand rather than resolved, so it is pinned until the
        # setting itself changes.
        self._checkpoint_for = (self.s.get("comfyui.checkpoint") or "").strip()

    def _workflow(self, prompt, width, height, seed):
        return {
            "1": {"class_type": "CheckpointLoaderSimple",
                  "inputs": {"ckpt_name": self.checkpoint()}},
            "2": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": prompt, "clip": ["1", 1]}},
            "3": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": self.s.get("image.negative_prompt", ""),
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
