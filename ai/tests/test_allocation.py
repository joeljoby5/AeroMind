import itertools

import numpy as np
import pytest

from ai.allocation import (INFEASIBLE_COST, allocate, build_cost_matrix, evaluate_allocation)
from ai.energy_model.features import Environment
from ai.energy_model.predict import EnergyPredictor, HeuristicEstimator
from ai.tests.helpers import make_drone, make_task, random_scenario

ENV = Environment(wind_speed_ms=6.0, wind_to_deg=60.0)


@pytest.fixture(scope="module")
def predictor():
    return EnergyPredictor()


@pytest.mark.parametrize("strategy", ["ml", "baseline"])
@pytest.mark.parametrize("seed", range(6))
def test_hungarian_matches_brute_force(strategy, seed, predictor):
    drones, tasks = random_scenario(seed, n_drones=3, n_tasks=3)
    cost = build_cost_matrix(drones, tasks, strategy, predictor, ENV)
    best = min(sum(cost[i, p[i]] for i in range(3)) for p in itertools.permutations(range(3)))
    res = allocate(drones, tasks, strategy, predictor, ENV)
    assert not res.unassigned
    chosen = {a.drone_id: a.task_id for a in res.assignments}
    got = sum(cost[i, [t.id for t in tasks].index(chosen[d.id])] for i, d in enumerate(drones))
    assert got == pytest.approx(best, rel=1e-9)


def test_baseline_cost_is_distance_in_metres():
    d = make_drone(1)
    t = make_task(1, north=300, east=400)
    cost = build_cost_matrix([d], [t], "baseline")
    assert cost[0, 0] == pytest.approx(500, rel=0.01)


def test_baseline_works_without_any_model():
    drones, tasks = random_scenario(1, 3, 5)
    res = allocate(drones, tasks, "baseline", predictor=None)
    assert len(res.assignments) == 5 and not res.unassigned


def test_ml_requires_a_predictor():
    with pytest.raises(ValueError):
        build_cost_matrix([make_drone(1)], [make_task(1, 100, 0)], "ml", None)


def test_unknown_strategy_rejected():
    with pytest.raises(ValueError):
        build_cost_matrix([make_drone(1)], [make_task(1, 100, 0)], "magic", None)


def test_infeasible_battery_gets_penalty_and_is_avoided(predictor):
    weak = make_drone(1, battery=20.0)        # cannot fly 1.5 km out and back with a reserve
    strong = make_drone(2, battery=95.0)
    far = make_task(1, north=1500, east=0)
    cost = build_cost_matrix([weak, strong], [far], "ml", predictor, ENV)
    assert cost[0, 0] == INFEASIBLE_COST and cost[1, 0] < INFEASIBLE_COST
    res = allocate([weak, strong], [far], "ml", predictor, ENV)
    assert [a.drone_id for a in res.assignments] == [2]


def test_task_nobody_can_reach_is_reported_unassigned_with_reason(predictor):
    drones = [make_drone(1, battery=20.0), make_drone(2, battery=25.0)]
    res = allocate(drones, [make_task(1, 2500, 0)], "ml", predictor, ENV)
    assert not res.assignments
    assert [u.task_id for u in res.unassigned] == [1]
    assert "battery" in res.unassigned[0].reason


def test_more_tasks_than_drones_assigns_every_task_in_rounds(predictor):
    drones, tasks = random_scenario(3, n_drones=2, n_tasks=7)
    for d in drones:
        d.battery_pct = 100.0
    res = allocate(drones, tasks, "ml", predictor, ENV)
    assert not res.unassigned
    assigned_ids = sorted(a.task_id for a in res.assignments)
    assert assigned_ids == sorted(t.id for t in tasks)
    assert sum(len(v) for v in res.per_drone.values()) == 7
    # per-drone order indices are 0..k-1 and match the ordered list
    for drone_id, ids in res.per_drone.items():
        mine = sorted((a for a in res.assignments if a.drone_id == drone_id), key=lambda a: a.order)
        assert [a.task_id for a in mine] == ids and [a.order for a in mine] == list(range(len(ids)))


def test_battery_is_depleted_between_rounds(predictor):
    """A drone that just flew a long leg must not be given a second long leg it cannot afford."""
    d = make_drone(1, battery=55.0)
    tasks = [make_task(1, 1200, 0), make_task(2, -1200, 0)]
    res = allocate([d], tasks, "ml", predictor, ENV)
    assert len(res.assignments) == 1 and len(res.unassigned) == 1


def test_total_energy_includes_return_legs(predictor):
    d = make_drone(1)
    res = allocate([d], [make_task(1, 600, 0)], "ml", predictor, ENV)
    assert res.total_energy_pct > res.assignments[0].predicted_energy_pct


def test_evaluate_flags_baseline_infeasible_assignment(predictor):
    weak = make_drone(1, battery=22.0)
    far = make_task(1, north=1400, east=0)
    base = allocate([weak], [far], "baseline", None, ENV)
    ml = allocate([weak], [far], "ml", predictor, ENV)
    assert evaluate_allocation(base, [weak], [far], ENV)["infeasible_assignments"] == 1
    assert evaluate_allocation(ml, [weak], [far], ENV)["infeasible_assignments"] == 0


def test_ml_uses_less_true_energy_than_baseline_on_average(predictor):
    ml_e, base_e = [], []
    for seed in range(30):
        drones, tasks = random_scenario(100 + seed, 4, 4)
        for d in drones:
            d.battery_pct = 100.0
        ml_e.append(evaluate_allocation(allocate(drones, tasks, "ml", predictor, ENV), drones, tasks, ENV)["total_energy_pct"])
        base_e.append(evaluate_allocation(allocate(drones, tasks, "baseline", None, ENV), drones, tasks, ENV)["total_energy_pct"])
    assert np.mean(ml_e) < np.mean(base_e)
