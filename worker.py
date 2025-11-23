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

# --- TMDb Search Functions ---

async def tmdb_search(api_key: str, query: str, media_type: MediaType) -> Optional[Dict[str, Any]]:
    """Searches TMDb for a movie or series."""
    if not api_key:
        menu.log_error("TMDb API Key missing in settings.")
        return None
        
    search_type = "movie" if media_type == MediaType.MOVIE else "tv"
    params = {"api_key": api_key, "query": query}
    try:
        data = await AsyncClient.get(f"{TMDB_API_BASE}/search/{search_type}", params=params, timeout=10)
        if data:
            results = data.get("results", [])
            if results:
                return results[0] # Take the first, best result
    except Exception as e:
        menu.log_error(f"TMDb search for '{query}' failed: {e}")
    return None

async def tmdb_get_tvdb_id(api_key: str, tmdb_id: int) -> Optional[int]:
    """Fetches the TVDb ID for a TMDb series ID."""
    if not api_key:
        menu.log_error("TMDb API Key missing in settings.")
        return None
    
    params = {"api_key": api_key}
    try:
        data = await AsyncClient.get(f"{TMDB_API_BASE}/tv/{tmdb_id}/external_ids", params=params, timeout=10)
        if data and data.get("tvdb_id"):
            return int(data["tvdb_id"])
    except Exception as e:
        menu.log_error(f"TMDb External ID search for '{tmdb_id}' failed: {e}")
    return None

# --- Generic Worker Logic ---

async def process_media_list(
    config: Dict[str, Any],
    source_name: str,
    media_type: MediaType,
    fetch_titles_func: Callable[[str], Awaitable[List[str]]]
) -> None:
    """
    Generic function for processing lists.
    
    Args:
        config: The configuration.
        source_name: Name of the source (for logs).
        media_type: MediaType.MOVIE or MediaType.SERIES.
        fetch_titles_func: Async function that takes a country code and returns a list of titles.
    """
    target_name = "Radarr" if media_type == MediaType.MOVIE else "Sonarr"
    menu.log(f"Starting {source_name} ({media_type.value}) -> {target_name}...")

    # 1. Checks
    tmdb_key = config["general"]["tmdb_api_key"]
    if not tmdb_key:
        menu.log_error("TMDb API Key missing. Please set in settings.")
        return

    target_cfg = config["radarr"] if media_type == MediaType.MOVIE else config["sonarr"]
    if not target_cfg["api_key"]:
        menu.log_error(f"{target_name} API Key missing. Please set in settings.")
        return

    # 2. Fetch existing media
    menu.log(f"Fetching existing entries from {target_name}...")
    existing_ids = {}
    if media_type == MediaType.MOVIE:
        existing_ids = await radarr.radarr_lookup_existing(target_cfg["url"], target_cfg["api_key"])
    else:
        existing_ids = await sonarr.sonarr_lookup_existing(target_cfg["url"], target_cfg["api_key"])
    
    menu.log(f"{len(existing_ids)} entries already exist in {target_name}.")

    # 3. Iterate countries and scrape
    countries = config["general"]["countries"]
    all_titles = set()

    for country in countries:
        menu.log(f"Scrape {source_name} for: {country}")
        titles = await fetch_titles_func(country)
        all_titles.update(titles)
    
    menu.log(f"Found {len(all_titles)} unique titles in total.")

    # 4. Process and Send
    added_count = 0
    for title in all_titles:
        # 4a. TMDb Search
        tmdb_match = await tmdb_search(tmdb_key, title, media_type)
        if not tmdb_match or not tmdb_match.get("id"):
            menu.log_warn(f"No TMDb match found for '{title}'.")
            continue
        
        tmdb_id = tmdb_match["id"]

        # 4b. Check if exists & Send
        if media_type == MediaType.MOVIE:
            if tmdb_id in existing_ids:
                menu.log(f"'{title}' (TMDb: {tmdb_id}) is already in Radarr. Skipping.")
                continue
            
            # Extract Year
            year_str = tmdb_match.get("release_date", "0000")[:4]
            year = int(year_str) if year_str.isdigit() else 0

            if await radarr.radarr_add_movie(config, tmdb_id, title, year):
                added_count += 1
                existing_ids[tmdb_id] = True
        
        else: # SERIES
            # For series we need the TVDb ID
            tvdb_id = await tmdb_get_tvdb_id(tmdb_key, tmdb_id)
            if not tvdb_id:
                menu.log_warn(f"No TVDb ID found for '{title}' (TMDb: {tmdb_id}).")

def show_run_menu(config: Dict[str, Any]) -> None:
    """Shows the menu to execute jobs."""
    while True:
        print("\n--- Run Top Lists Now ---")
        print("--- Netflix (Tudum) ---")
        print("1) Netflix (Movies) -> Radarr")
        print("2) Netflix (Series) -> Sonarr")
        print("--- FlixPatrol (Amazon) ---")
        print("3) Amazon Prime (Movies) -> Radarr")
        print("4) Amazon Prime (Series) -> Sonarr")
        print("--- FlixPatrol (Disney+) ---")
        print("5) Disney+ (Movies) -> Radarr")
        print("6) Disney+ (Series) -> Sonarr")
        print("--- FlixPatrol (HBO) ---")
        print("7) HBO Max (Movies) -> Radarr")
        print("8) HBO Max (Series) -> Sonarr")
        print("---")
        print("9) Back to Main Menu")
        
        choice = input("Select a job: ").strip()

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
            menu.log_warn("Invalid selection.")