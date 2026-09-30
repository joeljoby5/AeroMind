import math

import pytest

from ai.fsm import FsmContext, State, next_state


def ctx(**kw):
    return FsmContext(**kw)


@pytest.mark.parametrize(
    "state, c, expected",
    [
        (State.IDLE, ctx(), State.IDLE),
        (State.IDLE, ctx(mission_started=True), State.ARMED),
        (State.ARMED, ctx(), State.TAKEOFF),
        (State.ARMED, ctx(mission_stopped=True), State.LANDED),
        (State.ARMED, ctx(route_available=False), State.FAILSAFE),
        (State.TAKEOFF, ctx(), State.TAKEOFF),
        (State.TAKEOFF, ctx(altitude_reached=True, tasks_remaining=2), State.EN_ROUTE),
        (State.TAKEOFF, ctx(altitude_reached=True, tasks_remaining=0), State.RETURN_TO_LAUNCH),
        (State.EN_ROUTE, ctx(tasks_remaining=2), State.EN_ROUTE),
        (State.EN_ROUTE, ctx(tasks_remaining=2, at_task_waypoint=True), State.EXECUTING_TASK),
        (State.EN_ROUTE, ctx(tasks_remaining=2, min_range_m=20.0), State.AVOIDING),
        (State.EN_ROUTE, ctx(tasks_remaining=0), State.RETURN_TO_LAUNCH),
        (State.EXECUTING_TASK, ctx(tasks_remaining=1), State.EXECUTING_TASK),
        (State.EXECUTING_TASK, ctx(task_complete=True, tasks_remaining=1), State.EN_ROUTE),
        (State.EXECUTING_TASK, ctx(task_complete=True, tasks_remaining=0), State.RETURN_TO_LAUNCH),
        (State.AVOIDING, ctx(tasks_remaining=1), State.AVOIDING),
        (State.AVOIDING, ctx(tasks_remaining=1, replan_done=True), State.EN_ROUTE),
        (State.RETURN_TO_LAUNCH, ctx(), State.RETURN_TO_LAUNCH),
        (State.RETURN_TO_LAUNCH, ctx(at_home=True), State.LANDED),
        (State.LANDED, ctx(mission_started=True), State.LANDED),
        (State.FAILSAFE, ctx(at_home=True), State.FAILSAFE),
    ],
)
def test_transitions(state, c, expected):
    new, event = next_state(state, c)
    assert new == expected
    assert (event is None) == (new == state)  # a transition always carries an event string
    if event:
        assert isinstance(event, str) and len(event) > 5


@pytest.mark.parametrize("state", [State.TAKEOFF, State.EN_ROUTE, State.EXECUTING_TASK, State.AVOIDING])
def test_low_battery_triggers_rtl_from_every_flight_state(state):
    new, event = next_state(state, ctx(battery_pct=20, return_energy_pct=10, reserve_pct=15, tasks_remaining=3))
    assert new == State.RETURN_TO_LAUNCH and "Low battery" in event


def test_battery_just_above_threshold_keeps_flying():
    new, _ = next_state(State.EN_ROUTE, ctx(battery_pct=25.1, return_energy_pct=10, reserve_pct=15, tasks_remaining=3))
    assert new == State.EN_ROUTE


def test_no_rtl_loop_once_returning_with_low_battery():
    new, event = next_state(State.RETURN_TO_LAUNCH, ctx(battery_pct=5, return_energy_pct=10))
    assert new == State.RETURN_TO_LAUNCH and event is None


@pytest.mark.parametrize("state", [State.TAKEOFF, State.EN_ROUTE, State.EXECUTING_TASK, State.AVOIDING, State.RETURN_TO_LAUNCH])
def test_blocked_route_triggers_failsafe(state):
    new, event = next_state(state, ctx(route_available=False, tasks_remaining=1))
    assert new == State.FAILSAFE and "FAILSAFE" in event


@pytest.mark.parametrize("state", [State.TAKEOFF, State.EN_ROUTE, State.EXECUTING_TASK, State.AVOIDING])
def test_stop_command_returns_to_launch(state):
    new, event = next_state(state, ctx(mission_stopped=True, tasks_remaining=2))
    assert new == State.RETURN_TO_LAUNCH and "Stop" in event


def test_obstacle_exactly_at_threshold_is_not_detected():
    new, _ = next_state(State.EN_ROUTE, ctx(tasks_remaining=1, min_range_m=25.0, obstacle_threshold_m=25.0))
    assert new == State.EN_ROUTE


def test_failsafe_outranks_low_battery():
    new, _ = next_state(State.EN_ROUTE, ctx(route_available=False, battery_pct=1, tasks_remaining=1))
    assert new == State.FAILSAFE


def test_default_context_has_no_obstacle():
    assert math.isinf(FsmContext().min_range_m)
