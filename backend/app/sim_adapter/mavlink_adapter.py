"""Placeholder for the PX4 / Gazebo integration (next milestone)."""
from __future__ import annotations

from ai.types import DroneState
from app.sim_adapter.base import DroneAdapter, Telemetry

_MSG = (
    "MavlinkAdapter is a stub. The PX4 + Gazebo (MAVLink) simulation is the next milestone; "
    "use MockAdapter for now."
)


class MavlinkAdapter(DroneAdapter):
    """Adapter for real PX4 SITL / hardware over MAVLink. NOT IMPLEMENTED in the 30% build.

    Planned mapping once the simulation is wired in (pymavlink or MAVSDK-Python):

    * ``connect``            open ``udp:127.0.0.1:14540 + instance`` and wait for a heartbeat
    * ``arm``                ``MAV_CMD_COMPONENT_ARM_DISARM`` (param1 = 1)
    * ``goto``               offboard / guided ``SET_POSITION_TARGET_GLOBAL_INT``
    * ``get_telemetry``      ``GLOBAL_POSITION_INT`` + ``BATTERY_STATUS`` + ``HEARTBEAT``
    * ``return_to_launch``   ``MAV_CMD_NAV_RETURN_TO_LAUNCH``
    * LiDAR                  Gazebo ``gpu_lidar`` / distance sensor topic fed into ``ai.obstacles.detect``

    The mission runtime, FSM, allocation and A* planner need no change: they only use `DroneAdapter`.
    """

    def connect(self, drone: DroneState) -> None:
        raise NotImplementedError(_MSG)

    def arm(self, drone_id: int) -> None:
        raise NotImplementedError(_MSG)

    def goto(self, drone_id: int, lat: float, lon: float, alt_m: float) -> None:
        raise NotImplementedError(_MSG)

    def get_telemetry(self, drone_id: int) -> Telemetry:
        raise NotImplementedError(_MSG)

    def return_to_launch(self, drone_id: int) -> None:
        raise NotImplementedError(_MSG)
