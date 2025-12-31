#!/usr/bin/env python3
import json
import os
from typing import Any, Dict, List

# Importiert die API-Funktionen von unseren Zielen
import targets.radarr as radarr
import targets.sonarr as sonarr
import utils.menu as menu

SETTINGS_FILE = "settings.json"

# Definiert eine Liste von Ländern für das Menü
# Format: Dict für 'prompt_for_selection'
COMMON_COUNTRIES = [
    {"name": "Global / Weltweit", "code": "WORLD"}, 
    {"name": "Schweiz", "code": "CH"},
    {"name": "Deutschland", "code": "DE"},
    {"name": "Österreich", "code": "AT"},
    {"name": "USA", "code": "US"},
    {"name": "Großbritannien", "code": "GB"},
    {"name": "Frankreich", "code": "FR"},
    {"name": "Italien", "code": "IT"},
    {"name": "Spanien", "code": "ES"},
    {"name": "Kanada", "code": "CA"},
    {"name": "Australien", "code": "AU"},
]

# Liste der unterstützten Plattformen für die UI/Logik
SUPPORTED_PLATFORMS = [
    {"id": "netflix", "name": "Netflix", "slug": "netflix"},
    {"id": "amazon", "name": "Amazon Prime", "slug": "amazon-prime"},
    {"id": "disney", "name": "Disney+", "slug": "disney"},
    {"id": "hbo", "name": "HBO Max", "slug": "hbo-max"},
    {"id": "hulu", "name": "Hulu", "slug": "hulu"},
    {"id": "peacock", "name": "Peacock", "slug": "peacock"},
    {"id": "paramount", "name": "Paramount+", "slug": "paramount-plus"},
    {"id": "apple", "name": "Apple TV+", "slug": "apple-tv"},
    {"id": "discovery", "name": "Discovery+", "slug": "discovery-plus"},
    {"id": "star", "name": "Star+", "slug": "star-plus"},
    {"id": "rakuten", "name": "Rakuten TV", "slug": "rakuten-tv"},
    {"id": "google", "name": "Google Play", "slug": "google-play"},
    {"id": "crunchyroll", "name": "Crunchyroll", "slug": "crunchyroll"},
    {"id": "bbc", "name": "BBC iPlayer", "slug": "bbc"},
    {"id": "joyn", "name": "Joyn", "slug": "joyn"},
    {"id": "rtl", "name": "RTL+", "slug": "rtl-plus"},
    {"id": "sky", "name": "Sky", "slug": "sky"},
    {"id": "canal", "name": "Canal+", "slug": "canal-plus"},
]

def get_default_settings() -> Dict[str, Any]:
    """Definiert die Standardeinstellungen für einen neuen Benutzer."""
    return {
        "general": {
            "tmdb_api_key": "",
            "countries": ["DE", "US", "CH"], # Standardländer
            "top_count": 10  # How many top items to scrape (3, 5, 10)
        },
        "auth": {
            "enabled": False,
            "username": "admin",
            "password": "password"
        },
        "scheduler": {
            # Standardmäßig alle Jobs deaktiviert, User muss sie aktivieren
            "jobs": {
                "netflix_movies": {"enabled": False, "time": "04:00"},
                "netflix_series": {"enabled": False, "time": "04:15"},
                "amazon_movies": {"enabled": False, "time": "04:30"},
                "amazon_series": {"enabled": False, "time": "04:45"},
                "disney_movies": {"enabled": False, "time": "05:00"},
                "disney_series": {"enabled": False, "time": "05:15"},
                "hbo_movies": {"enabled": False, "time": "05:30"},
                "hbo_series": {"enabled": False, "time": "05:45"},
                "hulu_movies": {"enabled": False, "time": "06:00"},
                "hulu_series": {"enabled": False, "time": "06:15"},
                "peacock_movies": {"enabled": False, "time": "06:30"},
                "peacock_series": {"enabled": False, "time": "06:45"},
                "paramount_movies": {"enabled": False, "time": "07:00"},
                "paramount_series": {"enabled": False, "time": "07:15"},
                "apple_movies": {"enabled": False, "time": "07:30"},
                "apple_series": {"enabled": False, "time": "07:45"},
                "discovery_movies": {"enabled": False, "time": "08:00"},
                "discovery_series": {"enabled": False, "time": "08:15"},
                "star_movies": {"enabled": False, "time": "08:30"},
                "star_series": {"enabled": False, "time": "08:45"},
                "rakuten_movies": {"enabled": False, "time": "09:00"},
                "rakuten_series": {"enabled": False, "time": "09:15"},
                "google_movies": {"enabled": False, "time": "09:30"},
                "google_series": {"enabled": False, "time": "09:45"},
                "crunchyroll_movies": {"enabled": False, "time": "10:00"},
                "crunchyroll_series": {"enabled": False, "time": "10:15"},
                "bbc_movies": {"enabled": False, "time": "10:30"},
                "bbc_series": {"enabled": False, "time": "10:45"},
                "joyn_movies": {"enabled": False, "time": "11:00"},
                "joyn_series": {"enabled": False, "time": "11:15"},
                "rtl_movies": {"enabled": False, "time": "11:30"},
                "rtl_series": {"enabled": False, "time": "11:45"},
                "sky_movies": {"enabled": False, "time": "12:00"},
                "sky_series": {"enabled": False, "time": "12:15"},
                "canal_movies": {"enabled": False, "time": "12:30"},
                "canal_series": {"enabled": False, "time": "12:45"},
            }
        },
        "radarr": {
            "url": "http://localhost:7878",
            "api_key": "",
            "quality_profile_id": 1,
            "root_folder_path": "/movies",
            "search_on_add": True
        },
        "sonarr": {
            "url": "http://localhost:8989",
            "api_key": "",
            "quality_profile_id": 1,
            "root_folder_path": "/tv",
            "search_on_add": True
        }
    }

def load_settings() -> Dict[str, Any]:
    """Lädt die Einstellungen aus der JSON-Datei oder erstellt Standards."""
    if not os.path.exists(SETTINGS_FILE):
        defaults = get_default_settings()
        save_settings(defaults)
        config = defaults
    else:
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            menu.log_warn(f"Fehler beim Laden der Einstellungen: {e}")
            config = get_default_settings()
    
    # Apply environment variable overrides (maintain backward compatibility)
    # These override config values but don't modify the file
    if os.environ.get("MEDIATREND_TMDB_API_KEY"):
        config["general"]["tmdb_api_key"] = os.environ["MEDIATREND_TMDB_API_KEY"]
    if os.environ.get("MEDIATREND_RADARR_URL"):
        config["radarr"]["url"] = os.environ["MEDIATREND_RADARR_URL"]
    if os.environ.get("MEDIATREND_RADARR_API_KEY"):
        config["radarr"]["api_key"] = os.environ["MEDIATREND_RADARR_API_KEY"]
    if os.environ.get("MEDIATREND_SONARR_URL"):
        config["sonarr"]["url"] = os.environ["MEDIATREND_SONARR_URL"]
    if os.environ.get("MEDIATREND_SONARR_API_KEY"):
        config["sonarr"]["api_key"] = os.environ["MEDIATREND_SONARR_API_KEY"]
    if os.environ.get("MEDIATREND_AUTH_ENABLED"):
        config["auth"]["enabled"] = os.environ["MEDIATREND_AUTH_ENABLED"].lower() == "true"
    
    return config

import shutil

def save_settings(data: Dict[str, Any]) -> None:
    """Speichert die Einstellungen in die JSON-Datei."""
    try:
        tmp = SETTINGS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Override file content instead of replacing the inode (keeps docker bind-mounts alive)
        shutil.copyfile(tmp, SETTINGS_FILE)
        os.remove(tmp)
        
        menu.log("Einstellungen gespeichert.")
    except Exception as e:
        menu.log_warn(f"Speichern der Einstellungen fehlgeschlagen: {e}")

def edit_general_settings(config: Dict[str, Any]) -> None:
    """Interaktives Menü für allgemeine Einstellungen."""
    menu.log("Bearbeite allgemeine Einstellungen...")
    cfg = config["general"]
    
    cfg["tmdb_api_key"] = menu.prompt("TMDb API Key", cfg["tmdb_api_key"])
    
    # Länderauswahl
    selected_countries = menu.prompt_for_selection(
        title="Länder für Top-Listen auswählen",
        items=COMMON_COUNTRIES,
        display_key="name",
        current_value=cfg["countries"],
        value_key="code",
        allow_multi=True
    )
    # Entfernt 'all', falls es ausgewählt wurde
    cfg["countries"] = [c for c in selected_countries if c != 'all']
    
    save_settings(config)

def edit_radarr_settings(config: Dict[str, Any]) -> None:
    """Interaktives Menü für Radarr-Einstellungen."""
    menu.log("Bearbeite Radarr-Einstellungen...")
    cfg = config["radarr"]

    cfg["url"] = menu.prompt("Radarr URL", cfg["url"]).rstrip("/")
    cfg["api_key"] = menu.prompt("Radarr API Key", cfg["api_key"])

    if not cfg["url"] or not cfg["api_key"]:
        menu.log_warn("URL oder API Key fehlen. Überspringe Profil- und Ordnerabruf.")
        save_settings(config)
        return

    # 1. Qualitätsprofile abrufen und auswählen
    profiles = radarr.radarr_get_quality_profiles(cfg["url"], cfg["api_key"])
    if profiles:
        selected_id = menu.prompt_for_selection(
            title="Radarr-Qualitätsprofile",
            items=profiles,
            display_key="name",
            current_value=cfg["quality_profile_id"],
            value_key="id"
        )
        cfg["quality_profile_id"] = selected_id
    else:
        menu.log_warn("Keine Radarr-Profile gefunden.")

    # 2. Stammordner abrufen und auswählen
    folders = radarr.radarr_get_root_folders(cfg["url"], cfg["api_key"])
    if folders:
        # Konvertiert die Pfad-Strings in das erwartete Dict-Format
        folder_items = [{"path": p} for p in folders]
        selected_path = menu.prompt_for_selection(
            title="Radarr-Stammordner",
            items=folder_items,
            display_key="path",
            current_value=cfg["root_folder_path"],
            value_key="path"
        )
        cfg["root_folder_path"] = selected_path
    else:
        menu.log_warn("Keine Radarr-Stammordner gefunden.")

    cfg["search_on_add"] = menu.prompt_yes_no("Radarr: Automatisch nach Film suchen?", cfg["search_on_add"])
    save_settings(config)

def edit_sonarr_settings(config: Dict[str, Any]) -> None:
    """Interaktives Menü für Sonarr-Einstellungen."""
    menu.log("Bearbeite Sonarr-Einstellungen...")
    cfg = config["sonarr"]

    cfg["url"] = menu.prompt("Sonarr URL", cfg["url"]).rstrip("/")
    cfg["api_key"] = menu.prompt("Sonarr API Key", cfg["api_key"])

    if not cfg["url"] or not cfg["api_key"]:
        menu.log_warn("URL oder API Key fehlen. Überspringe Profil- und Ordnerabruf.")
        save_settings(config)
        return

    # 1. Qualitätsprofile abrufen und auswählen
    profiles = sonarr.sonarr_get_quality_profiles(cfg["url"], cfg["api_key"])
    if profiles:
        selected_id = menu.prompt_for_selection(
            title="Sonarr-Qualitätsprofile",
            items=profiles,
            display_key="name",
            current_value=cfg["quality_profile_id"],
            value_key="id"
        )
        cfg["quality_profile_id"] = selected_id
    else:
        menu.log_warn("Keine Sonarr-Profile gefunden.")

    # 2. Stammordner abrufen und auswählen
    folders = sonarr.sonarr_get_root_folders(cfg["url"], cfg["api_key"])
    if folders:
        folder_items = [{"path": p} for p in folders]
        selected_path = menu.prompt_for_selection(
            title="Sonarr-Stammordner",
            items=folder_items,
            display_key="path",
            current_value=cfg["root_folder_path"],
            value_key="path"
        )
        cfg["root_folder_path"] = selected_path
    else:
        menu.log_warn("Keine Sonarr-Stammordner gefunden.")
        
    cfg["search_on_add"] = menu.prompt_yes_no("Sonarr: Automatisch nach Serie suchen?", cfg["search_on_add"])
    save_settings(config)

def show_settings_menu(config: Dict[str, Any]) -> None:
    """Zeigt das Haupt-Einstellungsmenü an."""
    while True:
        print("\n--- Einstellungen verwalten ---")
        print("1) Allgemein (TMDb Key, Länder)")
        print("2) Radarr (Filme)")
        print("3) Sonarr (Serien)")
        print("9) Zurück zum Hauptmenü")
        
        choice = input("Wählen Sie einen Bereich: ").strip()

        if choice == "1":
            edit_general_settings(config)
        elif choice == "2":
            edit_radarr_settings(config)
        elif choice == "3":
            edit_sonarr_settings(config)
        elif choice == "9":
            break
        else:
            menu.log_warn("Ungültige Auswahl.")