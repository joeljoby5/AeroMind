"""Replaceable-module contracts. The backend talks to these, never to concrete classes' internals."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

import numpy as np

from ai.types import AllocationResult, DroneState, Obstacle, PathResult, Task


class EnergyEstimator(Protocol):
    """Predicts % battery consumed by a flight leg from a feature row."""

    model_name: str

    def predict(self, features: Mapping) -> float: ...

    def predict_batch(self, rows: Sequence[Mapping]) -> np.ndarray: ...


class TaskAllocator(Protocol):
    """Assigns tasks to drones. `strategy` is "ml" (energy-aware) or "baseline" (distance-only)."""

    def allocate(
        self, drones: Sequence[DroneState], tasks: Sequence[Task], strategy: str
    ) -> AllocationResult: ...


class PathPlanner(Protocol):
    """Plans an obstacle-free route between two (lat, lon) points."""

    def plan(
        self,
        start: tuple[float, float],
        goal: tuple[float, float],
        obstacles: Sequence[Obstacle],
    ) -> PathResult: ...
