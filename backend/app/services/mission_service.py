"""Mission / drone CRUD use cases (thin layer between the API and repositories)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import models, schemas
from app.repositories import DroneRepository, MissionRepository
from app.services.planning_service import PlanningError
from app.services.runtime_service import RuntimeService


class MissionService:
    def __init__(self, runtime: RuntimeService) -> None:
        self.runtime = runtime

    # ---- drones ----
    def list_drones(self, db: Session) -> list[models.Drone]:
        return DroneRepository(db).list()

    def create_drone(self, db: Session, body: schemas.DroneCreate) -> models.Drone:
        return DroneRepository(db).create(**body.model_dump())

    # ---- missions ----
    def list_missions(self, db: Session) -> list[models.Mission]:
        return MissionRepository(db).list()

    def create_mission(self, db: Session, body: schemas.MissionCreate) -> models.Mission:
        return MissionRepository(db).create(body.name, [t.model_dump() for t in body.tasks])

    def _require(self, db: Session, mission_id: int) -> models.Mission:
        mission = MissionRepository(db).get(mission_id)
        if mission is None:
            raise PlanningError(f"mission {mission_id} not found", 404)
        return mission

    def add_obstacle(self, db: Session, mission_id: int, body: schemas.ObstacleIn) -> models.Obstacle:
        self._require(db, mission_id)
        row = MissionRepository(db).add_obstacle(mission_id, body.lat, body.lon, body.radius_m)
        self.runtime.inject_obstacle(mission_id, row)
        return row

    def clear_obstacles(self, db: Session, mission_id: int) -> None:
        self._require(db, mission_id)
        if self.runtime.is_running(mission_id):
            raise PlanningError("cannot clear obstacles while the mission is running", 409)
        MissionRepository(db).clear_obstacles(mission_id)
