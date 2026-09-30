import numpy as np
import pandas as pd

from ai.energy_model.features import Environment, leg_features
from ai.energy_model.generate_dataset import generate, physical_energy_pct
from ai.energy_model.predict import EnergyPredictor, PhysicsEstimator


def _row(**over):
    base = dict(drone_type="quad_medium", battery_health=0.9, cruise_speed_ms=10.0,
                distance_m=1000.0, altitude_change_m=0.0, payload_kg=0.0,
                leg_bearing_deg=0.0, env=Environment(wind_speed_ms=0.0))
    base.update(over)
    return leg_features(**base)


def test_dataset_is_seeded_and_in_range():
    a, b = generate(500), generate(500)
    pd.testing.assert_frame_equal(a, b)
    assert a["energy_pct"].between(0.2, 100).all()
    assert a["distance_m"].between(50, 3000).all()


def test_physics_headwind_costs_more_than_tailwind():
    common = dict(drone_type="quad_small", distance_m=1000, altitude_change_m=0, payload_kg=0,
                  wind_speed_ms=10, battery_health=1.0, cruise_speed_ms=9)
    head = physical_energy_pct(wind_alignment=-1.0, **common)
    tail = physical_energy_pct(wind_alignment=1.0, **common)
    assert head > tail


def test_payload_hurts_small_drones_more():
    def ratio(t):
        kw = dict(drone_type=t, distance_m=1000, altitude_change_m=0, wind_speed_ms=0,
                  wind_alignment=0, battery_health=1.0, cruise_speed_ms=9)
        return physical_energy_pct(payload_kg=2.0, **kw) / physical_energy_pct(payload_kg=0.0, **kw)
    assert ratio("quad_small") > ratio("hex_heavy")


def test_trained_model_tracks_physics():
    pred = EnergyPredictor()
    assert not pred.is_fallback, "run `make train` first"
    rows = [_row(distance_m=d, payload_kg=p, altitude_change_m=a)
            for d, p, a in [(200, 0, 0), (800, 1.5, 30), (2500, 0.5, -20)]]
    got = pred.predict_batch(rows)
    want = PhysicsEstimator().predict_batch(rows)
    assert np.allclose(got, want, rtol=0.15, atol=1.0)


def test_predictor_single_returns_float_and_extrapolates_beyond_training_range():
    pred = EnergyPredictor()
    assert isinstance(pred.predict(_row()), float)
    assert pred.predict(_row(distance_m=6000)) > 1.6 * pred.predict(_row(distance_m=3000))


def test_fallback_when_artifact_missing(tmp_path, caplog):
    pred = EnergyPredictor(tmp_path / "nope.joblib")
    assert pred.is_fallback
    assert pred.predict(_row()) > 0
    assert "fallback" in caplog.text
