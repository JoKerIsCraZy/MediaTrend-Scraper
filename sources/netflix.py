#!/usr/bin/env python3

from bs4 import BeautifulSoup
from typing import List
import utils.menu as menu
from utils.types import MediaType
from utils.network import AsyncClient

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"

def country_name_from_code(code: str) -> str:
    """Wandelt einen ISO-Code in den Netflix-URL-Slug um."""
    mapping = {
        "CH": "switzerland", "DE": "germany", "AT": "austria", "FR": "france",
        "IT": "italy", "ES": "spain", "US": "united-states", "GB": "united-kingdom",
        "UK": "united-kingdom", "CA": "canada", "NL": "netherlands", "BE": "belgium",
        "DK": "denmark", "SE": "sweden", "NO": "norway", "FI": "finland",
        "PL": "poland", "PT": "portugal", "IE": "ireland", "AU": "australia",
        "NZ": "new-zealand",
    }
    return mapping.get(code.upper(), code.lower())

async def fetch_tudum_html(country_code: str, media_type: str = "film") -> str | None:
    """Holt die Top-10-HTML-Seite für ein bestimmtes Land und Medientyp."""
    
    # --- NEUE URL-LOGIK ---
    slug = country_name_from_code(country_code)
    url = f"https://www.netflix.com/tudum/top10/{slug}"
    if media_type == "tv":
        url += "/tv"
    # --- ENDE NEUE URL-LOGIK ---

    headers = {
        "User-Agent": USER_AGENT, 
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate"
    }
    try:
        text = await AsyncClient.get(url, headers=headers, timeout=20)
        if text:
            return text
        else:
            menu.log_warn(f"Tudum HTML-Abruf fehlgeschlagen für {country_code} ({media_type})")
    except Exception as e:
        menu.log_error(f"Tudum HTML-Abruffehler für {country_code} ({media_type}): {e}")
    return None

def parse_tudum_list(soup: BeautifulSoup) -> List[str]:
    """Parst die Tudum-Liste und gibt Titellisten zurück."""
    titles = []
    if not soup:
        return []
        
    # Heuristik: Wir suchen nach der ul, die die meisten Bilder mit alt-Text enthält.
    # Das ist robuster als sich auf kryptische CSS-Klassen zu verlassen.
    uls = soup.find_all("ul")
    best_ul = None
    max_titles = 0
    
    for ul in uls:
        current_titles = []
        lis = ul.find_all("li")
        for li in lis:
            # Wir suchen nach einem Bild im li, das einen alt-Text hat
            img = li.find("img")
            if img and img.get("alt"):
                title = img.get("alt").strip()
                if title:
                    current_titles.append(title)
        
        # Wir nehmen die Liste mit den meisten Treffern (wahrscheinlich die Top 10)
        if len(current_titles) > max_titles:
            max_titles = len(current_titles)
            best_ul = ul
            titles = current_titles
            
    return titles

async def scrape_netflix(country_code: str, media_type: MediaType) -> List[str]:
    """Scrapt die Top-Titel für ein Land und einen Medientyp."""
    type_str = "film" if media_type == MediaType.MOVIE else "tv"
    html = await fetch_tudum_html(country_code, type_str)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    
    # Die alte Tabelle gibt es nicht mehr. Wir parsen jetzt die Liste.
    return parse_tudum_list(soup)