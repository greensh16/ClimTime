from galactic import GalacticUnicorn
from picographics import PicoGraphics, DISPLAY_GALACTIC_UNICORN as DISPLAY
import time
from rtc_time import localtime

import wifi
import weather
import map_weather
import rtc_time

# === Init Display ===
gu = GalacticUnicorn()
graphics = PicoGraphics(DISPLAY)
WIDTH, HEIGHT = graphics.get_bounds()

# === Connect Wi-Fi ===
try:
    from secrets import WIFI_SSID, WIFI_PASSWORD, API_KEY, LOCATION
    wifi_available = True
except ImportError:
    print("Create secrets.py with your WiFi credentials to get time from NTP")
    wifi_available = False

wifi.connect_wifi(WIFI_SSID, WIFI_PASSWORD)

# === Set Time ===
rtc_time.sync_time()
start_hour = rtc_time.localtime()[3]

# === Background color function ===
def get_background_color(hour):
    if 6 <= hour <= 7 or 17 <= hour <= 18:
        return (80, 60, 10)  # Muted sunrise/sunset
    elif 8 <= hour <= 17:
        return (30, 60, 50)  # Soft, desaturated blue
    else:
        return (0, 0, 10)  # Very dim night

# === Pre-populate timeline with last 53 hours + now ===
print("Fetching historical weather...")
history = weather.fetch_past_53_hours(API_KEY, LOCATION)
wx_now = weather.fetch_weather(API_KEY, LOCATION)

# Timeline holds 53 columns, each a vertical pixel slice (11px high)
timeline = []
for wx in history + [wx_now]:
    timeline.append(map_weather.map_to_column(wx))

# Ensure exactly WIDTH=53 columns
timeline = timeline[-WIDTH:]

# === Main Loop ===
while True:
    wx = weather.fetch_weather(API_KEY, LOCATION)
    if not wx:
        print("Failed to fetch weather. Retrying in 10 minutes...")
        time.sleep(600)
        continue

    new_col = map_weather.map_to_column(wx)

    # Shift timeline left, append new column
    timeline = timeline[1:] + [new_col]

    # === Draw Background ===
    for x in range(WIDTH):
        column_hour = (start_hour - (WIDTH - 1 - x)) % 24
        bg_r, bg_g, bg_b = get_background_color(column_hour)
        bg_pen = graphics.create_pen(bg_r, bg_g, bg_b)
        for y in range(HEIGHT):
            graphics.set_pen(bg_pen)
            graphics.pixel(x, y)

    # === Overlay Weather Pixels ===
    for x in range(WIDTH):
        for y in range(HEIGHT):
            r, g, b = timeline[x][y]
            if (r, g, b) != (0, 0, 0):
                pen = graphics.create_pen(int(r), int(g), int(b))
                graphics.set_pen(pen)
                graphics.pixel(x, y)

    gu.update(graphics)
    print("Updated display with:", wx)

    # Increment hour offset for next shift
    start_hour = (start_hour + 1) % 24

    # Sleep until next hour
    now = rtc_time.localtime()
    seconds = 3600 - (now[4] * 60 + now[5])
    print(f"Sleeping for {seconds} seconds...")
    time.sleep(seconds)