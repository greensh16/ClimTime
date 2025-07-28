# Temporal Climate Timeline on Galactic Unicorn

A real-time weather art display built using the [Pimoroni Galactic Unicorn](https://shop.pimoroni.com/products/galactic-unicorn) and MicroPython.

This project turns hourly weather data into an abstract **weather tapestry**, visualized on a 53×11 LED grid. Each vertical column represents one hour, and the entire matrix evolves over time to reveal patterns in temperature, cloud cover, wind, and precipitation.

## Project Highlights

- **Color = Temperature**  
  Blue = cold, Red = hot (mapped via hue gradient)

- **Brightness = Cloud Cover**  
  Bright = sunny, Dim = overcast

- **Pixel Height = Wind Speed**  
  Stronger wind → taller vertical bars

- **Sparkle = Precipitation**  
  Flashing white pixels indicate rain or snow

- **Hourly Timeline Shift**  
  A new column slides in every hour, building a visual history

---

## How It Works

1. **Weather Fetch**  
   Retrieves current hourly data from the [Open-Meteo API](https://open-meteo.com/) using Wi-Fi.

2. **Data Mapping**  
   Weather values are translated into colors, brightness, and animation logic for the LED matrix.

3. **Frame Shift**  
   Each new hour adds a column to the right; the oldest column scrolls off the left.

4. **Display Update**  
   The entire timeline is rendered onto the Galactic Unicorn and refreshed continuously.

---

## Hardware Required

- [Pimoroni Galactic Unicorn](https://shop.pimoroni.com/products/galactic-unicorn)
- Raspberry Pi Pico W (comes with the Unicorn)
- USB power (5V 2A recommended)
- Optional: Diffuser panel, Li-Po battery, sensors for local fallback

---

## Software Setup

### 1. Flash MicroPython
Install the official [Galactic Unicorn MicroPython firmware](https://github.com/pimoroni/pimoroni-pico/releases) onto your Pico W.

### 2. Project Files

Place these files onto the Pico W using Thonny or rshell:

```
main.py
wifi.py
weather.py
map_weather.py
```

### 3. Update Wi-Fi

In `main.py`, replace:

```python
wifi.connect_wifi("YOUR_SSID", "YOUR_PASSWORD")
```

with your credentials.

### 4. Run

Use Thonny or a serial REPL to run `main.py`. The matrix will begin displaying the weather timeline, updating every hour.

---

## Visual Example

<Image here>

Each column shows:
- Color → temperature
- Brightness → cloud cover
- Sparkle at top → rain
- Height → wind speed

---

## Future Ideas

- **7-Day Scrolling Mode**  
  Allow continuous scroll for 168 hours (7 days of history)

- **Thunder Animation**  
  Flash columns white if a storm is detected

- **Sunrise/Sunset Glow**  
  Animate golden hour hues based on local solar times

- **Auto-Dimming**  
  Use the onboard light sensor to reduce brightness at night

- **Local Sensor Integration**  
  BME280 or similar as fallback when internet is down

- **Audio Output**  
  Add ambient weather sonification (e.g. wind = tone pitch)

- **Button Controls**  
  Use onboard buttons to switch between day, week, or custom visualizations

---

## Credits

- LED hardware: [Pimoroni Galactic Unicorn](https://shop.pimoroni.com/products/galactic-unicorn)
- Weather data: [Open-Meteo](https://open-meteo.com/)
- MicroPython: [Pimoroni firmware](https://github.com/pimoroni/pimoroni-pico)

---

## License

MIT License — feel free to remix, expand, and display this project for educational or outreach use.
