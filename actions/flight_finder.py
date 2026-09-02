"""
actions/flight_finder.py — Akıllı Uçuş Arama ve Fiyat Karşılaştırma

Google Flights entegrasyonu ile uçuş arar, tarihleri doğal dilden çözümler
ve doğrudan arama URL'si oluşturup tarayıcıda açar.

Debug: Uçuş parametreleri ve oluşturulan URL'ler loglanır.
"""

from __future__ import annotations

import re
import urllib.parse
import webbrowser
from datetime import datetime, timedelta
from typing import Optional

_MONTH_MAP = {
    "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
    "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_date(raw: str) -> str:
    """Doğal dil tarih ifadesini YYYY-MM-DD formatına çevirir."""
    raw = (raw or "").strip().lower()
    today = datetime.now()

    if not raw:
        return (today + timedelta(days=7)).strftime("%Y-%m-%d")

    # Doğrudan YYYY-MM-DD kontrolü
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw

    # Göreceli tarihler
    if raw in ("bugün", "today"):
        return today.strftime("%Y-%m-%d")
    if raw in ("yarın", "tomorrow"):
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if "hafta sonra" in raw:
        return (today + timedelta(days=7)).strftime("%Y-%m-%d")

    # Ay isimleri eşleme (örn: "15 haziran", "20 mart")
    for mname, mnum in _MONTH_MAP.items():
        if mname in raw:
            day_match = re.search(r"\d{1,2}", raw)
            day = int(day_match.group()) if day_match else 1
            year = today.year if mnum >= today.month else today.year + 1
            return f"{year}-{mnum:02d}-{day:02d}"

    # Standart formatlar (dd.mm.yyyy, dd/mm/yyyy)
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    return (today + timedelta(days=7)).strftime("%Y-%m-%d")


def build_flight_url(
    origin: str,
    destination: str,
    date: str,
    return_date: str = "",
    passengers: int = 1,
    cabin: str = "economy",
) -> str:
    """Google Flights URL'si oluşturur."""
    parsed_date = _parse_date(date)
    parsed_return = _parse_date(return_date) if return_date else ""

    if parsed_return:
        query = f"Flights from {origin} to {destination} on {parsed_date} returning {parsed_return}"
    else:
        query = f"Flights from {origin} to {destination} on {parsed_date}"

    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://www.google.com/travel/flights?q={encoded_query}&curr=TRY"
    return url


def search_flights(
    origin: str,
    destination: str,
    date: str = "",
    return_date: str = "",
    passengers: int = 1,
    cabin: str = "economy",
    open_browser: bool = True,
) -> str:
    """
    Uçuş araması yapar ve bağlantıyı açar.

    Args:
        origin: Kalkış şehri/havalimanı (örn: IST, Istanbul)
        destination: Varış şehri/havalimanı (örn: LHR, Londra)
        date: Gidiş tarihi (örn: "yarın", "15 Temmuz", "2026-08-01")
        return_date: Dönüş tarihi (opsiyonel)
        passengers: Yolcu sayısı
        cabin: economy | business | first
        open_browser: Tarayıcıda açılsın mı?
    """
    if not origin or not destination:
        return "Lütfen kalkış ve varış noktalarını belirtin."

    url = build_flight_url(origin, destination, date, return_date, passengers, cabin)
    print(f"[FlightFinder] ✈️ Uçuş aranıyor: {origin} -> {destination} ({date})")

    if open_browser:
        try:
            webbrowser.open(url)
            print(f"[FlightFinder] 🌐 Tarayıcı açıldı: {url}")
        except Exception as e:
            print(f"[FlightFinder] ⚠️ Tarayıcı açılamadı: {e}")

    ret_info = f" (Dönüş: {_parse_date(return_date)})" if return_date else ""
    return (
        f"✈️ {origin.upper()} ➔ {destination.upper()} uçuşları bulundu!\n"
        f"📅 Tarih: {_parse_date(date)}{ret_info}\n"
        f"🔗 Google Flights: {url}"
    )
