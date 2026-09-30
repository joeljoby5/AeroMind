"""Compare ML energy-aware allocation with the distance-only baseline on random missions.

Run:  python -m ai.evaluate_allocation [--missions 200]

Both allocations are scored against the noise-free physics ground truth (not against the model that
planned them), so the comparison cannot flatter the ML model with its own predictions. An
assignment is *battery-infeasible* if the drone could not fly to the task, return home and still
hold the 15 % reserve.
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np

from ai.allocation import allocate, evaluate_allocation
from ai.energy_model.features import Environment
from ai.energy_model.predict import EnergyPredictor
from ai.geo import LocalFrame
from ai.types import DroneState, Task

DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"
HOME = (12.9716, 77.5946)
TYPES = ("quad_small", "quad_medium", "hex_heavy")
ML_COLOR, BASE_COLOR = "#2a78d6", "#eb6834"  # categorical slots 1 and 2 of the reference palette


def random_mission(rnd: random.Random):
    frame = LocalFrame(*HOME)
    n_drones, n_tasks = rnd.randint(4, 5), rnd.randint(6, 10)
    drones = []
    for i in range(n_drones):
        lat, lon = frame.to_latlon(rnd.uniform(-60, 60), rnd.uniform(-60, 60))
        drones.append(DroneState(id=i + 1, name=f"D{i + 1}", type=rnd.choice(TYPES), lat=lat, lon=lon,
                                 battery_pct=rnd.uniform(25, 100), health=rnd.uniform(0.75, 1.0)))
    tasks = []
    for j in range(n_tasks):
        lat, lon = frame.to_latlon(rnd.uniform(-900, 900), rnd.uniform(-900, 900))
        tasks.append(Task(id=j + 1, lat=lat, lon=lon, altitude_m=rnd.uniform(20, 70),
                          payload_kg=rnd.choice([0.0, 0.0, rnd.uniform(0.3, 2.5)])))
    env = Environment(wind_speed_ms=rnd.uniform(2, 10), wind_to_deg=rnd.uniform(0, 360))
    return drones, tasks, env


def run(n_missions: int = 200, seed: int = 7) -> dict:
    rnd = random.Random(seed)
    predictor = EnergyPredictor()
    rows = {"ml": [], "baseline": []}
    for _ in range(n_missions):
        drones, tasks, env = random_mission(rnd)
        for strategy in rows:
            res = allocate(drones, tasks, strategy, predictor if strategy == "ml" else None, env)
            rows[strategy].append(evaluate_allocation(res, drones, tasks, env))

    def agg(strategy: str) -> dict:
        r = rows[strategy]
        energy = np.array([x["total_energy_pct"] for x in r])
        assigned = np.array([x["assigned"] for x in r])
        return {
            "avg_total_energy_pct": float(energy.mean()),
            "avg_energy_per_assigned_task_pct": float((energy.sum() / max(assigned.sum(), 1))),
            "missions_with_infeasible_pct": 100.0 * float(np.mean([x["infeasible_assignments"] > 0 for x in r])),
            "avg_infeasible_assignments": float(np.mean([x["infeasible_assignments"] for x in r])),
            "avg_unassigned_tasks": float(np.mean([x["unassigned"] for x in r])),
            "avg_assigned_tasks": float(assigned.mean()),
        }

    return {"n_missions": n_missions, "seed": seed, "model": predictor.model_name,
            "ml": agg("ml"), "baseline": agg("baseline")}


def save_chart(summary: dict, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    surface, ink, muted, grid = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), facecolor=surface)
    panels = [
        ("avg_total_energy_pct", "Average mission energy", "% battery (physics ground truth)"),
        ("missions_with_infeasible_pct", "Missions with a battery-infeasible assignment", "% of missions"),
    ]
    for ax, (key, title, ylabel) in zip(axes, panels):
        vals = [summary["ml"][key], summary["baseline"][key]]
        bars = ax.bar(["ML energy-aware", "Distance baseline"], vals, color=[ML_COLOR, BASE_COLOR], width=0.5)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.1f}", ha="center", va="bottom", color=ink, fontsize=11)
        ax.set_title(title, color=ink, fontsize=11, loc="left")
        ax.set_ylabel(ylabel, color=muted)
        ax.set_facecolor(surface)
        ax.set_ylim(0, max(vals) * 1.2 or 1)
        ax.yaxis.grid(True, color=grid, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.tick_params(colors=muted, length=0)
    fig.suptitle(f"ML vs distance-only allocation - {summary['n_missions']} random missions", color=ink, fontsize=12)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=surface)


def main() -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--missions", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    s = run(args.missions, args.seed)
    ml, base = s["ml"], s["baseline"]
    print(f"\nAllocation comparison over {s['n_missions']} random missions (model: {s['model']})")
    print(f"{'':44s}{'ML':>12s}{'Baseline':>12s}")
    rows = [
        ("Avg total energy per mission (%)", "avg_total_energy_pct"),
        ("Avg energy per assigned task (%)", "avg_energy_per_assigned_task_pct"),
        ("Missions with battery-infeasible assignment (%)", "missions_with_infeasible_pct"),
        ("Avg infeasible assignments per mission", "avg_infeasible_assignments"),
        ("Avg tasks assigned", "avg_assigned_tasks"),
        ("Avg tasks left unassigned", "avg_unassigned_tasks"),
    ]
    for label, key in rows:
        print(f"{label:44s}{ml[key]:12.2f}{base[key]:12.2f}")
    save_chart(s, DOCS_DIR / "allocation_comparison.png")
    print(f"\nchart saved -> {DOCS_DIR / 'allocation_comparison.png'}")
    return s


if __name__ == "__main__":
    main()
