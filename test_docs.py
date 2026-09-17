"""
Checks SETUP.md against the code it describes.

Documentation drifts silently, and a confidently wrong document is worse
than none - so the claims that can be checked mechanically are.
"""
from pathlib import Path

from avcore.config import DEFAULTS
from avgui import theme

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  {'PASS' if cond else '*** FAIL ***':<14} {name}"
          + (f"  [{detail}]" if detail else ""))


doc = Path("SETUP.md").read_text(encoding="utf-8")


def _registries_last(path):
    """
    Is every registry below the last thing it names?

    Checked rather than trusted: this has broken once per theme, and a
    registry stranded above a painter only fails when that theme is
    selected.
    """
    text = Path(path).read_text(encoding="utf-8")
    marker = text.find("PAINTERS = {")
    if marker < 0:
        return False
    after = text[marker:]
    # Nothing may define a painter or a stylesheet after the registries.
    return ("\ndef " not in after.replace("\ndef painter_for", "")
            .replace("\ndef theme_names", "")
            .replace("\ndef style_sheet", "")
            and "_QSS = " not in after)

print("=== every settings key it documents exists ===")


def flat(prefix, block):
    out = {}
    for key, value in block.items():
        if isinstance(value, dict):
            out.update(flat(f"{prefix}{key}.", value))
        else:
            out[f"{prefix}{key}"] = value
    return out


real_keys = set(flat("", DEFAULTS))
documented = set()
for line in doc.splitlines():
    if not (line.startswith("| `") and "` |" in line):
        continue
    key = line.split("`")[1]
    # Settings keys are dotted names. Filenames and paths also contain
    # dots, so they are excluded rather than reported as unknown keys.
    if "." not in key or "/" in key or "\\" in key:
        continue
    if key.rsplit(".", 1)[-1] in ("py", "exe", "json", "html", "ps1"):
        continue
    documented.add(key)

unknown = sorted(k for k in documented if k not in real_keys)
check("no settings key is documented that does not exist",
      not unknown, ", ".join(unknown) or "all valid")
print(f"     ({len(documented)} keys documented, "
      f"{len(real_keys)} exist)")

print("\n=== every test file it lists exists ===")
listed = set()
for line in doc.splitlines():
    if line.startswith("| `test_") and "` |" in line:
        listed.add(line.split("`")[1])
missing = sorted(t for t in listed if not Path(t).exists())
check("no test file is listed that is absent",
      not missing, ", ".join(missing) or f"{len(listed)} listed")

print("\n=== every suite in build.ps1 is documented ===")
build = Path("build.ps1").read_text(encoding="utf-8")
in_build = {part.split('"')[0] for part in build.split('"test_')[1:]}
in_build = {f"test_{p}" for p in in_build}
undocumented = sorted(t for t in in_build if t not in listed)
check("the test table covers what the build runs",
      not undocumented, ", ".join(undocumented) or f"{len(in_build)} suites")

print("\n=== colour names it references are real ===")
for name in ("TALLY", "WORKING", "OK", "FAVOURITE", "DANGER", "SELECTION"):
    check(f"theme.{name} exists", hasattr(theme, name))

print("\n=== selection is not the alarm colour ===")
# Selecting a word is not an emergency. Sharing the tally red here drains
# the meaning out of the colour that actually matters.
check("text selection is not the tally red",
      theme.SELECTION != theme.TALLY, theme.SELECTION)
check("and the stylesheet uses it",
      f"selection-background-color: {theme.SELECTION}" in theme.QSS)
check("the tally red is not used for any selection",
      f"selection-background-color: {theme.TALLY}" not in theme.QSS)

print("\n=== claims that must stay true ===")
check("the doc mentions the panels-hold-no-state rule",
      "Panels never store state" in doc)
check("it records why the style is split from the prompt",
      "cannot be separated again" in doc)
check("it warns about running ISCC alone",
      "Do not run ISCC on its own" in doc)
check("it explains the disabled-colour trap",
      "overrides Qt's" in doc and "disabled" in doc)
check("it still carries the style-suffix caution",
      "never agreed to it" in doc)

print("\n=== the decoration system is described accurately ===")
from avgui.sounds import EVENTS
from avgui.themes import OPTIONS, PAINTERS, SHEETS, theme_names

named = {k for k, _l, _n in theme_names() if k != "none"}
check("every theme has a painter, options, a sheet and sounds",
      all(k in PAINTERS and k in OPTIONS and k in SHEETS and k in EVENTS
          for k in named), str(sorted(named)))

# The document promises specific behaviour. Each of these is a claim that
# could quietly stop being true.
check("it states that artwork wins",
      "generated artwork always wins" in doc)
check("it states that controls and text win",
      "controls and text always win" in doc)
check("it explains the two regions",
      "patterned" in doc and "placed" in doc)
check("it records the tint-over-artwork bug",
      "banding" in doc)
check("it records the layout-switch stacking bug",
      "setCentralWidget" in doc)
check("it says registries go last",
      "move_registries" in doc)
check("it explains why a conical gradient is used",
      "conical gradient" in doc.lower())
check("it says sounds are opt-in",
      "opt-in" in doc and "silent by default" in doc)
check("it warns about excluding QtMultimedia",
      "QtMultimedia" in doc)
check("it explains why both sets of artwork are kept",
      "legitimate preference" in doc)
check("it records that enhanced visuals are opt-in",
      "decor_enhanced" in doc)
check("it collects the Qt traps that keep recurring",
      "## Qt traps" in doc)
check("including the one that deletes an animation early",
      "DeleteWhenStopped" in doc)
check("it explains why censoring scales down rather than blurs",
      "genuinely discards the detail" in doc)
check("it says the viewer walks the visible list",
      "what is currently visible" in doc)

print("\n  and the tools it points at exist:")
check("tools/move_registries.py is there",
      Path("tools/move_registries.py").exists())
check("the registries really are last in themes.py",
      _registries_last("avgui/themes.py"),
      "definitions above, registries below")

print("\n  every theme named in the document exists:")
for key in named:
    check(f"{key} is documented or at least real", key in PAINTERS)

print("\n=== the version is written down once ===")
# It used to live only in installer.iss, so the running app had no idea
# what it was and the build script had the filename typed out
# separately. Two copies, one of them easy to forget.
from avcore.version import __version__, as_tuple, is_newer

check("the app knows its own version", bool(__version__))
check("it looks like a version",
      all(part.isdigit() for part in __version__.split(".")),
      __version__)

iss = Path("installer.iss").read_text(encoding="utf-8")
check("the installer takes it as a parameter",
      "#ifndef AppVersion" in iss,
      "rather than carrying its own copy")
check("and does not hard-code this one", f'"{__version__}"' not in iss)

build = Path("build.ps1").read_text(encoding="utf-8")
check("the build script reads version.py",
      "version.py" in build and "DAppVersion" in build)
check("and names the installer from it",
      "WispWasp-$appVersion-setup.exe" in build,
      "a typed-out filename went stale every release")

print("\n  comparing versions:")
check("a later build is newer", is_newer("0.2.0", "0.1.1"))
check("a patch is newer", is_newer("0.1.2", "0.1.1"))
check("the same one is not", not is_newer("0.1.1", "0.1.1"))
check("an older one is not", not is_newer("0.1.0", "0.1.1"))
check("a leading v is tolerated", is_newer("v0.2.0", "0.1.1"),
      "release tags are usually written that way")
check("a suffix does not confuse it", is_newer("0.2.0-beta", "0.1.1"))
check("nonsense sorts low rather than raising",
      not is_newer("rubbish", "0.1.1"),
      "a malformed manifest must not stop the app starting")
check("and parses to something", as_tuple("rubbish") == (0,))

print("\n=== every local import resolves ===")
# An import inside a function fails at the moment it runs, and Qt
# swallows an exception raised inside a slot - so a button whose handler
# imports something that is not there does nothing at all, with no
# error anywhere. Exactly that shipped in 0.1.7: the video Install
# button imported two dialogs from the wrong module and looked dead.
import ast as _ast
import re as _re


def _exported(path):
    """Top-level names a module offers, aliases included."""
    names = set()
    for node in _ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, (_ast.ClassDef, _ast.FunctionDef,
                             _ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, _ast.Assign):
            for target in node.targets:
                if isinstance(target, _ast.Name):
                    names.add(target.id)
        elif isinstance(node, (_ast.Import, _ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


_broken = []
for _source in sorted(Path("avgui").glob("*.py")):
    _text = _source.read_text(encoding="utf-8")
    for _match in _re.finditer(r"from \.(\w+) import ([^\n(]+)", _text):
        _module, _names = _match.group(1), _match.group(2)
        _target = Path("avgui") / f"{_module}.py"
        if not _target.exists():
            continue
        _have = _exported(_target)
        _line = _text[:_match.start()].count("\n") + 1
        for _name in (n.strip() for n in _names.split(",")):
            if not _name:
                continue
            # "thing as other" is still an import of "thing".
            _wanted = _name.split(" as ")[0].strip()
            if _wanted and _wanted not in _have:
                _broken.append(
                    f"{_source.name}:{_line} imports {_wanted} "
                    f"from {_module}")

check("nothing imports a name its module does not have",
      not _broken,
      "; ".join(_broken) if _broken else "all of them resolve")

bad = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed")
if bad:
    print("FAILURES:")
    for n in bad:
        print(f"  - {n}")
    raise SystemExit(1)
print("the documentation matches the code")
