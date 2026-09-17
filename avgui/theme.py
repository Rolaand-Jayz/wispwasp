"""
Visual tokens and the stylesheet.

The window sits next to OBS in a dark room, so the palette is a slate
instrument panel rather than a document. Red is reserved for the tally
light and nothing else; amber means the GPU is working.
"""

BG = "#1A1F26"
PANEL = "#222932"
PANEL_HI = "#2A323D"
EDGE = "#323B47"
TEXT = "#E4E8EE"
MUTED = "#8A94A3"
# Dimmer than MUTED, and clearly so: a setting that cannot be changed
# should read as switched off at a glance, not merely as secondary text.
DISABLED = "#49525F"
DISABLED_BG = "#1E232B"
TALLY = "#E0392B"
WORKING = "#F0A32E"
OK = "#4FB286"
# Blue, and nothing else in the app uses it - so an outlined thumbnail
# cannot be mistaken for a selection or an error.
FAVOURITE = "#4C9BE8"
DANGER = "#E0564A"
# Text selection. Deliberately not the tally red: selecting a word is not
# an alarm, and using the same colour for both drains the meaning out of
# the one that matters. A muted navy reads as "selected" and competes
# with nothing.
SELECTION = "#35516F"

# --- the adjustable palette -------------------------------------------
# MAIN is the colour of doing something: the primary button, the marker
# beside the active page. ACCENT is the colour of noticing something:
# favourites, selections, the attention flash.
#
# The status colours above are deliberately NOT adjustable. Red meaning
# "live" and amber meaning "working" are the app telling the truth about
# its state, and letting those be repainted would let the interface lie.
DEFAULT_MAIN = "#E0392B"
DEFAULT_ACCENT = "#4C9BE8"

MAIN = DEFAULT_MAIN
ACCENT = DEFAULT_ACCENT


def mix(colour, other, amount):
    """Blend two hex colours. `amount` is how much of `other` to use."""
    a = colour.lstrip("#")
    b = other.lstrip("#")
    out = []
    for i in (0, 2, 4):
        first = int(a[i:i + 2], 16)
        second = int(b[i:i + 2], 16)
        out.append(int(round(first * (1 - amount) + second * amount)))
    return "#{:02X}{:02X}{:02X}".format(*out)


def readable_on(colour):
    """Black or white, whichever can be read on top of `colour`."""
    h = colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#10161C" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#FFFFFF"


UI_FONT = "Segoe UI Variable Text, Segoe UI, sans-serif"
FEED_FONT = "Cascadia Mono, Consolas, monospace"

def build_qss():
    """
    Build the stylesheet from the palette as it stands now.

    A function rather than a constant: the interface colours
    can be changed while the app is running, and an f-string
    evaluated once at import can never reflect that.
    """
    return f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: {UI_FONT};
    font-size: 13px;
}}

/* Labels must not paint their own background, or every label sitting on a
   panel punches a hole of the window colour through it. Id selectors below
   are more specific, so #feed still gets its own fill. */
QLabel {{
    background: transparent;
}}

/* Disabled styling has to be spelled out for every control, because the
   rules above set `color` unconditionally and that overrides Qt's own
   disabled palette - which is why a greyed-out setting still looked
   fully lit. */
QWidget:disabled {{
    color: {DISABLED};
}}
QLabel:disabled {{
    color: {DISABLED};
}}
QLabel#fieldLabel:disabled {{
    color: {DISABLED};
}}

#sidebar {{
    background: {PANEL};
    border-right: 1px solid {EDGE};
}}

#navButton {{
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    padding: 9px 14px;
    text-align: left;
    color: {MUTED};
}}
#navButton:hover {{
    background: {PANEL_HI};
    color: {TEXT};
}}
/* A nav entry that belongs to the one above it: indented, smaller, and
   quieter, so the hierarchy is visible without a tree widget. */
#navSubButton {{
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    color: {MUTED};
    font-size: 12px;
    padding: 7px 14px 7px 30px;
    text-align: left;
}}
#navSubButton:hover {{
    background: {PANEL};
    color: {TEXT};
}}
#navSubButton:checked {{
    background: {PANEL};
    border-left: 2px solid {ACCENT};
    color: {TEXT};
}}

#navButton:checked {{
    background: {PANEL_HI};
    border-left: 2px solid {MAIN};
    color: {TEXT};
    font-weight: 600;
}}

#sectionLabel {{
    color: {MUTED};
    font-size: 11px;
    padding: 14px 14px 4px 14px;
}}

#brandMark {{
    background: transparent;
}}

/* The header of a collapsible section. Reads as a control you can press
   rather than a label, without shouting for attention. */
#collapseHeader {{
    background: transparent;
    border: none;
    color: {MUTED};
    font-size: 12px;
    padding: 4px 2px;
    text-align: left;
}}
#collapseHeader:hover {{
    color: {TEXT};
}}
#collapseHeader:checked {{
    color: {TEXT};
}}

/* A hairline under the logo, so the artwork reads as a header rather than
   as the first nav item. */
#brandRule {{
    background: {EDGE};
    border: none;
    margin: 0 14px;
}}

#statusBar {{
    background: {PANEL};
    border-bottom: 1px solid {EDGE};
}}
#statusText {{
    color: {TEXT};
    font-size: 13px;
}}
#statusDetail {{
    color: {MUTED};
    font-size: 12px;
}}

#preview {{
    background: #121519;
    border: 1px solid {EDGE};
}}
#previewEmpty {{
    color: {MUTED};
    font-size: 13px;
}}

#feed {{
    background: {PANEL};
    border: 1px solid {EDGE};
    border-radius: 3px;
    color: {TEXT};
    font-family: {FEED_FONT};
    font-size: 12px;
    padding: 8px 10px;
}}
#feedMuted {{
    color: {MUTED};
    font-family: {FEED_FONT};
    font-size: 12px;
}}

/* The transcript history. Monospace, because it is a caption feed rather
   than interface text. */
#feedList {{
    background: {PANEL};
    border: 1px solid {EDGE};
    border-radius: 3px;
    color: {TEXT};
    font-family: {FEED_FONT};
    font-size: 12px;
    outline: none;
}}
#feedList::item {{
    padding: 3px 6px;
    border: none;
}}
#feedList::item:selected {{
    background: {PANEL_HI};
    color: {TEXT};
}}
#feedList::item:hover {{
    background: {PANEL_HI};
}}

#promptStrip {{
    background: {PANEL};
    border-top: 1px solid {EDGE};
}}

QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {BG};
    border: 1px solid {EDGE};
    border-radius: 3px;
    padding: 7px 9px;
    color: {TEXT};
    selection-background-color: {SELECTION};
    selection-color: {TEXT};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {MUTED};
}}

QPushButton {{
    background: {PANEL_HI};
    border: 1px solid {EDGE};
    border-radius: 3px;
    padding: 7px 14px;
    color: {TEXT};
}}
QPushButton:hover {{ background: #333D4A; }}
QPushButton:pressed {{ background: {PANEL}; }}
QPushButton:disabled {{ color: #5A6472; background: {PANEL}; }}

#primaryButton {{
    background: {MAIN};
    border: 1px solid {MAIN};
    color: {readable_on(MAIN)};
    color: #FFF;
    font-weight: 600;
}}
#primaryButton:hover {{ background: {mix(MAIN, "#FFFFFF", 0.12)}; }}
#primaryButton:disabled {{
    background: {PANEL};
    border: 1px solid {EDGE};
    color: #5A6472;
}}

QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {BG};
    border: 1px solid {EDGE};
    border-radius: 3px;
    padding: 6px 8px;
    color: {TEXT};
}}

/* A disabled field recedes: dimmer text, a flatter background and a
   softer border, so the whole row reads as inactive rather than just
   being unresponsive when clicked. */
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {{
    color: {DISABLED};
    background: {DISABLED_BG};
    border: 1px solid #2A313A;
}}
QSpinBox::up-button:disabled, QSpinBox::down-button:disabled,
QDoubleSpinBox::up-button:disabled, QDoubleSpinBox::down-button:disabled {{
    background: {DISABLED_BG};
    border-left: 1px solid #2A313A;
}}
QComboBox::drop-down:disabled {{
    background: {DISABLED_BG};
}}
QCheckBox:disabled {{
    color: {DISABLED};
}}
QCheckBox::indicator:disabled {{
    border: 1px solid #2A313A;
    background: {DISABLED_BG};
}}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {PANEL};
    border: 1px solid {EDGE};
    selection-background-color: {PANEL_HI};
    color: {TEXT};
}}

QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {PANEL_HI};
    border: none;
    border-left: 1px solid {EDGE};
    width: 15px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background: #3A4552;
}}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {EDGE};
    border-radius: 3px;
    background: {BG};
}}
QCheckBox::indicator:checked {{
    background: {OK};
    border: 1px solid {OK};
}}

/* Radio buttons had no rules at all, and with a stylesheet this size
   the platform default stops being drawn - the selected option lost its
   mark entirely and showed as bare text. Same shape as the checkboxes,
   round instead of square. */
QRadioButton {{ spacing: 8px; }}
QRadioButton::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {EDGE};
    border-radius: 8px;
    background: {BG};
}}
QRadioButton::indicator:hover {{
    border: 1px solid {MUTED};
}}
QRadioButton::indicator:checked {{
    background: {OK};
    border: 1px solid {OK};
}}
QRadioButton:disabled {{
    color: {DISABLED};
}}
QRadioButton::indicator:disabled {{
    border: 1px solid {DISABLED_BG};
    background: {DISABLED_BG};
}}

QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {EDGE}; border-radius: 5px; min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: #47525F; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{
    background: {EDGE}; border-radius: 5px; min-width: 28px;
}}

QLabel#fieldLabel {{ color: {MUTED}; font-size: 12px; }}
QLabel#errorText {{ color: {TALLY}; font-size: 12px; }}

QSplitter::handle:horizontal {{
    background: {EDGE};
    width: 1px;
}}
QSplitter::handle:horizontal:hover {{
    background: {MUTED};
}}

/* The divider between the image and the history. Given a few pixels of
   height so it can actually be grabbed - a one pixel line is a line, not
   a handle. */
QSplitter::handle:vertical {{
    background: {EDGE};
    height: 1px;
    margin: 3px 0;
}}
QSplitter::handle:vertical:hover {{
    background: {MUTED};
}}

/* The filter row above the gallery grid. Recessed slightly, so it reads
   as a control strip rather than as content. */
#filterBar {{
    background: {BG};
    border-bottom: 1px solid {EDGE};
}}

/* The three-state filter toggle. Green includes, red excludes, and the
   neutral state looks like any other unchecked box so it does not seem
   to be doing something when it is not. */
QCheckBox[filterState="include"] {{
    color: {OK};
}}
QCheckBox[filterState="include"]::indicator {{
    background: {OK};
    border: 1px solid {OK};
}}
QCheckBox[filterState="exclude"] {{
    color: {DANGER};
}}
QCheckBox[filterState="exclude"]::indicator {{
    background: {DANGER};
    border: 1px solid {DANGER};
}}

/* The expanded image viewer. Dimmed backdrop so the picture is the only
   lit thing, and controls that sit on the image without fighting it. */
#viewer {{
    background: rgba(8, 10, 14, 232);
}}
#viewerImage {{
    background: transparent;
}}
#viewerHint {{
    color: {TEXT};
    font-size: 15px;
    font-weight: 600;
    background: rgba(10, 12, 18, 120);
}}
#viewerCaption {{
    color: {MUTED};
    font-size: 12px;
}}
#viewerNav, #viewerClose {{
    background: rgba(18, 22, 30, 210);
    border: 1px solid {EDGE};
    border-radius: 6px;
    color: {TEXT};
    font-size: 20px;
}}
#viewerNav:hover, #viewerClose:hover {{
    background: {PANEL_HI};
    border: 1px solid {MUTED};
}}
#viewerNav:disabled {{
    color: {DISABLED};
    border: 1px solid {DISABLED_BG};
}}

/* The quietest thing in the window. It should be findable when
   somebody asks "which build are you on?" and invisible otherwise. */
#versionLabel {{
    color: {DISABLED};
    font-size: 11px;
    padding: 2px 0 2px 2px;
}}

QToolTip {{
    background: {PANEL};
    color: {TEXT};
    border: 1px solid {EDGE};
    padding: 5px;
}}

/* The cog on a hovered thumbnail. Sits over artwork of any colour, so it
   carries its own dark backing rather than relying on the tint. */
#cogButton {{
    background: rgba(20, 24, 30, 210);
    border: 1px solid {EDGE};
    border-radius: 12px;
    color: {TEXT};
    font-size: 14px;
    padding: 0;
}}
#cogButton:hover {{
    background: {PANEL_HI};
    border: 1px solid {MUTED};
}}

/* Favourite outlines and the attention flash follow the accent colour;
   both are drawn in code rather than styled here, and read theme.ACCENT
   when they paint. */

QMenu {{
    background: {PANEL};
    border: 1px solid {EDGE};
    padding: 4px;
}}
QMenu::item {{
    padding: 7px 18px 7px 14px;
    border-radius: 3px;
    color: {TEXT};
}}
QMenu::item:selected {{
    background: {PANEL_HI};
}}
QMenu::separator {{
    height: 1px;
    background: {EDGE};
    margin: 4px 6px;
}}
/* Destructive actions are red wherever they appear, so the colour means
   one thing throughout. */
QMenu::item[danger="true"] {{
    color: {DANGER};
}}

#confirmButton {{
    background: {OK};
    border: 1px solid {OK};
    color: #10231B;
    font-weight: 600;
    padding: 8px 20px;
}}
#confirmButton:hover {{ background: #5CC496; }}
#denyButton {{
    background: {DANGER};
    border: 1px solid {DANGER};
    color: #FFFFFF;
    font-weight: 600;
    padding: 8px 20px;
}}
#denyButton:hover {{ background: #EA6A5E; }}
#dialogTitle {{
    font-size: 15px;
    font-weight: 600;
}}

/* The unapplied-changes bar. Lighter than the panels behind it and
   outlined, so it reads as something sitting on top of the window rather
   than part of whatever page is showing. */
#changeBar {{
    background: {PANEL_HI};
    border: 1px solid {MUTED};
    border-radius: 6px;
}}
#changeBarText {{
    color: {TEXT};
    font-size: 13px;
    font-weight: 600;
}}
"""


# Derived from the palette, so they move with it.
FAVOURITE = ACCENT
SELECTION = mix(BG, ACCENT, 0.45)
QSS = build_qss()


def set_palette(main=None, accent=None):
    """
    Change the interface colours and return the new stylesheet.

    Only the two adjustable colours move; everything derived from them is
    recomputed here so no caller has to know what depends on what.
    """
    global MAIN, ACCENT, FAVOURITE, SELECTION, QSS
    if main:
        MAIN = main
    if accent:
        ACCENT = accent
    FAVOURITE = ACCENT
    SELECTION = mix(BG, ACCENT, 0.45)
    QSS = build_qss()
    return QSS


def apply_to(app, settings=None):
    """
    Push the current palette onto a running application.

    A decorative theme may append its own rules - button shapes and the
    like. Decoration is not allowed to paint over controls, so reshaping
    them through the stylesheet is the only way a theme can reach them.
    """
    main = accent = decor = None
    if settings is not None:
        main = settings.get("ui.theme_main") or None
        accent = settings.get("ui.theme_accent") or None
        decor = settings.get("ui.decor_theme") or None
    sheet = set_palette(main, accent)
    if decor:
        # Imported here rather than at module load: themes reads colours
        # from this module, and importing it at the top would loop.
        from .themes import style_sheet
        sheet = sheet + "\n" + style_sheet(decor)
    app.setStyleSheet(sheet)
    return sheet


def kind_colour(kind):
    """
    Colour for a history entry, looked up when it is drawn.

    A module-level dict would capture the palette at import and keep
    showing the old colours after a change.
    """
    return {"skipped": TALLY, "heard": OK, "typed": ACCENT}.get(kind)
