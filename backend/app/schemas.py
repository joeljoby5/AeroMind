"""Pydantic v2 request / response models."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DroneType = Literal["quad_small", "quad_medium", "hex_heavy"]
Strategy = Literal["ml", "baseline"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- drones ----
class DroneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    type: DroneType
    battery_pct: float = Field(default=100.0, ge=0, le=100)
    health: float = Field(default=1.0, ge=0.7, le=1.0)
    home_lat: float = Field(ge=-90, le=90)
    home_lon: float = Field(ge=-180, le=180)


class DroneOut(ORM):
    id: int
    name: str
    type: str
    battery_pct: float
    health: float
    home_lat: float
    home_lon: float
    status: str


# ---- missions ----
class TaskIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    altitude_m: float = Field(default=30.0, ge=5, le=120)
    payload_kg: float = Field(default=0.0, ge=0, le=2.5)


class MissionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    tasks: list[TaskIn] = Field(min_length=1, max_length=50)


class TaskOut(ORM):
    id: int
    lat: float
    lon: float
    altitude_m: float
    payload_kg: float


class MissionOut(ORM):
    id: int
    name: str
    status: str
    strategy: str | None
    created_at: datetime


class AssignmentOut(ORM):
    drone_id: int
    task_id: int
    order: int
    predicted_energy_pct: float


class ObstacleIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_m: float = Field(default=30.0, ge=10, le=300)


class ObstacleOut(ORM):
    id: int
    lat: float
    lon: float
    radius_m: float


class RouteOut(BaseModel):
    drone_id: int
    drone_name: str
    task_ids: list[int]
    polyline: list[tuple[float, float]]  # home -> tasks -> home, as [lat, lon]
    length_m: float


class UnassignedOut(BaseModel):
    task_id: int
    reason: str


class PlanOut(BaseModel):
    mission_id: int
    strategy: Strategy
    model: str
    assignments: list[AssignmentOut]
    routes: list[RouteOut]
    total_energy_pct: float
    unassigned: list[UnassignedOut]


class MissionDetail(BaseModel):
    mission: MissionOut
    tasks: list[TaskOut]
    assignments: list[AssignmentOut]
    obstacles: list[ObstacleOut]
    routes: list[RouteOut]


class StrategyResult(BaseModel):
    strategy: Strategy
    assignments: list[AssignmentOut]
    predicted_energy_pct: float  # what the planner expected
    actual_energy_pct: float  # physics ground truth for the same assignment
    infeasible_assignments: int  # legs the drone could not fly, return from and keep the reserve
    assigned: int
    unassigned: int


class CompareOut(BaseModel):
    mission_id: int
    model: str
    ml: StrategyResult
    baseline: StrategyResult
    energy_saving_pct: float  # (baseline - ml) / baseline * 100 on actual energy
    infeasible_avoided: int


# ---- AI ----
class PredictIn(BaseModel):
    drone_type: DroneType
    distance_m: float = Field(gt=0, le=20000)
    altitude_change_m: float = Field(default=0.0, ge=-200, le=300)
    payload_kg: float = Field(default=0.0, ge=0, le=5)
    wind_speed_ms: float = Field(default=0.0, ge=0, le=30)
    wind_alignment: float = Field(default=0.0, ge=-1, le=1)
    battery_health: float = Field(default=1.0, ge=0.5, le=1.0)
    cruise_speed_ms: float = Field(default=10.0, ge=1, le=30)


class PredictOut(BaseModel):
    energy_pct: float
    model: str
    is_fallback: bool
