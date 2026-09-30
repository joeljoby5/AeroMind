"""Synthetic, physically motivated flight-leg energy dataset (seeded, reproducible).

Run:  python -m ai.energy_model.generate_dataset

Target formula (``physical_energy_pct``), energy in % of battery for one leg::

    speed_mult   = 1 + 0.008 * (cruise_speed - v_opt[type])^2        # U-shaped efficiency curve
    wind_mult    = clip(1 - 0.035 * wind_speed * wind_alignment
                          + 0.004 * wind_speed, 0.45, 2.0)           # headwind costs, tailwind saves
    payload_mult = 1 + k_payload[type] * payload_kg
    climb        = c_climb[type] * altitude_change        if climbing
                 = 0.25 * c_climb[type] * altitude_change if descending (small credit, negative)
    cruise       = base[type] * distance * speed_mult * wind_mult
    energy       = (overhead + payload_mult * (cruise + climb)) / battery_health
    energy_pct   = clip(energy * N(1, 0.03), 0.2, 100)               # ~3 % Gaussian noise

with per-type constants

    ============  ===========  ===========  ===========  ======
    type          base (%/m)   k_payload    c_climb      v_opt
    ============  ===========  ===========  ===========  ======
    quad_small    0.0100       0.20         0.060        9 m/s
    quad_medium   0.0080       0.11         0.040        10 m/s
    hex_heavy     0.0065       0.06         0.030        8 m/s
    ============  ===========  ===========  ===========  ======

``overhead`` = 0.5 % (take-off / landing / hover). Small drones are the cheapest per metre but
suffer most from payload and climbing; the heavy hexacopter is the opposite. That cross-over is
exactly what a distance-only allocator cannot see and the ML energy model can.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ai.energy_model.features import DRONE_TYPES, FEATURE_COLUMNS, RANGES, TARGET

SEED = 42
N_ROWS = 20_000
OVERHEAD_PCT = 0.5
NOISE_FRAC = 0.03

BASE_PCT_PER_M = {"quad_small": 0.0100, "quad_medium": 0.0080, "hex_heavy": 0.0065}
PAYLOAD_K = {"quad_small": 0.20, "quad_medium": 0.11, "hex_heavy": 0.06}
CLIMB_PCT_PER_M = {"quad_small": 0.060, "quad_medium": 0.040, "hex_heavy": 0.030}
OPTIMAL_SPEED = {"quad_small": 9.0, "quad_medium": 10.0, "hex_heavy": 8.0}
DESCENT_CREDIT = 0.25

DEFAULT_CSV = Path(__file__).resolve().parents[2] / "data" / "energy_dataset.csv"


def physical_energy_pct(
    drone_type,
    distance_m,
    altitude_change_m,
    payload_kg,
    wind_speed_ms,
    wind_alignment,
    battery_health,
    cruise_speed_ms,
    *,
    rng: np.random.Generator | None = None,
    noise_frac: float = NOISE_FRAC,
):
    """Ground-truth energy (% battery) for a leg. Vectorised; scalars also work.

    With ``rng=None`` the result is noise-free (used as the "actual physics" reference).
    """
    t = np.asarray(drone_type)
    base = np.vectorize(BASE_PCT_PER_M.get, otypes=[float])(t)
    k_pay = np.vectorize(PAYLOAD_K.get, otypes=[float])(t)
    c_climb = np.vectorize(CLIMB_PCT_PER_M.get, otypes=[float])(t)
    v_opt = np.vectorize(OPTIMAL_SPEED.get, otypes=[float])(t)

    speed_mult = 1.0 + 0.008 * (np.asarray(cruise_speed_ms) - v_opt) ** 2
    wind_mult = np.clip(
        1.0 - 0.035 * np.asarray(wind_speed_ms) * np.asarray(wind_alignment)
        + 0.004 * np.asarray(wind_speed_ms),
        0.45,
        2.0,
    )
    payload_mult = 1.0 + k_pay * np.asarray(payload_kg)
    alt = np.asarray(altitude_change_m, dtype=float)
    climb = np.where(alt >= 0, c_climb * alt, DESCENT_CREDIT * c_climb * alt)
    cruise = base * np.asarray(distance_m) * speed_mult * wind_mult
    energy = (OVERHEAD_PCT + payload_mult * (cruise + climb)) / np.asarray(battery_health)
    if rng is not None:
        energy = energy * rng.normal(1.0, noise_frac, size=np.shape(energy))
    return np.clip(energy, 0.2, 100.0)


def generate(n: int = N_ROWS, seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    lo, hi = RANGES["distance_m"]
    # Half the legs span the full 50-3000 m range, half are campus-scale (50-800 m) legs so the
    # short legs that dominate real missions are well covered.
    full = rng.uniform(lo, hi, n)
    short = rng.uniform(lo, 800.0, n)
    distance = np.where(rng.random(n) < 0.5, full, short)
    df = pd.DataFrame(
        {
            "distance_m": distance,
            "altitude_change_m": rng.uniform(*RANGES["altitude_change_m"], n),
            "payload_kg": rng.uniform(*RANGES["payload_kg"], n),
            "wind_speed_ms": rng.uniform(*RANGES["wind_speed_ms"], n),
            "wind_alignment": rng.uniform(*RANGES["wind_alignment"], n),
            "battery_health": rng.uniform(*RANGES["battery_health"], n),
            "drone_type": rng.choice(DRONE_TYPES, n),
            "cruise_speed_ms": rng.uniform(*RANGES["cruise_speed_ms"], n),
        }
    )
    df[TARGET] = physical_energy_pct(
        df["drone_type"].to_numpy(),
        df["distance_m"].to_numpy(),
        df["altitude_change_m"].to_numpy(),
        df["payload_kg"].to_numpy(),
        df["wind_speed_ms"].to_numpy(),
        df["wind_alignment"].to_numpy(),
        df["battery_health"].to_numpy(),
        df["cruise_speed_ms"].to_numpy(),
        rng=rng,
    )
    return df[FEATURE_COLUMNS + [TARGET]].round(4)


def main(path: Path = DEFAULT_CSV) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = generate()
    df.to_csv(path, index=False)
    print(f"wrote {len(df)} rows -> {path}")
    return path


if __name__ == "__main__":
    main()
