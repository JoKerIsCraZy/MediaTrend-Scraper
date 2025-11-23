#!/usr/bin/env python3
import time
import asyncio
from bs4 import BeautifulSoup
from typing import List
from utils.types import MediaType

# Selenium-Importe
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

import utils.menu as menu

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"

def _get_flixpatrol_html_with_selenium(service_slug: str, country_code: str, media_type: str) -> str | None:
    """
    Holt die Top-10-Seite, klickt auf Cookie-Banner UND klickt auf die richtige Registerkarte,
    WENN sie existiert.
    """
    
    country_map = {
        'WORLD': 'world', 'DE': 'germany', 'CH': 'switzerland', 'AT': 'austria', 
        'US': 'united-states', 'GB': 'united-kingdom', 'FR': 'france', 'IT': 'italy', 
        'ES': 'spain', 'CA': 'canada', 'AU': 'australia', 'NL': 'netherlands', 
        'BE': 'belgium', 'PL': 'poland', 'SE': 'sweden', 'NO': 'norway', 'DK': 'denmark',
    }
    country_slug = country_map.get(country_code.upper())
    if not country_slug:
        menu.log_warn(f"[FlixPatrol] Ländercode {country_code} wird nicht unterstützt.")
        return None

    url = f"https://flixpatrol.com/top10/{service_slug}/{country_slug}/"
    menu.log(f"[FlixPatrol] Lade URL mit Selenium: {url}")

    driver = None
    try:
        options = ChromeOptions()
        options.add_argument(f"user-agent={USER_AGENT}")
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920x1080")
        options.add_argument("--log-level=3") 

        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.get(url)
        
        # Kurze Wartezeit für dynamisches Laden (SPA)
        time.sleep(2)

        # --- 1. PRÜFUNG AUF 404 / PAGE NOT FOUND ---
        page_source_lower = driver.page_source.lower()
        title_lower = driver.title.lower()
        
        if "page not found" in title_lower or "page not found" in page_source_lower or "404" in title_lower:
             menu.log_warn(f"Seite nicht gefunden (404) für {url}. Überspringe.")
             return None
        
        # --- 2. VERSUCHEN, AUF DIE KORREKTE REGISTERKARTE ZU KLICKEN ---
        tab_text = "Movies" if media_type == "movies" else "TV Shows"
        try:
            # Wir warten nur 5 Sekunden, da die Registerkarte bei Diensten wie Disney+ nicht existiert
            menu.log(f"[FlixPatrol] Suche nach '{tab_text}' Registerkarte (max 5s)...")
            # Robuster XPATH-Selektor
            xpath_selector = f"//a[span[text()='{tab_text}']]"
            tab_link = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, xpath_selector))
            )
            tab_link.click()
            menu.log(f"[FlixPatrol] Registerkarte '{tab_text}' geklickt.")
            time.sleep(3) # Kurze Pause, damit die neue Tabelle rendern kann
            
        except Exception as e:
            # Das ist jetzt ein erwarteter "Fehler" für Disney+
            menu.log_warn(f"[FlixPatrol] Registerkarte '{tab_text}' nicht gefunden. Verwende Standard/Overall-Ansicht.")
            if "404 Not Found" in driver.title:
                 menu.log_warn(f"Dienst '{service_slug}' für Land '{country_slug}' nicht auf FlixPatrol gefunden (404).")
                 return None

        # --- 3. AUF DEN INHALT WARTEN ---
        menu.log("[FlixPatrol] Warte auf das Laden der 'card -mx-content' (max 10s)...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.card.-mx-content"))
        )
        menu.log("[FlixPatrol] Inhalt ist geladen.")
        
        html = driver.page_source
        return html

    except Exception as e:
        menu.log_error(f"FlixPatrol Selenium-Fehler für {url}: {e}")
        return None
    finally:
        if driver:
            driver.quit()

def _parse_flixpatrol_table(table_card_soup: BeautifulSoup) -> List[str]:
    """
    Parst die HTML-Tabelle von FlixPatrol und extrahiert Titel.
    (REParierte Version, die alle Tabellentypen parsen kann)
    """
    titles = []
    
    table = table_card_soup.find('table', class_='card-table')
    if not table:
        menu.log_warn("[FlixPatrol] Parser konnte 'table.card-table' in der Karte nicht finden.")
        return []

    # Finde alle Zeilen im Tabellenkörper
    rows = table.find_all('tr')
    
    for row in rows:
        # Finde den Titel-Link (<a>-Tag). Dieser ist manchmal in der ersten
        # <td>, manchmal in der zweiten (nach der Rangliste).
        title_link = row.find('a') 
        
        if title_link:
            title = title_link.get_text(strip=True)
            if title:
                # Verhindert, dass Müll (z.B. leere Links) hinzugefügt wird
                titles.append(title)

    return titles

async def scrape_flixpatrol(service_slug: str, country_code: str, media_type: MediaType) -> List[str]:
    """
    Hauptfunktion für FlixPatrol-Scraping (Disney+, Amazon, HBO, etc.).
    """
    # Selenium is blocking, so we run it in a separate thread
    html = await asyncio.to_thread(_get_flixpatrol_html_with_selenium, service_slug, country_code, "movies" if media_type == MediaType.MOVIE else "tv")
    
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    
    # Wir suchen nach "Movies", "TV Shows" oder "TOP 10 Overall"
    # User-Feedback: "Es heisst entweder Movies oder TOP 10 Overall auf der website"
    
    target_header_primary = "Movies" if media_type == MediaType.MOVIE else "TV Shows"
    target_header_fallback = "TOP 10 Overall" 
    
    all_cards = soup.find_all("div", class_="card")
    found_card = None
    
    # 1. Suche nach dem primären Ziel (Movies / TV Shows)
    for card in all_cards:
        header = card.find('h3')
        if header:
            header_text = header.get_text(strip=True)
            # Exakter Match oder "TOP 10 Movies" falls sie es doch mal ändern, aber User sagt "Movies"
            if target_header_primary == header_text or f"TOP 10 {target_header_primary}" in header_text:
                menu.log(f"[FlixPatrol] Spezifische Tabelle '{header_text}' gefunden.")
                found_card = card
                break
    
    # 2. Suche nach dem Fallback (Overall), WENN das primäre Ziel fehlgeschlagen ist
    if not found_card:
        menu.log_warn(f"[FlixPatrol] '{target_header_primary}' nicht gefunden. Suche nach Fallback '{target_header_fallback}'.")
        for card in all_cards:
            header = card.find('h3')
            if header and target_header_fallback in header.get_text(strip=True):
                menu.log(f"[FlixPatrol] Fallback-Tabelle '{target_header_fallback}' gefunden.")
                found_card = card
                break

    if found_card:
        return _parse_flixpatrol_table(found_card)
    else:
        menu.log_warn(f"[FlixPatrol] Konnte weder '{target_header_primary}' noch '{target_header_fallback}' finden.")
        return []