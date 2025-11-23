#!/usr/bin/env python3
import asyncio
from typing import Dict, Any, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.base import JobLookupError

import utils.menu as menu
from utils.types import MediaType
import worker
import sources.netflix as netflix
import sources.flixpatrol as flixpatrol
import settings

class SchedulerService:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()

    def _setup_jobs(self):
        """Lädt die Jobs basierend auf der Konfiguration."""
        self.scheduler.remove_all_jobs()
        
        scheduler_config = self.config.get("scheduler", {}).get("jobs", {})
        
        for job_key, job_cfg in scheduler_config.items():
            if job_cfg.get("enabled", False):
                time_str = job_cfg.get("time", "04:00")
                try:
                    hour, minute = map(int, time_str.split(":"))
                    self.add_job(job_key, self._create_job_func(job_key), CronTrigger(hour=hour, minute=minute))
                except ValueError:
                    menu.log_error(f"Ungültiges Zeitformat für Job '{job_key}': {time_str}")

    def reload_jobs(self):
        """Lädt die Jobs neu (z.B. nach Einstellungsänderung)."""
        menu.log("Lade Scheduler-Jobs neu...")
        self._setup_jobs()

    def _create_job_func(self, job_key: str):
        """Erstellt eine Wrapper-Funktion für den Job."""
        # Parsen des Keys: z.B. "netflix_movies" -> platform="netflix", type="movies"
        parts = job_key.split("_")
        if len(parts) < 2:
            return lambda: None # Sollte nicht passieren
        
        platform_id = parts[0]
        media_type_str = parts[1] # "movies" oder "series"
        
        media_type = MediaType.MOVIE if media_type_str == "movies" else MediaType.SERIES
        
        # Finde den korrekten Namen und Slug
        platform_info = next((p for p in settings.SUPPORTED_PLATFORMS if p["id"] == platform_id), None)
        
        if not platform_info:
            menu.log_warn(f"Unbekannte Plattform-ID im Job: {platform_id}")
            return lambda: None

        platform_name = platform_info["name"]
        platform_slug = platform_info["slug"]

        async def job_wrapper():
            # Spezialfall Netflix: Hat eigenes Modul
            if platform_id == "netflix":
                await worker.process_media_list(self.config, platform_name, media_type, 
                                                lambda c: netflix.scrape_netflix(c, media_type))
            else:
                # Alle anderen über FlixPatrol
                await worker.process_media_list(self.config, platform_name, media_type, 
                                                lambda c: flixpatrol.scrape_flixpatrol(platform_slug, c, media_type))
        
        return job_wrapper

    def start(self):
        """Startet den Scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            menu.log("Scheduler gestartet.")

    def stop(self):
        """Stoppt den Scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            menu.log("Scheduler gestoppt.")

    def add_job(self, job_id: str, func, trigger, **kwargs):
        """Fügt einen Job hinzu."""
        try:
            self.scheduler.add_job(func, trigger, id=job_id, replace_existing=True, **kwargs)
            menu.log(f"Job '{job_id}' hinzugefügt (Trigger: {trigger}).")
        except Exception as e:
            menu.log_error(f"Fehler beim Hinzufügen von Job '{job_id}': {e}")

    def remove_job(self, job_id: str):
        """Entfernt einen Job."""
        try:
            self.scheduler.remove_job(job_id)
            menu.log(f"Job '{job_id}' entfernt.")
        except JobLookupError:
            pass
        except Exception as e:
            menu.log_error(f"Fehler beim Entfernen von Job '{job_id}': {e}")

    def get_jobs(self):
        """Gibt eine Liste der aktiven Jobs zurück."""
        return self.scheduler.get_jobs()

    async def run_job_now(self, job_key: str):
        """Führt einen Job sofort aus."""
        func = self._create_job_func(job_key)
        await func()

