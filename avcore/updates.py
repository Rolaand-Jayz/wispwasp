"""
Finding out whether a newer build exists.

Deliberately only finds out. Nothing here downloads or installs
anything: the app says a new version is available and offers to open the
page, and the person decides. Code that fetches and runs an executable
on someone else's machine is a serious thing to own, and this project
has no signing to back it up - so it does not do that.
"""

import json
import urllib.error
import urllib.request

from .version import RELEASES_PAGE, UPDATE_MANIFEST, __version__, is_newer

AGENT = "WispWasp/{}".format(__version__)


class UpdateError(Exception):
    """The check could not be completed."""


def fetch_manifest(url=None, opener=None, timeout=15):
    """
    Read the published manifest.

    Short timeout and no retries: this is a convenience, and an app that
    pauses on startup because a server is slow is worse than one that
    quietly does not know.
    """
    url = (url or UPDATE_MANIFEST or "").strip()
    if not url:
        raise UpdateError("No update source is configured.")

    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    try:
        with (opener or urllib.request.urlopen)(
                request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"The update server answered {exc.code}.") from exc
    except Exception as exc:
        raise UpdateError(f"Could not reach the update server: {exc}") from exc

    if not isinstance(payload, dict) or not payload.get("version"):
        raise UpdateError("The update information was not readable.")
    return payload


def check(url=None, current=None, opener=None):
    """
    Is there a newer build?

    Returns a dict describing it, or None when this is the latest. The
    version comparison tolerates anything - a malformed manifest makes
    the answer "no newer version", never a crash on startup.
    """
    running = current or __version__
    manifest = fetch_manifest(url, opener)
    offered = str(manifest.get("version", ""))
    if not is_newer(offered, running):
        return None
    return {
        "version": offered,
        # Carried along so the description cannot disagree with the
        # comparison. Reading the module version separately meant a
        # check made against another build described itself wrongly.
        "current": running,
        "page": (manifest.get("page") or RELEASES_PAGE or "").strip(),
        "notes": (manifest.get("notes") or "").strip(),
        "size": manifest.get("size") or 0,
    }


def describe(found):
    """One line a person can read, for whatever the check turned up."""
    if not found:
        return f"You have the latest version ({__version__})."
    running = found.get("current") or __version__
    size = found.get("size") or 0
    if size:
        return (f"Version {found['version']} is available "
                f"({size / 1_000_000:.0f} MB). You have {running}.")
    return f"Version {found['version']} is available. You have {running}."
