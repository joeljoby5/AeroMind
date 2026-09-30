import numpy as np
import pytest

from ai.obstacles import MAX_RANGE_M, N_RAYS, detect, lidar_scan, obstacles_within
from ai.tests.helpers import HOME, offset
from ai.types import Obstacle


def _ob(north, east, r):
    lat, lon = offset(*HOME, north, east)
    return Obstacle(lat, lon, r)


def test_no_obstacles_returns_max_range_on_36_rays():
    r = lidar_scan(*HOME, 0.0, [])
    assert r.shape == (N_RAYS,) and np.all(r == MAX_RANGE_M)
    assert not detect(r).detected


def test_obstacle_dead_ahead_is_seen_on_ray_zero():
    r = lidar_scan(*HOME, 0.0, [_ob(north=40, east=0, r=10)])  # heading north, surface at 30 m
    assert r[0] == pytest.approx(30, abs=0.5)
    assert r[18] == MAX_RANGE_M  # behind


def test_rays_rotate_with_heading():
    ob = [_ob(north=40, east=0, r=10)]
    r = lidar_scan(*HOME, 90.0, ob)  # heading east: obstacle is to the left (ray 27 = -90 deg)
    assert np.argmin(r) == 27


def test_threshold_detection():
    far = lidar_scan(*HOME, 0.0, [_ob(40, 0, 10)])       # 30 m away
    near = lidar_scan(*HOME, 0.0, [_ob(30, 0, 10)])      # 20 m away
    assert not detect(far).detected
    d = detect(near, heading_deg=0.0)
    assert d.detected and d.min_range_m == pytest.approx(20, abs=0.5) and d.bearing_deg == pytest.approx(0.0)


def test_beyond_max_range_not_seen():
    assert np.all(lidar_scan(*HOME, 0.0, [_ob(200, 0, 10)]) == MAX_RANGE_M)


def test_inside_obstacle_reads_zero():
    assert np.all(lidar_scan(*HOME, 0.0, [_ob(0, 3, 10)]) == 0)


def test_nearest_of_several_obstacles_wins():
    r = lidar_scan(*HOME, 0.0, [_ob(50, 0, 10), _ob(35, 0, 5)])
    assert r[0] == pytest.approx(30, abs=0.5)


def test_obstacles_within_association():
    near, far = _ob(30, 0, 10), _ob(300, 0, 10)
    assert obstacles_within(*HOME, [near, far], 25.0) == [near]
