#!/usr/bin/env python3
import os
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
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


# Global Instances
app = FastAPI()
security = HTTPBasic(auto_error=False)
scheduler_service = None
config = None

# Templates
templates = Jinja2Templates(directory="web/templates")

# In-Memory Log Buffer (kept very simple)
LOG_BUFFER = []

def web_logger(message: str):
    """Intercepts logs and stores them in the buffer."""
    print(message) # Also print to console
    LOG_BUFFER.append(message)
    if len(LOG_BUFFER) > 100:
        LOG_BUFFER.pop(0)

# Monkey-Patching of utils.menu.log (a bit hacky, but effective for this setup)
import utils.menu
utils.menu.log = web_logger
utils.menu.log_warn = lambda m: web_logger(f"[WARN] {m}")
utils.menu.log_error = lambda m: web_logger(f"[ERROR] {m}")


def check_auth(credentials: HTTPBasicCredentials = Depends(security)):
    """Checks the credentials if authentication is enabled."""
    if not config or not config.get("auth", {}).get("enabled", False):
        return True

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    correct_username = config["auth"]["username"]
    correct_password = config["auth"]["password"]

    # Simple string comparison (in production, use constant-time comparison)
    if credentials.username != correct_username or credentials.password != correct_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True


@app.on_event("startup")
async def startup_event():
    global scheduler_service, config
    config = settings.load_settings()
    scheduler_service = SchedulerService(config)
    scheduler_service.start()
    web_logger("Webserver started.")

@app.on_event("shutdown")
async def shutdown_event():
    if scheduler_service:
        scheduler_service.stop()
    web_logger("Webserver stopped.")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, authorized: bool = Depends(check_auth)):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/status")
async def get_status(authorized: bool = Depends(check_auth)):
    jobs = scheduler_service.get_jobs() if scheduler_service else []
    return {
        "scheduler_running": scheduler_service.scheduler.running if scheduler_service else False,
        "job_count": len(jobs)
    }

@app.get("/api/logs")
async def get_logs(authorized: bool = Depends(check_auth)):
    return {"logs": LOG_BUFFER}



# --- Settings API ---

@app.get("/api/settings")
async def get_settings(authorized: bool = Depends(check_auth)):
    return settings.load_settings()

@app.post("/api/settings")
async def update_settings(new_settings: Dict[str, Any], authorized: bool = Depends(check_auth)):
    global config
    settings.save_settings(new_settings)
    config = settings.load_settings()
    
    # Reload Scheduler
    if scheduler_service:
        scheduler_service.config = config
        scheduler_service.reload_jobs()
        
    return {"status": "success", "message": "Settings saved."}

@app.get("/api/platforms")
async def get_platforms(authorized: bool = Depends(check_auth)):
    return settings.SUPPORTED_PLATFORMS

@app.post("/api/run/{job_key}")
async def run_job(job_key: str, background_tasks: BackgroundTasks, authorized: bool = Depends(check_auth)):
    if not scheduler_service:
        return {"message": "Scheduler not initialized.", "status": "error"}
    
    # Start job in background
    background_tasks.add_task(scheduler_service.run_job_now, job_key)
    return {"message": f"Job '{job_key}' started.", "status": "success"}

@app.get("/api/constants")
async def get_constants(authorized: bool = Depends(check_auth)):
    return {
        "countries": settings.COMMON_COUNTRIES
    }

# --- Proxy API for Radarr/Sonarr (for Dropdowns) ---

class ServiceConfig(BaseModel):
    url: str
    api_key: str

@app.post("/api/radarr/profiles")
async def get_radarr_profiles(cfg: ServiceConfig, authorized: bool = Depends(check_auth)):
    try:
        profiles = await radarr.radarr_get_quality_profiles(cfg.url, cfg.api_key)
        return profiles
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/radarr/folders")
async def get_radarr_folders(cfg: ServiceConfig, authorized: bool = Depends(check_auth)):
    try:
        folders = await radarr.radarr_get_root_folders(cfg.url, cfg.api_key)
        # Radarr returns strings, we convert to objects for consistency
        return [{"path": f} for f in folders]
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/sonarr/profiles")
async def get_sonarr_profiles(cfg: ServiceConfig, authorized: bool = Depends(check_auth)):
    try:
        profiles = await sonarr.sonarr_get_quality_profiles(cfg.url, cfg.api_key)
        return profiles
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/sonarr/folders")
async def get_sonarr_folders(cfg: ServiceConfig, authorized: bool = Depends(check_auth)):
    try:
        folders = await sonarr.sonarr_get_root_folders(cfg.url, cfg.api_key)
        return [{"path": f} for f in folders]
    except Exception as e:
        return {"error": str(e)}


def start_web_server():
    """Starts the Uvicorn server."""
    # We must ensure we are in the correct directory or adjust paths
    # Since main.py is in root, it should be fine.
    uvicorn.run(app, host="0.0.0.0", port=8000)
