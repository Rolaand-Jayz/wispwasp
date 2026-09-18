"""
The model catalogue: searching, and downloading without losing work.

Every network call is faked. These tests are about how the code behaves
when a download is interrupted, resumed, refused or truncated - which is
most of what matters for a file measured in gigabytes - and none of that
needs a real server.
"""

import io
import json
import shutil
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QLabel

from avcore.models import (
    CatalogueError, ModelInfo, NeedsAccount, download, installed,
    part_files, search,
)

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    mark = "PASS" if ok else "FAIL"
    print(f"  {mark}  {name:<52}{('  [' + detail + ']') if detail else ''}")


tmp = Path("_modeltest")
shutil.rmtree(tmp, ignore_errors=True)
tmp.mkdir(parents=True, exist_ok=True)


class FakeResponse(io.BytesIO):
    """Just enough of an HTTP response."""

    def __init__(self, body, status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()
        return False


def catalogue_payload(count=3, nsfw=False):
    items = []
    for i in range(count):
        items.append({
            "id": 100 + i,
            "name": f"Model {i}",
            "description": "<p>A <b>useful</b> checkpoint.</p>",
            "nsfw": nsfw,
            "allowCommercialUse": ["Image"],
            "creator": {"username": "someone"},
            "tags": ["photo", "general"],
            "modelVersions": [{
                "baseModel": "SD 1.5",
                "images": [{"url": "https://example/img.png", "nsfw": False}],
                "files": [{
                    "primary": True,
                    "name": f"model_{i}.safetensors",
                    "sizeKB": 2_082_816,
                    "downloadUrl": f"https://example/download/{i}",
                }],
            }],
        })
    return json.dumps({"items": items}).encode("utf-8")


print("=== searching the catalogue ===")

seen = {}


def fake_search(request, timeout=None):
    seen["url"] = request.full_url
    seen["headers"] = dict(request.headers)
    return FakeResponse(catalogue_payload())


found = search(opener=fake_search)
check("it returns models", len(found) == 3, str(len(found)))
check("sizes are converted to bytes",
      found[0].size_bytes == 2_082_816 * 1024)
check("and shown in a form a person can judge",
      found[0].size_label == "2.1 GB", found[0].size_label)
check("html is stripped from descriptions",
      found[0].description == "A useful checkpoint.",
      found[0].description)
check("only checkpoints are asked for", "types=Checkpoint" in seen["url"])
check("the base model is passed through",
      "baseModels=SD+1.5" in seen["url"] or "SD%201.5" in seen["url"],
      seen["url"])

print("\n  adult content is filtered by default:")
check("the request asks for safe entries", "nsfw=false" in seen["url"])

search(include_adult=True, opener=fake_search)
check("and does not when adult content is wanted",
      "nsfw=false" not in seen["url"], seen["url"])


def adult_only(request, timeout=None):
    return FakeResponse(catalogue_payload(nsfw=True))


check("an adult entry is dropped even if the catalogue returns it",
      search(opener=adult_only) == [],
      "the filter is not left to the far end alone")
check("and kept when it was asked for",
      len(search(include_adult=True, opener=adult_only)) == 3)

print("\n  when the catalogue will not answer:")


def refuses(request, timeout=None):
    raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized",
                                 {}, None)


try:
    search(opener=refuses)
    check("a refusal is reported as needing an account", False)
except NeedsAccount as exc:
    check("a refusal is reported as needing an account",
          "API key" in str(exc), "not as a crash")
except Exception as exc:
    check("a refusal is reported as needing an account", False, str(exc))


def breaks(request, timeout=None):
    raise urllib.error.HTTPError(request.full_url, 500, "Server Error",
                                 {}, None)


try:
    search(opener=breaks)
    check("a server fault is reported plainly", False)
except CatalogueError as exc:
    check("a server fault is reported plainly", "500" in str(exc))

print("\n=== downloading ===")

BODY = bytes(range(256)) * 400          # 102,400 bytes
INFO = ModelInfo(
    name="Test Model",
    description="",
    base_model="SD 1.5",
    nsfw=False,
    file_name="test.safetensors",
    size_bytes=len(BODY),
    download_url="https://example/download/0",
)


def whole_file(request, timeout=None):
    return FakeResponse(BODY, 200,
                        {"Content-Length": str(len(BODY))})


into = tmp / "checkpoints"
path = download(INFO, into, opener=whole_file)
check("the file lands in the folder", path.exists())
check("with the right name", path.name == "test.safetensors")
check("and the right contents", path.read_bytes() == BODY)
check("no part file is left behind", not part_files(into))

print("\n  an interrupted download keeps what it got:")
shutil.rmtree(into, ignore_errors=True)
stopped_after = {"count": 0}


def stop_soon():
    stopped_after["count"] += 1
    return stopped_after["count"] > 2


def slow(request, timeout=None):
    return FakeResponse(BODY, 200, {"Content-Length": str(len(BODY))})


outcome = download(INFO, into, should_stop=stop_soon, opener=slow,
                   chunk=1024)
check("it reports that it did not finish", outcome is None)
parts = part_files(into)
check("a part file is kept", len(parts) == 1, str(len(parts)))
partial = parts[0].stat().st_size if parts else 0
check("holding what had arrived", 0 < partial < len(BODY), f"{partial} bytes")
check("and no finished file is pretended",
      not (into / "test.safetensors").exists(),
      "a truncated checkpoint that looks whole is the worst outcome")

print("\n  resuming asks only for the rest:")
asked = {}


def resume(request, timeout=None):
    asked["range"] = request.headers.get("Range")
    start = int(request.headers.get("Range").split("=")[1].split("-")[0])
    rest = BODY[start:]
    return FakeResponse(rest, 206, {"Content-Length": str(len(rest))})


path = download(INFO, into, opener=resume)
check("a Range header is sent", asked.get("range") is not None,
      str(asked.get("range")))
check("it starts from what was already there",
      asked["range"] == f"bytes={partial}-")
check("the finished file is complete", path.read_bytes() == BODY)
check("and the part file is gone", not part_files(into))

print("\n  a server that ignores Range does not corrupt the file:")
shutil.rmtree(into, ignore_errors=True)
into.mkdir(parents=True)
(into / "test.safetensors.part").write_bytes(BODY[:5000])


def ignores_range(request, timeout=None):
    # Answers 200 with the whole file despite being asked for part.
    return FakeResponse(BODY, 200, {"Content-Length": str(len(BODY))})


path = download(INFO, into, opener=ignores_range)
check("the file is still correct", path.read_bytes() == BODY,
      "appending to the part file would have doubled the start")

print("\n  a download that stops early is not passed off as finished:")
shutil.rmtree(into, ignore_errors=True)


def truncated(request, timeout=None):
    return FakeResponse(BODY[:1000], 200,
                        {"Content-Length": str(len(BODY))})


try:
    download(INFO, into, opener=truncated)
    check("it raises rather than returning a short file", False)
except CatalogueError as exc:
    check("it raises rather than returning a short file",
          "carry on" in str(exc), "and says the progress is kept")
check("no finished file was written",
      not (into / "test.safetensors").exists())

print("\n  a model that needs an account says so:")
shutil.rmtree(into, ignore_errors=True)


def needs_key(request, timeout=None):
    raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, None)


try:
    download(INFO, into, opener=needs_key)
    check("it explains rather than failing obscurely", False)
except NeedsAccount as exc:
    check("it explains rather than failing obscurely",
          "API key" in str(exc), "and names the model")

print("\n  an API key is attached when there is one:")
keys = {}


def capture_key(request, timeout=None):
    keys["auth"] = request.headers.get("Authorization")
    return FakeResponse(catalogue_payload())


search(api_key="secret-key", opener=capture_key)
check("as a bearer token", keys.get("auth") == "Bearer secret-key",
      str(keys.get("auth")))

search(opener=capture_key)
check("and not when there is not", keys.get("auth") is None)

print("\n  what is already installed:")
shutil.rmtree(into, ignore_errors=True)
into.mkdir(parents=True)
(into / "one.safetensors").write_bytes(b"x")
(into / "two.ckpt").write_bytes(b"x")
(into / "notes.txt").write_text("ignore me")
(into / "half.safetensors.part").write_bytes(b"x")
names = [p.name for p in installed(into)]
check("checkpoints are listed", names == ["one.safetensors", "two.ckpt"],
      str(names))
check("other files are not", "notes.txt" not in names)
check("part files are not offered as models",
      "half.safetensors.part" not in names)
check("but can be found for tidying up", len(part_files(into)) == 1)

shutil.rmtree(tmp, ignore_errors=True)

print("\n=== the browse window ===")
# The catalogue itself is stubbed. What is being checked here is the
# window's behaviour - what it lists, what it enables, where it saves -
# not that Civitai answers.
from PySide6.QtWidgets import QApplication, QPushButton

import avgui.model_browser as browser_module
from avgui import theme
from avgui.model_browser import ConfirmDownload, ModelBrowser

app = QApplication.instance() or QApplication([])
theme.apply_to(app, None)

asked = {}


def fake_search(query="", base_model="SD 1.5", include_adult=False,
                limit=20, api_key=None, opener=None):
    asked["query"] = query
    asked["base_model"] = base_model
    asked["include_adult"] = include_adult
    return [
        ModelInfo(name="Alpha", description="A model.", base_model="SD 1.5",
                  nsfw=False, file_name="alpha.safetensors",
                  size_bytes=2_147_483_648,
                  download_url="https://example/a", creator="someone",
                  licence="commercial use: Image"),
        ModelInfo(name="Beta", description="", base_model="SD 1.5",
                  nsfw=True, file_name="beta.safetensors",
                  size_bytes=4_294_967_296,
                  download_url="https://example/b"),
    ]


browser_module.search = fake_search

from avcore.config import Settings

panel_tmp = tmp / "browser"
panel_tmp.mkdir(parents=True, exist_ok=True)
sb = Settings.load(path=panel_tmp / "s.json")
sb.set("comfyui.path", str(panel_tmp / "ComfyUI"))
sb.save()

window = ModelBrowser(sb)


def settle(seconds=3.0):
    import time as _time
    end = _time.time() + seconds
    while _time.time() < end:
        app.processEvents()
        _time.sleep(0.01)
        worker = window._search
        if worker is not None and not worker.isRunning():
            app.processEvents()
            break


settle()
check("it lists what the catalogue returned", window.list.count() == 2,
      str(window.list.count()))
check("the search runs off the interface thread",
      isinstance(window._search, browser_module.SearchWorker),
      "a blocking call here froze the whole window once already")

print("\n  the download button waits for a choice:")
check("nothing selected, nothing to download", not window.get.isEnabled())
window.list.setCurrentRow(0)
app.processEvents()
check("choosing one offers it", window.get.isEnabled())

print("\n  it saves where ComfyUI looks:")
folder = window.checkpoints_folder()
check("under the configured ComfyUI",
      folder == panel_tmp / "ComfyUI" / "models" / "checkpoints",
      str(folder))
sb.set("comfyui.path", "")
check("and falls back to the default install",
      window.checkpoints_folder().name == "checkpoints",
      str(window.checkpoints_folder()))
sb.set("comfyui.path", str(panel_tmp / "ComfyUI"))

print("\n  the adult toggle changes the request, not the model:")
window.adult.setChecked(True)
settle()
check("it asks the catalogue for them", asked.get("include_adult") is True)
window.adult.setChecked(False)
settle()
check("and stops asking when unticked",
      asked.get("include_adult") is False)
check("the wording does not promise a restraint",
      "does not restrain" in window.adult.toolTip(),
      window.adult.toolTip()[:48])

print("\n  searching is not styled as a destructive action:")
check("the search button takes the ordinary style",
      window.go.objectName() == "",
      "the primary colour is for actions that change something")

print("\n  the confirmation states what it will cost:")
info = fake_search()[0]
dialog = ConfirmDownload(info, folder)
labels = " ".join(l.text() for l in dialog.findChildren(QLabel))
buttons = {b.objectName(): b for b in dialog.findChildren(QPushButton)}
# Same file, decimal units.
check("the size, in the title of the button", "2.1 GB" in labels)
check("where it is going", "checkpoints" in labels)
check("the licence terms", "commercial use" in labels)
check("that it can be resumed", "picked up again" in labels)
check("and refusing is the default",
      buttons["denyButton"].isDefault(),
      "nothing measured in gigabytes starts on a stray Enter")
dialog.reject()

print("\n=== managing what is installed ===")
from avgui.model_browser import ConfirmRemove

store = panel_tmp / "ComfyUI" / "models" / "checkpoints"
store.mkdir(parents=True, exist_ok=True)
(store / "alpha.safetensors").write_bytes(b"x" * 3_000_000)
(store / "beta.safetensors").write_bytes(b"x" * 5_000_000)
(store / "gamma.ckpt").write_bytes(b"x" * 1_000_000)
(store / "leftover.safetensors.part").write_bytes(b"x" * 2_000_000)
sb.set("comfyui.checkpoint", "beta.safetensors")

window.tabs.setCurrentIndex(1)
app.processEvents()

check("it lists what is on disk", window.have.count() == 3,
      str(window.have.count()))
check("with the total disk used", "9 MB" in window.disk.text(),
      window.disk.text())
check("sizes read sensibly below a gigabyte",
      "MB" in window.have.item(0).text(),
      "a list of 0.00 GB entries says nothing")
rows = [window.have.item(i).text() for i in range(window.have.count())]
check("the model in use is marked",
      any("in use" in row for row in rows),
      "removing it changes what gets generated")
check("unfinished downloads are counted separately",
      "unfinished" in window.leftovers.text(), window.leftovers.text())
check("and can be cleared", not window.tidy.isHidden())
check("download is hidden on this tab", not window.get.isVisible(),
      "a greyed-out button invites the question of why")

print("\n  removing waits for a choice:")
check("nothing picked, nothing to remove", not window.remove.isEnabled())
window.have.setCurrentRow(0)
app.processEvents()
check("picking one offers it", window.remove.isEnabled())

print("\n  the confirmation says what it costs:")
dialog = ConfirmRemove(store / "beta.safetensors", "5 MB", True)
words = " ".join(l.text() for l in dialog.findChildren(QLabel))
check("how much it frees", "5 MB" in words)
check("that it cannot be undone", "cannot be recovered" in words)
check("and that this one is in use", "currently selected" in words)
buttons = {b.objectName(): b for b in dialog.findChildren(QPushButton)}
check("keeping it is the default", buttons["denyButton"].isDefault())
dialog.reject()

print("\n  clearing unfinished downloads:")
window._tidy()
app.processEvents()
check("the part file is gone", not list(store.glob("*.part")))
check("it says how much was freed", "2 MB" in window.manage_note.text(),
      window.manage_note.text())
check("the models themselves are untouched", window.have.count() == 3)

print("\n  each tab keeps its own message:")
# A search finishing in the background used to wipe out the message
# about what had just been deleted.
window.find_note.setText("a search result")
window.manage_note.setText("a deletion result")
window._show(fake_search())
app.processEvents()
check("the find tab's line updated",
      "models" in window.find_note.text(), window.find_note.text())
check("the installed tab's line survived",
      window.manage_note.text() == "a deletion result",
      window.manage_note.text())

window.close()
app.processEvents()

print("\n=== progress survives a file bigger than 2 GB ===")
# Qt's int is 32 bits. A worker declaring Signal(int, int) wrapped any
# size over 2,147,483,647: a 4.27GB download arrived as -29,870,600 and
# the bar read "0.14 of -0.03 GB". Worse, the larger models wrapped to
# believable numbers - 9.6GB came through as 5.3GB, which nobody would
# think to report.
from PySide6.QtCore import QObject, Signal

from avgui.model_browser import DownloadWorker
from avgui.setup_panel import ModelFetch

LIMIT = 2 ** 31 - 1


def _carries(worker, value):
    """What a size looks like after a trip through the signal."""
    seen = []
    worker.progress.connect(lambda done, total: seen.append(total))
    worker.progress.emit(0, value)
    app.processEvents()
    return seen[-1] if seen else None


_dummy = ModelInfo(name="x", description="", base_model="", nsfw=False,
                   file_name="x", size_bytes=1, download_url="")
for name, worker in (("the model browser",
                      DownloadWorker(_dummy, tmp, None)),
                     ("the setup fetcher",
                      ModelFetch(Settings.load(path=tmp / "wrap.json")))):
    for label, size in (("a 4.27 GB model", 4_265_096_696),
                        ("the 9.6 GB video model", 9_559_625_980),
                        ("a 2 GB model", 2_000_000_000)):
        carried = _carries(worker, size)
        check(f"{name} carries {label} intact",
              carried == size,
              f"{carried:,} instead of {size:,}"
              if carried != size else f"{size:,}")

check("the wrap this replaces produced a negative",
      4_265_096_696 - 2 ** 32 < 0,
      "which is what showed as -0.03 GB")
check("and sizes under the limit were never affected",
      2_000_000_000 < LIMIT,
      "which is why small models looked fine and nobody noticed")

bad = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed")
if bad:
    print("FAILURES:")
    for n in bad:
        print(f"  - {n}")
    raise SystemExit(1)
print("the model catalogue works")
