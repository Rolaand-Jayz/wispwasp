import re

MIN_WORDS = 3
MAX_PROMPT_CHARS = 400
STYLE_SUFFIX = ""
HALLUCINATIONS = {
    "you", "thank you", "thanks for watching", "thank you for watching",
    "bye", "bye bye", "subscribe", "please subscribe", "okay", "so",
    "thanks", "the end", "music", "applause", "outro", "intro",
}

src = open("listener.py").read()
ns = {"re": re, "MIN_WORDS": MIN_WORDS, "MAX_PROMPT_CHARS": MAX_PROMPT_CHARS,
      "STYLE_SUFFIX": STYLE_SUFFIX, "HALLUCINATIONS": HALLUCINATIONS}
for fn in ("looks_repetitive", "build_prompt"):
    s = src.index(f"def {fn}")
    e = src.index("\ndef ", s + 5)
    exec(compile(src[s:e], fn, "exec"), ns)

tests = [
    "We are, we are, we are, we are, we are, we are, we are, we are, we are.",
    "All right, let me show you this guys only if you're okay with seeing a cow die",
    "It's dead. It's dead. The mom is dead?",
    "Thank you.",
    "Bro, this is live? Put up two fingers. No way, it's live!",
    "  ",
]
for t in tests:
    out = ns["build_prompt"](t)
    verdict = "SKIP" if out is None else "PASS"
    print(f"{verdict}  in={t.strip()[:52]!r}")
    if out:
        print(f"      out={out[:52]!r}  verbatim={out == ' '.join(t.split())}")
