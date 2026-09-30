"""Mission runtime: drives drones through the FSM on a simulated clock.

Each tick:  adapter.step(dt)  ->  per drone: read telemetry, advance waypoints, run the simulated
LiDAR, evaluate the FSM (`ai.fsm.next_state`) and perform the entry action of any new state
(arm, take off, follow a leg, replan around an obstacle, return to launch ...).

The adapter only moves vehicles and drains batteries; all decisions live here, so replacing
`MockAdapter` with a PX4/Gazebo adapter does not change this module.
"""
from __future__ import annotations

import logging
import math
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from ai.fsm import ACTIVE_FLIGHT, TERMINAL, FsmContext, State, next_state
from ai.geo import haversine_m
from ai.interfaces import PathPlanner
from ai.obstacles import DETECTION_THRESHOLD_M, detect, lidar_scan, obstacles_within
from ai.types import DroneState, Obstacle
from app import models
from app.config import Settings
from app.repositories import DroneRepository, MissionRepository
from app.services.planning_service import Leg, PlanningError, PlanningService, to_obstacle, to_state, to_task
from app.sim_adapter.base import DroneAdapter, Telemetry

log = logging.getLogger("aeromind.runtime")

PERSIST_EVERY_TICKS = 4
MIN_RTL_ALT_M = 10.0


@dataclass
class _Run:
    """Supervisor state for one participating drone."""

    ai: DroneState
    legs: list[Leg]
    home_path: list[tuple[float, float]]
    state: State = State.IDLE
    leg_idx: int = 0
    wp_idx: int = 1
    known: set[int] = field(default_factory=set)
    arrived_task: bool = False
    altitude_ok: bool = False
    dwell_left: float = 0.0
    landing: bool = False
    landed: bool = False
    route_ok: bool = True
    replan_done: bool = False
    rtl_path: list[tuple[float, float]] = field(default_factory=list)
    rtl_alt: float = MIN_RTL_ALT_M
    tasks_done: int = 0
    tasks_total: int = 0
    tel: Telemetry | None = None
    lidar_min_m: float = 60.0


def _path_len(pts: list[tuple[float, float]]) -> float:
    return sum(haversine_m(a[0], a[1], b[0], b[1]) for a, b in zip(pts, pts[1:]))


class RuntimeService:
    def __init__(self, settings: Settings, session_factory: sessionmaker[Session],
                 planning: PlanningService, adapter_factory: Callable[[], DroneAdapter]) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.planning = planning
        self.planner: PathPlanner = planning.planner
        self.adapter_factory = adapter_factory
        self._lock = threading.RLock()
        self._events: deque = deque(maxlen=500)
        self._event_seq = 0
        self._reset_run_state()

    # ------------------------------------------------------------------ state
    def _reset_run_state(self) -> None:
        self.running = False
        self.mission_id: int | None = None
        self.mission_status = "idle"
        self.sim_time = 0.0
        self.adapter: DroneAdapter | None = None
        self.runs: dict[int, _Run] = {}
        self.idle_drones: list[dict] = []
        self.world_obstacles: list[Obstacle] = []
        self._stop_requested = False
        self._tick_count = 0
        self._new_events: list[dict] = []

    @property
    def dt_sim(self) -> float:
        return self.settings.tick_s * self.settings.speedup

    # ------------------------------------------------------------------ events
    def _emit(self, run: _Run | None, message: str, level: str = "info") -> None:
        self._event_seq += 1
        ev = {
            "id": self._event_seq,
            "ts": datetime.now(timezone.utc).isoformat(),
            "sim_time_s": round(self.sim_time, 1),
            "drone_id": run.ai.id if run else None,
            "drone_name": run.ai.name if run else "Command",
            "level": level,
            "message": message,
        }
        self._events.append(ev)
        self._new_events.append(ev)
        log.info("event drone=%s level=%s %s", ev["drone_id"], level, message)

    def history(self, n: int = 100) -> list[dict]:
        with self._lock:
            return list(self._events)[-n:]

    # ------------------------------------------------------------------ commands
    def start(self, mission_id: int) -> dict:
        with self._lock:
            if self.running:
                raise PlanningError("a mission is already running", 409)
            with self.session_factory() as db:
                repo = MissionRepository(db)
                mission = repo.get(mission_id)
                if mission is None:
                    raise PlanningError(f"mission {mission_id} not found", 404)
                assignments = repo.assignments(mission_id)
                if not assignments:
                    raise PlanningError("plan the mission before starting it")
                drone_rows = DroneRepository(db).list()
                obstacles = [to_obstacle(o) for o in repo.obstacles(mission_id)]
                tasks_by_id = {t.id: to_task(t) for t in mission.tasks}
                drones = [to_state(d) for d in drone_rows]
                per_drone: dict[int, list[int]] = {}
                for a in assignments:
                    per_drone.setdefault(a.drone_id, []).append(a.task_id)
                routes = self.planning.build_routes(drones, per_drone, tasks_by_id, obstacles)
                mission_name = mission.name

            self._reset_run_state()
            self.mission_id = mission_id
            self.adapter = self.adapter_factory()
            self.world_obstacles = list(obstacles)
            by_id = {d.id: d for d in drones}
            flying = {r.drone_id: r for r in routes if r.legs}
            for d in drones:
                self.adapter.connect(d)
                if d.id in flying:
                    r = flying[d.id]
                    run = _Run(ai=d, legs=r.legs, home_path=r.home_path, tasks_total=len(r.legs),
                               known={o.id for o in obstacles})
                    run.state = State.IDLE
                    self.runs[d.id] = run
                else:
                    self.idle_drones.append(self._drone_dict_idle(d))
            if not self.runs:
                raise PlanningError("no drone has a flyable route; re-plan the mission")
            self.running = True
            self.mission_status = "running"
            self._emit(None, f"Mission '{mission_name}' started with {len(self.runs)} drone(s)")
            with self.session_factory() as db:
                MissionRepository(db).set_status(mission_id, "running")
                DroneRepository(db).set_status(self.runs.keys(), "flying")
            log.info("mission %s started", mission_id)
            return self.snapshot()

    def stop(self) -> dict:
        with self._lock:
            if not self.running:
                return self.snapshot()
            self._stop_requested = True
            self._emit(None, "Stop command received: all drones returning to launch", "warn")
            return self.snapshot()

    def inject_obstacle(self, mission_id: int, row: models.Obstacle) -> None:
        """Add an obstacle to the simulated world. Drones only learn about it through their LiDAR."""
        with self._lock:
            if self.running and self.mission_id == mission_id:
                self.world_obstacles.append(to_obstacle(row))
                self._emit(None, f"Obstacle #{row.id} injected ({row.radius_m:.0f} m radius) - "
                                 "drones will detect it with LiDAR", "warn")

    def is_running(self, mission_id: int | None = None) -> bool:
        with self._lock:
            return self.running and (mission_id is None or self.mission_id == mission_id)

    def drain_battery(self, drone_id: int, pct: float) -> None:
        with self._lock:
            run = self.runs.get(drone_id)
            if not self.running or run is None:
                raise PlanningError("drone is not flying a mission", 409)
            self.adapter.inject_battery_fault(drone_id, pct)
            self._emit(run, f"Battery fault injected: -{pct:.0f}%", "warn")

    # ------------------------------------------------------------------ clock
    def tick(self) -> dict:
        with self._lock:
            if not self.running:
                return self.snapshot()
            dt = self.dt_sim
            self.sim_time += dt
            self._tick_count += 1
            self.adapter.step(dt)
            for run in self.runs.values():
                if run.state not in TERMINAL:
                    self._supervise(run, dt)
                else:
                    run.tel = self.adapter.get_telemetry(run.ai.id)
            if self._tick_count % PERSIST_EVERY_TICKS == 0:
                self._persist_telemetry()
            if all(r.state in TERMINAL for r in self.runs.values()):
                self._finish()
            return self.snapshot(consume_events=True)

    def _finish(self) -> None:
        self.running = False
        failed = [r for r in self.runs.values() if r.state == State.FAILSAFE]
        self.mission_status = "stopped" if self._stop_requested else "completed"
        summary = f"Mission {self.mission_status}: " + ", ".join(
            f"{r.ai.name} {r.state.value} ({r.tasks_done}/{r.tasks_total} tasks, {r.tel.battery_pct:.0f}% battery)"
            for r in self.runs.values())
        self._emit(None, summary, "alert" if failed else "info")
        with self.session_factory() as db:
            MissionRepository(db).set_status(self.mission_id, self.mission_status)
            DroneRepository(db).set_status(self.runs.keys(), "idle")
        self._persist_telemetry()

    def _persist_telemetry(self) -> None:
        rows = [dict(drone_id=r.ai.id, lat=r.tel.lat, lon=r.tel.lon, alt=r.tel.alt_m,
                     battery_pct=r.tel.battery_pct, state=r.state.value)
                for r in self.runs.values() if r.tel is not None]
        if rows:
            with self.session_factory() as db:
                MissionRepository(db).add_telemetry(rows)

    # ------------------------------------------------------------------ per-drone supervision
    def _supervise(self, r: _Run, dt: float) -> None:
        tel = self.adapter.get_telemetry(r.ai.id)
        r.tel = tel
        self._progress(r, tel, dt)

        r.lidar_min_m, unknown_min = self._lidar(r, tel)
        if r.state == State.RETURN_TO_LAUNCH and unknown_min < DETECTION_THRESHOLD_M and not r.landing:
            self._reroute_rtl(r, tel)

        airborne = r.state in ACTIVE_FLIGHT
        ctx = FsmContext(
            mission_started=True,
            mission_stopped=self._stop_requested,
            altitude_reached=r.altitude_ok,
            at_task_waypoint=r.arrived_task,
            task_complete=r.state == State.EXECUTING_TASK and r.dwell_left <= 0,
            tasks_remaining=self._remaining(r),
            at_home=r.landed,
            battery_pct=tel.battery_pct,
            return_energy_pct=self.planning.return_energy_pct(r.ai, tel.lat, tel.lon, tel.alt_m) if airborne else 0.0,
            reserve_pct=self.settings.reserve_pct,
            min_range_m=unknown_min if r.state == State.EN_ROUTE else math.inf,
            obstacle_threshold_m=DETECTION_THRESHOLD_M,
            route_available=r.route_ok,
            replan_done=r.replan_done,
        )
        new_state, event = next_state(r.state, ctx)
        if new_state != r.state:
            self._transition(r, new_state, event, tel)

    @staticmethod
    def _remaining(r: _Run) -> int:
        done = r.leg_idx + (1 if r.state == State.EXECUTING_TASK else 0)
        return max(len(r.legs) - done, 0)

    def _lidar(self, r: _Run, tel: Telemetry) -> tuple[float, float]:
        """Return (closest return over all obstacles, closest return from not-yet-mapped obstacles)."""
        if r.state not in ACTIVE_FLIGHT and r.state != State.RETURN_TO_LAUNCH:
            return 60.0, math.inf
        all_min = float(lidar_scan(tel.lat, tel.lon, tel.heading_deg, self.world_obstacles).min())
        unknown = [o for o in self.world_obstacles if o.id not in r.known]
        if not unknown:
            return all_min, math.inf
        det = detect(lidar_scan(tel.lat, tel.lon, tel.heading_deg, unknown), tel.heading_deg)
        return all_min, det.min_range_m

    def _progress(self, r: _Run, tel: Telemetry, dt: float) -> None:
        """Advance waypoints / timers from the latest telemetry."""
        aid = r.ai.id
        if r.state == State.TAKEOFF:
            r.altitude_ok = tel.arrived
        elif r.state == State.EN_ROUTE and tel.arrived and not r.arrived_task:
            leg = r.legs[r.leg_idx]
            r.wp_idx += 1
            if r.wp_idx < len(leg.path):
                self.adapter.goto(aid, *leg.path[r.wp_idx], leg.alt_m)
            else:
                r.arrived_task = True
        elif r.state == State.EXECUTING_TASK:
            r.dwell_left -= dt
        elif r.state == State.RETURN_TO_LAUNCH and tel.arrived:
            if r.landing:
                r.landed = True
            else:
                r.wp_idx += 1
                if r.wp_idx < len(r.rtl_path):
                    self.adapter.goto(aid, *r.rtl_path[r.wp_idx], r.rtl_alt)
                else:
                    self._begin_landing(r)

    def _begin_landing(self, r: _Run) -> None:
        r.landing = True
        self.adapter.goto(r.ai.id, r.ai.home_lat, r.ai.home_lon, 0.0)

    # ------------------------------------------------------------------ transitions
    def _transition(self, r: _Run, new: State, event: str | None, tel: Telemetry) -> None:
        old, r.state = r.state, new
        level = {State.AVOIDING: "warn", State.RETURN_TO_LAUNCH: "warn", State.FAILSAFE: "alert"}.get(new, "info")
        if event:
            self._emit(r, f"{old.value} -> {new.value}: {event}", level)
        aid = r.ai.id
        if new == State.ARMED:
            self.adapter.arm(aid)
        elif new == State.TAKEOFF:
            r.altitude_ok = False
            self.adapter.goto(aid, r.ai.home_lat, r.ai.home_lon, r.legs[0].alt_m)
        elif new == State.EN_ROUTE:
            if old == State.EXECUTING_TASK:
                r.leg_idx += 1
            if old != State.AVOIDING:
                r.wp_idx = 1
            r.replan_done = False
            r.arrived_task = False
            leg = r.legs[r.leg_idx]
            self.adapter.set_payload(aid, leg.payload_kg)
            if r.wp_idx < len(leg.path):
                self.adapter.goto(aid, *leg.path[r.wp_idx], leg.alt_m)
            else:
                r.arrived_task = True
        elif new == State.EXECUTING_TASK:
            r.arrived_task = False
            r.dwell_left = self.settings.task_dwell_s
            r.tasks_done += 1
            self.adapter.set_payload(aid, 0.0)
        elif new == State.AVOIDING:
            self.adapter.goto(aid, tel.lat, tel.lon, tel.alt_m)  # hold position while replanning
            self._replan(r, tel)
        elif new == State.RETURN_TO_LAUNCH:
            self.adapter.set_payload(aid, 0.0)
            self._start_rtl(r, tel)
        elif new == State.FAILSAFE:
            self.adapter.goto(aid, tel.lat, tel.lon, 0.0)  # emergency landing in place

    def _known_obstacles(self, r: _Run) -> list[Obstacle]:
        return [o for o in self.world_obstacles if o.id in r.known]

    def _replan(self, r: _Run, tel: Telemetry) -> None:
        """LiDAR detected an unmapped obstacle: add it to the drone's map and re-route A*."""
        unknown = [o for o in self.world_obstacles if o.id not in r.known]
        seen = obstacles_within(tel.lat, tel.lon, unknown, DETECTION_THRESHOLD_M)
        r.known.update(o.id for o in seen)
        obstacles = self._known_obstacles(r)
        current = r.legs[r.leg_idx]
        old_len = _path_len([(tel.lat, tel.lon)] + current.path[r.wp_idx:])

        here = (tel.lat, tel.lon)
        res = self.planner.plan(here, current.target, obstacles)
        if res.path is None:
            r.route_ok = False
            self._emit(r, f"Replan failed ({res.reason})", "alert")
            return
        current.path = res.path
        cur = current.target
        kept = [current]
        for leg in r.legs[r.leg_idx + 1:]:  # later tasks are re-routed; unreachable ones are dropped
            nxt = self.planner.plan(cur, leg.target, obstacles)
            if nxt.path is None:
                self._emit(r, f"Task {leg.task_id} unreachable after obstacle ({nxt.reason}): skipped", "warn")
                continue
            leg.path = nxt.path
            kept.append(leg)
            cur = leg.target
        r.legs = r.legs[:r.leg_idx] + kept
        r.tasks_total = len(r.legs)
        back = self.planner.plan(cur, (r.ai.home_lat, r.ai.home_lon), obstacles)
        if back.path:
            r.home_path = back.path
        r.wp_idx = 1
        r.replan_done = True
        self._emit(r, f"Replanned A* route: {len(res.path)} waypoints, {res.length_m:.0f} m "
                      f"({res.length_m - old_len:+.0f} m vs previous route), {len(seen)} obstacle(s) mapped")

    def _start_rtl(self, r: _Run, tel: Telemetry) -> None:
        home = (r.ai.home_lat, r.ai.home_lon)
        res = self.planner.plan((tel.lat, tel.lon), home, self._known_obstacles(r))
        if res.path is None:
            r.route_ok = False
            self._emit(r, f"No route home ({res.reason})", "alert")
            return
        r.rtl_path, r.wp_idx, r.landing = res.path, 1, False
        r.rtl_alt = max(tel.alt_m, MIN_RTL_ALT_M)
        if len(res.path) > 1:
            self.adapter.goto(r.ai.id, *res.path[1], r.rtl_alt)
        else:
            self._begin_landing(r)

    def _reroute_rtl(self, r: _Run, tel: Telemetry) -> None:
        unknown = [o for o in self.world_obstacles if o.id not in r.known]
        seen = obstacles_within(tel.lat, tel.lon, unknown, DETECTION_THRESHOLD_M)
        r.known.update(o.id for o in seen)
        self._emit(r, "LiDAR: obstacle on the return path, re-routing home", "warn")
        self._start_rtl(r, tel)

    # ------------------------------------------------------------------ snapshots
    def _remaining_route(self, r: _Run) -> list[list[float]]:
        if r.tel is None or r.state in TERMINAL:
            return []
        pts: list[tuple[float, float]] = [(r.tel.lat, r.tel.lon)]
        if r.state == State.RETURN_TO_LAUNCH:
            pts += [] if r.landing else r.rtl_path[r.wp_idx:]
        else:
            for k in range(r.leg_idx, len(r.legs)):
                if k == r.leg_idx and r.state == State.EXECUTING_TASK:
                    continue
                path = r.legs[k].path
                first = r.wp_idx if (k == r.leg_idx and r.state in (State.EN_ROUTE, State.AVOIDING)) else 1
                pts += path[first:]
            pts += r.home_path[1:]
        return [[round(la, 6), round(lo, 6)] for la, lo in pts]

    def _drone_dict_idle(self, d: DroneState) -> dict:
        return {"id": d.id, "name": d.name, "type": d.type, "lat": d.home_lat, "lon": d.home_lon,
                "alt_m": 0.0, "battery_pct": round(d.battery_pct, 1), "state": State.IDLE.value,
                "heading_deg": 0.0, "current_task_id": None, "lidar_min_m": None, "route": [],
                "tasks_done": 0, "tasks_total": 0}

    def _drone_dict(self, r: _Run) -> dict:
        t = r.tel
        if t is None:
            return self._drone_dict_idle(r.ai) | {"tasks_total": r.tasks_total}
        task_id = r.legs[r.leg_idx].task_id if r.state in (State.EN_ROUTE, State.AVOIDING, State.EXECUTING_TASK) \
            and r.leg_idx < len(r.legs) else None
        return {"id": r.ai.id, "name": r.ai.name, "type": r.ai.type, "lat": round(t.lat, 6),
                "lon": round(t.lon, 6), "alt_m": round(t.alt_m, 1), "battery_pct": round(t.battery_pct, 1),
                "state": r.state.value, "heading_deg": round(t.heading_deg, 1), "current_task_id": task_id,
                "lidar_min_m": round(r.lidar_min_m, 1), "route": self._remaining_route(r),
                "tasks_done": r.tasks_done, "tasks_total": r.tasks_total}

    def _idle_from_db(self) -> list[dict]:
        with self.session_factory() as db:
            return [self._drone_dict_idle(to_state(d)) for d in DroneRepository(db).list()]

    def snapshot(self, with_history: bool = False, consume_events: bool = False) -> dict:
        with self._lock:
            if self.runs:
                drones = [self._drone_dict(r) for r in self.runs.values()] + list(self.idle_drones)
                drones.sort(key=lambda d: d["id"])
            else:
                drones = self._idle_from_db()
            snap = {
                "type": "snapshot" if with_history else "tick",
                "ts": datetime.now(timezone.utc).isoformat(),
                "mission_id": self.mission_id,
                "mission_status": self.mission_status,
                "running": self.running,
                "sim_time_s": round(self.sim_time, 1),
                "speedup": self.settings.speedup,
                "drones": drones,
                "obstacles": [{"id": o.id, "lat": o.lat, "lon": o.lon, "radius_m": o.radius_m}
                              for o in self.world_obstacles],
                "events": self.history(100) if with_history else list(self._new_events),
            }
            if consume_events:
                self._new_events = []
            return snap
