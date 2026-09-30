from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends

from ai.energy_model.features import Environment, leg_features
from app import schemas
from app.api.deps import get_container
from app.container import Container

router = APIRouter(prefix="/api/ai", tags=["ai"])

METRICS_PATH = Path(__file__).resolve().parents[3] / "ai" / "energy_model" / "artifacts" / "metrics.json"


@router.get("/model-info")
def model_info(c: Container = Depends(get_container)) -> dict:
    """Contents of metrics.json plus which estimator is actually serving predictions."""
    metrics = json.loads(METRICS_PATH.read_text()) if METRICS_PATH.exists() else {}
    return {**metrics, "active_model": c.predictor.model_name, "is_fallback": c.predictor.is_fallback}


@router.post("/predict-energy", response_model=schemas.PredictOut)
def predict_energy(body: schemas.PredictIn, c: Container = Depends(get_container)):
    row = leg_features(
        drone_type=body.drone_type, battery_health=body.battery_health, cruise_speed_ms=body.cruise_speed_ms,
        distance_m=body.distance_m, altitude_change_m=body.altitude_change_m, payload_kg=body.payload_kg,
        leg_bearing_deg=0.0, env=Environment(body.wind_speed_ms, 0.0))
    row["wind_alignment"] = body.wind_alignment  # caller gives the alignment directly
    return schemas.PredictOut(energy_pct=round(c.predictor.predict(row), 3), model=c.predictor.model_name,
                              is_fallback=c.predictor.is_fallback)
