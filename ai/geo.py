"""Small geodesy helpers: haversine, bearing and a local metric projection."""
from __future__ import annotations

import math

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing in degrees, clockwise from north, in [0, 360)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlmb = math.radians(lon2 - lon1)
    y = math.sin(dlmb) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlmb)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


class LocalFrame:
    """Equirectangular projection around an origin: x = east (m), y = north (m).

    Accurate to well under a metre over the few-km areas a campus mission covers.
    """

    def __init__(self, lat0: float, lon0: float) -> None:
        self.lat0 = lat0
        self.lon0 = lon0
        self._kx = EARTH_RADIUS_M * math.cos(math.radians(lat0)) * math.pi / 180.0
        self._ky = EARTH_RADIUS_M * math.pi / 180.0

    def to_xy(self, lat: float, lon: float) -> tuple[float, float]:
        return (lon - self.lon0) * self._kx, (lat - self.lat0) * self._ky

    def to_latlon(self, x: float, y: float) -> tuple[float, float]:
        return self.lat0 + y / self._ky, self.lon0 + x / self._kx


def move_towards(
    lat: float, lon: float, target_lat: float, target_lon: float, step_m: float
) -> tuple[float, float, bool]:
    """Advance `step_m` metres from (lat, lon) towards the target. Returns (lat, lon, arrived)."""
    frame = LocalFrame(lat, lon)
    tx, ty = frame.to_xy(target_lat, target_lon)
    dist = math.hypot(tx, ty)
    if dist <= step_m or dist < 1e-9:
        return target_lat, target_lon, True
    nlat, nlon = frame.to_latlon(tx / dist * step_m, ty / dist * step_m)
    return nlat, nlon, False
