"""
Round two. Brief: sharp, a bit menacing.

Three directions, all on the app's amber-on-slate palette:
  A  the stripes double as a waveform - the app's own idea as a shape
  B  the lantern from round one, faceted and given an edge
  C  a new direction: the wasp head on, as a mask
"""

SLATE = "#1A1F26"
PANEL = "#222932"
AMBER = "#F0A32E"
AMBER_DIM = "#A96C14"
PALE = "#FFD98A"

# --- A: waveform abdomen -----------------------------------------------
# The vertical bars read as an audio level meter on the left and as wasp
# stripes on the right; the same marks do both jobs. Bar heights vary the
# way real audio does, inside an envelope that tapers to the sting. Tilted
# so it has some motion and cannot be mistaken for a play button.
WAVEFORM_ABDOMEN = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <g transform="rotate(-18 32 32)">
    <g stroke="{AMBER_DIM}" stroke-linecap="round" fill="none"
       opacity="0.85">
      <path d="M20 25 C 24 12, 38 8, 48 12" stroke-width="3"/>
      <path d="M20 29 C 26 20, 38 17, 46 19" stroke-width="2.4"
            opacity="0.7"/>
    </g>
    <circle cx="12" cy="32" r="6.4" fill="{AMBER}"/>
    <path d="M7 28 L2 23" stroke="{AMBER}" stroke-width="2.2"
          stroke-linecap="round"/>
    <path d="M7 36 L2 41" stroke="{AMBER}" stroke-width="2.2"
          stroke-linecap="round"/>
    <g fill="{AMBER}">
      <rect x="20" y="21" width="4.4" height="22" rx="2.2"/>
      <rect x="26" y="17" width="4.4" height="30" rx="2.2"/>
      <rect x="32" y="23" width="4.4" height="18" rx="2.2"/>
      <rect x="38" y="26" width="4.4" height="12" rx="2.2"/>
      <rect x="44" y="29" width="4.4" height="6" rx="2.2"/>
    </g>
    <path d="M50 32 L60 32" stroke="{PALE}" stroke-width="2.6"
          stroke-linecap="round"/>
  </g>
</svg>
"""

# --- B: the faceted lantern --------------------------------------------
# Keeps round one's legibility - one big mass, few marks - but the circle
# becomes a hexagon, the wings become swept blades, and the bottom comes
# to a point instead of rounding off.
FACETED = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <path d="M30 14 L10 20 L8 30 L26 33 Z" fill="{AMBER_DIM}"/>
  <path d="M34 14 L54 20 L56 30 L38 33 Z" fill="{AMBER_DIM}"/>
  <path d="M32 17 L47 26 L44 44 L32 56 L20 44 L17 26 Z" fill="{AMBER}"/>
  <g fill="{SLATE}">
    <path d="M19 31 L45 31 L44.4 35 L19.6 35 Z"/>
    <path d="M21 40 L43 40 L42 44 L22 44 Z"/>
  </g>
  <path d="M32 56 L32 62" stroke="{PALE}" stroke-width="2.6"
        stroke-linecap="round"/>
</svg>
"""

# --- C: head on --------------------------------------------------------
# A mask rather than a whole insect: two hard diagonals, two eyes, a point
# below. Reads as a face, which is what makes it feel like it is looking
# back at you.
HEAD_ON = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <path d="M6 14 L26 24 L22 30 Z" fill="{AMBER_DIM}"/>
  <path d="M58 14 L38 24 L42 30 Z" fill="{AMBER_DIM}"/>
  <path d="M32 10 L50 22 L46 40 L32 54 L18 40 L14 22 Z" fill="{AMBER}"/>
  <g fill="{SLATE}">
    <path d="M20 25 L29 29 L26 35 L18 31 Z"/>
    <path d="M44 25 L35 29 L38 35 L46 31 Z"/>
    <path d="M28 42 L36 42 L34 47 L30 47 Z"/>
  </g>
  <path d="M32 54 L32 61" stroke="{PALE}" stroke-width="2.8"
        stroke-linecap="round"/>
</svg>
"""

CONCEPTS = [("A  waveform abdomen", WAVEFORM_ABDOMEN),
            ("B  faceted lantern", FACETED),
            ("C  head on", HEAD_ON)]
