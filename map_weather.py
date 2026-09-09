"""Turn a weather reading into one vertical pixel column for the display.

Column layout (bottom-up):
  - bar height  = temperature, scaled to the range visible on the panel
  - bar colour  = temperature (blue -> cyan -> yellow -> red)
  - bar dimming = cloud cover
  - top pixel   = white when it is raining

Temperature drives height because it has the strongest daily cycle of anything
the API gives us, so the panel reads as a wave rather than a flat line. Wind is
still fetched but no longer displayed.
"""

# Display column height (Galactic Unicorn is 53x11). main.py passes the real
# value from graphics.get_bounds(); this is only the fallback.
HEIGHT = 11

# The scale adapts to whatever is on screen, but never compresses below this
# many degrees -- otherwise a still, flat day gets amplified into noise.
MIN_SPAN_C = 8.0
SPAN_PAD_C = 0.5

MIN_BRIGHTNESS = 0.25     # brightness at 100% cloud cover
PRECIP_SPARKLE_MM = 0.5   # mm of rain that lights the top pixel white

# Colour ramp. Deliberately avoids passing through grey: the old blue->yellow
# ramp went through (127,127,127) at its midpoint, which is exactly where mild
# temperatures landed.
RAMP = (
    (0.00, (0, 50, 255)),     # cold, deep blue
    (0.34, (0, 205, 195)),    # cool, cyan
    (0.67, (255, 220, 0)),    # mild, yellow
    (1.00, (255, 30, 0)),     # hot, red
)

# Quantisation caps how many distinct colours we can ask for, keeping main.py's
# pen cache inside the finite PicoGraphics palette.
TEMP_BUCKETS = 14
CLOUD_BUCKETS = 6

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

DEFAULT_SCALE = (2.0, 24.0)


def _clamp(value, low, high):
    return max(low, min(high, value))


def _quantise(value, buckets):
    if buckets < 2:
        return value
    return round(value * (buckets - 1)) / (buckets - 1)


def scale_for(readings, minimum_span=MIN_SPAN_C):
    """Pick (low, high) degrees C covering everything currently on the panel.

    Widens symmetrically to `minimum_span` when the real spread is narrow, so
    the bars mean roughly the same thing from one day to the next.
    """
    temps = [r["temp"] for r in readings
             if r and r.get("temp") is not None]
    if not temps:
        return DEFAULT_SCALE

    low = min(temps) - SPAN_PAD_C
    high = max(temps) + SPAN_PAD_C

    span = high - low
    if span < minimum_span:
        middle = (high + low) / 2.0
        low = middle - minimum_span / 2.0
        high = middle + minimum_span / 2.0

    return (low, high)


def temperature_position(temp_c, scale=DEFAULT_SCALE):
    """Where a temperature sits on the current scale, 0.0 to 1.0."""
    low, high = scale
    if high <= low:
        return 0.5
    return _clamp((temp_c - low) / (high - low), 0.0, 1.0)


def ramp_color(position):
    """Sample the colour ramp at 0.0-1.0. Returns 0-255."""
    p = _quantise(_clamp(position, 0.0, 1.0), TEMP_BUCKETS)
    for i in range(len(RAMP) - 1):
        stop, colour = RAMP[i]
        next_stop, next_colour = RAMP[i + 1]
        if p <= next_stop:
            t = (p - stop) / (next_stop - stop)
            return tuple(int(colour[j] + (next_colour[j] - colour[j]) * t)
                         for j in range(3))
    return RAMP[-1][1]


def blank_column(height=HEIGHT):
    """An all-off column, used for padding and for missing readings."""
    return [BLACK] * height


def map_to_column(weather, scale=DEFAULT_SCALE, height=HEIGHT):
    """Build one column of (r, g, b) tuples, index 0 = top of the display.

    `weather` may be None (a reading we failed to fetch), in which case the
    column is blank and the sky background shows through.
    """
    if not weather:
        return blank_column(height)

    temp = weather.get("temp")
    if temp is None:
        return blank_column(height)

    position = temperature_position(temp, scale)

    r, g, b = ramp_color(position)
    cloud = _clamp(weather.get("cloud") or 0, 0, 100)
    cloud_level = _quantise(cloud / 100.0, CLOUD_BUCKETS)
    brightness = MIN_BRIGHTNESS + (1 - MIN_BRIGHTNESS) * (1 - cloud_level)
    lit = (int(r * brightness), int(g * brightness), int(b * brightness))

    # Always at least one pixel, so a cold hour still reads as present data
    # rather than as a gap in the timeline.
    bar = _clamp(int(round(position * (height - 1))) + 1, 1, height)

    pixels = [BLACK] * height
    for y in range(bar):
        pixels[y] = lit

    if (weather.get("precip") or 0) > PRECIP_SPARKLE_MM:
        pixels[bar - 1] = WHITE

    # Built bottom-up; reverse so index 0 is the top row the display expects.
    return pixels[::-1]
