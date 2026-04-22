"""
Weather module using Open-Meteo (free, no API key, no signup).
Supports Munich-wide queries and specific district/area queries.
"""

import requests
from datetime import datetime, timezone, timedelta

# Munich district/area coordinates
MUNICH_LOCATIONS = {
    # Districts
    "innenstadt": (48.1374, 11.5755),
    "maxvorstadt": (48.1502, 11.5678),
    "schwabing": (48.1633, 11.5836),
    "haidhausen": (48.1286, 11.6017),
    "sendling": (48.1136, 11.5456),
    "neuhausen": (48.1525, 11.5278),
    "bogenhausen": (48.1500, 11.6167),
    "pasing": (48.1436, 11.4628),
    "moosach": (48.1769, 11.5178),
    "milbertshofen": (48.1808, 11.5625),
    "au": (48.1236, 11.5878),
    "giesing": (48.1069, 11.5794),
    "riem": (48.1286, 11.7000),
    # Nearby cities
    "garching": (48.2489, 11.6519),
    "ismaning": (48.2247, 11.6858),
    "unterschleißheim": (48.2806, 11.5728),
    "dachau": (48.2597, 11.4342),
    "starnberg": (47.9989, 11.3414),
    "freising": (48.4028, 11.7489),
    "erding": (48.3058, 11.9061),
    "fürstenfeldbruck": (48.1786, 11.2347),
    "großhadern": (48.1072, 11.4742),
    "klinikum großhadern": (48.1072, 11.4742),
    # Generic Munich fallback
    "munich": (48.1351, 11.5820),
    "münchen": (48.1351, 11.5820),
}

BASE_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"


def _resolve_coordinates(location: str) -> tuple[float, float]:
    """Return (lat, lon) for a location name."""
    key = location.lower().strip()
    if key in MUNICH_LOCATIONS:
        return MUNICH_LOCATIONS[key]

    # Try geocoding API
    try:
        r = requests.get(
            GEOCODE_URL,
            params={"name": location, "count": 1, "language": "en", "format": "json"},
            timeout=8,
        )
        results = r.json().get("results", [])
        if results:
            return results[0]["latitude"], results[0]["longitude"]
    except Exception:
        pass

    return MUNICH_LOCATIONS["munich"]


def _fetch_weather(lat: float, lon: float) -> dict | None:
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,weathercode,windspeed_10m",
        "hourly": "temperature_2m,precipitation_probability,precipitation,weathercode",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "Europe/Berlin",
        "forecast_days": 2,
    }
    try:
        r = requests.get(BASE_URL, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _wmo_description(code: int) -> str:
    """Convert WMO weather code to human-readable string."""
    codes = {
        0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
        45: "foggy", 48: "foggy",
        51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
        61: "light rain", 63: "rain", 65: "heavy rain",
        71: "light snow", 73: "snow", 75: "heavy snow",
        77: "snow grains",
        80: "light showers", 81: "showers", 82: "heavy showers",
        85: "snow showers", 86: "heavy snow showers",
        95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with heavy hail",
    }
    return codes.get(code, "mixed conditions")


def get_weather_briefing(location: str = "Munich") -> str:
    lat, lon = _resolve_coordinates(location)
    data = _fetch_weather(lat, lon)

    if not data:
        return "Weather data unavailable right now."

    current = data.get("current", {})
    temp = round(current.get("temperature_2m", 0))
    feels = round(current.get("apparent_temperature", temp))
    wind = round(current.get("windspeed_10m", 0))
    code = current.get("weathercode", 0)
    desc = _wmo_description(code)

    # Find rain windows in next 12 hours
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    precip_prob = hourly.get("precipitation_probability", [])
    precip_mm = hourly.get("precipitation", [])

    now = datetime.now()
    rain_windows = []
    for i, t in enumerate(times[:24]):
        slot_time = datetime.fromisoformat(t)
        hours_ahead = (slot_time - now).total_seconds() / 3600
        if 0 <= hours_ahead <= 12:
            prob = precip_prob[i] if i < len(precip_prob) else 0
            mm = precip_mm[i] if i < len(precip_mm) else 0
            if prob >= 40 or mm > 0:
                rain_windows.append((slot_time.strftime("%-I %p"), prob, mm))

    location_label = location.title() if location.lower() not in ("munich", "münchen") else "Munich"
    speech = f"{location_label}: {temp} degrees Celsius, {desc}, wind {wind} kilometres per hour."

    if rain_windows:
        first = rain_windows[0]
        heaviest = max(rain_windows, key=lambda x: x[2])
        speech += f" Rain expected from {first[0]}"
        if heaviest[0] != first[0]:
            speech += f", heaviest around {heaviest[0]}"
        speech += "."

    speech += " " + _clothing_suggestion(temp, bool(rain_windows), wind, feels)
    return speech


def get_rain_detail(location: str = "Munich") -> str:
    lat, lon = _resolve_coordinates(location)
    data = _fetch_weather(lat, lon)

    if not data:
        return "Rain forecast unavailable."

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    precip_prob = hourly.get("precipitation_probability", [])
    precip_mm = hourly.get("precipitation", [])

    now = datetime.now()
    rain_slots = []
    for i, t in enumerate(times[:24]):
        slot_time = datetime.fromisoformat(t)
        hours_ahead = (slot_time - now).total_seconds() / 3600
        if 0 <= hours_ahead <= 12:
            prob = precip_prob[i] if i < len(precip_prob) else 0
            mm = precip_mm[i] if i < len(precip_mm) else 0
            if prob >= 30 or mm > 0:
                intensity = "heavy" if mm > 5 else "moderate" if mm > 2 else "light"
                rain_slots.append(f"{intensity} rain at {slot_time.strftime('%-I %p')} ({int(prob)}% chance)")

    if not rain_slots:
        return "No significant rain expected in the next 12 hours."

    return "Rain forecast: " + ", then ".join(rain_slots) + "."


def _clothing_suggestion(temp: float, rain: bool, wind_kmh: float, feels: float) -> str:
    if temp < 5:
        base = "heavy winter coat"
    elif temp < 12:
        base = "warm jacket"
    elif temp < 18:
        base = "light jacket or layer"
    else:
        base = "light clothing"

    extras = []
    if rain:
        base = "waterproof jacket"
        extras.append("closed shoes")
    if wind_kmh > 40:
        extras.append("windproof layer")
    if feels < temp - 3:
        extras.append("it feels colder than it looks")

    items = [base] + extras
    return "Wear " + ", ".join(items) + "."
