"""Verify the demo is ready and print the final checklist.  Run:  make checklist

Hard checks (exit code 1 if any fails): tests pass, notebook executed without errors, model and
dataset artifacts exist, frontend type-checks. Soft checks: API / dashboard reachable right now.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
results: list[tuple[str, bool, str, bool]] = []  # (name, ok, detail, hard)


def check(name: str, ok: bool, detail: str = "", hard: bool = True) -> None:
    results.append((name, ok, detail, hard))


def run(cmd: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def http_ok(url: str) -> bool:
    try:
        return urllib.request.urlopen(url, timeout=2).status == 200
    except Exception:
        return False


def main() -> int:
    # 1. tests
    p = run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    tail = (p.stdout.strip().splitlines() or [""])[-1]
    check("Python tests (AI + backend + e2e smoke)", p.returncode == 0, tail)

    # 2. notebook executed
    nb_path = ROOT / "notebooks" / "01_energy_model.ipynb"
    if nb_path.exists():
        nb = json.loads(nb_path.read_text())
        code = [c for c in nb["cells"] if c["cell_type"] == "code"]
        executed = all(c.get("outputs") is not None and c.get("execution_count") for c in code)
        errors = sum(1 for c in code for o in c.get("outputs", []) if o.get("output_type") == "error")
        images = sum(1 for c in code for o in c.get("outputs", []) if "image/png" in o.get("data", {}))
        check("Notebook executed with stored outputs", executed and errors == 0 and images >= 5,
              f"{len(code)} code cells, {images} plots, {errors} errors")
    else:
        check("Notebook executed with stored outputs", False, "notebooks/01_energy_model.ipynb missing")

    # 3. artifacts
    art = ROOT / "ai" / "energy_model" / "artifacts"
    metrics = json.loads((art / "metrics.json").read_text()) if (art / "metrics.json").exists() else {}
    best = metrics.get("models", {}).get(metrics.get("best_model", ""), {})
    check("Trained model + metrics.json", (art / "energy_model.joblib").exists() and bool(best),
          f"{metrics.get('best_model')}  MAE={best.get('mae')}  RMSE={best.get('rmse')}  R2={best.get('r2')}")
    csv = ROOT / "data" / "energy_dataset.csv"
    rows = sum(1 for _ in csv.open()) - 1 if csv.exists() else 0
    check("Dataset committed", rows >= 20000, f"{rows} rows")
    check("Allocation comparison chart", (ROOT / "docs" / "allocation_comparison.png").exists(), "docs/allocation_comparison.png")

    # 4. frontend type-check
    fe = ROOT / "frontend"
    if (fe / "node_modules").exists():
        t = run(["npx", "--no-install", "tsc", "--noEmit"], cwd=fe)
        check("Frontend type-check (tsc)", t.returncode == 0, "clean" if t.returncode == 0 else t.stdout[-200:])
    else:
        check("Frontend type-check (tsc)", False, "run `make setup` first (node_modules missing)")

    # 5. live services (soft)
    check("API running on :8000", http_ok("http://localhost:8000/health"), "make dev / docker compose up", hard=False)
    check("Dashboard running on :3000", http_ok("http://localhost:3000"), "make dev / docker compose up", hard=False)

    print("\nAeroMind 30% review - final checklist\n" + "=" * 40)
    for name, ok, detail, hard in results:
        mark = "PASS" if ok else ("FAIL" if hard else "NOTE")
        print(f"[{mark}] {name}" + (f"  - {detail}" if detail else ""))

    print("\nStubbed / simulated (be upfront about these in the review)\n" + "-" * 40)
    for line in [
        "PX4 + Gazebo + MAVLink: NOT integrated. MavlinkAdapter is a stub that raises NotImplementedError.",
        "Flight: MockAdapter kinematics (straight-line motion, fixed climb rate), not a flight dynamics model.",
        "Energy dataset: SYNTHETIC (physically motivated formula + noise). Model accuracy shows the pipeline works,",
        "  not real-world accuracy. Retrain on PX4/Gazebo logs in the next milestone.",
        "LiDAR: simulated 36-ray circle-intersection scan over user-injected obstacles (no real sensor data).",
        "Wind: one constant wind vector for the whole area. No auth, single mission at a time.",
        "docker-compose.yml: validated with `docker compose config`; images not built in the authoring sandbox.",
    ]:
        print(" *", line)

    hard_fail = [n for n, ok, _, hard in results if hard and not ok]
    print("\nRESULT:", "READY" if not hard_fail else f"NOT READY ({len(hard_fail)} failing: {', '.join(hard_fail)})")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
