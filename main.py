from galactic import GalacticUnicorn
from picographics import PicoGraphics, DISPLAY_GALACTIC_UNICORN as DISPLAY
import time
from rtc_time import localtime

import wifi
import weather
import map_weather
import rtc_time

gu = GalacticUnicorn()
graphics = PicoGraphics(DISPLAY)
WIDTH, HEIGHT = graphics.get_bounds()

try:
    from secrets import WIFI_SSID, WIFI_PASSWORD, API_KEY, LOCATION
    wifi_available = True
except ImportError:
    print("Create secrets.py with your WiFi credentials to get time from NTP")
    wifi_available = False

# Pens
BLACK = graphics.create_pen(0, 0, 0)
WHITE = graphics.create_pen(255, 255, 255)

# Pixel history: 1 column per hour
timeline = [[(0, 0, 0)] * HEIGHT for _ in range(WIDTH)]

# Connect to Wi-Fi
wifi.connect_wifi(WIFI_SSID, WIFI_PASSWORD)
rtc_time.sync_time()

def sleep_until_next_hour():
    now = localtime()
    seconds = 3600 - (now[4] * 60 + now[5])
    print(f"Sleeping {seconds} seconds until next hour")
    time.sleep(seconds)

while True:
    wx = weather.fetch_weather(API_KEY, LOCATION)
    if not wx:
        print("Skipping this hour due to fetch error")
    else:
        new_col = map_weather.map_to_column(wx)

    # Shift buffer left and append new column
    timeline = timeline[1:] + [new_col]

    # Clear display
    graphics.set_pen(BLACK)
    graphics.clear()

    # Draw pixels
    for x in range(WIDTH):
        for y in range(HEIGHT):
            r, g, b = timeline[x][y]
            pen = graphics.create_pen(int(r), int(g), int(b))
            graphics.set_pen(pen)
            graphics.pixel(x, y)

    gu.update(graphics)

    print("Display updated:", wx)
    sleep_until_next_hour()