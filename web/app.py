#!/usr/bin/env python3
import os
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

import settings
from scheduler import SchedulerService
import targets.radarr as radarr
import targets.sonarr as sonarr
from pydantic import BaseModel
from typing import List, Dict, Any


# Globale Instanzen
app = FastAPI()
scheduler_service = None
config = None

# Templates
templates = Jinja2Templates(directory="web/templates")

# In-Memory Log Buffer (sehr einfach gehalten)
LOG_BUFFER = []

def web_logger(message: str):
    """Fängt Logs ab und speichert sie im Buffer."""
    print(message) # Auch auf Konsole ausgeben
    LOG_BUFFER.append(message)
    if len(LOG_BUFFER) > 100:
        LOG_BUFFER.pop(0)

# Monkey-Patching von utils.menu.log (etwas hacky, aber effektiv für dieses Setup)
import utils.menu
utils.menu.log = web_logger
utils.menu.log_warn = lambda m: web_logger(f"[WARN] {m}")
utils.menu.log_error = lambda m: web_logger(f"[ERROR] {m}")


@app.on_event("startup")
async def startup_event():
    global scheduler_service, config
    config = settings.load_settings()
    scheduler_service = SchedulerService(config)
    scheduler_service.start()
    web_logger("Webserver gestartet.")

@app.on_event("shutdown")
async def shutdown_event():
    if scheduler_service:
        scheduler_service.stop()
    web_logger("Webserver gestoppt.")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/status")
async def get_status():
    jobs = scheduler_service.get_jobs() if scheduler_service else []
    return {
        "scheduler_running": scheduler_service.scheduler.running if scheduler_service else False,
        "job_count": len(jobs)
    }

@app.get("/api/logs")
async def get_logs():
    return {"logs": LOG_BUFFER}



# --- Settings API ---

@app.get("/api/settings")
async def get_settings():
    return settings.load_settings()

@app.post("/api/settings")
async def update_settings(new_settings: Dict[str, Any]):
    global config, scheduler_service
    settings.save_settings(new_settings)
    config = settings.load_settings()
    
    # Scheduler neu laden
    if scheduler_service:
        scheduler_service.config = config
        scheduler_service.reload_jobs()
        
    return {"status": "success", "message": "Einstellungen gespeichert."}

@app.get("/api/platforms")
async def get_platforms():
    return settings.SUPPORTED_PLATFORMS

@app.post("/api/run/{job_key}")
async def run_job(job_key: str, background_tasks: BackgroundTasks):
    if not scheduler_service:
        return {"message": "Scheduler nicht initialisiert.", "status": "error"}

    # Job im Hintergrund starten
    background_tasks.add_task(scheduler_service.run_job_now, job_key)
    return {"message": f"Job '{job_key}' wurde gestartet.", "status": "success"}

@app.get("/api/constants")
async def get_constants():
    return {
        "countries": settings.COMMON_COUNTRIES
    }

# --- Proxy API für Radarr/Sonarr (für Dropdowns) ---

class ServiceConfig(BaseModel):
    url: str
    api_key: str

@app.post("/api/radarr/profiles")
async def get_radarr_profiles(cfg: ServiceConfig):
    try:
        profiles = await radarr.radarr_get_quality_profiles(cfg.url, cfg.api_key)
        return profiles
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/radarr/folders")
async def get_radarr_folders(cfg: ServiceConfig):
    try:
        folders = await radarr.radarr_get_root_folders(cfg.url, cfg.api_key)
        # Radarr gibt Strings zurück, wir machen Objekte draus für Konsistenz
        return [{"path": f} for f in folders]
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/sonarr/profiles")
async def get_sonarr_profiles(cfg: ServiceConfig):
    try:
        profiles = await sonarr.sonarr_get_quality_profiles(cfg.url, cfg.api_key)
        return profiles
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/sonarr/folders")
async def get_sonarr_folders(cfg: ServiceConfig):
    try:
        folders = await sonarr.sonarr_get_root_folders(cfg.url, cfg.api_key)
        return [{"path": f} for f in folders]
    except Exception as e:
        return {"error": str(e)}


def start_web_server():
    """Startet den Uvicorn-Server."""
    # Wir müssen sicherstellen, dass wir im richtigen Verzeichnis sind oder Pfade anpassen
    # Da main.py im Root liegt, sollte es passen.
    uvicorn.run(app, host="0.0.0.0", port=8000)
