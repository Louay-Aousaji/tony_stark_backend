"""
Munich U-Bahn station registry with fuzzy name matching.
Used to resolve spoken station names from voice recognition output.
"""

import unicodedata
import re
from modules.transit import _get_all_stations

MUNICH_PLACES = {"münchen", "garching (b münchen)", "munich"}

_UBAHN_STATIONS: list[dict] = []


def _normalize(text: str) -> str:
    """Lowercase, strip accents/umlauts to ASCII, remove punctuation."""
    text = text.lower().strip()
    # Replace German umlauts explicitly before stripping accents
    replacements = {
        "ä": "a", "ö": "o", "ü": "u", "ß": "ss",
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
    }
    for char, rep in replacements.items():
        text = text.replace(char, rep)
    # Strip remaining diacritics
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Normalize hyphens to spaces so "olympia-einkaufszentrum" == "olympia einkaufszentrum"
    text = text.replace("-", " ")
    # Remove remaining punctuation
    text = re.sub(r"[^\w\s]", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _build_aliases(name: str) -> list[str]:
    """Generate common spoken variants of a station name."""
    n = _normalize(name)
    aliases = [n]

    # "straße" / "strasse" / "str"
    aliases.append(n.replace("strasse", "str"))
    aliases.append(n.replace("strasse", "straße"))
    aliases.append(n.replace("str ", " "))

    # "platz" -> "platz" stays, but handle spoken forms
    # "bahnhof" variants
    aliases.append(n.replace("hauptbahnhof", "hbf"))
    aliases.append(n.replace("hbf", "hauptbahnhof"))

    # "forschungszentrum" -> "forschungszentrum" / "research center"
    if "forschungszentrum" in n:
        aliases.append(n.replace("forschungszentrum", "research center"))
        aliases.append(n.replace("forschungszentrum", "research centre"))
        aliases.append(n.replace("garching-forschungszentrum", "garching forschungszentrum"))

    # Remove city prefix "münchen," or "munich,"
    for prefix in ["munchen, ", "munich, ", "münchen, "]:
        if n.startswith(prefix):
            aliases.append(n[len(prefix):])

    return list(dict.fromkeys(a for a in aliases if a))  # deduplicate


def get_ubahn_stations() -> list[dict]:
    global _UBAHN_STATIONS
    if _UBAHN_STATIONS:
        return _UBAHN_STATIONS
    all_stations = _get_all_stations()
    _UBAHN_STATIONS = [
        s for s in all_stations
        if "UBAHN" in s.get("products", [])
        and s.get("place", "").lower() in MUNICH_PLACES
    ]
    return _UBAHN_STATIONS


def resolve_station(spoken: str) -> dict | None:
    """
    Match a spoken/typed station name to a real Munich U-Bahn station.
    Returns the station dict (with divaId, name, etc.) or None.
    """
    stations = get_ubahn_stations()
    spoken_norm = _normalize(spoken)

    # Score each station
    best_station = None
    best_score = -1

    for s in stations:
        s_norm = _normalize(s["name"])
        s_aliases = _build_aliases(s["name"])

        score = 0

        # Exact normalized match
        if spoken_norm == s_norm:
            score = 100
        # Alias exact match
        elif spoken_norm in s_aliases:
            score = 90
        # Spoken is fully contained in station name (e.g. "garching" matches "Garching-Forschungszentrum")
        elif spoken_norm in s_norm:
            score = 70 - len(s_norm)  # shorter match is better
        # Station name contained in spoken (handles extra words)
        elif s_norm in spoken_norm:
            score = 60
        # Any alias is contained in spoken
        else:
            for alias in s_aliases:
                if alias and alias in spoken_norm:
                    score = 50
                    break
            # Word-level overlap
            if score == 0:
                spoken_words = set(spoken_norm.split())
                station_words = set(s_norm.split())
                overlap = spoken_words & station_words
                if overlap:
                    score = len(overlap) * 10

            # Fuzzy: check if spoken words are substrings of station words (handles "teresian" ≈ "theresien")
            if score == 0:
                for sw in spoken_norm.split():
                    for tw in s_norm.split():
                        if len(sw) >= 5 and len(tw) >= 5:
                            # count matching chars at start
                            common = sum(a == b for a, b in zip(sw, tw))
                            ratio = common / max(len(sw), len(tw))
                            if ratio >= 0.75:
                                score = max(score, int(ratio * 40))

        if score > best_score:
            best_score = score
            best_station = s

    # Minimum confidence threshold
    return best_station if best_score >= 10 else None


def list_all_station_names() -> list[str]:
    return sorted(s["name"] for s in get_ubahn_stations())
