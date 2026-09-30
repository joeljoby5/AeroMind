"""Train and compare energy models, save the best pipeline and metrics.json.

Run:  python -m ai.energy_model.train
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ai.energy_model.features import CATEGORICAL_FEATURES, FEATURE_COLUMNS, NUMERIC_FEATURES, TARGET
from ai.energy_model.generate_dataset import DEFAULT_CSV, SEED
from ai.energy_model.generate_dataset import main as generate_dataset

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "energy_model.joblib"
METRICS_PATH = ARTIFACT_DIR / "metrics.json"


def build_pipelines() -> dict[str, Pipeline]:
    """One-hot encode drone_type, pass numerics through, then fit the regressor."""

    def prep() -> ColumnTransformer:
        return ColumnTransformer(
            [("type", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES)],
            remainder="passthrough",
        )

    models = {
        "LinearRegression": LinearRegression(),
        "RandomForestRegressor": RandomForestRegressor(
            n_estimators=200, min_samples_leaf=2, n_jobs=-1, random_state=SEED
        ),
        "GradientBoostingRegressor": GradientBoostingRegressor(
            n_estimators=400, learning_rate=0.08, max_depth=4, subsample=0.9, random_state=SEED
        ),
    }
    return {name: Pipeline([("prep", prep()), ("model", m)]) for name, m in models.items()}


def load_split(csv_path: Path = DEFAULT_CSV):
    if not csv_path.exists():
        generate_dataset(csv_path)
    df = pd.read_csv(csv_path)
    x_train, x_test, y_train, y_test = train_test_split(
        df[FEATURE_COLUMNS], df[TARGET], test_size=0.2, random_state=SEED
    )
    return df, x_train, x_test, y_train, y_test


def rmse(y_true, y_pred) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def feature_importance(pipe: Pipeline) -> dict[str, float]:
    """Importance per ORIGINAL feature (one-hot columns are summed back into drone_type)."""
    model = pipe.named_steps["model"]
    names = pipe.named_steps["prep"].get_feature_names_out()
    if hasattr(model, "feature_importances_"):
        raw = model.feature_importances_
    else:  # linear model: |coefficient| scaled by feature std is not available -> use |coef|
        raw = np.abs(model.coef_)
    agg: dict[str, float] = {f: 0.0 for f in NUMERIC_FEATURES + CATEGORICAL_FEATURES}
    for name, val in zip(names, raw):
        clean = name.split("__", 1)[1]
        key = "drone_type" if clean.startswith("drone_type_") else clean
        agg[key] += float(val)
    total = sum(agg.values()) or 1.0
    return {k: round(v / total, 4) for k, v in sorted(agg.items(), key=lambda kv: -kv[1])}


def main() -> dict:
    df, x_train, x_test, y_train, y_test = load_split()
    kfold = KFold(n_splits=5, shuffle=True, random_state=SEED)
    results: dict[str, dict] = {}
    fitted: dict[str, Pipeline] = {}

    for name, pipe in build_pipelines().items():
        cv = cross_validate(
            pipe,
            x_train,
            y_train,
            cv=kfold,
            scoring=("neg_root_mean_squared_error", "neg_mean_absolute_error", "r2"),
        )
        pipe.fit(x_train, y_train)
        pred = pipe.predict(x_test)
        results[name] = {
            "mae": round(float(mean_absolute_error(y_test, pred)), 4),
            "rmse": round(rmse(y_test, pred), 4),
            "r2": round(float(r2_score(y_test, pred)), 4),
            "cv_rmse_mean": round(float(-cv["test_neg_root_mean_squared_error"].mean()), 4),
            "cv_rmse_std": round(float(cv["test_neg_root_mean_squared_error"].std()), 4),
            "cv_mae_mean": round(float(-cv["test_neg_mean_absolute_error"].mean()), 4),
            "cv_r2_mean": round(float(cv["test_r2"].mean()), 4),
        }
        fitted[name] = pipe
        print(f"{name:28s} test RMSE={results[name]['rmse']:.4f} R2={results[name]['r2']:.4f} "
              f"| CV RMSE={results[name]['cv_rmse_mean']:.4f}")

    best = min(results, key=lambda n: results[n]["cv_rmse_mean"])
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(fitted[best], MODEL_PATH)

    metrics = {
        "best_model": best,
        "selection_criterion": "lowest 5-fold cross-validated RMSE on the training split",
        "target": TARGET,
        "features": FEATURE_COLUMNS,
        "n_rows": int(len(df)),
        "n_train": int(len(x_train)),
        "n_test": int(len(x_test)),
        "seed": SEED,
        "sklearn_version": sklearn.__version__,
        "models": results,
        "feature_importance": feature_importance(fitted[best]),
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    print(f"best model: {best}  -> {MODEL_PATH}")
    return metrics


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
