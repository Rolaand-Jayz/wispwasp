"""
Round three: the waveform idea, made to work.

What was wrong with A: the wings read as a wifi symbol, the head was a
lollipop, and it was assembled from separate floating parts so the
silhouette fell apart at small sizes.

The fix running through all three: one solid enveloping mass, with the
waveform carried as negative space cut out of it. Cut stripes cannot
scatter the way floating bars do - at 16px they close up and leave a
clean shape behind instead of a smudge.
"""

SLATE = "#1A1F26"
PANEL = "#222932"
AMBER = "#F0A32E"
AMBER_DIM = "#A96C14"
PALE = "#FFD98A"

# --- A1: cut stripes ----------------------------------------------------
# Solid tapered abdomen, stripes cut out at varying heights so they read
# as a level meter. Blade wings, angular head, long sting.
CUT = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <g transform="rotate(-14 32 32)">
    <path d="M22 24 L44 8 L52 12 L30 28 Z" fill="{AMBER_DIM}"/>
    <path d="M22 30 L46 22 L50 28 L28 34 Z" fill="{AMBER_DIM}"
          opacity="0.75"/>
    <path d="M4 32 L14 23 L20 27 L20 37 L14 41 Z" fill="{AMBER}"/>
    <path d="M20 21 L26 21 L26 43 L20 43 Z" fill="{AMBER}"/>
    <path d="M26 20 L48 29 L58 32 L48 35 L26 44 Z" fill="{AMBER}"/>
    <g fill="{SLATE}">
      <rect x="29" y="21" width="3" height="22" rx="1.5"/>
      <rect x="35" y="25" width="3" height="15" rx="1.5"/>
      <rect x="41" y="28" width="3" height="9" rx="1.5"/>
    </g>
    <path d="M8 27 L3 21" stroke="{AMBER}" stroke-width="2.4"
          stroke-linecap="round"/>
    <path d="M8 37 L3 43" stroke="{AMBER}" stroke-width="2.4"
          stroke-linecap="round"/>
  </g>
</svg>
"""

# --- A2: the meter leading in -------------------------------------------
# Same solid creature, but free bars step up to it from the left, so the
# mark reads left to right as sound turning into the wasp.
METER = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <g transform="rotate(-14 32 32)">
    <g fill="{AMBER}" opacity="0.55">
      <rect x="2" y="29" width="3.4" height="6" rx="1.7"/>
      <rect x="8" y="25" width="3.4" height="14" rx="1.7"/>
    </g>
    <path d="M14 23 L22 23 L22 41 L14 41 Z" fill="{AMBER}"/>
    <path d="M22 25 L44 12 L50 16 L28 30 Z" fill="{AMBER_DIM}"/>
    <path d="M22 32 L46 26 L48 32 L28 37 Z" fill="{AMBER_DIM}"
          opacity="0.7"/>
    <path d="M22 19 L46 29 L60 32 L46 35 L22 45 Z" fill="{AMBER}"/>
    <g fill="{SLATE}">
      <rect x="26" y="21" width="3.2" height="22" rx="1.6"/>
      <rect x="33" y="24" width="3.2" height="16" rx="1.6"/>
      <rect x="40" y="27" width="3.2" height="10" rx="1.6"/>
    </g>
  </g>
</svg>
"""

# --- A3: the sting, stripped back ---------------------------------------
# The fewest marks that still say wasp: one wedge, three cuts, two blades.
# Built for the small sizes first.
BLADE = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <g transform="rotate(-14 32 32)">
    <path d="M18 26 L40 10 L47 15 L26 30 Z" fill="{AMBER_DIM}"/>
    <path d="M10 32 L20 22 L20 42 Z" fill="{AMBER}"/>
    <path d="M20 18 L50 30 L62 32 L50 34 L20 46 Z" fill="{AMBER}"/>
    <g fill="{SLATE}">
      <rect x="24" y="21" width="3.6" height="22" rx="1.8"/>
      <rect x="31.5" y="24" width="3.6" height="16" rx="1.8"/>
      <rect x="39" y="27" width="3.6" height="10" rx="1.8"/>
    </g>
  </g>
</svg>
"""

CONCEPTS = [("A1  cut stripes", CUT),
            ("A2  meter leading in", METER),
            ("A3  stripped back", BLADE)]
