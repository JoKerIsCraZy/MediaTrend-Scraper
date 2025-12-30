#!/usr/bin/env python3
import os
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import logging

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import settings
from scheduler import SchedulerService
import targets.radarr as radarr
import targets.sonarr as sonarr
from pydantic import BaseModel
from typing import List, Dict, Any


# Global Instances
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

import secrets
from utils.password import verify_password, hash_password, needs_rehash

def check_auth(credentials: HTTPBasicCredentials = Depends(security)):
    """Checks the credentials if authentication is enabled."""
    global config
    
    if not config or not config.get("auth", {}).get("enabled", False):
        return True

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    # Support environment variable overrides for credentials
    correct_username = os.environ.get("MEDIATREND_AUTH_USERNAME", config["auth"]["username"])
    correct_password = os.environ.get("MEDIATREND_AUTH_PASSWORD", config["auth"]["password"])

    # Use timing-safe comparison for username
    username_match = secrets.compare_digest(credentials.username.encode('utf-8'), correct_username.encode('utf-8'))
    
    # Use bcrypt verification for password (handles both hashed and legacy plaintext)
    password_match = verify_password(credentials.password, correct_password)
    
    if not (username_match and password_match):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    # Auto-migrate plaintext password to bcrypt hash on successful login
    if password_match and needs_rehash(config["auth"]["password"]) and not os.environ.get("MEDIATREND_AUTH_PASSWORD"):
        config["auth"]["password"] = hash_password(credentials.password)
        settings.save_settings(config)
        web_logger("[SECURITY] Password migrated to bcrypt hash.")
    
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
@limiter.limit("60/minute")
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

@app.post("/api/logs/clear")
async def clear_logs(authorized: bool = Depends(check_auth)):
    LOG_BUFFER.clear()
    return {"status": "success", "message": "Logs cleared"}



# --- Settings API ---

@app.get("/api/settings")
async def get_settings(authorized: bool = Depends(check_auth)):
    return settings.load_settings()

@app.post("/api/settings")
async def update_settings(new_settings: Dict[str, Any], authorized: bool = Depends(check_auth)):
    global config
    
    # Hash password if it was changed and is not already a hash
    if "auth" in new_settings and "password" in new_settings["auth"]:
        new_password = new_settings["auth"]["password"]
        if needs_rehash(new_password):
            new_settings["auth"]["password"] = hash_password(new_password)
            web_logger("[SECURITY] Password hashed before saving.")
    
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

@app.post("/api/run-job/{job_key}")
@limiter.limit("10/minute")
async def run_job(request: Request, job_key: str, background_tasks: BackgroundTasks, authorized: bool = Depends(check_auth)):
    if not scheduler_service:
        return {"message": "Scheduler not initialized.", "status": "error"}
    
    background_tasks.add_task(scheduler_service.run_job_now, job_key)
    return {"status": "success", "message": f"Job '{job_key}' started in background."}

@app.post("/api/run-all")
@limiter.limit("5/minute")
async def run_all_jobs(request: Request, background_tasks: BackgroundTasks, authorized: bool = Depends(check_auth)):
    if not scheduler_service:
        return {"message": "Scheduler not initialized.", "status": "error"}

    background_tasks.add_task(scheduler_service.run_all_jobs_sequentially)
    return {"status": "success", "message": "All jobs started sequentially in background."}

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
    except Exception:
        logging.exception("Failed to fetch Radarr quality profiles")
        return {"error": "Failed to fetch Radarr quality profiles."}

@app.post("/api/radarr/folders")
async def get_radarr_folders(cfg: ServiceConfig, authorized: bool = Depends(check_auth)):
    try:
        folders = await radarr.radarr_get_root_folders(cfg.url, cfg.api_key)
        # Radarr returns strings, we convert to objects for consistency
        return [{"path": f} for f in folders]
    except Exception:
        logging.exception("Failed to fetch Radarr root folders")
        return {"error": "Failed to fetch Radarr root folders."}

@app.post("/api/sonarr/profiles")
async def get_sonarr_profiles(cfg: ServiceConfig, authorized: bool = Depends(check_auth)):
    try:
        profiles = await sonarr.sonarr_get_quality_profiles(cfg.url, cfg.api_key)
        return profiles
    except Exception:
        logging.exception("Failed to fetch Sonarr quality profiles")
        return {"error": "Failed to fetch Sonarr quality profiles."}

@app.post("/api/sonarr/folders")
async def get_sonarr_folders(cfg: ServiceConfig, authorized: bool = Depends(check_auth)):
    try:
        folders = await sonarr.sonarr_get_root_folders(cfg.url, cfg.api_key)
        return [{"path": f} for f in folders]
    except Exception:
        logging.exception("Failed to fetch Sonarr root folders")
        return {"error": "Failed to fetch Sonarr root folders."}


def start_web_server():
    """Starts the Uvicorn server."""
    # Support environment variable configuration for host/port
    host = os.environ.get("MEDIATREND_HOST", "0.0.0.0")
    port = int(os.environ.get("MEDIATREND_PORT", "9000"))
    uvicorn.run(app, host=host, port=port)
