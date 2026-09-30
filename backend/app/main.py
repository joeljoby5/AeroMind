"""AeroMind API entry point:  uvicorn app.main:app  (run with PYTHONPATH=<repo root>)."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import ai, drones, missions, telemetry_ws
from app.config import Settings, get_settings
from app.container import build_container
from app.services.planning_service import PlanningError

log = logging.getLogger("aeromind")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname,
                   "logger": record.name, "msg": record.getMessage()}
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


async def _ticker(app: FastAPI) -> None:
    """Advance the simulation and push a telemetry message to every WebSocket client each tick."""
    c = app.state.container
    while True:
        await asyncio.sleep(c.settings.tick_s)
        try:
            snap = c.runtime.tick()
            if c.manager.connections:
                await c.manager.broadcast(snap)
        except Exception:  # never let one bad tick kill the loop
            log.exception("tick failed")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    container = build_container(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(_ticker(app)) if settings.auto_tick else None
        log.info("AeroMind API up (db=%s, energy model=%s)", settings.database_url.split("@")[-1],
                 container.predictor.model_name)
        yield
        if task:
            task.cancel()

    app = FastAPI(title="AeroMind", version="0.3.0", lifespan=lifespan)
    app.state.container = container
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                       allow_headers=["*"])

    @app.exception_handler(PlanningError)
    async def planning_error(_: Request, exc: PlanningError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "model": container.predictor.model_name,
                "model_is_fallback": container.predictor.is_fallback,
                "mission_running": container.runtime.is_running()}

    app.include_router(drones.router)
    app.include_router(missions.router)
    app.include_router(ai.router)
    app.include_router(telemetry_ws.router)
    return app


setup_logging()
app = create_app()
