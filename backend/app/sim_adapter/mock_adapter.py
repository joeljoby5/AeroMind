"""Kinematic drone simulator behind the `DroneAdapter` interface.

Each drone flies in a straight line to its current `goto` target at cruise speed and climbs at a
fixed vertical rate. Battery drains with the SAME energy model the planner uses: the per-metre
rate for the current leg is the marginal slope of the model's energy-vs-distance curve for that
drone, payload, wind and heading, with small Gaussian noise. Hovering has a small constant drain.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from ai.energy_model.features import DEFAULT_CRUISE_SPEED_MS, Environment, leg_features
from ai.geo import bearing_deg, haversine_m, move_towards
from ai.interfaces import EnergyEstimator
from ai.types import DroneState
from app.sim_adapter.base import DroneAdapter, Telemetry

TAKEOFF_OVERHEAD_PCT = 0.5  # the model's constant take-off / landing overhead, paid at arming
HOVER_DRAIN_PCT_PER_S = 0.015
CLIMB_RATE_MS = 3.0
ARRIVE_TOL_M = 0.75
_REF_NEAR_M, _REF_FAR_M = 400.0, 1200.0


@dataclass
class _Sim:
    spec: DroneState
    lat: float
    lon: float
    alt: float = 0.0
    battery: float = 100.0
    speed: float = 10.0
    heading: float = 0.0
    armed: bool = False
    payload_kg: float = 0.0
    target: tuple[float, float, float] | None = None
    rate_pct_per_m: float = 0.01
    moving: bool = False


class MockAdapter(DroneAdapter):
    def __init__(self, estimator: EnergyEstimator, env: Environment, seed: int = 42,
                 noise: float = 0.03) -> None:
        self.estimator, self.env, self.noise = estimator, env, noise
        self._rng = random.Random(seed)
        self._sims: dict[int, _Sim] = {}

    # ---- DroneAdapter ----
    def connect(self, drone: DroneState) -> None:
        speed = drone.cruise_speed_ms or DEFAULT_CRUISE_SPEED_MS[drone.type]
        self._sims[drone.id] = _Sim(spec=drone, lat=drone.lat, lon=drone.lon, alt=drone.alt_m,
                                    battery=drone.battery_pct, speed=speed)

    def arm(self, drone_id: int) -> None:
        s = self._sims[drone_id]
        s.armed = True
        s.battery = max(s.battery - TAKEOFF_OVERHEAD_PCT / s.spec.health, 0.0)

    def goto(self, drone_id: int, lat: float, lon: float, alt_m: float) -> None:
        s = self._sims[drone_id]
        s.target = (lat, lon, alt_m)
        s.rate_pct_per_m = self._drain_rate(s, lat, lon)

    def get_telemetry(self, drone_id: int) -> Telemetry:
        s = self._sims[drone_id]
        arrived = False
        if s.target is not None:
            arrived = (haversine_m(s.lat, s.lon, s.target[0], s.target[1]) <= ARRIVE_TOL_M
                       and abs(s.alt - s.target[2]) <= ARRIVE_TOL_M)
        return Telemetry(drone_id, s.lat, s.lon, s.alt, s.battery, s.heading,
                         s.speed if s.moving else 0.0, s.armed, arrived)

    def return_to_launch(self, drone_id: int) -> None:
        s = self._sims[drone_id]
        self.goto(drone_id, s.spec.home_lat, s.spec.home_lon, 0.0)

    def step(self, dt_s: float) -> None:
        for s in self._sims.values():
            self._step_one(s, dt_s)

    def set_payload(self, drone_id: int, payload_kg: float) -> None:
        self._sims[drone_id].payload_kg = payload_kg

    def inject_battery_fault(self, drone_id: int, pct: float) -> None:
        s = self._sims[drone_id]
        s.battery = max(s.battery - pct, 0.0)

    # ---- internals ----
    def _drain_rate(self, s: _Sim, lat: float, lon: float) -> float:
        """Marginal % battery per metre for the current conditions, from the energy model."""
        heading = bearing_deg(s.lat, s.lon, lat, lon) if (lat, lon) != (s.lat, s.lon) else s.heading

        def energy(dist: float) -> float:
            return self.estimator.predict(leg_features(
                drone_type=s.spec.type, battery_health=s.spec.health, cruise_speed_ms=s.speed,
                distance_m=dist, altitude_change_m=0.0, payload_kg=s.payload_kg,
                leg_bearing_deg=heading, env=self.env))

        slope = (energy(_REF_FAR_M) - energy(_REF_NEAR_M)) / (_REF_FAR_M - _REF_NEAR_M)
        return max(slope, 0.0005)

    def _step_one(self, s: _Sim, dt: float) -> None:
        s.moving = False
        if not s.armed or s.target is None:
            return
        tlat, tlon, talt = s.target
        step_m = s.speed * dt
        dist = haversine_m(s.lat, s.lon, tlat, tlon)
        moved = 0.0
        if dist > 1e-6:
            new_lat, new_lon, _ = move_towards(s.lat, s.lon, tlat, tlon, step_m)
            moved = min(step_m, dist)
            s.heading = bearing_deg(s.lat, s.lon, tlat, tlon)
            s.lat, s.lon = new_lat, new_lon
            s.moving = True
        dz = talt - s.alt
        s.alt += math.copysign(min(abs(dz), CLIMB_RATE_MS * dt), dz)
        noise = self._rng.gauss(1.0, self.noise)
        if moved > 0:
            s.battery -= s.rate_pct_per_m * moved * noise
        else:
            s.battery -= HOVER_DRAIN_PCT_PER_S * dt * noise
        s.battery = max(s.battery, 0.0)
