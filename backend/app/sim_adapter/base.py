"""The contract between the mission runtime and whatever flies the drones.

`MockAdapter` implements it with simple kinematics so the whole platform runs on a laptop.
`MavlinkAdapter` is the stub where the PX4 + Gazebo integration will plug in later. The runtime
only ever talks to this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ai.types import DroneState


@dataclass
class Telemetry:
    drone_id: int
    lat: float
    lon: float
    alt_m: float
    battery_pct: float
    heading_deg: float
    speed_ms: float
    armed: bool
    arrived: bool  # True once the last `goto` target has been reached


class DroneAdapter(ABC):
    @abstractmethod
    def connect(self, drone: DroneState) -> None:
        """Register / connect a vehicle at its home position."""

    @abstractmethod
    def arm(self, drone_id: int) -> None:
        """Arm the motors."""

    @abstractmethod
    def goto(self, drone_id: int, lat: float, lon: float, alt_m: float) -> None:
        """Fly to a position (non-blocking). `Telemetry.arrived` turns True when it is reached."""

    @abstractmethod
    def get_telemetry(self, drone_id: int) -> Telemetry:
        """Latest position, battery and status."""

    @abstractmethod
    def return_to_launch(self, drone_id: int) -> None:
        """Fly straight home and land (the runtime normally sends obstacle-free A* waypoints)."""

    # ---- optional hooks (defaults are no-ops / unsupported) ----
    def step(self, dt_s: float) -> None:
        """Advance the simulation clock. Real vehicles fly on their own, so this is a no-op."""

    def set_payload(self, drone_id: int, payload_kg: float) -> None:
        """Tell a simulator how much payload the vehicle carries (real vehicles just carry it)."""

    def inject_battery_fault(self, drone_id: int, pct: float) -> None:
        raise NotImplementedError("battery fault injection is only available in the simulator")
