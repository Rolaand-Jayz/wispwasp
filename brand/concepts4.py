"""
Round four: A3 given a head, against the hornet for comparison.

A3 had the right energy but no insect in it - no head, one fin-like blade,
so it read as a dart. Two fixes here, plus B carried forward sharpened so
the choice is a fair one.
"""

SLATE = "#1A1F26"
PANEL = "#222932"
AMBER = "#F0A32E"
AMBER_DIM = "#A96C14"
PALE = "#FFD98A"

# --- A4: the dart, with a head -----------------------------------------
# A3's silhouette kept intact. Added: a blunt angular head with a cut eye
# at the wide end, and a second blade below so the wings read as a pair
# rather than a fin.
DART_HEAD = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <g transform="rotate(-14 32 32)">
    <path d="M20 25 L41 9 L48 14 L28 29 Z" fill="{AMBER_DIM}"/>
    <path d="M20 36 L38 44 L36 50 L22 42 Z" fill="{AMBER_DIM}"
          opacity="0.7"/>
    <path d="M6 26 L20 20 L20 44 L6 38 Z" fill="{AMBER}"/>
    <path d="M20 19 L50 30 L62 32 L50 34 L20 45 Z" fill="{AMBER}"/>
    <g fill="{SLATE}">
      <path d="M9 29 L16 26 L16 32 L9 34 Z"/>
      <rect x="25" y="22" width="3.6" height="20" rx="1.8"/>
      <rect x="32.5" y="25" width="3.6" height="14" rx="1.8"/>
      <rect x="40" y="28" width="3.6" height="8" rx="1.8"/>
    </g>
  </g>
</svg>
"""

# --- A5: the same, with the head separated -----------------------------
# A notch between head and body gives a neck, which is what makes an
# insect read as segmented rather than as one solid wedge.
DART_NECK = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <g transform="rotate(-14 32 32)">
    <path d="M22 24 L42 9 L49 14 L30 28 Z" fill="{AMBER_DIM}"/>
    <path d="M22 37 L39 45 L37 51 L24 43 Z" fill="{AMBER_DIM}"
          opacity="0.7"/>
    <path d="M4 32 L13 23 L19 26 L19 38 L13 41 Z" fill="{AMBER}"/>
    <path d="M22 20 L50 30 L62 32 L50 34 L22 44 Z" fill="{AMBER}"/>
    <g fill="{SLATE}">
      <path d="M7 30 L13 27 L13 33 L7 35 Z"/>
      <rect x="27" y="23" width="3.6" height="18" rx="1.8"/>
      <rect x="34" y="26" width="3.6" height="12" rx="1.8"/>
      <rect x="41" y="28.5" width="3.6" height="7" rx="1.8"/>
    </g>
  </g>
</svg>
"""

# --- B2: the hornet, sharpened -----------------------------------------
# Round two's most legible mark, with the epaulette wings swept back into
# blades and the eye notches from the mask carried onto the thorax.
HORNET = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <path d="M29 15 L6 13 L9 24 L27 28 Z" fill="{AMBER_DIM}"/>
  <path d="M35 15 L58 13 L55 24 L37 28 Z" fill="{AMBER_DIM}"/>
  <path d="M32 8 L42 14 L40 24 L24 24 L22 14 Z" fill="{AMBER}"/>
  <path d="M32 26 L46 30 L43 45 L32 58 L21 45 L18 30 Z" fill="{AMBER}"/>
  <g fill="{SLATE}">
    <path d="M25 14 L30 17 L28 21 L24 19 Z"/>
    <path d="M39 14 L34 17 L36 21 L40 19 Z"/>
    <path d="M20 33 L44 33 L43.4 37 L20.6 37 Z"/>
    <path d="M22 42 L42 42 L41 46 L23 46 Z"/>
  </g>
</svg>
"""

CONCEPTS = [("A4  dart with head", DART_HEAD),
            ("A5  dart with neck", DART_NECK),
            ("B2  hornet, sharpened", HORNET)]
