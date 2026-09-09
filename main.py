"""ClimTime - a rolling 53-hour weather timeline on a Galactic Unicorn.

Each column is one hour: newest on the right, oldest on the left. Bar height
and colour are both temperature, dimness is cloud, a white cap means rain.
Behind the bars, a sky gradient tracks real sunrise and sunset for that day:
brightest at the top row, fading to black at the horizon so the data stays
legible.

The temperature scale adapts to whatever is on the panel, so the bars use the
full height in any season. When the scale moves, every column is rebuilt --
otherwise older columns would be drawn against a scale that no longer applies.
"""

import gc
import time

from galactic import GalacticUnicorn
from picographics import PicoGraphics, DISPLAY_GALACTIC_UNICORN as DISPLAY

import map_weather
import rtc_time
import sky
import weather
import wifi

# === Display ===
gu = GalacticUnicorn()
graphics = PicoGraphics(DISPLAY)
WIDTH, HEIGHT = graphics.get_bounds()

DAY_BRIGHTNESS = 0.6
NIGHT_BRIGHTNESS = 0.25
RETRY_DELAY_S = 600       # after a failed fetch
MIN_SLEEP_S = 30

# Only rebuild the panel when the temperature scale has really moved. Without
# this the whole timeline would be recomputed every hour for a 0.1 degree
# wobble, churning the pen cache for no visible gain.
RESCALE_THRESHOLD_C = 0.5

# Slot layout. Each column keeps its own reading so it can be redrawn on a new
# scale without refetching.
COLUMN, BACKGROUND, HOUR, SUNRISE, SUNSET, READING = range(6)

BLACK = (0, 0, 0)

PENS = {}


def _pen(rgb):
    """Create pens once and reuse them.

    PicoGraphics uses a palette-backed pen mode here, and the palette has a
    finite number of slots -- calling create_pen per pixel per frame will
    eventually exhaust it. map_weather and sky both quantise their output so
    this cache stays bounded well inside the palette.
    """
    p = PENS.get(rgb)
    if p is None:
        p = graphics.create_pen(rgb[0], rgb[1], rgb[2])
        PENS[rgb] = p
    return p


def fatal(message):
    """Show a message on the panel and stop, rather than dying silently."""
    print("FATAL:", message)
    try:
        graphics.set_pen(_pen(BLACK))
        graphics.clear()
        graphics.set_pen(_pen((140, 0, 0)))
        graphics.text(message, 0, 2, WIDTH, 1)
        gu.update(graphics)
    except Exception:
        pass
    raise SystemExit(message)


# === Credentials ===
try:
    from secrets import WIFI_SSID, WIFI_PASSWORD, API_KEY, LOCATION
except ImportError:
    fatal("NO SECRETS.PY")

# === Network and clock ===
if not wifi.connect_wifi(WIFI_SSID, WIFI_PASSWORD):
    fatal("NO WIFI")

if not rtc_time.sync_time():
    # Without a valid clock every history date would be wrong.
    fatal("NO NTP")


def make_slot(wx, hour, sunrise, sunset, scale):
    """One timeline column: the weather bar, its backdrop, and its metadata.

    The background is baked in when the column is created, so a column always
    shows the sky for the hour it actually represents and draw() stays cheap.
    """
    return [
        map_weather.map_to_column(wx, scale, HEIGHT),
        sky.background_column(hour, sunrise, sunset, HEIGHT),
        hour,
        sunrise,
        sunset,
        wx,
    ]


def current_scale(timeline):
    return map_weather.scale_for([slot[READING] for slot in timeline])


def rescale(timeline, scale):
    """Redraw every bar against a new temperature scale."""
    for slot in timeline:
        slot[COLUMN] = map_weather.map_to_column(slot[READING], scale, HEIGHT)


def scale_moved(old, new):
    return (abs(new[0] - old[0]) > RESCALE_THRESHOLD_C or
            abs(new[1] - old[1]) > RESCALE_THRESHOLD_C)


def draw(timeline):
    """Blit the background column, then overlay any lit weather pixels.

    Clearing first is load-bearing. Lit bar pixels are never black (see
    MIN_BRIGHTNESS) and the sky gradient fades to black by row 4, so the lower
    rows are only written when a bar reaches them. Compositing onto the
    previous frame would turn those rows into a high-water mark of the hottest
    hour ever displayed -- bars could grow but never shrink.
    """
    graphics.set_pen(_pen(BLACK))
    graphics.clear()

    for x in range(WIDTH):
        column, background = timeline[x][COLUMN], timeline[x][BACKGROUND]
        for y in range(HEIGHT):
            rgb = column[y]
            if rgb == BLACK:
                rgb = background[y]
                if rgb == BLACK:
                    continue
            graphics.set_pen(_pen(rgb))
            graphics.pixel(x, y)

    gu.update(graphics)


def build_timeline():
    """Seed the display with the last WIDTH hours, newest last."""
    print("Fetching historical weather...")
    readings = weather.fetch_past_hours(API_KEY, LOCATION, WIDTH - 1)
    readings.append(weather.fetch_weather(API_KEY, LOCATION))

    now_hour = rtc_time.localtime()[3]
    count = len(readings)
    scale = map_weather.scale_for(readings)

    # Best sun times we have seen so far, used for columns whose own fetch
    # failed. Prefer today's, so scan backwards from the newest reading.
    sunrise = sunset = None
    for wx in reversed(readings):
        if wx and wx.get("sunrise"):
            sunrise, sunset = wx["sunrise"], wx["sunset"]
            break

    timeline = []
    for i, wx in enumerate(readings):
        hour = wx["hour"] if wx else (now_hour - (count - 1 - i)) % 24
        rise = (wx.get("sunrise") if wx else None) or sunrise
        set_ = (wx.get("sunset") if wx else None) or sunset
        timeline.append(make_slot(wx, hour, rise, set_, scale))

    # Pad on the left if history came back short -- otherwise draw() would
    # index past the end of the list.
    while len(timeline) < WIDTH:
        hour = (timeline[0][HOUR] - 1) % 24 if timeline else now_hour
        timeline.insert(0, make_slot(None, hour, sunrise, sunset, scale))

    return timeline[-WIDTH:], scale


def hour_index():
    """Absolute hour bucket, so a long outage cannot wrap and look like none.

    Derived from UTC rather than local time: the bucket boundary still lines up
    with the local hour (the offset is a whole number of hours) but a DST
    change cannot fabricate or swallow an hour.
    """
    return int(time.time() // 3600)


def seconds_to_next_hour():
    now = rtc_time.localtime()
    return max(MIN_SLEEP_S, 3600 - (now[4] * 60 + now[5]))


# === Startup ===
timeline, scale = build_timeline()
last_index = hour_index()
last_sun = (timeline[-1][SUNRISE], timeline[-1][SUNSET])
gu.set_brightness(DAY_BRIGHTNESS if sky.is_daylight(timeline[-1][HOUR], *last_sun)
                  else NIGHT_BRIGHTNESS)
draw(timeline)
print("Temperature scale: {:.1f} to {:.1f} C".format(*scale))
print("Pens in cache after first draw:", len(PENS))

# === Main loop ===
while True:
    gc.collect()

    if not wifi.ensure_connected(WIFI_SSID, WIFI_PASSWORD):
        print("Still offline. Retrying in 60s...")
        time.sleep(60)
        continue

    rtc_time.maybe_resync()

    wx = weather.fetch_weather(API_KEY, LOCATION)
    if not wx:
        print("Failed to fetch weather. Retrying in 10 minutes...")
        time.sleep(RETRY_DELAY_S)
        continue

    hour = rtc_time.localtime()[3]
    sunrise = wx.get("sunrise") or last_sun[0]
    sunset = wx.get("sunset") or last_sun[1]
    last_sun = (sunrise, sunset)
    slot = make_slot(wx, hour, sunrise, sunset, scale)

    # Shift one column per hour that actually passed. RETRY_DELAY_S is ten
    # minutes, so a failing API can hold us here for hours; shifting only once
    # on recovery would hide the gap and silently mislabel every column to the
    # left. Clamped to WIDTH -- a longer outage just blanks the whole panel.
    index = hour_index()
    gap = min(max(index - last_index, 0), WIDTH)

    if gap == 0:
        # Same hour as the last column (e.g. we are recovering from a failed
        # fetch): refresh in place instead of shifting, so one column always
        # means one hour.
        timeline[-1] = slot
    else:
        for i in range(gap - 1):
            missed = (hour - (gap - 1 - i)) % 24
            timeline.pop(0)
            timeline.append(make_slot(None, missed, sunrise, sunset, scale))
        timeline.pop(0)
        timeline.append(slot)

    last_index = index

    # An hour dropping off the left, or a new extreme arriving on the right,
    # can move the scale. Redraw everything so the panel stays on one scale.
    fresh = current_scale(timeline)
    if scale_moved(scale, fresh):
        print("Temperature scale: {:.1f} to {:.1f} C".format(*fresh))
        scale = fresh
        rescale(timeline, scale)

    gu.set_brightness(DAY_BRIGHTNESS if sky.is_daylight(hour, sunrise, sunset)
                      else NIGHT_BRIGHTNESS)
    draw(timeline)
    print("Updated display with:", wx)

    sleep_s = seconds_to_next_hour()
    print("Sleeping for {} seconds...".format(sleep_s))
    time.sleep(sleep_s)
