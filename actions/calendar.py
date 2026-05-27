"""
Takvim — Windows sürümü.

Apple Calendar ve EventKit yalnızca macOS'ta çalışır.
Windows'ta Google Calendar, Outlook veya Windows Calendar açılır.
"""

from __future__ import annotations

import webbrowser


def _open_google_calendar():
    webbrowser.open("https://calendar.google.com")


def get_calendar_events(query: str = "today", limit: int = 6) -> str:
    _open_google_calendar()
    return (
        "Apple Calendar bu platformda desteklenmiyor. "
        "Google Calendar tarayıcıda açıldı. "
        "Outlook kullanıyorsan 'outlookcal:' adresini açmamı isteyebilirsin."
    )


def add_calendar_event(
    title: str,
    start_iso: str,
    end_iso: str = "",
    notes: str = "",
    location: str = "",
    calendar_name: str = "",
    all_day: bool = False,
) -> str:
    # Google Calendar quick add URL
    import urllib.parse
    params = {"text": title}
    if start_iso:
        date_part = start_iso.replace(":", "").replace("-", "").split("T")[0]
        time_part = start_iso.split("T")[1].replace(":", "")[:4] if "T" in start_iso else ""
        if time_part:
            params["dates"] = f"{date_part}T{time_part}00/{date_part}T{time_part}00"
        else:
            params["dates"] = f"{date_part}/{date_part}"
    if location:
        params["location"] = location
    if notes:
        params["details"] = notes
    url = "https://calendar.google.com/calendar/render?action=TEMPLATE&" + urllib.parse.urlencode(params)
    webbrowser.open(url)
    return (
        f"Apple Calendar bu platformda desteklenmiyor. "
        f"Google Calendar'da '{title}' etkinliği oluşturmak için tarayıcı açıldı."
    )


def delete_calendar_event(
    title: str,
    start_iso: str = "",
    calendar_name: str = "",
    delete_all_matches: bool = False,
) -> str:
    _open_google_calendar()
    return (
        "Apple Calendar bu platformda desteklenmiyor. "
        "Google Calendar tarayıcıda açıldı — etkinliği oradan silebilirsin."
    )
