"""Background sky for one timeline column, driven by real sunrise/sunset.

The colour is brightest at the top row and falls away toward the bottom, so
the weather bars -- which grow up from the bottom -- always sit against the
darkest part of the panel. The effect reads as sky above a horizon rather
than a wash behind the data.
"""

# Key colours, top-of-panel. Deliberately dim: the background must never
# compete with the weather bars.
NIGHT = (16, 8, 48)
DAWN = (140, 58, 12)
DAY = (26, 64, 96)
DUSK = (148, 48, 14)

TWILIGHT_H = 1.2      # hours of fade either side of sunrise/sunset

# Brightness multiplier per row down the panel. Steep on purpose: it keeps the
# sky in the top four or five rows, leaving the lower two thirds of the panel
# black for the weather bars to stand against.
FALLOFF = 0.52

# The palette is finite, so bound how many distinct colours we can ask for:
# quantise the fade into steps, snap channels to a grid, and drop anything too
# dim to see. Measured worst case with these values is well inside 256 pens --
# see the palette budget test.
PHASE_STEPS = 6
COLOUR_STEP = 8
CUTOFF = 10

# Used when the API gives us no astro data (roughly equinox in Sydney).
DEFAULT_SUNRISE = 6.5
DEFAULT_SUNSET = 17.5

BLACK = (0, 0, 0)


def parse_time(text):
    """'06:55 AM' or '18:04' -> hours as a float. None if unparseable."""
    if not text:
        return None
    try:
        parts = text.strip().split()
        clock = parts[0]
        hh, mm = clock.split(":")[:2]
        hour = int(hh) % 12 if len(parts) > 1 else int(hh)
        if len(parts) > 1 and parts[1].upper().startswith("P"):
            hour += 12
        value = hour + int(mm) / 60.0
        return value if 0.0 <= value < 24.0 else None
    except (ValueError, IndexError):
        return None


def _snap(value):
    """Quantise one channel and drop it entirely if it is too dim to matter."""
    v = int(round(value / COLOUR_STEP)) * COLOUR_STEP
    return 0 if v < CUTOFF else min(255, v)


def _blend(a, b, t):
    t = round(max(0.0, min(1.0, t)) * PHASE_STEPS) / PHASE_STEPS
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def sky_color(hour, sunrise=DEFAULT_SUNRISE, sunset=DEFAULT_SUNSET):
    """Top-row sky colour for a given hour, faded through dawn and dusk."""
    if sunrise is None:
        sunrise = DEFAULT_SUNRISE
    if sunset is None or sunset <= sunrise:
        sunset = max(sunrise + 1.0, DEFAULT_SUNSET)

    tw = TWILIGHT_H
    if hour < sunrise - tw or hour > sunset + tw:
        return NIGHT
    if hour < sunrise:
        return _blend(NIGHT, DAWN, (hour - (sunrise - tw)) / tw)
    if hour < sunrise + tw:
        return _blend(DAWN, DAY, (hour - sunrise) / tw)
    if hour < sunset - tw:
        return DAY
    if hour < sunset:
        return _blend(DAY, DUSK, (hour - (sunset - tw)) / tw)
    return _blend(DUSK, NIGHT, (hour - sunset) / tw)


def background_column(hour, sunrise=DEFAULT_SUNRISE, sunset=DEFAULT_SUNSET,
                      height=11):
    """One column of background pixels, index 0 = top row."""
    base = sky_color(hour, sunrise, sunset)
    column = []
    level = 1.0
    for _ in range(height):
        rgb = (_snap(base[0] * level),
               _snap(base[1] * level),
               _snap(base[2] * level))
        column.append(BLACK if rgb == BLACK else rgb)
        level *= FALLOFF
    return column


def is_daylight(hour, sunrise=DEFAULT_SUNRISE, sunset=DEFAULT_SUNSET):
    """Used to pick panel brightness."""
    if sunrise is None:
        sunrise = DEFAULT_SUNRISE
    if sunset is None:
        sunset = DEFAULT_SUNSET
    return sunrise <= hour <= sunset
