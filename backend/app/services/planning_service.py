"""Planning: task allocation (ML / baseline) + A* routes. Wraps the `ai/` modules for the API."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ai.allocation import evaluate_allocation
from ai.allocation import allocate as ai_allocate
from ai.allocation import leg_energy
from ai.energy_model.features import Environment
from ai.geo import haversine_m
from ai.interfaces import EnergyEstimator, PathPlanner
from ai.types import AllocationResult, DroneState, Obstacle, Task
from app import models, schemas
from app.config import Settings
from app.repositories import DroneRepository, MissionRepository

log = logging.getLogger("aeromind.planning")


class PlanningError(Exception):
    """Raised for user-fixable planning problems (mapped to HTTP 4xx by the API layer)."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class Leg:
    """One task leg: the A* path from the previous point to `target` at `alt_m`."""

    task_id: int
    target: tuple[float, float]
    alt_m: float
    payload_kg: float
    path: list[tuple[float, float]]


@dataclass
class DroneRoute:
    drone_id: int
    legs: list[Leg] = field(default_factory=list)
    home_path: list[tuple[float, float]] = field(default_factory=list)
    skipped: list[tuple[int, str]] = field(default_factory=list)  # (task_id, reason): no route

    @property
    def polyline(self) -> list[tuple[float, float]]:
        pts: list[tuple[float, float]] = []
        for path in [leg.path for leg in self.legs] + [self.home_path]:
            pts.extend(path if not pts else path[1:])
        return pts

    @property
    def length_m(self) -> float:
        pts = self.polyline
        return sum(haversine_m(a[0], a[1], b[0], b[1]) for a, b in zip(pts, pts[1:]))


def to_state(d: models.Drone) -> DroneState:
    return DroneState(id=d.id, name=d.name, type=d.type, lat=d.home_lat, lon=d.home_lon,
                      battery_pct=d.battery_pct, health=d.health, home_lat=d.home_lat, home_lon=d.home_lon)


def to_task(t: models.Task) -> Task:
    return Task(id=t.id, lat=t.lat, lon=t.lon, altitude_m=t.altitude_m, payload_kg=t.payload_kg)


def to_obstacle(o: models.Obstacle) -> Obstacle:
    return Obstacle(lat=o.lat, lon=o.lon, radius_m=o.radius_m, id=o.id)


class PlanningService:
    def __init__(self, settings: Settings, predictor: EnergyEstimator, planner: PathPlanner) -> None:
        self.settings = settings
        self.predictor = predictor
        self.planner = planner
        self.env = Environment(settings.wind_speed_ms, settings.wind_to_deg)

    # ------------------------------------------------------------------ helpers
    def allocate(self, drones: list[DroneState], tasks: list[Task], strategy: str) -> AllocationResult:
        # The predictor is passed for both strategies: the baseline ignores it for its *costs* but
        # uses it to report comparable predicted energies.
        return ai_allocate(drones, tasks, strategy, self.predictor, self.env, self.settings.reserve_pct)

    def return_energy_pct(self, drone: DroneState, lat: float, lon: float, alt_m: float) -> float:
        return leg_energy(drone, (lat, lon, alt_m), (drone.home_lat, drone.home_lon, 0.0), 0.0,
                          self.env, self.predictor)

    def build_routes(self, drones: list[DroneState], per_drone: dict[int, list[int]],
                     tasks_by_id: dict[int, Task], obstacles: list[Obstacle]) -> list[DroneRoute]:
        routes = []
        for d in drones:
            ids = per_drone.get(d.id, [])
            if not ids:
                continue
            route = DroneRoute(drone_id=d.id)
            cur = (d.home_lat, d.home_lon)
            for tid in ids:
                t = tasks_by_id[tid]
                res = self.planner.plan(cur, (t.lat, t.lon), obstacles)
                if res.path is None:
                    route.skipped.append((tid, f"no obstacle-free route: {res.reason}"))
                    continue
                route.legs.append(Leg(tid, (t.lat, t.lon), t.altitude_m, t.payload_kg, res.path))
                cur = (t.lat, t.lon)
            back = self.planner.plan(cur, (d.home_lat, d.home_lon), obstacles)
            if back.path is None:  # home enclosed by obstacles: fall back to a direct line
                log.warning("no obstacle-free route home for drone %s", d.id)
            route.home_path = back.path or [cur, (d.home_lat, d.home_lon)]
            routes.append(route)
        return routes

    @staticmethod
    def _route_out(route: DroneRoute, names: dict[int, str]) -> schemas.RouteOut:
        return schemas.RouteOut(drone_id=route.drone_id, drone_name=names[route.drone_id],
                                task_ids=[leg.task_id for leg in route.legs],
                                polyline=route.polyline, length_m=round(route.length_m, 1))

    def _load(self, db: Session, mission_id: int):
        mission = MissionRepository(db).get(mission_id)
        if mission is None:
            raise PlanningError(f"mission {mission_id} not found", 404)
        if mission.status == "running":
            raise PlanningError("mission is running; stop it before re-planning", 409)
        drones = [d for d in DroneRepository(db).list() if d.status != "flying"]
        if not drones:
            raise PlanningError("no drones available: register a drone first")
        return mission, drones

    # ------------------------------------------------------------------ use cases
    def plan(self, db: Session, mission_id: int, strategy: str) -> schemas.PlanOut:
        mission, drone_rows = self._load(db, mission_id)
        repo = MissionRepository(db)
        drones = [to_state(d) for d in drone_rows]
        tasks = [to_task(t) for t in mission.tasks]
        tasks_by_id = {t.id: t for t in tasks}
        obstacles = [to_obstacle(o) for o in repo.obstacles(mission_id)]

        result = self.allocate(drones, tasks, strategy)
        routes = self.build_routes(drones, result.per_drone, tasks_by_id, obstacles)

        # A task whose obstacle-free route does not exist cannot be flown: report it as unassigned.
        unroutable = {tid: reason for r in routes for tid, reason in r.skipped}
        energy_by_task = {a.task_id: a for a in result.assignments}
        rows = []
        for r in routes:
            for order, leg in enumerate(r.legs):
                a = energy_by_task[leg.task_id]
                rows.append(dict(drone_id=r.drone_id, task_id=leg.task_id, order=order,
                                 predicted_energy_pct=round(a.predicted_energy_pct, 3)))
        saved = repo.replace_assignments(mission_id, rows)
        repo.set_status(mission_id, "planned", strategy)

        names = {d.id: d.name for d in drones}
        unassigned = [schemas.UnassignedOut(task_id=u.task_id, reason=u.reason) for u in result.unassigned]
        unassigned += [schemas.UnassignedOut(task_id=t, reason=r) for t, r in unroutable.items()]
        total = sum(a.predicted_energy_pct for a in saved)
        log.info("planned mission=%s strategy=%s assigned=%d unassigned=%d", mission_id, strategy,
                 len(saved), len(unassigned))
        return schemas.PlanOut(
            mission_id=mission_id, strategy=strategy, model=self.predictor.model_name,
            assignments=[schemas.AssignmentOut.model_validate(a) for a in saved],
            routes=[self._route_out(r, names) for r in routes],
            total_energy_pct=round(result.total_energy_pct, 2), unassigned=unassigned)

    def compare(self, db: Session, mission_id: int) -> schemas.CompareOut:
        mission, drone_rows = self._load(db, mission_id)
        drones = [to_state(d) for d in drone_rows]
        tasks = [to_task(t) for t in mission.tasks]
        out: dict[str, schemas.StrategyResult] = {}
        for strategy in ("ml", "baseline"):
            res = self.allocate(drones, tasks, strategy)
            actual = evaluate_allocation(res, drones, tasks, self.env, self.settings.reserve_pct)
            out[strategy] = schemas.StrategyResult(
                strategy=strategy,
                assignments=[schemas.AssignmentOut(drone_id=a.drone_id, task_id=a.task_id, order=a.order,
                                                   predicted_energy_pct=round(a.predicted_energy_pct, 3))
                             for a in res.assignments],
                predicted_energy_pct=round(res.total_energy_pct, 2),
                actual_energy_pct=round(actual["total_energy_pct"], 2),
                infeasible_assignments=actual["infeasible_assignments"],
                assigned=actual["assigned"], unassigned=actual["unassigned"])
        ml, base = out["ml"], out["baseline"]
        saving = (base.actual_energy_pct - ml.actual_energy_pct) / base.actual_energy_pct * 100 \
            if base.actual_energy_pct else 0.0
        return schemas.CompareOut(
            mission_id=mission_id, model=self.predictor.model_name, ml=ml, baseline=base,
            energy_saving_pct=round(saving, 2),
            infeasible_avoided=base.infeasible_assignments - ml.infeasible_assignments)

    def mission_detail(self, db: Session, mission_id: int) -> schemas.MissionDetail:
        repo = MissionRepository(db)
        mission = repo.get(mission_id)
        if mission is None:
            raise PlanningError(f"mission {mission_id} not found", 404)
        assignments = repo.assignments(mission_id)
        obstacles = repo.obstacles(mission_id)
        routes: list[schemas.RouteOut] = []
        if assignments:
            drones = [to_state(d) for d in DroneRepository(db).list()]
            per_drone: dict[int, list[int]] = {}
            for a in assignments:  # already ordered by (drone, order)
                per_drone.setdefault(a.drone_id, []).append(a.task_id)
            tasks_by_id = {t.id: to_task(t) for t in mission.tasks}
            names = {d.id: d.name for d in drones}
            routes = [self._route_out(r, names) for r in self.build_routes(
                drones, per_drone, tasks_by_id, [to_obstacle(o) for o in obstacles])]
        return schemas.MissionDetail(
            mission=schemas.MissionOut.model_validate(mission),
            tasks=[schemas.TaskOut.model_validate(t) for t in mission.tasks],
            assignments=[schemas.AssignmentOut.model_validate(a) for a in assignments],
            obstacles=[schemas.ObstacleOut.model_validate(o) for o in obstacles], routes=routes)
