"""Simulated 2D LiDAR and threshold-based obstacle detection (pure geometry, no ML / OpenCV)."""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from ai.geo import LocalFrame
from ai.types import Obstacle

N_RAYS = 36
MAX_RANGE_M = 60.0
DETECTION_THRESHOLD_M = 25.0


@dataclass(frozen=True)
class Detection:
    detected: bool
    min_range_m: float
    bearing_deg: float | None  # absolute compass bearing of the closest return


def lidar_scan(
    lat: float,
    lon: float,
    heading_deg: float,
    obstacles: Sequence[Obstacle],
    n_rays: int = N_RAYS,
    max_range_m: float = MAX_RANGE_M,
) -> np.ndarray:
    """Range (m) along `n_rays` evenly spaced rays; ray 0 points along the heading.

    Each obstacle is a circle; a ray returns the distance to the circle's surface
    (0 if the drone is inside it) or `max_range_m` when nothing is hit.
    """
    frame = LocalFrame(lat, lon)
    angles = np.radians(heading_deg + np.arange(n_rays) * (360.0 / n_rays))
    dx, dy = np.sin(angles), np.cos(angles)  # compass bearing: 0 deg = north
    ranges = np.full(n_rays, max_range_m, dtype=float)
    for o in obstacles:
        cx, cy = frame.to_xy(o.lat, o.lon)
        if math.hypot(cx, cy) <= o.radius_m:
            return np.zeros(n_rays)
        proj = cx * dx + cy * dy  # distance along each ray to the closest approach
        perp_sq = cx * cx + cy * cy - proj * proj
        hit = (proj > 0) & (perp_sq <= o.radius_m ** 2)
        t = proj - np.sqrt(np.maximum(o.radius_m ** 2 - perp_sq, 0.0))
        ranges = np.where(hit, np.minimum(ranges, np.maximum(t, 0.0)), ranges)
    return np.minimum(ranges, max_range_m)


def detect(
    ranges: np.ndarray,
    heading_deg: float = 0.0,
    threshold_m: float = DETECTION_THRESHOLD_M,
) -> Detection:
    """Threshold check: an obstacle is detected when the closest return is under `threshold_m`."""
    idx = int(np.argmin(ranges))
    min_range = float(ranges[idx])
    if min_range >= threshold_m:
        return Detection(False, min_range, None)
    bearing = (heading_deg + idx * (360.0 / len(ranges))) % 360.0
    return Detection(True, min_range, bearing)


def obstacles_within(
    lat: float, lon: float, obstacles: Sequence[Obstacle], max_range_m: float = DETECTION_THRESHOLD_M
) -> list[Obstacle]:
    """Data association: which mapped obstacles produced a return inside `max_range_m`."""
    frame = LocalFrame(lat, lon)
    out = []
    for o in obstacles:
        cx, cy = frame.to_xy(o.lat, o.lon)
        if math.hypot(cx, cy) - o.radius_m < max_range_m:
            out.append(o)
    return out
