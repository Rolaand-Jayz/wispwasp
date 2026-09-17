"""
Icon concepts for WispWasp.

Rendered with Qt rather than an image library, since PySide6 is already
here. Each concept is drawn large and at 16px on the same sheet, because
16px is where an icon lives or dies and it is easy to design something
that only works big.
"""

SLATE = "#1A1F26"
PANEL = "#222932"
AMBER = "#F0A32E"
AMBER_DIM = "#B9791F"
PALE = "#FFD98A"

# --- concept 1: the wasp dissolving upward into a wisp ------------------
# The body reads as an insect; the tail breaks into drifting motes, so the
# silhouette still resolves once the motes vanish at small sizes.
WISP_TRAIL = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <path d="M32 47 C 24 41, 24 31, 32 25 C 40 31, 40 41, 32 47 Z"
        fill="{AMBER}"/>
  <g fill="none" stroke="{AMBER}" stroke-linecap="round">
    <path d="M32 25 C 30 19, 30 14, 32 9" stroke-width="3.2"/>
    <path d="M21 30 C 14 26, 12 19, 16 15" stroke-width="2.6"
          opacity="0.75"/>
    <path d="M43 30 C 50 26, 52 19, 48 15" stroke-width="2.6"
          opacity="0.75"/>
  </g>
  <g fill="{SLATE}">
    <rect x="25" y="31" width="14" height="2.6" rx="1.3"/>
    <rect x="26" y="37" width="12" height="2.6" rx="1.3"/>
  </g>
  <g fill="{PALE}">
    <circle cx="32" cy="6" r="2.6"/>
    <circle cx="26" cy="11" r="1.5" opacity="0.7"/>
    <circle cx="38" cy="12" r="1.2" opacity="0.55"/>
  </g>
</svg>
"""

# --- concept 2: a waveform that sharpens into a stinger -----------------
# The app in one mark: sound going in, something pointed coming out.
WAVE_STING = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <g stroke="{AMBER}" stroke-linecap="round" fill="none" opacity="0.9">
    <path d="M7 27 L7 37" stroke-width="4"/>
    <path d="M15 21 L15 43" stroke-width="4"/>
    <path d="M23 15 L23 49" stroke-width="4"/>
  </g>
  <path d="M31 16 C 44 20, 51 26, 55 32 C 51 38, 44 44, 31 48 Z"
        fill="{AMBER}"/>
  <g fill="{SLATE}">
    <rect x="35" y="22" width="3.4" height="20" rx="1.7"/>
    <rect x="42" y="25" width="3.4" height="14" rx="1.7"/>
  </g>
  <path d="M55 32 L61 32" stroke="{PALE}" stroke-width="3"
        stroke-linecap="round"/>
</svg>
"""

# --- concept 3: the lantern, a glowing body with blade wings ------------
# The most legible option: one round mass and two hard diagonals.
LANTERN = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <path d="M31 13 C 16 17, 10 25, 12 31 C 14 36, 22 37, 29 34"
        fill="{AMBER_DIM}"/>
  <path d="M33 13 C 48 17, 54 25, 52 31 C 50 36, 42 37, 35 34"
        fill="{AMBER_DIM}"/>
  <circle cx="32" cy="38" r="16" fill="{AMBER}"/>
  <g fill="{SLATE}">
    <rect x="18" y="33" width="28" height="3.4" rx="1.7"/>
    <rect x="20" y="41" width="24" height="3.4" rx="1.7"/>
    <rect x="25" y="49" width="14" height="3.4" rx="1.7"/>
  </g>
</svg>
"""

CONCEPTS = [("wisp_trail", WISP_TRAIL), ("wave_sting", WAVE_STING),
            ("lantern", LANTERN)]
