#!/usr/bin/env python3
import asyncio
from typing import Dict, Any, Optional, List, Callable, Set, Awaitable

import sources.netflix as netflix
import sources.flixpatrol as flixpatrol
import targets.radarr as radarr
import targets.sonarr as sonarr
import utils.menu as menu
from utils.types import MediaType
from utils.network import AsyncClient

TMDB_API_BASE = "https://api.themoviedb.org/3"

# --- TMDb Suchfunktionen ---

async def tmdb_search(api_key: str, query: str, media_type: MediaType) -> Optional[Dict[str, Any]]:
    """Sucht bei TMDb nach einem Film oder einer Serie."""
    if not api_key:
        menu.log_error("TMDb API Key fehlt in den Einstellungen.")
        return None
        
    search_type = "movie" if media_type == MediaType.MOVIE else "tv"
    params = {"api_key": api_key, "query": query}
    try:
        data = await AsyncClient.get(f"{TMDB_API_BASE}/search/{search_type}", params=params, timeout=10)
        if data:
            results = data.get("results", [])
            if results:
                return results[0] # Nimm das erste, beste Ergebnis
    except Exception as e:
        menu.log_error(f"TMDb-Suche für '{query}' fehlgeschlagen: {e}")
    return None

async def tmdb_get_tvdb_id(api_key: str, tmdb_id: int) -> Optional[int]:
    """Holt die TVDb-ID für eine TMDb-Serien-ID."""
    if not api_key:
        menu.log_error("TMDb API Key fehlt in den Einstellungen.")
        return None
    
    params = {"api_key": api_key}
    try:
        data = await AsyncClient.get(f"{TMDB_API_BASE}/tv/{tmdb_id}/external_ids", params=params, timeout=10)
        if data and data.get("tvdb_id"):
            return int(data["tvdb_id"])
    except Exception as e:
        menu.log_error(f"TMDb External ID-Suche für '{tmdb_id}' fehlgeschlagen: {e}")
    return None

# --- Generische Worker-Logik ---

async def process_media_list(
    config: Dict[str, Any],
    source_name: str,
    media_type: MediaType,
    fetch_titles_func: Callable[[str], Awaitable[List[str]]]
) -> None:
    """
    Generische Funktion zum Verarbeiten von Listen.
    
    Args:
        config: Die Konfiguration.
        source_name: Name der Quelle (für Logs).
        media_type: MediaType.MOVIE oder MediaType.SERIES.
        fetch_titles_func: Async Funktion, die einen Ländercode annimmt und eine Liste von Titeln zurückgibt.
    """
    target_name = "Radarr" if media_type == MediaType.MOVIE else "Sonarr"
    menu.log(f"Starte {source_name} ({media_type.value}) -> {target_name}...")

    # 1. Überprüfungen
    tmdb_key = config["general"]["tmdb_api_key"]
    if not tmdb_key:
        menu.log_error("TMDb API Key fehlt. Bitte in den Einstellungen festlegen.")
        return

    target_cfg = config["radarr"] if media_type == MediaType.MOVIE else config["sonarr"]
    if not target_cfg["api_key"]:
        menu.log_error(f"{target_name} API Key fehlt. Bitte in den Einstellungen festlegen.")
        return

    # 2. Vorhandene Medien abrufen
    menu.log(f"Rufe vorhandene Einträge von {target_name} ab...")
    existing_ids = {}
    if media_type == MediaType.MOVIE:
        existing_ids = await radarr.radarr_lookup_existing(target_cfg["url"], target_cfg["api_key"])
    else:
        existing_ids = await sonarr.sonarr_lookup_existing(target_cfg["url"], target_cfg["api_key"])
    
    menu.log(f"{len(existing_ids)} Einträge bereits in {target_name} vorhanden.")

    # 3. Länder durchlaufen und scrapen
    countries = config["general"]["countries"]
    all_titles = set()

    for country in countries:
        menu.log(f"Scrape {source_name} für: {country}")
        titles = await fetch_titles_func(country)
        all_titles.update(titles)
    
    menu.log(f"Insgesamt {len(all_titles)} einzigartige Titel gefunden.")

    # 4. Verarbeiten und Senden
    added_count = 0
    for title in all_titles:
        # 4a. TMDb Suche
        tmdb_match = await tmdb_search(tmdb_key, title, media_type)
        if not tmdb_match or not tmdb_match.get("id"):
            menu.log_warn(f"Keine TMDb-Übereinstimmung für '{title}' gefunden.")
            continue
        
        tmdb_id = tmdb_match["id"]

        # 4b. Prüfen ob vorhanden & Senden
        if media_type == MediaType.MOVIE:
            if tmdb_id in existing_ids:
                menu.log(f"'{title}' (TMDb: {tmdb_id}) ist bereits in Radarr. Überspringe.")
                continue
            
            # Extrahiere Jahr
            year_str = tmdb_match.get("release_date", "0000")[:4]
            year = int(year_str) if year_str.isdigit() else 0

            if await radarr.radarr_add_movie(config, tmdb_id, title, year):
                added_count += 1
                existing_ids[tmdb_id] = True
        
        else: # SERIES
            # Für Serien brauchen wir die TVDb ID
            tvdb_id = await tmdb_get_tvdb_id(tmdb_key, tmdb_id)
            if not tvdb_id:
                menu.log_warn(f"Keine TVDb-ID für '{title}' (TMDb: {tmdb_id}) gefunden.")
                continue
            
            if tvdb_id in existing_ids:
                menu.log(f"'{title}' (TVDb: {tvdb_id}) ist bereits in Sonarr. Überspringe.")
                continue

            if await sonarr.sonarr_add_series(config, tvdb_id):
                added_count += 1
                existing_ids[tvdb_id] = True

    menu.log(f"{source_name} -> {target_name} Task abgeschlossen. {added_count} neue Einträge hinzugefügt.")


# --- Wrapper für das Menü ---

def show_run_menu(config: Dict[str, Any]) -> None:
    """Zeigt das Menü zum Ausführen der Jobs an."""
    while True:
        print("\n--- Top-Listen jetzt ausführen ---")
        print("--- Netflix (Tudum) ---")
        print("1) Netflix (Filme) -> Radarr")
        print("2) Netflix (Serien) -> Sonarr")
        print("--- FlixPatrol (Amazon) ---")
        print("3) Amazon Prime (Filme) -> Radarr")
        print("4) Amazon Prime (Serien) -> Sonarr")
        print("--- FlixPatrol (Disney+) ---")
        print("5) Disney+ (Filme) -> Radarr")
        print("6) Disney+ (Serien) -> Sonarr")
        print("--- FlixPatrol (HBO) ---")
        print("7) HBO Max (Filme) -> Radarr")
        print("8) HBO Max (Serien) -> Sonarr")
        print("---")
        print("9) Zurück zum Hauptmenü")
        
        choice = input("Wählen Sie einen Job: ").strip()

        async def run_job(job_func):
            try:
                await job_func
            finally:
                await AsyncClient.close()

        if choice == "1":
            asyncio.run(run_job(process_media_list(config, "Netflix", MediaType.MOVIE, 
                               lambda c: netflix.scrape_netflix(c, MediaType.MOVIE))))
        elif choice == "2":
            asyncio.run(run_job(process_media_list(config, "Netflix", MediaType.SERIES, 
                               lambda c: netflix.scrape_netflix(c, MediaType.SERIES))))
        elif choice == "3":
            asyncio.run(run_job(process_media_list(config, "Amazon Prime", MediaType.MOVIE, 
                               lambda c: flixpatrol.scrape_flixpatrol("amazon-prime", c, MediaType.MOVIE))))
        elif choice == "4":
            asyncio.run(run_job(process_media_list(config, "Amazon Prime", MediaType.SERIES, 
                               lambda c: flixpatrol.scrape_flixpatrol("amazon-prime", c, MediaType.SERIES))))
        elif choice == "5":
            asyncio.run(run_job(process_media_list(config, "Disney+", MediaType.MOVIE, 
                               lambda c: flixpatrol.scrape_flixpatrol("disney", c, MediaType.MOVIE))))
        elif choice == "6":
            asyncio.run(run_job(process_media_list(config, "Disney+", MediaType.SERIES, 
                               lambda c: flixpatrol.scrape_flixpatrol("disney", c, MediaType.SERIES))))
        elif choice == "7":
            asyncio.run(run_job(process_media_list(config, "HBO Max", MediaType.MOVIE, 
                               lambda c: flixpatrol.scrape_flixpatrol("hbo-max", c, MediaType.MOVIE))))
        elif choice == "8":
            asyncio.run(run_job(process_media_list(config, "HBO Max", MediaType.SERIES, 
                               lambda c: flixpatrol.scrape_flixpatrol("hbo-max", c, MediaType.SERIES))))
        elif choice == "9":
            break
        else:
            menu.log_warn("Ungültige Auswahl.")