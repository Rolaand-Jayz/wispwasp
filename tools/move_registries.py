"""
Moves the registry section of avgui/themes.py to the very end.

Registries name every painter and stylesheet, so they must come after
all of them. Appending a theme puts new code below whatever was last in
the file, which repeatedly left the registries stranded above the thing
they refer to. Run this after adding a theme.
"""
from pathlib import Path

p = Path("avgui/themes.py")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)

start = next((i for i, line in enumerate(lines)
              if line.startswith("# ---- registries")), None)
if start is None:
    print("no registry section found")
    raise SystemExit(1)

# The section runs from the marker to the end of the last registry
# helper, whatever happens to be inside it.
end = next((i for i in range(start, len(lines))
            if lines[i].startswith("    return SHEETS.get(")), None)
if end is None:
    print("could not find the end of the registry section")
    raise SystemExit(1)
end += 1

block = "".join(lines[start:end]).rstrip()
del lines[start:end]
body = "".join(lines).rstrip()

p.write_text(f"{body}\n\n\n{block}\n", encoding="utf-8")
print("registries moved to the end")
