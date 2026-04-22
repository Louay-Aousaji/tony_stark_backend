"""
Morning briefing module.

Phase 1 (parallel): battery, weather, messages, forex  →  spoken immediately
Phase 2 (interactive): ask destination, fetch transit   →  spoken after user replies
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from modules.weather import get_weather_briefing
from modules.transit import format_route_speech
from modules.notifications import get_battery_level, get_notification_summary
from modules.forex import get_forex_briefing
from modules.stations import resolve_station


def _safe(fn, *args, fallback="Unavailable."):
    try:
        return fn(*args)
    except Exception:
        return fallback


def build_phase1() -> str:
    """Fetch battery, weather, messages, forex in parallel and return spoken text."""
    tasks = {
        "battery": (get_battery_level,),
        "weather": (get_weather_briefing, "Munich"),
        "messages": (get_notification_summary,),
        "forex": (get_forex_briefing,),
    }

    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_map = {
            executor.submit(_safe, *args): key
            for key, args in tasks.items()
        }
        for future in as_completed(future_map):
            key = future_map[future]
            results[key] = future.result()

    import re
    text = (
        f"{results.get('battery', '')} "
        f"{results.get('weather', '')} "
        f"{results.get('messages', '')} "
        f"{results.get('forex', '')}"
    )
    return re.sub(r"\s{2,}", " ", text).strip()


def build_transit_segment(destination: str) -> str:
    """Fetch transit route to the given destination and return spoken text."""
    from config.settings import HOME_STATION
    return _safe(format_route_speech, HOME_STATION, destination,
                 fallback=f"Could not find a route to {destination}.")


def parse_destination_from_speech(spoken: str) -> tuple[dict | None, str]:
    """
    Try to extract and resolve a U-Bahn destination from spoken text.
    Returns (station_dict_or_None, display_name).
    """
    # Strip filler phrases
    import re
    cleaned = re.sub(
        r"^(i(?:'m| am) going to|take me to|route to|i need to go to|heading to|going to|to)\s+",
        "", spoken.strip(), flags=re.IGNORECASE
    )
    station = resolve_station(cleaned)
    if station:
        return station, station["name"]
    # Try full spoken text as fallback
    station = resolve_station(spoken)
    return station, station["name"] if station else spoken.title()
