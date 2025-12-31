#!/usr/bin/env python3
import time
import asyncio
from bs4 import BeautifulSoup
from typing import List
from utils.types import MediaType

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
# from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

import utils.menu as menu

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"

def _get_flixpatrol_html_with_selenium(service_slug: str, country_code: str, media_type: str) -> str | None:
    """
    Fetches the Top 10 page, clicks on cookie banner AND clicks on the correct tab,
    IF it exists.
    """
    
    country_map = {
        'WORLD': 'world', 'DE': 'germany', 'CH': 'switzerland', 'AT': 'austria', 
        'US': 'united-states', 'GB': 'united-kingdom', 'FR': 'france', 'IT': 'italy', 
        'ES': 'spain', 'CA': 'canada', 'AU': 'australia', 'NL': 'netherlands', 
        'BE': 'belgium', 'PL': 'poland', 'SE': 'sweden', 'NO': 'norway', 'DK': 'denmark',
    }
    country_slug = country_map.get(country_code.upper())
    if not country_slug:
        menu.log_warn(f"[FlixPatrol] Country code {country_code} is not supported.")
        return None

    url = f"https://flixpatrol.com/top10/{service_slug}/{country_slug}/"
    menu.log(f"[FlixPatrol] Loading URL with Selenium: {url}")

    driver = None
    try:
        options = ChromeOptions()
        options.add_argument(f"user-agent={USER_AGENT}")
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920x1080")
        options.add_argument("--log-level=3") 
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage") 

        options.add_argument("--disable-dev-shm-usage") 
        
        # Use system installed chromedriver instead of downloading mismatching version
        service = ChromeService("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.get(url)
        
        # Short wait for dynamic loading (SPA)
        time.sleep(2)

        # --- 1. CHECK FOR 404 / PAGE NOT FOUND ---
        page_source_lower = driver.page_source.lower()
        title_lower = driver.title.lower()
        
        if "page not found" in title_lower or "page not found" in page_source_lower or "404" in title_lower:
             menu.log_warn(f"Page not found (404) for {url}. Skipping.")
             return None
        
        # --- 2. TRY TO CLICK ON THE CORRECT TAB ---
        tab_text = "Movies" if media_type == "movies" else "TV Shows"
        try:
            # We wait only 5 seconds, as the tab might not exist for services like Disney+
            menu.log(f"[FlixPatrol] Searching for '{tab_text}' tab (max 5s)...")
            # Robust XPATH selector
            xpath_selector = f"//a[span[text()='{tab_text}']]"
            tab_link = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, xpath_selector))
            )
            tab_link.click()
            menu.log(f"[FlixPatrol] Clicked tab '{tab_text}'.")
            time.sleep(3) # Short pause to let the new table render
            
        except Exception as e:
            # This is now an expected "error" for Disney+
            menu.log_warn(f"[FlixPatrol] Tab '{tab_text}' not found. Using default/overall view.")
            if "404 Not Found" in driver.title:
                 menu.log_warn(f"Service '{service_slug}' for country '{country_slug}' not found on FlixPatrol (404).")
                 return None

        # --- 3. WAIT FOR CONTENT ---
        menu.log("[FlixPatrol] Waiting for 'card -mx-content' to load (max 10s)...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.card.-mx-content"))
        )
        menu.log("[FlixPatrol] Content loaded.")
        
        html = driver.page_source
        return html

    except Exception as e:
        menu.log_error(f"FlixPatrol Selenium error for {url}: {e}")
        return None
    finally:
        if driver:
            driver.quit()

def _parse_flixpatrol_table(table_card_soup: BeautifulSoup) -> List[str]:
    """
    Parses the HTML table from FlixPatrol and extracts titles.
    (FIXED version that can parse all table types)
    """
    titles = []
    
    table = table_card_soup.find('table', class_='card-table')
    if not table:
        menu.log_warn("[FlixPatrol] Parser could not find 'table.card-table' in the card.")
        return []

    # Find all rows in table body
    rows = table.find_all('tr')
    
    for row in rows:
        # Find the title link (<a> tag). This is sometimes in the first
        # <td>, sometimes in the second (after the rank).
        title_link = row.find('a') 
        
        if title_link:
            title = title_link.get_text(strip=True)
            if title:
                # Prevents adding garbage (e.g., empty links)
                titles.append(title)

    return titles

async def scrape_flixpatrol(service_slug: str, country_code: str, media_type: MediaType) -> List[str]:
    """
    Main function for FlixPatrol scraping (Disney+, Amazon, HBO, etc.).
    """
    # Selenium is blocking, so we run it in a separate thread
    html = await asyncio.to_thread(_get_flixpatrol_html_with_selenium, service_slug, country_code, "movies" if media_type == MediaType.MOVIE else "tv")
    
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    
    # We look for "Movies", "TV Shows" or "TOP 10 Overall"
    # User Feedback: "It says either Movies or TOP 10 Overall on the website"
    
    target_header_primary = "Movies" if media_type == MediaType.MOVIE else "TV Shows"
    target_header_fallback = "TOP 10 Overall" 
    
    all_cards = soup.find_all("div", class_="card")
    found_card = None
    
    # 1. Search for primary target (Movies / TV Shows)
    for card in all_cards:
        header = card.find('h3')
        if header:
            header_text = header.get_text(strip=True)
            # Exact match or "TOP 10 Movies" in case they change it, but user says "Movies"
            if target_header_primary == header_text or f"TOP 10 {target_header_primary}" in header_text:
                menu.log(f"[FlixPatrol] Specific table '{header_text}' found.")
                found_card = card
                break
    
    # 2. Search for fallback (Overall), IF primary target failed
    if not found_card:
        menu.log_warn(f"[FlixPatrol] '{target_header_primary}' not found. Searching for fallback '{target_header_fallback}'.")
        for card in all_cards:
            header = card.find('h3')
            if header and target_header_fallback in header.get_text(strip=True):
                menu.log(f"[FlixPatrol] Fallback table '{target_header_fallback}' found.")
                found_card = card
                break

    if found_card:
        return _parse_flixpatrol_table(found_card)
    else:
        menu.log_warn(f"[FlixPatrol] Could not find neither '{target_header_primary}' nor '{target_header_fallback}'.")
        return []