"""EnergyPredictor: loads the trained pipeline, falls back to a linear heuristic if missing."""
from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ai.energy_model.features import FEATURE_COLUMNS, RANGES
from ai.energy_model.generate_dataset import physical_energy_pct

log = logging.getLogger("aeromind.energy")

DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "artifacts" / "energy_model.joblib"
_MAX_TRAIN_DISTANCE = RANGES["distance_m"][1]


def _to_frame(rows: Sequence[Mapping] | pd.DataFrame) -> pd.DataFrame:
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows))
    return df[FEATURE_COLUMNS]


def heuristic_energy(df: pd.DataFrame) -> np.ndarray:
    """Fallback: simple linear estimate that ignores wind and drone type."""
    return (
        0.5
        + 0.0085 * df["distance_m"].to_numpy() * (1 + 0.1 * df["payload_kg"].to_numpy())
        / df["battery_health"].to_numpy()
        + 0.04 * np.maximum(df["altitude_change_m"].to_numpy(), 0.0)
    )


class EnergyPredictor:
    """Implements the `EnergyEstimator` protocol with the trained scikit-learn pipeline."""

    def __init__(self, model_path: Path | str | None = None) -> None:
        path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self.pipeline = None
        self.is_fallback = False
        if path.exists():
            self.pipeline = joblib.load(path)
            self.model_name = type(self.pipeline.named_steps["model"]).__name__
        else:
            self.is_fallback = True
            self.model_name = "LinearHeuristic (fallback)"
            log.warning("energy model artifact %s missing; using linear heuristic fallback", path)

    def predict_batch(self, rows: Sequence[Mapping] | pd.DataFrame) -> np.ndarray:
        df = _to_frame(rows)
        if len(df) == 0:
            return np.zeros(0)
        raw = heuristic_energy(df) if self.is_fallback else self.pipeline.predict(df)
        # Trees cannot extrapolate: scale linearly beyond the longest training leg.
        over = np.maximum(df["distance_m"].to_numpy() / _MAX_TRAIN_DISTANCE, 1.0)
        return np.clip(raw * over, 0.2, None)

    def predict(self, features: Mapping) -> float:
        return float(self.predict_batch([features])[0])


class PhysicsEstimator:
    """Noise-free ground truth from the dataset formula. Used to *evaluate* plans, not to plan."""

    model_name = "PhysicsGroundTruth"
    is_fallback = False

    def predict_batch(self, rows: Sequence[Mapping] | pd.DataFrame) -> np.ndarray:
        df = _to_frame(rows)
        if len(df) == 0:
            return np.zeros(0)
        return np.asarray(
            physical_energy_pct(
                df["drone_type"].to_numpy(),
                df["distance_m"].to_numpy(),
                df["altitude_change_m"].to_numpy(),
                df["payload_kg"].to_numpy(),
                df["wind_speed_ms"].to_numpy(),
                df["wind_alignment"].to_numpy(),
                df["battery_health"].to_numpy(),
                df["cruise_speed_ms"].to_numpy(),
            ),
            dtype=float,
        )

    def predict(self, features: Mapping) -> float:
        return float(self.predict_batch([features])[0])
