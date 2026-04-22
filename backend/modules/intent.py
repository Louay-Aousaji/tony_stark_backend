import re
from config.settings import MORNING_TRIGGERS


NAVIGATION_PATTERNS = [
    r"(go(ing)? to|get to|route to|how do i get to|directions? to|take me to)\s+(.+)",
    r"(next|when is the next)\s+(u\d|s\d|tram|bus)\s*(from\s+(.+))?",
    r"(is|are) (the\s+)?(u.bahn|s.bahn|tram|bus|train).*(running|strike|delay|disruption)",
    r"(strike|disruption|delay).*(today|now|u.bahn|s.bahn|tram|bus)",
]

WEATHER_PATTERNS = [
    r"(when is it going to|when will it|will it) rain",
    r"(what.s the weather|how.s the weather|weather (today|now|forecast))",
    r"(rain|umbrella|jacket|coat|what (should|do) i wear)",
]


def classify_intent(text: str) -> dict:
    text = text.lower().strip()

    if any(trigger in text for trigger in MORNING_TRIGGERS):
        return {"intent": "morning_briefing"}

    for pattern in NAVIGATION_PATTERNS:
        match = re.search(pattern, text)
        if match:
            destination = _extract_destination(text)
            line = _extract_line(text)
            station = _extract_station(text)
            return {
                "intent": "navigation",
                "destination": destination,
                "line": line,
                "station": station,
                "raw": text,
            }

    for pattern in WEATHER_PATTERNS:
        if re.search(pattern, text):
            location = _extract_weather_location(text)
            return {"intent": "weather", "location": location}

    if "battery" in text:
        return {"intent": "battery"}

    if any(w in text for w in ["message", "whatsapp", "notification", "texts"]):
        return {"intent": "messages"}

    if any(w in text for w in ["forex", "market", "news", "usd", "dollar", "fed", "cpi"]):
        return {"intent": "forex"}

    return {"intent": "unknown", "raw": text}


def _extract_destination(text: str) -> str | None:
    patterns = [
        r"(?:go(?:ing)? to|get to|route to|take me to|directions? to|how do i get to)\s+(.+?)(?:\s+(?:in munich|from|via|using|with).*)?$",
        r"(?:to|towards)\s+([A-Z][a-z][\w\s]+?)(?:\s+(?:station|stop|in munich))?$",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip().title()
    return None


def _extract_line(text: str) -> str | None:
    m = re.search(r"\b(u\d|s\d|tram\s*\d+|bus\s*\d+)\b", text, re.IGNORECASE)
    return m.group(1).upper() if m else None


def _extract_station(text: str) -> str | None:
    m = re.search(r"from\s+([A-Za-z][\w\s]+?)(?:\s+(?:station|stop|to|towards|$))", text, re.IGNORECASE)
    return m.group(1).strip().title() if m else None


def _extract_weather_location(text: str) -> str:
    """Extract a Munich district or area from a weather query."""
    m = re.search(
        r"(?:in|at|for|around)\s+([A-Za-zäöüÄÖÜß][\w\säöüÄÖÜß]+?)(?:\s+(?:today|now|forecast|tomorrow|\?))?$",
        text, re.IGNORECASE
    )
    if m:
        loc = m.group(1).strip()
        # Filter out filler words
        if loc.lower() not in ("munich", "münchen", "the", "a", "an"):
            return loc
    return "Munich"
