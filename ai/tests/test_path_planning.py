import math

import pytest

from ai.geo import LocalFrame
from ai.path_planning import AStarPlanner, plan_path
from ai.tests.helpers import HOME, offset
from ai.types import Obstacle


def _obstacle(north, east, r):
    lat, lon = offset(*HOME, north, east)
    return Obstacle(lat, lon, r)


def _min_clearance(path, obstacle, frame):
    cx, cy = frame.to_xy(obstacle.lat, obstacle.lon)
    pts = [frame.to_xy(*p) for p in path]
    best = math.inf
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        vx, vy = bx - ax, by - ay
        L = vx * vx + vy * vy
        t = 0 if L == 0 else max(0, min(1, ((cx - ax) * vx + (cy - ay) * vy) / L))
        best = min(best, math.hypot(ax + t * vx - cx, ay + t * vy - cy) - obstacle.radius_m)
    return best


def test_straight_path_when_clear():
    goal = offset(*HOME, 400, 300)
    res = plan_path(HOME, goal, [])
    assert res.path == [HOME, goal]
    assert res.length_m == pytest.approx(500, rel=0.01)


def test_same_start_and_goal():
    res = plan_path(HOME, HOME, [])
    assert res.path == [HOME] and res.length_m == 0


def test_path_goes_around_obstacle_with_safety_margin():
    goal = offset(*HOME, 400, 0)
    ob = _obstacle(200, 0, 40)
    res = AStarPlanner(safety_m=12).plan(HOME, goal, [ob])
    assert res.path is not None and len(res.path) > 2
    assert res.path[0] == HOME and res.path[-1] == goal
    assert _min_clearance(res.path, ob, LocalFrame(*HOME)) >= 12 - 6  # grid-resolution tolerance
    assert 400 < res.length_m < 520  # longer than straight, but a sensible detour


def test_path_is_smoothed_no_collinear_points():
    goal = offset(*HOME, 400, 0)
    res = plan_path(HOME, goal, [_obstacle(200, 0, 40)])
    frame = LocalFrame(*HOME)
    pts = [frame.to_xy(*p) for p in res.path]
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        assert abs(cross) > 1e-6
    assert len(res.path) <= 8


def test_no_path_when_goal_enclosed_by_ring_of_obstacles():
    goal = offset(*HOME, 300, 0)
    ring = [_obstacle(300 + 45 * math.cos(a), 45 * math.sin(a), 30)
            for a in [i * math.pi / 6 for i in range(12)]]
    res = plan_path(HOME, goal, ring)
    assert res.path is None and res.reason


def test_goal_inside_obstacle():
    goal = offset(*HOME, 300, 0)
    res = plan_path(HOME, goal, [_obstacle(300, 5, 30)])
    assert res.path is None and "goal" in res.reason


def test_start_inside_safety_ring_can_escape():
    """After LiDAR detection the drone may already be inside the inflated (not physical) radius."""
    goal = offset(*HOME, 300, 0)
    ob = _obstacle(45, 0, 30)  # 45 m away: outside the body, inside r + 12 + margin ring
    res = AStarPlanner(safety_m=20).plan(HOME, goal, [ob])
    assert res.path is not None and res.path[-1] == goal


def test_planning_area_limit():
    far = offset(*HOME, 40_000, 0)
    res = AStarPlanner(max_cells=100).plan(HOME, far, [_obstacle(20_000, 0, 50), _obstacle(1, 0, 1) ])
    assert res.path is None
