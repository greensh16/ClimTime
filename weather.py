import urequests

def fetch_weather(API_KEY, LOCATION):
    url = f"http://api.weatherapi.com/v1/current.json?key={API_KEY}&q={LOCATION}&aqi=no"
    try:
        r = urequests.get(url)
        data = r.json()
        r.close()
    except Exception as e:
        print("WeatherAPI fetch error:", e)
        return None

    current = data.get("current", {})
    return {
        "temp": current.get("temp_c"),
        "cloud": current.get("cloud"),
        "precip": current.get("precip_mm", 0),
        "wind": current.get("wind_kph", 0),
        "is_day": current.get("is_day", 1)
    }