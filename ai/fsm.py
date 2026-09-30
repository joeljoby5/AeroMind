"""Drone finite state machine as a pure function: ``next_state(state, context) -> (state, event)``.

States: IDLE, ARMED, TAKEOFF, EN_ROUTE, EXECUTING_TASK, AVOIDING, RETURN_TO_LAUNCH, LANDED, FAILSAFE.

Transition table (evaluated top to bottom, first match wins)::

    IDLE              --mission_started-->                        ARMED
    ARMED             --mission_stopped-->                        LANDED
    ARMED             --no route-->                               FAILSAFE
    ARMED             --(always)-->                               TAKEOFF
    any flight state  --no route (path blocked, replan failed)--> FAILSAFE
    TAKEOFF..AVOIDING --battery < return energy + reserve-->      RETURN_TO_LAUNCH
    TAKEOFF..AVOIDING --mission_stopped-->                        RETURN_TO_LAUNCH
    TAKEOFF           --altitude_reached-->                       EN_ROUTE (or RTL if no tasks)
    EN_ROUTE          --LiDAR range < threshold-->                AVOIDING
    EN_ROUTE          --at_task_waypoint-->                       EXECUTING_TASK
    EXECUTING_TASK    --task_complete-->                          EN_ROUTE (or RTL if none left)
    AVOIDING          --replan_done-->                            EN_ROUTE
    RETURN_TO_LAUNCH  --at_home-->                                LANDED

LANDED and FAILSAFE are terminal. Every transition returns a human-readable event string for the
dashboard log; when nothing changes the event is ``None``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class State(str, Enum):
    IDLE = "IDLE"
    ARMED = "ARMED"
    TAKEOFF = "TAKEOFF"
    EN_ROUTE = "EN_ROUTE"
    EXECUTING_TASK = "EXECUTING_TASK"
    AVOIDING = "AVOIDING"
    RETURN_TO_LAUNCH = "RETURN_TO_LAUNCH"
    LANDED = "LANDED"
    FAILSAFE = "FAILSAFE"


ACTIVE_FLIGHT = (State.TAKEOFF, State.EN_ROUTE, State.EXECUTING_TASK, State.AVOIDING)
TERMINAL = (State.LANDED, State.FAILSAFE)


@dataclass
class FsmContext:
    mission_started: bool = False
    mission_stopped: bool = False
    altitude_reached: bool = False
    at_task_waypoint: bool = False
    task_complete: bool = False
    tasks_remaining: int = 0
    at_home: bool = False
    battery_pct: float = 100.0
    return_energy_pct: float = 0.0  # predicted energy to fly home from the current position
    reserve_pct: float = 15.0
    min_range_m: float = math.inf  # closest LiDAR return from a not-yet-mapped obstacle
    obstacle_threshold_m: float = 25.0
    route_available: bool = True  # False once a replan found no path
    replan_done: bool = False


def next_state(state: State, ctx: FsmContext) -> tuple[State, str | None]:
    if state in TERMINAL:
        return state, None

    if state == State.IDLE:
        if ctx.mission_started:
            return State.ARMED, "Mission started: arming motors"
        return state, None

    if state == State.ARMED:
        if ctx.mission_stopped:
            return State.LANDED, "Stop command before take-off: disarmed"
        if not ctx.route_available:
            return State.FAILSAFE, "No route available before take-off: FAILSAFE"
        return State.TAKEOFF, "Armed: taking off"

    # ---- guards shared by every airborne state ----
    if not ctx.route_available:
        return State.FAILSAFE, "Path blocked and no route found: FAILSAFE (emergency landing)"

    if state in ACTIVE_FLIGHT:
        needed = ctx.return_energy_pct + ctx.reserve_pct
        if ctx.battery_pct < needed:
            return State.RETURN_TO_LAUNCH, (
                f"Low battery {ctx.battery_pct:.1f}% < {needed:.1f}% "
                f"(return {ctx.return_energy_pct:.1f}% + reserve {ctx.reserve_pct:.0f}%): return to launch"
            )
        if ctx.mission_stopped:
            return State.RETURN_TO_LAUNCH, "Stop command: return to launch"

    if state == State.TAKEOFF:
        if ctx.altitude_reached:
            if ctx.tasks_remaining > 0:
                return State.EN_ROUTE, "Take-off complete: en route to first task"
            return State.RETURN_TO_LAUNCH, "No tasks assigned: return to launch"

    elif state == State.EN_ROUTE:
        if ctx.min_range_m < ctx.obstacle_threshold_m:
            return State.AVOIDING, (
                f"LiDAR: obstacle at {ctx.min_range_m:.0f} m "
                f"(< {ctx.obstacle_threshold_m:.0f} m threshold): replanning route"
            )
        if ctx.at_task_waypoint:
            return State.EXECUTING_TASK, "Reached task waypoint: executing task"
        if ctx.tasks_remaining == 0:
            return State.RETURN_TO_LAUNCH, "All tasks complete: return to launch"

    elif state == State.EXECUTING_TASK:
        if ctx.task_complete:
            if ctx.tasks_remaining > 0:
                return State.EN_ROUTE, "Task complete: en route to next task"
            return State.RETURN_TO_LAUNCH, "All tasks complete: return to launch"

    elif state == State.AVOIDING:
        if ctx.replan_done:
            return State.EN_ROUTE, "Replan complete: resuming route around obstacle"

    elif state == State.RETURN_TO_LAUNCH:
        if ctx.at_home:
            return State.LANDED, "Landed at home"

    return state, None
