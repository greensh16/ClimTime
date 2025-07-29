import ntptime
import time

# Set timezone offset in hours (e.g. +10 for AEST, +11 for AEDT)
UTC_OFFSET = 10 * 3600

def sync_time():
    try:
        print("Syncing time via NTP...")
        ntptime.settime()  # sets the RTC
        print("RTC time (UTC):", time.localtime())
    except Exception as e:
        print("NTP sync failed:", e)

def localtime():
    """Returns localtime adjusted for UTC offset."""
    t = time.time() + UTC_OFFSET
    return time.localtime(t)