import urequests
from rtc_time import localtime
import time

def get_past_53_hours():
    now = time.mktime(localtime())  # local time → timestamp
    timestamps = []
    for h in range(53, 0, -1):
        ts = now - h * 3600
        t = time.localtime(ts)
        date_str = f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d}"
        hour = t[3]
        timestamps.append((date_str, hour))
    return timestamps

def group_by_date(timestamps):
    grouped = {}
    for date_str, hour in timestamps:
        if date_str not in grouped:
            grouped[date_str] = []
        grouped[date_str].append(hour)
    return grouped

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

def fetch_past_53_hours(API_KEY, LOCATION):
    timestamps = get_past_53_hours()
    grouped = group_by_date(timestamps)

    result = []
    for date_str, hours in grouped.items():
        url = f"http://api.weatherapi.com/v1/history.json?key={API_KEY}&q={LOCATION}&dt={date_str}"
        try:
            r = urequests.get(url)
            data = r.json()
            r.close()
            hourly = data["forecast"]["forecastday"][0]["hour"]
            for h in hours:
                entry = hourly[h]
                result.append({
                    "temp": entry["temp_c"],
                    "cloud": entry["cloud"],
                    "precip": entry["precip_mm"],
                    "wind": entry["wind_kph"],
                    "is_day": entry["is_day"]
                })
        except Exception as e:
            print(f"Failed to fetch {date_str}: {e}")
    return result