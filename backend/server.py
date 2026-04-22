from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from concurrent.futures import ThreadPoolExecutor, as_completed

from modules.weather import get_weather_briefing, get_rain_detail
from modules.transit import format_route_speech, format_departures_speech, get_disruptions
from modules.forex import get_forex_briefing
from modules.stations import resolve_station, list_all_station_names
from modules.briefing import build_phase1, build_transit_segment
from config.settings import HOME_STATION

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/briefing/phase1")
def briefing_phase1():
    return {"text": build_phase1()}


@app.get("/briefing/transit")
def briefing_transit(destination: str = Query(...)):
    station = resolve_station(destination)
    if not station:
        return {"text": f"I couldn't find a station called {destination} in Munich.", "station": None}
    text = build_transit_segment(station["name"])
    return {"text": text, "station": station["name"]}


@app.get("/weather")
def weather(location: str = Query(default="Munich")):
    return {"text": get_weather_briefing(location)}


@app.get("/rain")
def rain(location: str = Query(default="Munich")):
    return {"text": get_rain_detail(location)}


@app.get("/transit/route")
def transit_route(destination: str = Query(...)):
    station = resolve_station(destination)
    dest_name = station["name"] if station else destination
    return {"text": format_route_speech(HOME_STATION, dest_name)}


@app.get("/transit/departures")
def transit_departures(station: str = Query(...), line: str = Query(default=None)):
    return {"text": format_departures_speech(station, line_filter=line)}


@app.get("/transit/disruptions")
def transit_disruptions():
    d = get_disruptions()
    if d:
        return {"text": "Disruptions: " + ". ".join(d[:2]) + "."}
    return {"text": "No active disruptions on the MVG network."}


@app.get("/forex")
def forex():
    return {"text": get_forex_briefing()}


@app.get("/stations")
def stations():
    return {"stations": list_all_station_names()}
