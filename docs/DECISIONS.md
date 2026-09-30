# Design decisions and assumptions

The build prompt said: *if a requirement is ambiguous, choose the simplest option, note it here, and continue.* These are those choices, plus the places where I deliberately added something small. Items marked **⚠ check** are worth confirming against your SDD / guide's expectations.

## Scope and naming

| # | Decision | Why |
|---|---|---|
| D-01 | The repository root **is** the monorepo (no nested `aeromind/` folder). | The repo is already named AeroMind. |
| D-02 ⚠ check | **FR-01 … FR-07 were assigned by me** from the project description (see the README mapping). | The SDD was not available to me. Renumber/rename to match your SDD. |
| D-03 ⚠ check | Endpoint names are the defaults from the prompt. | "If my SDD lists different names, keep my SDD names" - no SDD was provided. |
| D-04 | Default home location is a sample point in Bengaluru (`12.9716, 77.5946`), configurable with `HOME_LAT` / `HOME_LON`; run `make reseed` after changing it. | "Sample campus location" was not specified. |

## AI

| # | Decision | Why |
|---|---|---|
| D-10 | Best model is selected by **lowest 5-fold CV RMSE on the training split**, not by test RMSE. | Keeps the test set untouched for the final numbers. |
| D-11 | Half of the dataset's legs are 50-800 m, half 50-3000 m. | Campus missions are dominated by short legs; uniform sampling under-covers them. Still within the specified 50-3000 m range. |
| D-12 | `physical_energy_pct` (noise-free) is the **ground truth used to evaluate plans** (`evaluate_allocation`, `/compare`, `make evaluate`). | Evaluating the ML plan with the ML model would be circular. |
| D-13 | The **baseline is pure distance - no feasibility check**. The ML strategy has the feasibility penalty. | "Distance-only baseline"; comparing infeasible assignments is meaningless otherwise. The baseline uses the predictor only to *report* comparable predicted energies. |
| D-14 | Multi-round allocation: an infeasible pair chosen by the Hungarian solver is dropped and its task retried next round; a round with no feasible pair ends allocation and the remaining tasks are reported *unassigned* with a reason. | Spec: every task gets assigned if possible. |
| D-15 | Legs longer than the 3 km training maximum are extrapolated linearly from the model's 3 km prediction. | Trees cannot extrapolate. |
| D-16 | A\* adds **line-of-sight shortcutting** on top of collinear-point removal; a straight line is returned directly when it clears all (inflated) obstacles. | Collinear removal alone left 13-waypoint staircases on the map. |
| D-17 | The return-to-home energy used by the FSM and the feasibility check is for the **direct line** home, not the A\* path. | Simplicity; the 15 % reserve absorbs detours. |

## Runtime and simulator

| # | Decision | Why |
|---|---|---|
| D-20 | **Split of responsibilities:** `MockAdapter` only moves vehicles and drains batteries; FSM, LiDAR and replanning live in `runtime_service`. | The prompt lists both under "MockAdapter", but a real PX4 adapter also only provides telemetry and accepts `goto`; keeping decisions above the adapter means nothing changes when it is swapped. |
| D-21 | Injected obstacles are **unknown to drones until LiDAR detects them** (< 25 m). Obstacles present at plan/start time are known and planned around. | Matches the demo ("LiDAR threshold triggers replanning") and is more realistic than an omniscient replan. |
| D-22 | `AVOIDING` is entered only from `EN_ROUTE`. During return-to-launch a newly seen obstacle triggers a silent re-route (event logged, no state change); if no route exists → `FAILSAFE`. A later task made unreachable by a new obstacle is skipped with an event; only an unreachable *current* target causes `FAILSAFE`. | Keeps the prescribed state machine simple. |
| D-23 | Battery drain in the mock = marginal slope of the energy model's energy-vs-distance curve for the current conditions × distance flown × noise (3 %), plus a fixed hover drain and the 0.5 % take-off overhead at arming. | "Same energy model with small noise" without charging the model's per-leg overhead on every small path segment. |
| D-24 | A drone flies carrying the payload of the task it is heading to and drops it (0 kg) after the task; return legs carry 0 kg. | Matches how the allocator prices legs. |
| D-25 | A run does **not** write the drained battery back to the `Drone` row. | Keeps the demo repeatable. |
| D-26 | One mission may run at a time; one constant wind vector over the area. | Simplest thing that works for the demo. |
| D-27 | Default `SPEEDUP=2.0` (tick 0.5 s → 1 simulated second per tick). Measured: the sample mission completes in about 105 s. | "About 2 minutes." |
| D-28 | Telemetry samples are persisted every 4th tick. | Keeps the table small. |

## Small additions beyond the prompt

| # | Addition | Why |
|---|---|---|
| D-30 | `POST /api/drones/{id}/drain` and the **⚡ −20 %** button. | The demo must show low battery → RTL; with planner-enforced reserves that would otherwise only happen by chance. |
| D-31 | `DELETE /api/missions/{id}/obstacles` and the **Clear (n)** button. | Obstacles persist with the mission; without this a second demo run would not be repeatable. |
| D-32 | **Register drone** form (with pick-on-map). | Goal 1 of the demo says "register drones"; the API alone was not demoable. |
| D-33 | `scripts/final_checklist.py` / `make checklist`. | The prompt asks for a final checklist. |
| D-34 | `HungarianAllocator`, `AStarPlanner`, `EnergyPredictor` implement the `ai/interfaces.py` Protocols; `HeuristicEstimator` and `PhysicsEstimator` are extra `EnergyEstimator`s. | Needed for "independently replaceable"; Physics is the evaluator (D-12). |

## Frontend and tooling

| # | Decision | Why |
|---|---|---|
| D-40 | Editing waypoints does not mutate a saved mission: the next **Plan** creates a new mission with the edited waypoints. | No edit endpoints were listed; avoids stale assignments. |
| D-41 | Next.js 15, React 19, Tailwind 3.4, TypeScript 5.9, react-leaflet 5, recharts 3 (pinned). | Stable, mutually compatible versions. |
| D-42 | No Alembic migrations; tables are created with `create_all`. | "No premature abstractions"; acceptable for a demo database. |
| D-43 | The dark map is OpenStreetMap tiles inverted with a CSS filter. | The prompt requires OSM tiles and a dark theme. |
| D-44 ⚠ check | `docker-compose.yml` validates (`docker compose config`) but the images were **not built** - there was no Docker daemon where this was written. `make dev` (SQLite) was run and tested end to end. | Be upfront if Docker is demoed. |
