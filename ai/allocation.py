"""Task allocation: cost-matrix builder + Hungarian algorithm (scipy linear_sum_assignment).

Two strategies share the same solver and differ only in the cost matrix:

* ``ml``       cost[i][j] = predicted energy (% battery) for drone i to fly to task j.
               Pairs that cannot be flown safely (energy + return-to-home + reserve > battery)
               get ``INFEASIBLE_COST`` so they are never chosen unless nothing else is possible.
* ``baseline`` cost[i][j] = straight-line distance in metres. No model, no feasibility check -
               this is the deterministic fallback and the comparison reference.

When there are more tasks than drones the solver runs in rounds: each round is one Hungarian
assignment, then every assigned drone "moves" to its task (position + battery updated) and the
next round allocates what is left. The per-drone ordered task list is the round order.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment

from ai.energy_model.features import Environment, leg_features
from ai.energy_model.predict import HeuristicEstimator, PhysicsEstimator
from ai.geo import bearing_deg, haversine_m
from ai.interfaces import EnergyEstimator
from ai.types import AllocationResult, AssignedTask, DroneState, Task, UnassignedTask

INFEASIBLE_COST = 1e6
DEFAULT_RESERVE_PCT = 15.0
STRATEGIES = ("ml", "baseline")


def _leg_row(d: DroneState, frm: tuple[float, float, float], to: tuple[float, float, float],
             payload_kg: float, env: Environment) -> dict:
    return leg_features(
        drone_type=d.type,
        battery_health=d.health,
        cruise_speed_ms=d.cruise_speed_ms,
        distance_m=haversine_m(frm[0], frm[1], to[0], to[1]),
        altitude_change_m=to[2] - frm[2],
        payload_kg=payload_kg,
        leg_bearing_deg=bearing_deg(frm[0], frm[1], to[0], to[1]),
        env=env,
    )


def leg_energy(d: DroneState, frm, to, payload_kg: float, env: Environment,
               estimator: EnergyEstimator) -> float:
    return float(estimator.predict(_leg_row(d, frm, to, payload_kg, env)))


def _energy_tables(drones, tasks, estimator, env):
    """Energy (%) to fly drone i -> task j (carrying the payload) and task j -> drone i's home."""
    n, m = len(drones), len(tasks)
    go_rows, back_rows = [], []
    for d in drones:
        for t in tasks:
            go_rows.append(_leg_row(d, (d.lat, d.lon, d.alt_m), (t.lat, t.lon, t.altitude_m),
                                    t.payload_kg, env))
            back_rows.append(_leg_row(d, (t.lat, t.lon, t.altitude_m),
                                      (d.home_lat, d.home_lon, 0.0), 0.0, env))
    go = estimator.predict_batch(go_rows).reshape(n, m)
    back = estimator.predict_batch(back_rows).reshape(n, m)
    return go, back


def build_cost_matrix(
    drones: Sequence[DroneState],
    tasks: Sequence[Task],
    strategy: str,
    predictor: EnergyEstimator | None = None,
    env: Environment | None = None,
    reserve_pct: float = DEFAULT_RESERVE_PCT,
) -> np.ndarray:
    """(n_drones x n_tasks) cost matrix. See module docstring for the two strategies."""
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {STRATEGIES}, got {strategy!r}")
    env = env or Environment()
    if strategy == "baseline":
        return np.array([[haversine_m(d.lat, d.lon, t.lat, t.lon) for t in tasks] for d in drones])
    if predictor is None:
        raise ValueError("strategy 'ml' needs an energy predictor")
    go, back = _energy_tables(drones, tasks, predictor, env)
    battery = np.array([d.battery_pct for d in drones])[:, None]
    cost = go.copy()
    cost[go + back + reserve_pct > battery] = INFEASIBLE_COST
    return cost


def allocate(
    drones: Sequence[DroneState],
    tasks: Sequence[Task],
    strategy: str = "ml",
    predictor: EnergyEstimator | None = None,
    env: Environment | None = None,
    reserve_pct: float = DEFAULT_RESERVE_PCT,
) -> AllocationResult:
    """Assign every task that can be assigned; report the rest as unassigned with a reason."""
    env = env or Environment()
    # Bookkeeping estimator: the baseline must work with no model at all.
    est: EnergyEstimator = predictor or HeuristicEstimator()
    state = {d.id: dataclasses.replace(d) for d in drones}
    result = AllocationResult(strategy=strategy, per_drone={d.id: [] for d in drones})
    remaining = list(tasks)

    while remaining and state:
        ds = list(state.values())
        cost = build_cost_matrix(ds, remaining, strategy, predictor, env, reserve_pct)
        rows, cols = linear_sum_assignment(cost)
        chosen, progressed = [], False
        for i, j in zip(rows, cols):
            if strategy == "ml" and cost[i, j] >= INFEASIBLE_COST:
                continue  # forced infeasible pair: leave the task for a later round / unassigned
            d, t = ds[i], remaining[j]
            e = leg_energy(d, (d.lat, d.lon, d.alt_m), (t.lat, t.lon, t.altitude_m),
                           t.payload_kg, env, est)
            result.assignments.append(AssignedTask(d.id, t.id, len(result.per_drone[d.id]), e))
            result.per_drone[d.id].append(t.id)
            result.total_energy_pct += e
            d.lat, d.lon, d.alt_m = t.lat, t.lon, t.altitude_m
            d.battery_pct = max(d.battery_pct - e, 0.0)
            chosen.append(j)
            progressed = True
        remaining = [t for k, t in enumerate(remaining) if k not in set(chosen)]
        if not progressed:
            break

    reason = (
        f"No drone has enough battery to reach the task, return home and keep a {reserve_pct:.0f}% reserve"
        if strategy == "ml" else "No drone available"
    )
    result.unassigned = [UnassignedTask(t.id, reason) for t in remaining]

    # Return-to-home leg for every drone that received work.
    for d in state.values():
        if result.per_drone[d.id]:
            result.total_energy_pct += leg_energy(
                d, (d.lat, d.lon, d.alt_m), (d.home_lat, d.home_lon, 0.0), 0.0, env, est
            )
    return result


def evaluate_allocation(
    result: AllocationResult,
    drones: Sequence[DroneState],
    tasks: Sequence[Task],
    env: Environment | None = None,
    reserve_pct: float = DEFAULT_RESERVE_PCT,
    estimator: EnergyEstimator | None = None,
) -> dict:
    """Score an allocation against the physics ground truth (not the model that planned it).

    An assignment is *infeasible* if, after flying to that task, the drone's real remaining battery
    would not cover the flight home plus the reserve.
    """
    env = env or Environment()
    est = estimator or PhysicsEstimator()
    by_id = {d.id: d for d in drones}
    tasks_by_id = {t.id: t for t in tasks}
    total, infeasible = 0.0, 0
    for drone_id, task_ids in result.per_drone.items():
        if not task_ids:
            continue
        d = by_id[drone_id]
        pos, battery = (d.lat, d.lon, d.alt_m), d.battery_pct
        for tid in task_ids:
            t = tasks_by_id[tid]
            to = (t.lat, t.lon, t.altitude_m)
            e = leg_energy(d, pos, to, t.payload_kg, env, est)
            back = leg_energy(d, to, (d.home_lat, d.home_lon, 0.0), 0.0, env, est)
            battery -= e
            total += e
            if battery - back < reserve_pct:
                infeasible += 1
            pos = to
        total += leg_energy(d, pos, (d.home_lat, d.home_lon, 0.0), 0.0, env, est)
    return {
        "total_energy_pct": total,
        "infeasible_assignments": infeasible,
        "assigned": sum(len(v) for v in result.per_drone.values()),
        "unassigned": len(result.unassigned),
    }


class HungarianAllocator:
    """`TaskAllocator` implementation bundling a predictor, environment and reserve."""

    def __init__(self, predictor: EnergyEstimator | None = None, env: Environment | None = None,
                 reserve_pct: float = DEFAULT_RESERVE_PCT) -> None:
        self.predictor, self.env, self.reserve_pct = predictor, env or Environment(), reserve_pct

    def allocate(self, drones, tasks, strategy: str = "ml") -> AllocationResult:
        return allocate(drones, tasks, strategy, self.predictor, self.env, self.reserve_pct)
