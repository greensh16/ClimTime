"""NTP sync plus a DST-aware local time for New South Wales, Australia.

The RTC itself always holds UTC. localtime() applies the correct offset for
the date, so the clock does not sit an hour out for half the year.
"""

import time

import ntptime

STD_OFFSET = 10 * 3600    # AEST, UTC+10
DST_OFFSET = 11 * 3600    # AEDT, UTC+11
OBSERVE_DST = True        # set False for QLD/WA/NT, which do not use DST

RESYNC_INTERVAL_S = 24 * 3600
_SYNC_RETRIES = 3

_last_sync = 0            # epoch seconds of the last successful NTP sync


def _weekday(y, m, d):
    """Sakamoto's algorithm. 0 = Sunday. Avoids mktime portability quirks."""
    t = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    if m < 3:
        y -= 1
    return (y + y // 4 - y // 100 + y // 400 + t[m - 1] + d) % 7


def _first_sunday(y, m):
    return 1 + ((7 - _weekday(y, m, 1)) % 7)


def _is_dst(t):
    """Is AEDT in effect? `t` is a time tuple already expressed in AEST.

    NSW: starts 02:00 AEST on the first Sunday in October,
         ends   02:00 AEST on the first Sunday in April.
    """
    y, m, d, hour = t[0], t[1], t[2], t[3]

    if m > 10 or m < 4:
        return True
    if 4 < m < 10:
        return False

    boundary = _first_sunday(y, m)
    if m == 10:
        if d > boundary:
            return True
        return d == boundary and hour >= 2
    # April: DST ends on the boundary day at 02:00
    if d < boundary:
        return True
    return d == boundary and hour < 2


def utc_offset(t=None):
    """Seconds to add to UTC for local wall-clock time at UTC instant `t`.

    Takes an instant rather than always answering for "now" so that callers
    walking backwards through history (see weather.get_past_hours) get the
    offset that was actually in force then, not today's.
    """
    if not OBSERVE_DST:
        return STD_OFFSET
    if t is None:
        t = time.time()
    standard = time.localtime(t + STD_OFFSET)
    return DST_OFFSET if _is_dst(standard) else STD_OFFSET


def localtime(t=None):
    """Local wall-clock time as a time tuple, for UTC instant `t` or now."""
    if t is None:
        t = time.time()
    return time.localtime(t + utc_offset(t))


def time_is_valid():
    """False while the RTC still holds its power-on default."""
    return time.localtime()[0] >= 2024


def sync_time(retries=_SYNC_RETRIES):
    """Set the RTC from NTP. Returns True on success."""
    global _last_sync
    for attempt in range(1, retries + 1):
        try:
            print("Syncing time via NTP (attempt {}/{})...".format(attempt, retries))
            ntptime.settime()
            _last_sync = time.time()
            print("RTC set. Local time:", localtime())
            return True
        except Exception as e:
            print("  NTP sync failed:", e)
            time.sleep(2)
    return False


def maybe_resync(interval=RESYNC_INTERVAL_S):
    """Resync if the clock is unset or the last sync has gone stale.

    The Pico's RTC drifts noticeably over days, which slowly misaligns the
    timeline columns with real hours.
    """
    if not time_is_valid():
        return sync_time()
    if time.time() - _last_sync >= interval:
        return sync_time()
    return True
