"""
Starts and stops the local ComfyUI process.

Launched without a console window, since a stray black terminal sitting on
screen during a stream is exactly what nobody wants.
"""

import subprocess
import time

import requests

from .setup import locate

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ComfyLauncher:
    def __init__(self, settings):
        self.s = settings
        self.process = None
        self.error = ""

    @property
    def url(self):
        return self.s.get("comfyui.url", "http://127.0.0.1:8188").rstrip("/")

    def is_up(self, timeout=3):
        try:
            requests.get(f"{self.url}/system_stats",
                         timeout=timeout).raise_for_status()
            return True
        except requests.RequestException:
            return False

    def is_starting(self):
        """True when a process we launched is alive but not yet answering."""
        if self.process is None:
            return False
        if self.process.poll() is not None:
            # It exited. Clearing this is what allows another attempt;
            # otherwise a crashed ComfyUI would look permanently "starting".
            self.process = None
            return False
        return not self.is_up()

    def wait_until_up(self, seconds, on_progress=None):
        """Wait for an instance that is already booting."""
        report = on_progress or (lambda msg: None)
        deadline = time.time() + seconds
        while time.time() < deadline:
            if self.is_up():
                report("ComfyUI is ready")
                return True
            if self.process is not None and self.process.poll() is not None:
                self.process = None
                self.error = ("ComfyUI stopped while starting up. Try "
                              "running it on its own to see why.")
                return False
            time.sleep(2)
        return False

    def start(self, wait=240, on_progress=None):
        """
        Start ComfyUI if it is not already answering.

        Returns True once it responds. Somebody else's instance answering
        on the same port counts as success - starting a second one would
        just fight over the GPU.
        """
        report = on_progress or (lambda msg: None)

        if self.is_up():
            report("ComfyUI is already running")
            return True

        # Never leave a second process behind: if one we started is still
        # alive, wait on it rather than spawning another.
        if self.process is not None and self.process.poll() is None:
            return self.wait_until_up(wait, on_progress)
        self.process = None

        info = locate(self.s)[1]
        if not info:
            self.error = ("ComfyUI is not installed yet. Open Setup to "
                          "install it.")
            return False

        port = self.url.rsplit(":", 1)[-1]
        python = info.get("python")
        if info["portable"]:
            cmd = [str(python), "-s", str(info["main"]),
                   "--windows-standalone-build"]
        elif python is not None:
            # The clone's own virtual environment, which is where torch
            # lives. Anything else exits immediately.
            cmd = [str(python), str(info["main"])]
        else:
            self.error = (
                f"No Python environment was found for the ComfyUI at "
                f"{info['base']}. It needs a virtual environment - a "
                f".venv folder alongside main.py - with its requirements "
                f"installed. Starting ComfyUI once by hand will create it.")
            return False
        cmd += ["--port", port]

        try:
            self.process = subprocess.Popen(
                cmd, cwd=str(info["main"].parent),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=_NO_WINDOW,
            )
        except OSError as exc:
            self.error = f"Could not start ComfyUI: {exc}"
            return False

        report("Starting ComfyUI...")
        deadline = time.time() + wait
        while time.time() < deadline:
            if self.process.poll() is not None:
                self.error = ("ComfyUI stopped while starting up. Try "
                              "running it on its own to see why.")
                return False
            if self.is_up():
                report("ComfyUI is ready")
                return True
            time.sleep(2)

        self.error = f"ComfyUI did not answer within {wait} seconds."
        return False

    def stop(self):
        """
        Stop an instance this app started, and its children.

        ComfyUI relaunches itself, so the process we spawned is the parent
        of the one actually serving. Terminating only our own handle left
        that child alive, still holding port 8188 and the GPU - which
        looks exactly like "ComfyUI did not close properly", and stops the
        next run from starting cleanly.
        """
        proc = self.process
        self.process = None
        if proc is None or proc.poll() is not None:
            return

        try:
            import psutil
            parent = psutil.Process(proc.pid)
            family = parent.children(recursive=True) + [parent]
        except Exception:
            family = []

        if family:
            for p in family:
                try:
                    p.terminate()
                except Exception:
                    pass
            try:
                import psutil
                _alive = psutil.wait_procs(family, timeout=8)[1]
                for p in _alive:
                    p.kill()
            except Exception:
                pass
            return

        # No psutil, so fall back to asking Windows to kill the tree.
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True, timeout=15,
                creationflags=_NO_WINDOW)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
