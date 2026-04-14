import os
from logging import getLogger
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import admin, auth, health, jobs, labeling
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.state import queue_manager
from app.utils.paths import ensure_storage_dirs


configure_logging()
ensure_storage_dirs()
logger = getLogger(__name__)

app = FastAPI(title=settings.app_name, docs_url="/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, __: Exception):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.on_event("startup")
async def startup_event() -> None:
    await queue_manager.start()
    pod_id = os.getenv("RUNPOD_POD_ID") or os.getenv("POD_ID")

    logger.info("Backend local URL: http://localhost:8000")
    if pod_id:
        logger.info("Backend RunPod proxy URL: https://%s-8000.proxy.runpod.net", pod_id)
    else:
        logger.info("Backend RunPod proxy URL: unavailable (RUNPOD_POD_ID not set)")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await queue_manager.stop()


app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(jobs.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(labeling.router, prefix=settings.api_prefix)


@app.get("/")
def root() -> dict:
    return {"name": settings.app_name, "status": "ok", "docs": "/docs"}
