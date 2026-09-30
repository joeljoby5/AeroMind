import pytest

from ai.geo import LocalFrame
from tests.conftest import drone, run_until


def _start(client, strategy="ml"):
    client.post(f"/api/missions/1/plan?strategy={strategy}")
    r = client.post("/api/missions/1/start")
    assert r.status_code == 200
    return r.json()


def test_e2e_smoke_seed_plan_start_and_state_transitions(client, runtime):
    """Seed -> plan -> start -> tick: every drone goes through the normal flight states and lands."""
    snap = _start(client)
    assert snap["running"] and all(d["state"] == "IDLE" for d in snap["drones"])
    seen: dict[str, set] = {}
    snap, ticks = run_until(runtime, lambda s: (
        [seen.setdefault(d["name"], set()).add(d["state"]) for d in s["drones"]] and not s["running"]))
    assert snap["mission_status"] == "completed"
    for name, states in seen.items():
        assert {"ARMED", "TAKEOFF", "EN_ROUTE", "EXECUTING_TASK", "RETURN_TO_LAUNCH", "LANDED"} <= states, name
    assert all(d["state"] == "LANDED" and d["tasks_done"] == d["tasks_total"] for d in snap["drones"])
    assert all(d["battery_pct"] > 15 for d in snap["drones"])  # reserve respected
    assert client.get("/api/missions/1").json()["mission"]["status"] == "completed"
    assert {d["status"] for d in client.get("/api/drones").json()} == {"idle"}


def test_telemetry_is_persisted(client, runtime):
    from app.repositories import MissionRepository
    _start(client)
    run_until(runtime, lambda s: not s["running"])
    with runtime.session_factory() as db:
        assert MissionRepository(db).telemetry_count() > 20


def test_battery_drains_while_flying_and_drones_move(client, runtime):
    snap0 = _start(client)
    home = {d["name"]: (d["lat"], d["lon"]) for d in snap0["drones"]}
    snap, _ = run_until(runtime, lambda s: all(d["state"] == "EN_ROUTE" for d in s["drones"]))
    for _ in range(10):
        snap = runtime.tick()
    for d in snap["drones"]:
        assert d["battery_pct"] < next(x for x in snap0["drones"] if x["name"] == d["name"])["battery_pct"]
        assert (d["lat"], d["lon"]) != home[d["name"]]
        assert d["route"] and d["alt_m"] > 10


def test_lidar_obstacle_triggers_avoiding_and_astar_replan(client, runtime):
    _start(client)
    snap, _ = run_until(runtime, lambda s: drone(s, "Falcon-1")["state"] == "EN_ROUTE")
    f = drone(snap, "Falcon-1")
    frame = LocalFrame(f["lat"], f["lon"])
    x, y = frame.to_xy(*f["route"][1])
    norm = (x * x + y * y) ** 0.5
    lat, lon = frame.to_latlon(x / norm * 110, y / norm * 110)  # 110 m ahead, on the route
    before = f["route"]
    r = client.post("/api/missions/1/obstacles", json={"lat": lat, "lon": lon, "radius_m": 30})
    assert r.status_code == 201
    assert any("injected" in e["message"] for e in runtime.tick()["events"])

    snap, _ = run_until(runtime, lambda s: drone(s, "Falcon-1")["state"] == "AVOIDING")
    assert drone(snap, "Falcon-1")["lidar_min_m"] < 25
    snap, _ = run_until(runtime, lambda s: drone(s, "Falcon-1")["state"] == "EN_ROUTE")
    assert drone(snap, "Falcon-1")["route"] != before  # the route changed around the obstacle
    assert any("Replanned A* route" in e["message"] for e in runtime.history(200))

    snap, _ = run_until(runtime, lambda s: not s["running"])
    f = drone(snap, "Falcon-1")
    assert f["state"] == "LANDED" and f["tasks_done"] == f["tasks_total"]  # still finishes its tasks


def test_low_battery_triggers_return_to_launch(client, runtime):
    _start(client)
    snap, _ = run_until(runtime, lambda s: drone(s, "Hawk-2")["state"] == "EN_ROUTE")
    assert drone(snap, "Hawk-2")["tasks_done"] == 0
    hawk_id = drone(snap, "Hawk-2")["id"]
    assert client.post(f"/api/drones/{hawk_id}/drain?pct=60").status_code == 202
    snap, _ = run_until(runtime, lambda s: drone(s, "Hawk-2")["state"] == "RETURN_TO_LAUNCH")
    assert drone(snap, "Hawk-2")["tasks_done"] < drone(snap, "Hawk-2")["tasks_total"]
    assert any("Low battery" in e["message"] for e in runtime.history(200))
    snap, _ = run_until(runtime, lambda s: not s["running"])
    assert drone(snap, "Hawk-2")["state"] == "LANDED"


def test_stop_sends_everyone_home(client, runtime):
    _start(client)
    run_until(runtime, lambda s: all(d["state"] == "EN_ROUTE" for d in s["drones"]))
    assert client.post("/api/missions/1/stop").status_code == 200
    snap, _ = run_until(runtime, lambda s: not s["running"])
    assert snap["mission_status"] == "stopped"
    assert all(d["state"] == "LANDED" and d["tasks_done"] < d["tasks_total"] for d in snap["drones"])
    assert client.get("/api/missions/1").json()["mission"]["status"] == "stopped"


def test_blocked_route_triggers_failsafe(client, runtime):
    """An obstacle dropped on a drone's next task makes the goal unreachable -> FAILSAFE."""
    client.post("/api/missions/1/plan?strategy=ml")
    detail = client.get("/api/missions/1").json()
    tasks = {t["id"]: t for t in detail["tasks"]}
    falcon = next(d for d in client.get("/api/drones").json() if d["name"] == "Falcon-1")
    first = next(a for a in detail["assignments"] if a["drone_id"] == falcon["id"] and a["order"] == 0)
    t = tasks[first["task_id"]]
    client.post("/api/missions/1/start")
    run_until(runtime, lambda s: drone(s, "Falcon-1")["state"] == "EN_ROUTE")
    client.post("/api/missions/1/obstacles", json={"lat": t["lat"], "lon": t["lon"], "radius_m": 40})
    snap, _ = run_until(runtime, lambda s: drone(s, "Falcon-1")["state"] in ("FAILSAFE", "LANDED"))
    assert drone(snap, "Falcon-1")["state"] == "FAILSAFE"
    assert any("FAILSAFE" in e["message"] for e in runtime.history(200))
    snap, _ = run_until(runtime, lambda s: not s["running"])  # the other drones finish normally
    assert snap["mission_status"] == "completed"


def test_cannot_start_twice_or_replan_while_running(client):
    _start(client)
    assert client.post("/api/missions/1/start").status_code == 409
    assert client.post("/api/missions/1/plan").status_code == 409
    assert client.delete("/api/missions/1/obstacles").status_code == 409


def test_drain_requires_a_flying_drone(client):
    assert client.post("/api/drones/1/drain?pct=10").status_code == 409


def test_restart_after_completion_works(client, runtime):
    _start(client)
    run_until(runtime, lambda s: not s["running"])
    snap = _start(client)
    assert snap["running"] and snap["sim_time_s"] == 0.0


def test_mavlink_adapter_is_a_documented_stub():
    from ai.types import DroneState
    from app.sim_adapter.mavlink_adapter import MavlinkAdapter
    with pytest.raises(NotImplementedError, match="next milestone"):
        MavlinkAdapter().connect(DroneState(1, "d", "quad_small", 0, 0))
    assert MavlinkAdapter.__doc__ and "PX4" in MavlinkAdapter.__doc__
