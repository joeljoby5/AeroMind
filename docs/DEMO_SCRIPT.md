# AeroMind - demo script (about 8 minutes)

**Before you start (2 min, do it once):**

1. `make setup && make seed && make dev`, then open **http://localhost:3000** (Chrome, full screen).
2. Open `notebooks/01_energy_model.ipynb` in a second tab (`make jupyter`, or VS Code). Outputs are already stored.
3. The sample mission (8 waypoints) and 4 drones load automatically. If you have already run a mission, run `make reseed`, restart the API and refresh.
4. Internet is needed for the map tiles; without it the demo still works on a dark background.

**Screen layout:** left = fleet + mission controls, centre = map, right = tabs (*Allocation · AI Comparison · Model · Events*).

---

## 1. The problem and the screen (0:00 - 0:45)

**Do:** stay on the dashboard; point at the fleet, the map and the tabs.

**Say:** "AeroMind lets an operator plan and supervise a multi-drone mission. The interesting part is the planning: which drone should fly which task, and can it get home afterwards? The flight itself is simulated in this milestone - PX4/Gazebo is the next one - but everything above the simulator is real."

## 2. Fleet and mission (0:45 - 1:45)

**Do:** point at the four drone cards, then at the map.

**Say:** "Four drones of three airframe types: small quad, medium quad, heavy hex. They differ in battery level and battery health - **Wren-4 is deliberately at 38 %**. The grey numbered circles are the eight sample waypoints; the **H** squares are the drones' launch pads."

**Do (creating a mission, ~20 s):** click **＋ Add waypoints**, click the map once or twice to drop extra waypoints (they appear in the list on the left with altitude and payload fields), then click **Load sample** to return to the 8-waypoint sample.

**Say:** "Missions are created by clicking waypoints. Each waypoint has an altitude and a payload - payload matters because it changes how much energy the leg costs."

**Do (registering a drone, optional, ~30 s - do this last if you want the numbers below to stay as written):** click **＋ Register drone**, name it *Kite-5*, Type = *Hex (heavy)*, click **Pick on map** and click a spot near the base, then **Register**. The fleet count becomes 5.

**Say:** "Drones are registered here and stored in the database; a new drone is included in the next plan."

## 3. Plan with AI (1:45 - 3:15)

**Do:** make sure the strategy toggle says **AI · energy-aware**, click **Plan**. Switch to the **Allocation** tab.

**Say:** "Planning does two things. First, **task allocation**: a regression model trained to predict battery use for every drone-to-task leg feeds the **Hungarian algorithm**, which finds the assignment with the lowest total energy. A pairing is forbidden if the drone could not fly there, get home, and still keep a **15 % reserve**. Second, **A\* path planning** routes each drone around known obstacles."

**Do:** point at the colours - each drone has its own colour on the map (dashed routes) and in the table. Hover a numbered waypoint to show which drone owns it and the predicted % battery. Point at Wren-4's row.

**Say:** "Wren-4 only got two short tasks - about 12 % of its battery - because it starts at 38 %. The heavy hex takes heavy-payload tasks because payload hurts small quads far more."

## 4. AI vs baseline (3:15 - 4:30)

**Do:** open the **AI Comparison** tab.

**Say:** "This is the same mission allocated the naive way - **distance only**, no model. Both plans are scored against the noise-free physics formula, not against the ML model, so it isn't grading its own homework. On this mission the AI plan uses about **12 % less energy** and avoids **one assignment that would have broken the battery reserve**."

**Do (optional, 30 s):** click the **Baseline · distance** toggle, click **Plan**, show how the Allocation tab changes (and Wren-4's load); toggle back to **AI** and **Plan** again.

**Say (be candid - examiners like this):** "Over 200 random missions the average energy saving is only about **2 %**. The real benefit is **safety**: the baseline breaks the battery-reserve rule in **58 % of missions**, the AI in **3 %**." *(Numbers from `make evaluate`; chart in `docs/allocation_comparison.png`.)*

## 5. The model and notebook (4:30 - 5:45)

**Do:** click the **Model** tab, then switch to the notebook tab.

**Say:** "The data is **synthetic** - 20,000 flight legs generated from a documented physical formula, because real multi-drone logs don't exist yet. I compared linear regression, random forest and gradient boosting with 5-fold cross-validation. Gradient boosting wins: **MAE 0.64 % battery, R² 0.993**; linear regression is much worse because energy depends on interactions between airframe, payload and wind. Distance is the most important feature, but payload, airframe and wind carry real signal - exactly what the distance-only method throws away."

**Do:** scroll the notebook: dataset table → correlation heatmap → model comparison → predicted-vs-actual → feature importance.

**Say:** "Because the data is synthetic, the accuracy proves the pipeline, not real-world accuracy. The next milestone regenerates this dataset from PX4/Gazebo flights and reruns `make train`. The model is only an *advisory* estimator - a distance fallback always exists."

## 6. Fly it (5:45 - 6:30)

**Do:** return to the dashboard, open the **Events** tab, click **▶ Start**.

**Say:** "Drones take off and follow their routes; positions and battery stream over a WebSocket every half second from a mock simulator. The badge on each card is the drone's **finite-state machine**: armed, take-off, en route, executing task, avoiding, return to launch, landed, failsafe. Every transition shows up in the event log." *(A full run takes about 1 min 45 s.)*

## 7. Obstacle → LiDAR → replan (6:30 - 7:10)

**Do:** about 10 seconds after Start, click **⚠ Inject obstacle**, then click the map **on a coloured line roughly 100 m ahead of a drone** (not right at the base). Watch the Events tab.

**Say:** "I just dropped an obstacle the drones didn't know about. Each drone has a simulated LiDAR - 36 rays, 60 m range. When a return comes in under **25 m** the FSM switches to *AVOIDING*, the drone holds, **A\*** replans around the obstacle, and it resumes - the route on the map bends around the red circle."

**Events to point at:** `EN_ROUTE -> AVOIDING: LiDAR: obstacle at 22 m …` → `Replanned A* route: … (+37 m vs previous route)` → `AVOIDING -> EN_ROUTE`.

## 8. Low battery → return to launch (7:10 - 7:40)

**Do:** on a drone that is still flying (Wren-4 is a good one), click **⚡ −20 %** on its card.

**Say:** "A battery fault. The FSM compares the battery with the *energy needed to get home plus the reserve*. The drone no longer has enough, so it abandons the rest of its tasks and goes to **return-to-launch**."

**Events to point at:** `… Low battery … : return to launch` → `RETURN_TO_LAUNCH -> LANDED`.

## 9. Wrap-up (7:40 - 8:00)

**Say:** "To summarise: a trained energy model feeding Hungarian allocation with a deterministic fallback, A\* planning and live replanning, an FSM per drone, and a real-time dashboard. Simulated in this milestone: the flight, the LiDAR, and the training data. Next milestone: plug PX4 + Gazebo in behind the `DroneAdapter` interface - the `MavlinkAdapter` stub is already there - and retrain on real simulator logs."

---

## If something goes wrong

| symptom | fix |
|---|---|
| Red banner "Cannot reach the API" | `make dev` is not running or the API crashed - restart it |
| **Plan** and **Start** greyed out | a mission is still running - click **■ Stop**, wait for *landed*, or refresh |
| Start is greyed out | click **Plan** first (Start is enabled only when a plan exists for the waypoints shown) |
| Obstacle didn't trigger a replan | it wasn't on/near a route ahead of a drone - after the run click **Clear (n)** and repeat |
| Numbers differ from this script | you registered a drone or edited waypoints; **Load sample** → **Plan** restores the sample numbers |
| Blank map background | no internet for tiles - everything else still works |
| Run it again | wait for *completed*, press **Plan** then **Start** (batteries reset; obstacles persist until **Clear**) |

## Questions you may get

- **Why synthetic data?** No real multi-drone energy logs exist yet; the formula is documented in `ai/energy_model/generate_dataset.py`, and the pipeline is what matters until PX4/Gazebo produces logs.
- **Why is the average energy saving only ~2 %?** With similar drones, distance is already a good proxy. The model matters when drones differ in type, payload, health and battery - and for *feasibility*, where the gap is large (58 % vs 3 % of missions).
- **Why does the ML plan still have 3 % infeasible missions?** Prediction error right at the reserve boundary (MAE 0.64 %). A larger reserve or a conservative bias would remove them at some energy cost.
- **What is deterministic?** The baseline allocation, A\*, the FSM and the LiDAR check. The model is an advisory cost estimator behind an interface, with a heuristic fallback.
- **What changes for PX4/Gazebo?** Implement `MavlinkAdapter` (the mapping is documented in its docstring) and feed the simulated LiDAR topic into `ai.obstacles.detect`; everything else is unchanged.
