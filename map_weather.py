from hsv_utils import hsv_to_rgb

def map_to_column(weather):
    pixels = [(0, 0, 0)] * 11

    t = max(-10, min(40, weather['temp']))
    hue = (40 - t) / 50.0 * 0.66
    r, g, b = hsv_to_rgb(hue, 1.0, 1.0)

    brightness = (100 - weather['cloud']) / 100
    sparkle = weather['precip'] > 0.5
    wind = max(0, min(weather['wind'], 50))
    height = int((wind / 50) * 11)
    if height < 1:
        height = 1

    for y in range(height):
        px = (
            int(r * 255 * brightness),
            int(g * 255 * brightness),
            int(b * 255 * brightness)
        )
        if sparkle and y == height - 1:
            px = (255, 255, 255)
        pixels[y] = px

    return pixels[::-1]