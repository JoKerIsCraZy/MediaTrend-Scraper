#!/usr/bin/env python3
import json
from typing import List, Dict, Any, Optional
import utils.menu as menu
from utils.network import AsyncClient

async def _get_api(base_url: str, api_key: str, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Private Hilfsfunktion für GET-Anfragen an Sonarr."""
    try:
        return await AsyncClient.get(
            f"{base_url}/api/v3/{endpoint}",
            params=params,
            headers={"X-Api-Key": api_key},
            timeout=10
        )
    except Exception as e:
        menu.log_error(f"Sonarr API GET-Fehler ({endpoint}): {e}")
    return None

async def _post_api(base_url: str, api_key: str, endpoint: str, data: Dict[str, Any]) -> Any:
    """Private Hilfsfunktion für POST-Anfragen an Sonarr."""
    try:
        return await AsyncClient.post(
            f"{base_url}/api/v3/{endpoint}",
            json_data=data,
            headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
            timeout=20
        )
    except Exception as e:
        menu.log_error(f"Sonarr API POST-Fehler ({endpoint}): {e}")
    return None

async def sonarr_get_quality_profiles(sonarr_url: str, sonarr_token: str) -> List[Dict[str, Any]]:
    """Ruft alle Qualitätsprofile von Sonarr ab."""
    data = await _get_api(sonarr_url, sonarr_token, "qualityprofile")
    return sorted(data, key=lambda p: p.get("id", 0)) if data else []

async def sonarr_get_root_folders(sonarr_url: str, sonarr_token: str) -> List[str]:
    """Ruft alle Stammordner von Sonarr ab."""
    data = await _get_api(sonarr_url, sonarr_token, "rootfolder")
    return [f.get("path") for f in data if f.get("path")] if data else []

async def sonarr_lookup_existing(sonarr_url: str, sonarr_token: str) -> Dict[int, Any]:
    """Ruft alle Serien in Sonarr ab und gibt ein Dict {tvdbId: series} zurück."""
    data = await _get_api(sonarr_url, sonarr_token, "series")
    return {int(s.get("tvdbId")): s for s in data if s.get("tvdbId")} if data else {}

async def sonarr_lookup_series(config: Dict[str, Any], tvdb_id: int) -> Optional[Dict[str, Any]]:
    """
    Sucht nach einer neuen Serie anhand ihrer TVDb-ID.
    Gibt das erste Ergebnis zurück, das für den POST-Endpunkt benötigt wird.
    """
    sonarr_cfg = config["sonarr"]
    menu.log(f"Suche in Sonarr nach TVDb-ID: {tvdb_id}...")
    
    # Sonarr benötigt den Begriff 'tvdb:ID_HIER'
    params = {"term": f"tvdb:{tvdb_id}"}
    results = await _get_api(sonarr_cfg["url"], sonarr_cfg["api_key"], "series/lookup", params)
    
    if results:
        # Gibt das erste Suchergebnis zurück
        return results[0]
    else:
        menu.log_warn(f"Sonarr-Suche für TVDb-ID {tvdb_id} ergab keine Treffer.")
        return None

async def sonarr_add_series(config: Dict[str, Any], tvdb_id: int) -> bool:
    """
    Fügt eine Serie zu Sonarr hinzu.
    Führt intern einen Lookup durch, um die notwendigen Daten zu erhalten.
    """
    sonarr_cfg = config["sonarr"]
    
    # 1. Lookup durchführen
    series_data = await sonarr_lookup_series(config, tvdb_id)
    if not series_data:
        menu.log_warn(f"Konnte Serie mit TVDb-ID {tvdb_id} nicht in Sonarr finden.")
        return False
        
    title = series_data.get('title', f"TVDb: {tvdb_id}")
    menu.log(f"Sende '{title}' an Sonarr...")

    # 2. Payload vorbereiten
    payload = series_data
    payload["qualityProfileId"] = sonarr_cfg["quality_profile_id"]
    payload["rootFolderPath"] = sonarr_cfg["root_folder_path"]
    payload["monitored"] = True
    payload["addOptions"] = {
        "searchForMissingEpisodes": sonarr_cfg["search_on_add"],
        "monitor": "all" # Standardmäßig alle Staffeln überwachen
    }
    
    response = await _post_api(sonarr_cfg["url"], sonarr_cfg["api_key"], "series", payload)
    
    if response and response.get("id"):
        menu.log(f"Erfolgreich '{title}' zu Sonarr hinzugefügt.")
        return True
    else:
        menu.log_warn(f"Fehler beim Hinzufügen von '{title}' zu Sonarr.")
        return False