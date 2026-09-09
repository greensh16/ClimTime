"""WeatherAPI.com client: current conditions plus the last N hours of history."""

import gc
import time

import urequests

import sky
from rtc_time import localtime

# Number of past hours the display shows (53-wide panel, newest column = now).
TIMELINE_HOURS = 53

# HTTPS keeps the API key off the wire. TLS costs a few tens of KB of RAM on a
# Pico W; if you start seeing MemoryError on fetch, set this to False.
USE_HTTPS = True

_REQUEST_RETRIES = 2      # extra attempts after the first
_RETRY_DELAY_S = 3


def _free():
    """Free heap in bytes, or None on a host CPython (no gc.mem_free)."""
    try:
        return gc.mem_free()
    except AttributeError:
        return None


def _base():
    return "https://api.weatherapi.com/v1" if USE_HTTPS else "http://api.weatherapi.com/v1"


def _get_json(url, label):
    """GET a URL and return parsed JSON, or None. Always closes the socket.

    `label` is used in log messages so the API key in `url` is never printed.
    """
    for attempt in range(_REQUEST_RETRIES + 1):
        gc.collect()
        r = None
        try:
            r = urequests.get(url)
            if 400 <= r.status_code < 500:
                # A bad key, a bad location or a date outside the plan's
                # history window will fail identically forever, so don't burn
                # startup time (and three sleeps per date) retrying it.
                print("  {} rejected: HTTP {}".format(label, r.status_code))
                return None
            if r.status_code != 200:
                raise OSError("HTTP {}".format(r.status_code))
            return r.json()
        except Exception as e:
            free = _free()
            print("  {} failed (attempt {}/{}): {}{}".format(
                label, attempt + 1, _REQUEST_RETRIES + 1, e,
                "" if free is None else "  [free heap {} B]".format(free)))
        finally:
            # Must run even when .json() raises, or the socket leaks and the
            # device eventually runs out of memory.
            if r is not None:
                try:
                    r.close()
                except Exception:
                    pass
        if attempt < _REQUEST_RETRIES:
            time.sleep(_RETRY_DELAY_S)
    return None


def get_past_hours(hours=TIMELINE_HOURS):
    """(date_str, hour) for each of the last `hours` hours, oldest first.

    Excludes the current hour, which is fetched separately as live conditions.

    Steps backwards in UTC and converts each instant separately, because UTC
    hours are uniform and local ones are not. Walking back through local wall
    clock instead would assume today's UTC offset held for the whole window,
    so on the two DST changeover days a year every column older than the
    transition would be fetched an hour out.
    """
    now = time.time()               # UTC epoch: no DST discontinuity
    stamps = []
    for h in range(hours, 0, -1):
        t = localtime(now - h * 3600)
        stamps.append(("{:04d}-{:02d}-{:02d}".format(t[0], t[1], t[2]), t[3]))
    return stamps


def group_by_date(stamps):
    """Group (date, hour) pairs into {date: [hours]} so we fetch each day once."""
    grouped = {}
    for date_str, hour in stamps:
        grouped.setdefault(date_str, []).append(hour)
    return grouped


def _astro(data):
    """Pull (sunrise, sunset) as float hours out of a forecast/history payload.

    Both endpoints carry an `astro` block, so real sun times cost no extra
    requests. Returns (None, None) if the block is missing or malformed and
    the caller falls back to sky.py's defaults.
    """
    try:
        block = data["forecast"]["forecastday"][0]["astro"]
    except (KeyError, IndexError, TypeError):
        return (None, None)
    return (sky.parse_time(block.get("sunrise")),
            sky.parse_time(block.get("sunset")))


def _reading(src, hour, sunrise=None, sunset=None):
    """Normalise a WeatherAPI current/hourly object into our own dict."""
    return {
        "temp": src.get("temp_c"),
        "cloud": src.get("cloud"),
        "precip": src.get("precip_mm", 0),
        "wind": src.get("wind_kph", 0),
        "is_day": src.get("is_day", 1),
        "hour": hour,
        "sunrise": sunrise,
        "sunset": sunset,
    }


def fetch_weather(api_key, location):
    """Current conditions plus today's sun times, or None on failure.

    Uses forecast.json rather than current.json: it returns the same `current`
    block *and* today's astro data in a single request, so the background can
    track real sunrise/sunset through the year instead of assuming 6am/5pm.

    `hour=0` is a memory optimisation, not a time selector. We read only
    `current` and `astro`, but forecast.json otherwise ships a 24-entry hourly
    array we immediately discard -- on an hourly loop that runs forever, that
    is the payload most likely to eventually meet a fragmented heap. Asking
    for one hour keeps both blocks we actually use.
    """
    url = "{}/forecast.json?key={}&q={}&days=1&hour=0&aqi=no&alerts=no".format(
        _base(), api_key, location)
    data = _get_json(url, "current conditions")
    if not data:
        return None

    current = data.get("current")
    if not isinstance(current, dict):
        print("  unexpected forecast.json response:", data.get("error", data))
        return None

    sunrise, sunset = _astro(data)
    return _reading(current, localtime()[3], sunrise, sunset)


def _readings_for_date(api_key, location, date_str, wanted):
    """Fetch one date and reduce it to just the readings we asked for.

    Deliberately its own function. history.json is the largest thing this
    firmware parses -- 24 hours of ~20 fields each -- and keeping it inside a
    frame that returns guarantees the whole tree is unreachable before the
    next date's request starts allocating. Inlined in a loop, the previous
    date's payload stays referenced while the next one is being built, so peak
    memory holds two of them at once.

    Always returns exactly len(wanted) entries, None for anything missing.
    """
    url = "{}/history.json?key={}&q={}&dt={}".format(
        _base(), api_key, location, date_str)
    data = _get_json(url, "history for " + date_str)
    if not data:
        return [None] * len(wanted)

    try:
        hourly = data["forecast"]["forecastday"][0]["hour"]
    except (KeyError, IndexError, TypeError):
        print("  unexpected history.json response for", date_str)
        return [None] * len(wanted)

    # Sun times for that specific date, so columns from different days get
    # their own dawn and dusk.
    sunrise, sunset = _astro(data)

    return [_reading(hourly[h], h, sunrise, sunset) if h < len(hourly) else None
            for h in wanted]


def fetch_past_hours(api_key, location, hours=TIMELINE_HOURS):
    """The last `hours` readings, oldest first.

    Always returns exactly `hours` entries. Any reading we could not retrieve
    is None rather than missing, so callers can rely on positional alignment
    between list index and time.
    """
    grouped = group_by_date(get_past_hours(hours))

    result = []
    # MicroPython dicts do NOT preserve insertion order, so sort explicitly --
    # otherwise the days come back shuffled and the timeline is scrambled.
    for date_str in sorted(grouped):
        result.extend(_readings_for_date(
            api_key, location, date_str, sorted(grouped[date_str])))
        # Reclaim the payload before the next request allocates its own.
        gc.collect()

    return result
