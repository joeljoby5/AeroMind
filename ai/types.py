"""Plain dataclasses shared by every AI module (no ORM / API coupling)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Task:
    id: int
    lat: float
    lon: float
    altitude_m: float = 30.0
    payload_kg: float = 0.0


@dataclass
class DroneState:
    id: int
    name: str
    type: str  # quad_small | quad_medium | hex_heavy
    lat: float
    lon: float
    battery_pct: float = 100.0
    health: float = 1.0  # battery health factor, 0.70 - 1.00
    home_lat: float | None = None
    home_lon: float | None = None
    alt_m: float = 0.0
    cruise_speed_ms: float | None = None  # None -> default for the drone type

    def __post_init__(self) -> None:
        if self.home_lat is None:
            self.home_lat = self.lat
        if self.home_lon is None:
            self.home_lon = self.lon


@dataclass(frozen=True)
class Obstacle:
    lat: float
    lon: float
    radius_m: float
    id: int | None = None


@dataclass(frozen=True)
class AssignedTask:
    drone_id: int
    task_id: int
    order: int  # 0-based position in the drone's ordered task list
    predicted_energy_pct: float  # energy of the leg flown to this task


@dataclass(frozen=True)
class UnassignedTask:
    task_id: int
    reason: str


@dataclass
class AllocationResult:
    strategy: str  # "ml" | "baseline"
    assignments: list[AssignedTask] = field(default_factory=list)
    per_drone: dict[int, list[int]] = field(default_factory=dict)  # drone_id -> ordered task ids
    total_energy_pct: float = 0.0  # predicted: all outbound legs + return-to-home legs
    unassigned: list[UnassignedTask] = field(default_factory=list)


@dataclass
class PathResult:
    path: list[tuple[float, float]] | None  # [(lat, lon), ...] or None if no route
    reason: str = "ok"
    length_m: float = 0.0
