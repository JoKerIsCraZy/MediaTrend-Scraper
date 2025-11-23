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

    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    try:
        text = await AsyncClient.get(url, headers=headers, timeout=20)
        if text:
            return text
        else:
            menu.log_warn(f"Tudum HTML-Abruf fehlgeschlagen für {country_code} ({media_type})")
    except Exception as e:
        menu.log_error(f"Tudum HTML-Abruffehler für {country_code} ({media_type}): {e}")
    return None

def parse_tudum_table(table_soup: BeautifulSoup) -> List[str]:
    """Parst eine einzelne Tudum-Tabelle (Film oder TV) und gibt Titellisten zurück."""
    titles = []
    if not table_soup:
        return []
        
    title_cells = table_soup.find_all("td", class_="title")

    for cell in title_cells:
        button = cell.find("button")
        if button:
            title = button.get_text(strip=True)
            if title:
                titles.append(title)
    return titles

async def scrape_netflix(country_code: str, media_type: MediaType) -> List[str]:
    """Scrapt die Top-Titel für ein Land und einen Medientyp."""
    type_str = "film" if media_type == MediaType.MOVIE else "tv"
    html = await fetch_tudum_html(country_code, type_str)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("div", {"data-uia": "top10-table"})
    if not table:
        menu.log_warn(f"[{country_code}] Konnte keine Tabelle für {media_type.value} finden.")
        return []
        
    return parse_tudum_table(table)