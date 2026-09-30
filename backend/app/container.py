"""Wires the application together (one container per FastAPI app)."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from ai.energy_model.features import Environment
from ai.energy_model.predict import EnergyPredictor
from ai.path_planning import AStarPlanner
from app.config import Settings
from app.db import init_db, make_engine, make_session_factory
from app.services.mission_service import MissionService
from app.services.planning_service import PlanningService
from app.services.runtime_service import RuntimeService
from app.sim_adapter.mock_adapter import MockAdapter


class ConnectionManager:
    """Tracks WebSocket clients and fans out JSON messages."""

    def __init__(self) -> None:
        self.connections: set = set()

    async def connect(self, ws) -> None:
        await ws.accept()
        self.connections.add(ws)

    def disconnect(self, ws) -> None:
        self.connections.discard(ws)

    async def broadcast(self, message: dict) -> None:
        for ws in list(self.connections):
            try:
                await ws.send_json(message)
            except Exception:  # client went away mid-send
                self.disconnect(ws)


@dataclass
class Container:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    predictor: EnergyPredictor
    planning: PlanningService
    runtime: RuntimeService
    missions: MissionService
    manager: ConnectionManager = field(default_factory=ConnectionManager)


def build_container(settings: Settings) -> Container:
    engine = make_engine(settings.database_url)
    init_db(engine)
    session_factory = make_session_factory(engine)
    predictor = EnergyPredictor(settings.energy_model_path)
    planner = AStarPlanner()
    planning = PlanningService(settings, predictor, planner)
    env = Environment(settings.wind_speed_ms, settings.wind_to_deg)
    runtime = RuntimeService(
        settings, session_factory, planning,
        adapter_factory=lambda: MockAdapter(predictor, env, seed=settings.sim_seed))
    return Container(settings, engine, session_factory, predictor, planning, runtime, MissionService(runtime))
