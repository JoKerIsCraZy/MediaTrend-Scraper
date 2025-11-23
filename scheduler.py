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
        """Loads jobs based on configuration."""
        self.scheduler.remove_all_jobs()
        
        scheduler_config = self.config.get("scheduler", {}).get("jobs", {})
        
        for job_key, job_cfg in scheduler_config.items():
            if job_cfg.get("enabled", False):
                time_str = job_cfg.get("time", "04:00")
                try:
                    hour, minute = map(int, time_str.split(":"))
                    self.add_job(job_key, self._create_job_func(job_key), CronTrigger(hour=hour, minute=minute))
                except ValueError:
                    menu.log_error(f"Invalid time format for job '{job_key}': {time_str}")

    def reload_jobs(self):
        """Reloads jobs (e.g., after settings change)."""
        menu.log("Reloading scheduler jobs...")
        self._setup_jobs()

    def _create_job_func(self, job_key: str):
        """Creates a wrapper function for the job."""
        # Parse key: e.g. "netflix_movies" -> platform="netflix", type="movies"
        parts = job_key.split("_")
        if len(parts) < 2:
            return lambda: None # Should not happen
        
        platform_id = parts[0]
        media_type_str = parts[1] # "movies" oder "series"
        
        media_type = MediaType.MOVIE if media_type_str == "movies" else MediaType.SERIES
        
        # Find correct name and slug
        platform_info = next((p for p in settings.SUPPORTED_PLATFORMS if p["id"] == platform_id), None)
        
        if not platform_info:
            menu.log_warn(f"Unknown platform ID in job: {platform_id}")
            return lambda: None

        platform_name = platform_info["name"]
        platform_slug = platform_info["slug"]

        async def job_wrapper():
            # Special case Netflix: Has its own module
            if platform_id == "netflix":
                await worker.process_media_list(self.config, platform_name, media_type, 
                                                lambda c: netflix.scrape_netflix(c, media_type))
            else:
                # All others via FlixPatrol
                await worker.process_media_list(self.config, platform_name, media_type, 
                                                lambda c: flixpatrol.scrape_flixpatrol(platform_slug, c, media_type))
        
        return job_wrapper

    def start(self):
        """Starts the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            menu.log("Scheduler started.")

    def stop(self):
        """Stops the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            menu.log("Scheduler stopped.")

    def add_job(self, job_id: str, func, trigger, **kwargs):
        """Adds a job."""
        try:
            self.scheduler.add_job(func, trigger, id=job_id, replace_existing=True, **kwargs)
            menu.log(f"Job '{job_id}' added (Trigger: {trigger}).")
        except Exception as e:
            menu.log_error(f"Error adding job '{job_id}': {e}")

    def remove_job(self, job_id: str):
        """Removes a job."""
        try:
            self.scheduler.remove_job(job_id)
            menu.log(f"Job '{job_id}' removed.")
        except JobLookupError:
            pass
        except Exception as e:
            menu.log_error(f"Error removing job '{job_id}': {e}")

    def get_jobs(self):
        """Returns a list of active jobs."""
        return self.scheduler.get_jobs()

    async def run_job_now(self, job_key: str):
        """Executes a job immediately."""
        func = self._create_job_func(job_key)
        await func()

