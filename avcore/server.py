"""
The little web server behind the overlay.

Runs in a daemon thread inside the app. Serves three things: the overlay
page, the state file it polls, and the images themselves. OBS can either
point a Browser Source at it or capture a browser window showing it -
both routes hit the same server.
"""

import logging
import socket
import threading
from pathlib import Path

from flask import Flask, jsonify, send_file, send_from_directory


def port_is_free(port, host="127.0.0.1"):
    """
    True when nothing is listening on the port.

    This probes with a connection rather than a bind. On Windows,
    SO_REUSEADDR permits binding a port that another socket is actively
    listening on, so a bind test reports a busy port as free - and two
    copies of the app would both think they had it.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        if sock.connect_ex((host, port)) == 0:
            return False   # something answered

    # Nothing answered, but the port could still be reserved, so confirm
    # it can actually be bound - without SO_REUSEADDR this time.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


class OverlayServer:
    def __init__(self, settings, app_dir=None):
        self.s = settings
        self.app_dir = Path(app_dir or Path(__file__).resolve().parent.parent)
        self.thread = None
        self.error = ""
        self._flask = self._build()

    @property
    def port(self):
        return int(self.s.get("server.port", 8420))

    def _overlay_dir(self):
        return self.s.dir_for("paths.overlay_dir", "output")

    def _build(self):
        app = Flask(__name__, static_folder=None)

        # Flask's request log would fill the console, since the overlay
        # polls every couple of seconds.
        logging.getLogger("werkzeug").setLevel(logging.ERROR)

        @app.route("/")
        @app.route("/overlay.html")
        def overlay():
            page = self.app_dir / "overlay.html"
            if not page.exists():
                return "overlay.html is missing", 404
            return send_file(page)

        @app.after_request
        def _never_cache(response):
            """
            Tell every browser not to keep the page.

            OBS's browser source caches hard, and the page changes shape
            between versions - when it learned to be transparent, a
            cached copy carried on painting itself black over the scene
            and looked exactly like the app being broken. "no-cache"
            only asks for revalidation; "no-store" means it cannot be
            kept at all, which is what is wanted for a page that is
            served from localhost and costs nothing to fetch again.
            """
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0")
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

        @app.route("/state.json")
        def state():
            f = self._overlay_dir() / "state.json"
            if not f.exists():
                return jsonify({"image": None, "status": "starting up"})
            return send_file(f, mimetype="application/json")

        @app.route("/img/<path:name>")
        def image(name):
            # send_from_directory rejects paths that escape the folder, so
            # a crafted name cannot reach the rest of the disk.
            return send_from_directory(self._overlay_dir(), name)

        return app

    def start(self):
        """
        Start serving. Returns True on success; on a port clash it records
        the reason instead of raising, because a busy port is a normal
        thing to hit (an old listener.py still running) and shouldn't stop
        the app from opening.
        """
        if self.thread and self.thread.is_alive():
            return True

        if not port_is_free(self.port):
            self.error = (
                f"Port {self.port} is already in use. If listener.py or "
                f"another copy of the app is running, close it - or pick a "
                f"different port in Settings.")
            return False

        def serve():
            try:
                self._flask.run(host="127.0.0.1", port=self.port,
                                threaded=True, debug=False,
                                use_reloader=False)
            except Exception as exc:
                self.error = str(exc)

        self.thread = threading.Thread(
            target=serve, name="av-server", daemon=True)
        self.thread.start()
        self.error = ""
        return True

    def url(self, bare=True):
        suffix = "?bare=1" if bare else ""
        return f"http://127.0.0.1:{self.port}/overlay.html{suffix}"

    def is_running(self):
        return bool(self.thread and self.thread.is_alive())
