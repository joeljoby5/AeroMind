"""Persistence layer: the only place that talks SQL."""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import models


class DroneRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[models.Drone]:
        return list(self.db.scalars(select(models.Drone).order_by(models.Drone.id)))

    def get(self, drone_id: int) -> models.Drone | None:
        return self.db.get(models.Drone, drone_id)

    def create(self, **fields) -> models.Drone:
        drone = models.Drone(**fields)
        self.db.add(drone)
        self.db.commit()
        return drone

    def set_status(self, drone_ids: Iterable[int], status: str) -> None:
        for drone in self.db.scalars(select(models.Drone).where(models.Drone.id.in_(list(drone_ids)))):
            drone.status = status
        self.db.commit()


class MissionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- missions & tasks ----
    def list(self) -> list[models.Mission]:
        return list(self.db.scalars(select(models.Mission).order_by(models.Mission.id.desc())))

    def get(self, mission_id: int) -> models.Mission | None:
        return self.db.get(models.Mission, mission_id)

    def create(self, name: str, tasks: Iterable[dict]) -> models.Mission:
        mission = models.Mission(name=name, status="draft")
        mission.tasks = [models.Task(**t) for t in tasks]
        self.db.add(mission)
        self.db.commit()
        return mission

    def set_status(self, mission_id: int, status: str, strategy: str | None = None) -> None:
        mission = self.db.get(models.Mission, mission_id)
        mission.status = status
        if strategy is not None:
            mission.strategy = strategy
        self.db.commit()

    # ---- assignments ----
    def assignments(self, mission_id: int) -> list[models.Assignment]:
        q = (select(models.Assignment).where(models.Assignment.mission_id == mission_id)
             .order_by(models.Assignment.drone_id, models.Assignment.order))
        return list(self.db.scalars(q))

    def replace_assignments(self, mission_id: int, rows: Iterable[dict]) -> list[models.Assignment]:
        self.db.execute(delete(models.Assignment).where(models.Assignment.mission_id == mission_id))
        created = [models.Assignment(mission_id=mission_id, **r) for r in rows]
        self.db.add_all(created)
        self.db.commit()
        return created

    # ---- obstacles ----
    def obstacles(self, mission_id: int) -> list[models.Obstacle]:
        q = select(models.Obstacle).where(models.Obstacle.mission_id == mission_id).order_by(models.Obstacle.id)
        return list(self.db.scalars(q))

    def add_obstacle(self, mission_id: int, lat: float, lon: float, radius_m: float) -> models.Obstacle:
        ob = models.Obstacle(mission_id=mission_id, lat=lat, lon=lon, radius_m=radius_m)
        self.db.add(ob)
        self.db.commit()
        return ob

    def clear_obstacles(self, mission_id: int) -> None:
        self.db.execute(delete(models.Obstacle).where(models.Obstacle.mission_id == mission_id))
        self.db.commit()

    # ---- telemetry ----
    def add_telemetry(self, samples: Iterable[dict]) -> None:
        self.db.add_all([models.TelemetrySample(**s) for s in samples])
        self.db.commit()

    def telemetry_count(self) -> int:
        return len(list(self.db.scalars(select(models.TelemetrySample.id))))
