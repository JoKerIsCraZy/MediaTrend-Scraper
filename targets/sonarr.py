#!/usr/bin/env python3
import json
from typing import List, Dict, Any, Optional
import utils.menu as menu
from utils.network import AsyncClient

async def _get_api(base_url: str, api_key: str, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Private helper function for GET requests to Sonarr."""
    try:
        return await AsyncClient.get(
            f"{base_url}/api/v3/{endpoint}",
            params=params,
            headers={"X-Api-Key": api_key},
            timeout=10
        )
    except Exception as e:
        menu.log_error(f"Sonarr API GET Error ({endpoint}): {e}")
    return None

async def _post_api(base_url: str, api_key: str, endpoint: str, data: Dict[str, Any]) -> Any:
    """Private helper function for POST requests to Sonarr."""
    try:
        return await AsyncClient.post(
            f"{base_url}/api/v3/{endpoint}",
            json_data=data,
            headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
            timeout=20
        )
    except Exception as e:
        menu.log_error(f"Sonarr API POST Error ({endpoint}): {e}")
    return None

async def sonarr_get_quality_profiles(sonarr_url: str, sonarr_token: str) -> List[Dict[str, Any]]:
    """Fetches all quality profiles from Sonarr."""
    data = await _get_api(sonarr_url, sonarr_token, "qualityprofile")
    return sorted(data, key=lambda p: p.get("id", 0)) if data else []

async def sonarr_get_root_folders(sonarr_url: str, sonarr_token: str) -> List[str]:
    """Fetches all root folders from Sonarr."""
    data = await _get_api(sonarr_url, sonarr_token, "rootfolder")
    return [f.get("path") for f in data if f.get("path")] if data else []

async def sonarr_lookup_series(config: Dict[str, Any], tvdb_id: int) -> Optional[Dict[str, Any]]:
    """
    Searches for a new series by its TVDb ID.
    Returns the first result required for the POST endpoint.
    """
    sonarr_cfg = config["sonarr"]
    menu.log(f"Searching Sonarr for TVDb ID: {tvdb_id}...")
    
    # Sonarr requires the term 'tvdb:ID_HERE'
    params = {"term": f"tvdb:{tvdb_id}"}
    results = await _get_api(sonarr_cfg["url"], sonarr_cfg["api_key"], "series/lookup", params)
    
    if results:
        # Returns the first search result
        return results[0]
    else:
        menu.log_warn(f"Sonarr search for TVDb ID {tvdb_id} returned no results.")
        return None

async def sonarr_add_series(config: Dict[str, Any], series_data: Dict[str, Any]) -> bool:
    """
    Adds a series to Sonarr using the data from sonarr_lookup_series.
    """
    sonarr_cfg = config["sonarr"]
    tvdb_id = series_data.get("tvdbId", 0)
    title = series_data.get('title', f"TVDb: {tvdb_id}")
    
    menu.log(f"Sending '{title}' to Sonarr...")

    # 2. Prepare Payload
    payload = series_data
    payload["qualityProfileId"] = sonarr_cfg["quality_profile_id"]
    payload["rootFolderPath"] = sonarr_cfg["root_folder_path"]
    payload["monitored"] = True
    payload["addOptions"] = {
        "searchForMissingEpisodes": sonarr_cfg["search_on_add"],
        "monitor": "all" # Monitor all seasons by default
    }
    
    response = await _post_api(sonarr_cfg["url"], sonarr_cfg["api_key"], "series", payload)
    
    if response and response.get("id"):
        menu.log(f"Successfully added '{title}' to Sonarr.")
        return True
    else:
        menu.log_warn(f"Error adding '{title}' to Sonarr.")
        return False