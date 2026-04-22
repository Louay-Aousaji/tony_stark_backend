"""
Transit module using MVV EFA API (free, no key required).
Replaces the broken mvg-api library.
"""

import requests
from datetime import datetime
from functools import lru_cache

EFA_BASE = "https://efa.mvv-muenchen.de/mvv"
HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}

_STATION_CACHE: list[dict] = []


def _efa_get(endpoint: str, params: dict) -> dict:
    """GET an EFA endpoint and return parsed JSON with correct encoding."""
    r = requests.get(f"{EFA_BASE}/{endpoint}", params=params, headers=HEADERS, timeout=12)
    r.encoding = "utf-8"
    return r.json()


def _get_all_stations() -> list[dict]:
    global _STATION_CACHE
    if _STATION_CACHE:
        return _STATION_CACHE
    try:
        r = requests.get("https://www.mvg.de/.rest/zdm/stations", headers=HEADERS, timeout=12)
        r.encoding = "utf-8"
        _STATION_CACHE = r.json()
    except Exception:
        _STATION_CACHE = []
    return _STATION_CACHE


def _station_score(s: dict, name_lower: str) -> int:
    """Higher score = better match. Prefer München, U-Bahn/S-Bahn over bus-only."""
    score = 0
    place = s.get("place", "").lower()
    products = s.get("products", [])
    if "münchen" in place or place == "munich":
        score += 100
    if "UBAHN" in products or "SBAHN" in products:
        score += 10
    if s["name"].lower() == name_lower:
        score += 50
    elif s["name"].lower().startswith(name_lower):
        score += 20
    return score


def find_station(name: str) -> dict | None:
    """Find best matching station by name, preferring München U/S-Bahn stations."""
    name_lower = name.lower().strip()
    stations = _get_all_stations()

    candidates = []
    for s in stations:
        sname = s["name"].lower()
        if sname == name_lower or sname.startswith(name_lower) or name_lower in sname:
            candidates.append(s)

    if not candidates:
        return None

    return max(candidates, key=lambda s: _station_score(s, name_lower))


def get_departures(station_name: str, limit: int = 6) -> list[dict]:
    """Get real-time departures from a station using EFA."""
    station = find_station(station_name)
    if not station:
        return []

    diva_id = f"1{station['divaId']:06d}"  # EFA uses 1001540 format (7 digits)
    try:
        data = _efa_get("XML_DM_REQUEST", {
            "outputFormat": "JSON",
            "type_dm": "stop",
            "name_dm": diva_id,
            "useRealtime": "1",
            "limit": str(limit),
            "mode": "direct",
        })
        raw_deps = data.get("departureList", [])
        if not isinstance(raw_deps, list):
            raw_deps = [raw_deps]

        deps = []
        now = datetime.now()
        for d in raw_deps:
            dt = d.get("dateTime", {})
            rt_hour = int(dt.get("hour", dt.get("rtHour", 0)))
            rt_min = int(dt.get("minute", dt.get("rtMinute", 0)))
            dep_time = now.replace(hour=rt_hour, minute=rt_min, second=0, microsecond=0)
            minutes_away = int(d.get("countdown", 0))

            line_info = d.get("servingLine", {})
            deps.append({
                "line": line_info.get("symbol", line_info.get("number", "?")),
                "direction": line_info.get("direction", "?"),
                "minutes": minutes_away,
                "platform": d.get("platformName", ""),
                "delay": 0,
                "product": line_info.get("name", ""),
                "disruptions": _extract_disruptions(d),
            })
        return deps

    except Exception:
        return []


def _extract_disruptions(dep: dict) -> list[str]:
    infos = dep.get("lineInfos", [])
    if not infos:
        return []
    if isinstance(infos, dict):
        infos = [infos.get("lineInfo", {})]
    msgs = []
    for info in infos:
        if isinstance(info, dict):
            text = info.get("infoLinkText", "")
            if text:
                msgs.append(text)
    return msgs


def get_route(origin_name: str, destination_name: str) -> dict | None:
    """Get best transit route between two stations."""
    origin = find_station(origin_name)
    dest = find_station(destination_name)

    origin_id = f"1{origin['divaId']:06d}" if origin else None
    dest_id = f"1{dest['divaId']:06d}" if dest else None

    try:
        params = {
            "outputFormat": "JSON",
            "useRealtime": "1",
            "maxJourneys": "1",
        }
        if origin_id:
            params.update({"type_origin": "stop", "name_origin": origin_id})
        else:
            params.update({"type_origin": "any", "name_origin": origin_name})

        if dest_id:
            params.update({"type_destination": "stop", "name_destination": dest_id})
        else:
            params.update({"type_destination": "any", "name_destination": destination_name})

        data = _efa_get("XML_TRIP_REQUEST2", params)
        trips = data.get("trips", [])
        if not trips:
            return None

        trip = trips[0]
        duration_str = trip.get("duration", "?")
        interchanges = int(trip.get("interchange", 0))
        legs = trip.get("legs", [])

        parsed_legs = []
        for leg in legs:
            mode = leg.get("mode", {})
            pts = leg.get("points", [])
            dep_pt = next((p for p in pts if p.get("usage") == "departure"), pts[0] if pts else {})
            arr_pt = next((p for p in pts if p.get("usage") == "arrival"), pts[-1] if pts else {})

            line = mode.get("number", "")
            direction = mode.get("destination", "")
            product = mode.get("product", "")
            dep_time = dep_pt.get("dateTime", {}).get("rtTime") or dep_pt.get("dateTime", {}).get("time", "")
            from_name = dep_pt.get("name", "")
            to_name = arr_pt.get("name", "")

            if "Fußweg" in product or "walk" in product.lower() or not line:
                walk_min = int(leg.get("timeMinute", 0))
                if walk_min > 0:
                    parsed_legs.append({"type": "walk", "minutes": walk_min})
            else:
                parsed_legs.append({
                    "type": "transit",
                    "line": line,
                    "direction": direction,
                    "from": from_name,
                    "to": to_name,
                    "dep_time": dep_time,
                    "product": product,
                })

        # Parse duration "HH:MM" -> minutes
        total_minutes = None
        if ":" in str(duration_str):
            h, m = duration_str.split(":")
            total_minutes = int(h) * 60 + int(m)

        return {
            "legs": parsed_legs,
            "total_minutes": total_minutes,
            "interchanges": interchanges,
        }

    except Exception:
        return None


def get_disruptions() -> list[str]:
    """Fetch current MVG disruptions via EFA info endpoint."""
    try:
        data = _efa_get("XML_DM_REQUEST", {
            "outputFormat": "JSON",
            "type_dm": "stop",
            "name_dm": "1000001",  # Hauptbahnhof divaId=1 → 1000001
            "useRealtime": "1",
            "limit": "3",
        })
        deps = data.get("departureList", [])
        if not isinstance(deps, list):
            deps = [deps]

        seen = set()
        msgs = []
        for d in deps:
            for msg in _extract_disruptions(d):
                if msg not in seen:
                    seen.add(msg)
                    msgs.append(msg)
        return msgs
    except Exception:
        return []


def _minutes_until(dep_time_str: str) -> int | None:
    """Convert HH:MM string to minutes from now."""
    try:
        now = datetime.now()
        h, m = map(int, dep_time_str.split(":"))
        dep = now.replace(hour=h, minute=m, second=0, microsecond=0)
        diff = (dep - now).total_seconds() / 60
        if diff < 0:
            diff += 24 * 60  # next day
        return int(diff)
    except Exception:
        return None


def format_departures_speech(station_name: str, line_filter: str | None = None) -> str:
    deps = get_departures(station_name)
    if not deps:
        return f"No departures found at {station_name}."

    if line_filter:
        deps = [d for d in deps if line_filter.upper() in d["line"].upper()]
        if not deps:
            return f"No {line_filter} departures found at {station_name}."

    d = deps[0]
    minutes = d["minutes"]
    platform = f". Platform {d['platform']}" if d["platform"] else ""
    speech = (
        f"At {station_name}, the next {d['line']} towards {d['direction']} "
        f"leaves in {minutes} {'minute' if minutes == 1 else 'minutes'}{platform}."
    )
    if len(deps) > 1:
        d2 = deps[1]
        speech += f" Following one in {d2['minutes']} minutes."

    # Check for disruptions on this line
    all_disruptions = [msg for dep in deps[:3] for msg in dep.get("disruptions", [])]
    if all_disruptions:
        speech += f" Note: {all_disruptions[0]}."

    return speech


def format_route_speech(origin: str, destination: str) -> str:
    route = get_route(origin, destination)

    if not route:
        return f"Could not find a route from {origin} to {destination}."

    parts = []
    for leg in route["legs"]:
        if leg["type"] == "transit":
            parts.append(f"take {leg['line']} towards {leg['direction']} from {leg['from']}")
        elif leg["type"] == "walk" and leg["minutes"] > 1:
            parts.append(f"walk {leg['minutes']} minutes")

    if not parts:
        return f"Route to {destination} found but could not be described."

    speech = f"To {destination}: " + ", then ".join(parts) + "."

    if route["total_minutes"]:
        speech += f" Total {route['total_minutes']} minutes."

    if route["interchanges"] == 0:
        speech += " Direct connection, no changes."
    elif route["interchanges"] == 1:
        speech += " One change."

    # Get departures from origin for timing
    first_transit = next((l for l in route["legs"] if l["type"] == "transit"), None)
    if first_transit:
        deps = get_departures(origin, limit=3)
        matching = [d for d in deps if first_transit["line"].upper() in d["line"].upper()]
        if matching:
            mins = matching[0]["minutes"]
            speech += f" Next {first_transit['line']} in {mins} {'minute' if mins == 1 else 'minutes'}."
            # Check disruptions
            if matching[0].get("disruptions"):
                speech += f" Warning: {matching[0]['disruptions'][0]}."

    return speech
