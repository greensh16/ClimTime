# ClimTime — a rolling weather timeline on a Galactic Unicorn

MicroPython firmware for a [Pimoroni Galactic Unicorn](https://shop.pimoroni.com/products/galactic-unicorn)
(Raspberry Pi Pico W + 53×11 LED matrix) that renders the last **53 hours** of
weather as a living tapestry.

One column is one hour. The newest hour is on the right; every hour the whole
panel shifts one column to the left. Behind the data, a sky gradient tracks the
real sunrise and sunset for the hour each column represents, so the display
breathes with the day as well as the weather.

## What each pixel means

| Channel | Meaning |
|---|---|
| **Bar height** | Temperature, on a scale that adapts to what is on screen |
| **Bar colour** | Temperature — deep blue → cyan → yellow → red |
| **Bar dimness** | Cloud cover — bright is clear, dim is overcast |
| **White top pixel** | Rain (over 0.5 mm in that hour) |
| **Background glow** | Time of day, faded through dawn and dusk from real sun times |
| **Panel brightness** | Drops at night, so the display is not a lamp at 3 am |

Temperature drives both height and colour because it has the strongest daily
cycle of anything the API returns — it makes the panel read as a wave rather
than a flat line. Wind is still fetched but is no longer displayed.

The sky gradient is brightest at the top row and falls away steeply, leaving
the lower two thirds of the panel black. The bars grow up from the bottom, so
they always sit against the darkest part of the display.

### The adaptive scale

There is one temperature scale for the whole panel, derived from every reading
currently displayed, widened to a minimum span of 8 °C so a still, flat day
does not get amplified into noise. When the scale moves more than 0.5 °C, every
column is rebuilt — otherwise older columns would be drawn against a scale that
no longer applies. Each column keeps its raw reading for exactly this reason,
so a rescale costs no network traffic.

## How it works

1. **Startup** — connect to Wi-Fi, sync the clock over NTP, then backfill the
   panel with the last 52 hours from WeatherAPI.com's history endpoint plus the
   current conditions.
2. **Hourly loop** — fetch current conditions, shift in a new column, rescale if
   needed, redraw, then sleep to the top of the next hour.
3. **Failures degrade visibly.** A failed fetch becomes a blank column with the
   sky showing through, never a missing entry, so column position always means
   the same thing in time. An outage spanning several hours shifts in one blank
   column per *missed* hour, so the gap is visible rather than silently
   compressing the timeline.

Time is handled carefully. The RTC holds UTC and local time is derived by
applying the correct NSW offset for the date, so the panel does not sit an hour
out for half the year — and history is walked backwards in UTC, converting each
instant separately, because UTC hours are uniform and local ones are not.

## Hardware

- [Pimoroni Galactic Unicorn](https://shop.pimoroni.com/products/galactic-unicorn) (includes a Raspberry Pi Pico W)
- USB power, 5 V 2 A recommended
- Optional: diffuser panel

## Setup

### 1. Flash MicroPython

Install the [Pimoroni Galactic Unicorn MicroPython build](https://github.com/pimoroni/pimoroni-pico/releases)
onto the Pico W. The stock MicroPython image will not work — this code needs
Pimoroni's `galactic` and `picographics` modules.

### 2. Get a WeatherAPI key

Sign up at [WeatherAPI.com](https://www.weatherapi.com/). The free tier covers
the current conditions and the few days of history this project reads.

### 3. Create `secrets.py`

```python
WIFI_SSID = "YOUR_SSID"
WIFI_PASSWORD = "YOUR_PASSWORD"
API_KEY = "YOUR_API_KEY"
LOCATION = "Sydney"
```

`secrets.py` is gitignored. Check `git status` before committing anyway.

### 4. Copy the files to the device

```
main.py
wifi.py
weather.py
map_weather.py
rtc_time.py
sky.py
secrets.py
```

Use Thonny, `rshell` or `mpremote`.

### 5. Run

Run `main.py` from the REPL, or let it autostart on power-up. Startup failures
— no `secrets.py`, no Wi-Fi, no NTP — print a message on the panel and exit
rather than hanging silently.

## Configuration

Most tuning lives at the top of each module:

| Where | Setting |
|---|---|
| `main.py` | `DAY_BRIGHTNESS`, `NIGHT_BRIGHTNESS`, `RETRY_DELAY_S`, `RESCALE_THRESHOLD_C` |
| `map_weather.py` | `RAMP` colours, `MIN_SPAN_C`, `MIN_BRIGHTNESS`, `PRECIP_SPARKLE_MM` |
| `sky.py` | `NIGHT`/`DAWN`/`DAY`/`DUSK` colours, `TWILIGHT_H`, `FALLOFF` |
| `rtc_time.py` | `STD_OFFSET`, `OBSERVE_DST` — set `OBSERVE_DST = False` for QLD/WA/NT |

**One caveat when changing colours.** PicoGraphics runs in a palette-backed pen
mode with a finite number of slots, so `map_weather` and `sky` both quantise
their output (`TEMP_BUCKETS`, `CLOUD_BUCKETS`, `PHASE_STEPS`, `COLOUR_STEP`) to
keep the number of distinct colours bounded — the measured worst case across a
year is 137 pens of 256. Adding gradients or smooth interpolation without
quantising will exhaust the palette at runtime.

## Development notes

There is no build, no test suite and no package manager. The code runs **only on
the device** — `main.py` and its I/O modules import MicroPython-only names
(`galactic`, `picographics`, `urequests`, `network`, `ntptime`).

The pure-logic modules — `map_weather.py`, `sky.py`, and the date maths in
`rtc_time.py` — have no MicroPython imports and can be imported under host
CPython for quick checks in a REPL.

### Module layout

`main.py` is the orchestrator and the only module that touches the display.
Everything else is a pure function or an I/O leaf:

- **`weather.py`** — WeatherAPI.com client. Normalises current conditions and
  history into one reading dict (`temp`, `cloud`, `precip`, `wind`, `is_day`,
  `hour`, `sunrise`, `sunset`).
- **`map_weather.py`** — pure: reading → foreground pixel column.
- **`sky.py`** — pure: hour + sun times → background gradient column.
- **`rtc_time.py`** — NTP sync and DST-aware local time for New South Wales.
- **`wifi.py`** — connect with timeout and retries, plus `ensure_connected()`.

### Memory

RAM is the real constraint on a Pico W, and several things in `weather.py` exist
only to manage it: `forecast.json` is requested with `hour=0` to drop a 24-entry
hourly array the code never reads (13.9 KB → 1.9 KB), history is parsed one date
per function call so each payload becomes unreachable before the next request
allocates, `gc.collect()` runs before each request, and HTTP responses are closed
in a `finally` so the socket cannot leak. Fetch failures print free heap, so a
`MemoryError` is distinguishable from a network fault.

`weather.USE_HTTPS = False` saves the TLS buffers but puts the API key on the
wire in cleartext — a diagnostic, not a fix.

## Ideas

- Auto-dimming from the onboard light sensor
- Button controls to switch between day, week and custom views
- Thunder animation on storm conditions
- A local BME280 as fallback when the internet is down

## Credits

- LED hardware and firmware: [Pimoroni](https://github.com/pimoroni/pimoroni-pico)
- Weather data: [WeatherAPI.com](https://www.weatherapi.com/)
