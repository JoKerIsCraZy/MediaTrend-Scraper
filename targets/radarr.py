#!/usr/bin/env python3
import json
from typing import List, Dict, Any, Optional
import utils.menu as menu
from utils.network import AsyncClient

async def _get_api(base_url: str, api_key: str, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Private Hilfsfunktion für GET-Anfragen an Radarr."""
    try:
        return await AsyncClient.get(
            f"{base_url}/api/v3/{endpoint}",
            params=params,
            headers={"X-Api-Key": api_key},
            timeout=10
        )
    except Exception as e:
        menu.log_error(f"Radarr API GET-Fehler ({endpoint}): {e}")
    return None

async def _post_api(base_url: str, api_key: str, endpoint: str, data: Dict[str, Any]) -> Any:
    """Private Hilfsfunktion für POST-Anfragen an Radarr."""
    try:
        return await AsyncClient.post(
            f"{base_url}/api/v3/{endpoint}",
            json_data=data,
            headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
            timeout=20
        )
    except Exception as e:
        menu.log_error(f"Radarr API POST-Fehler ({endpoint}): {e}")
    return None

async def radarr_get_quality_profiles(radarr_url: str, radarr_token: str) -> List[Dict[str, Any]]:
    """Ruft alle Qualitätsprofile von Radarr ab."""
    data = await _get_api(radarr_url, radarr_token, "qualityprofile")
    return sorted(data, key=lambda p: p.get("id", 0)) if data else []

async def radarr_get_root_folders(radarr_url: str, radarr_token: str) -> List[str]:
    """Ruft alle Stammordner von Radarr ab."""
    data = await _get_api(radarr_url, radarr_token, "rootfolder")
    return [f.get("path") for f in data if f.get("path")] if data else []

async def radarr_lookup_existing(radarr_url: str, radarr_token: str) -> Dict[int, Any]:
    """Ruft alle Filme in Radarr ab und gibt ein Dict {tmdbId: movie} zurück."""
    data = await _get_api(radarr_url, radarr_token, "movie")
    return {int(m.get("tmdbId")): m for m in data if m.get("tmdbId")} if data else {}

async def radarr_add_movie(config: Dict[str, Any], tmdb_id: int, title: str, year: int = 0) -> bool:
    """
    Fügt einen einzelnen Film zu Radarr hinzu.
    """
    radarr_cfg = config["radarr"]
    
    # Wenn Jahr 0 ist, nicht senden (verursacht sonst Fehler)
    if year == 0:
        menu.log_warn(f"'{title}' hat kein gültiges Release-Jahr. Sende ohne Jahr...")

    menu.log(f"Sende '{title}' ({year}) (TMDb: {tmdb_id}) an Radarr...")

    payload = {
        "tmdbId": tmdb_id,
        "title": title,
        "qualityProfileId": radarr_cfg["quality_profile_id"],
        "rootFolderPath": radarr_cfg["root_folder_path"],
        "monitored": True,
        "addOptions": {
            "searchForMovie": radarr_cfg["search_on_add"]
        }
    }
    
    # Füge 'year' nur hinzu, wenn es gültig ist
    if year > 0:
        payload["year"] = year

    response = await _post_api(radarr_cfg["url"], radarr_cfg["api_key"], "movie", payload)
    
    if response and response.get("id"):
        menu.log(f"Erfolgreich '{title}' zu Radarr hinzugefügt.")
        return True
    else:
        menu.log_warn(f"Fehler beim Hinzufügen von '{title}' zu Radarr.")
        # Der Fehler (z.B. Ordnerbenennung) wurde bereits in _post_api geloggt.
        return False