"""Feature schema shared by dataset generation, training and inference."""
from __future__ import annotations

import math
from dataclasses import dataclass

DRONE_TYPES = ("quad_small", "quad_medium", "hex_heavy")

# Typical cruise speed used when a drone does not specify its own (m/s).
DEFAULT_CRUISE_SPEED_MS = {"quad_small": 10.0, "quad_medium": 11.0, "hex_heavy": 8.0}

NUMERIC_FEATURES = [
    "distance_m",
    "altitude_change_m",
    "payload_kg",
    "wind_speed_ms",
    "wind_alignment",
    "battery_health",
    "cruise_speed_ms",
]
CATEGORICAL_FEATURES = ["drone_type"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET = "energy_pct"

# Ranges the dataset was generated on. Inputs are clipped to these at inference.
RANGES = {
    "distance_m": (50.0, 3000.0),
    "altitude_change_m": (-60.0, 120.0),
    "payload_kg": (0.0, 2.5),
    "wind_speed_ms": (0.0, 14.0),
    "wind_alignment": (-1.0, 1.0),
    "battery_health": (0.70, 1.00),
    "cruise_speed_ms": (5.0, 15.0),
}


@dataclass(frozen=True)
class Environment:
    """Steady wind over the mission area. `wind_to_deg` is the direction the wind blows TOWARDS."""

    wind_speed_ms: float = 6.0
    wind_to_deg: float = 60.0


def wind_alignment(env: Environment, leg_bearing_deg: float) -> float:
    """+1 = pure tailwind, -1 = pure headwind, 0 = crosswind."""
    if env.wind_speed_ms <= 0:
        return 0.0
    return math.cos(math.radians(leg_bearing_deg - env.wind_to_deg))


def _clip(name: str, value: float) -> float:
    lo, hi = RANGES[name]
    return min(max(value, lo), hi)


def leg_features(
    *,
    drone_type: str,
    battery_health: float,
    cruise_speed_ms: float | None,
    distance_m: float,
    altitude_change_m: float,
    payload_kg: float,
    leg_bearing_deg: float,
    env: Environment,
) -> dict:
    """Build one model-input row for a flight leg (clipped to the training ranges)."""
    if drone_type not in DRONE_TYPES:
        raise ValueError(f"unknown drone_type {drone_type!r}; expected one of {DRONE_TYPES}")
    speed = cruise_speed_ms if cruise_speed_ms is not None else DEFAULT_CRUISE_SPEED_MS[drone_type]
    return {
        # clipped low only; the predictor extrapolates linearly above the training maximum
        "distance_m": max(distance_m, RANGES["distance_m"][0]),
        "altitude_change_m": _clip("altitude_change_m", altitude_change_m),
        "payload_kg": _clip("payload_kg", payload_kg),
        "wind_speed_ms": _clip("wind_speed_ms", env.wind_speed_ms),
        "wind_alignment": _clip("wind_alignment", wind_alignment(env, leg_bearing_deg)),
        "battery_health": _clip("battery_health", battery_health),
        "cruise_speed_ms": _clip("cruise_speed_ms", speed),
        "drone_type": drone_type,
    }
