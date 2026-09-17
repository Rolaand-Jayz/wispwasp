# Retired

These are the scripts WispWasp grew out of, kept for reference rather than
use. Everything here has been replaced by the desktop app.

| Retired | What replaced it |
|---|---|
| `listener.py` | `avcore/engine.py` plus `avcore/server.py` |
| `prompt_tool.py` | the Prompt panel in the app |
| `START.bat`, `run.bat`, `start-all.ps1` | `WISPWASP.bat`, or the installed app |
| `STOP.bat` | closing the window |
| `PROMPT.bat`, `start-prompt.ps1` | the Prompt panel |
| `test_comfy.py`, `test_filter.py`, `test_core.py` | `test_server.py`, `test_wav.py`, `test_engine.py` |
| `bench_sizes.py` | the benchmark numbers it produced are in `SETUP.md` |

They are unlikely to still run. `listener.py` and `prompt_tool.py` expect a
`settings.json` next to them and write to `output/`, which the app no
longer uses in the same way, and they will fight the app over port 8420 if
both are started at once.

Nothing here is imported by the app, so this folder can be deleted
whenever you are confident you will not want to look back at it.
