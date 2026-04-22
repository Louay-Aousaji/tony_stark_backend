import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from config.settings import FOREX_KEYWORDS


FOREX_FACTORY_URL = "https://www.forexfactory.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; Termux) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    )
}


def _fetch_page(url: str) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception:
        return None


def get_usd_red_folders() -> list[str]:
    soup = _fetch_page(f"{FOREX_FACTORY_URL}/calendar")
    if not soup:
        return []

    events = []
    today = datetime.now().strftime("%a %b %d").replace(" 0", " ")  # e.g. "Sun Apr 20"

    rows = soup.select("tr.calendar__row")
    current_date = ""
    for row in rows:
        date_cell = row.select_one(".calendar__date")
        if date_cell and date_cell.get_text(strip=True):
            current_date = date_cell.get_text(strip=True)

        if today.lower() not in current_date.lower() and current_date.lower() not in today.lower():
            continue

        currency = row.select_one(".calendar__currency")
        impact = row.select_one(".calendar__impact span")
        title = row.select_one(".calendar__event-title")

        if not (currency and impact and title):
            continue

        if currency.get_text(strip=True).upper() != "USD":
            continue

        impact_class = impact.get("class", [])
        if any("high" in c.lower() or "red" in c.lower() for c in impact_class):
            events.append(title.get_text(strip=True))

    return events


def get_recent_headlines(hours: int = 10) -> list[str]:
    soup = _fetch_page(f"{FOREX_FACTORY_URL}/news")
    if not soup:
        return []

    matched = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    articles = soup.select("div.flexposts__story, div.news__item, article")
    for article in articles:
        headline_el = article.select_one("h3, h2, .title, a[href*='/news/']")
        if not headline_el:
            continue
        headline = headline_el.get_text(strip=True).lower()
        if any(kw.lower() in headline for kw in FOREX_KEYWORDS):
            matched.append(headline_el.get_text(strip=True))

    return matched[:5]  # cap at 5 headlines


def get_forex_briefing() -> str:
    red_folders = get_usd_red_folders()
    headlines = get_recent_headlines()

    if red_folders:
        folders_text = "Today's USD red folders: " + ", ".join(red_folders) + "."
    else:
        folders_text = "No USD high-impact events today."

    if headlines:
        headlines_text = "Key news in the last 10 hours: " + ". ".join(headlines[:3]) + "."
    else:
        headlines_text = "No major market-moving headlines found."

    return f"{folders_text} {headlines_text}"
