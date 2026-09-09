"""Wi-Fi connection with a timeout, retries, and a reconnect helper."""

import network
import time

CONNECT_TIMEOUT_S = 20
CONNECT_RETRIES = 3

_wlan = None

# Status codes that mean "stop waiting". Looked up defensively because not
# every MicroPython port defines all of them.
_FATAL_STATUS = {}
for _name in ("STAT_WRONG_PASSWORD", "STAT_NO_AP_FOUND", "STAT_CONNECT_FAIL"):
    _value = getattr(network, _name, None)
    if _value is not None:
        _FATAL_STATUS[_value] = _name


def _get_wlan():
    global _wlan
    if _wlan is None:
        _wlan = network.WLAN(network.STA_IF)
    return _wlan


def is_connected():
    wlan = _get_wlan()
    try:
        return bool(wlan.active() and wlan.isconnected())
    except Exception:
        return False


def connect_wifi(ssid, password, timeout=CONNECT_TIMEOUT_S, retries=CONNECT_RETRIES):
    """Connect to Wi-Fi. Returns True on success, False on give-up.

    The original version looped forever with no timeout and no status check, so
    a wrong password or a missing AP hung the board at boot with no output.
    """
    wlan = _get_wlan()
    wlan.active(True)

    for attempt in range(1, retries + 1):
        if wlan.isconnected():
            print("Network config:", wlan.ifconfig())
            return True

        print("Connecting to network (attempt {}/{})...".format(attempt, retries))
        try:
            wlan.connect(ssid, password)
        except OSError as e:
            print("  connect() raised:", e)

        deadline = time.ticks_add(time.ticks_ms(), int(timeout * 1000))
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            if wlan.isconnected():
                print("Network config:", wlan.ifconfig())
                return True

            status = wlan.status()
            if status in _FATAL_STATUS:
                reason = _FATAL_STATUS[status]
                print("  Wi-Fi error:", reason)
                if reason == "STAT_WRONG_PASSWORD":
                    return False  # retrying will never help
                break
            time.sleep(0.5)
        else:
            print("  timed out after {}s".format(timeout))

        try:
            wlan.disconnect()
        except Exception:
            pass
        time.sleep(1)

    print("Wi-Fi: giving up after {} attempts".format(retries))
    return False


def ensure_connected(ssid, password, **kwargs):
    """Cheap check first, reconnect only if the link has actually dropped."""
    if is_connected():
        return True
    print("Wi-Fi link lost, reconnecting...")
    return connect_wifi(ssid, password, **kwargs)
