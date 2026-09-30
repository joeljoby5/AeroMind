import pytest


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["model_is_fallback"] is False


def test_seed_data_present_and_idempotent(client, settings):
    from app.seed import seed
    drones = client.get("/api/drones").json()
    assert [d["name"] for d in drones] == ["Falcon-1", "Hawk-2", "Atlas-3", "Wren-4"]
    assert {d["type"] for d in drones} == {"quad_small", "quad_medium", "hex_heavy"}
    assert seed(settings)["seeded"] is False
    detail = client.get("/api/missions/1").json()
    assert len(detail["tasks"]) == 8 and detail["mission"]["status"] == "draft"


def test_create_drone_and_validation(client):
    ok = client.post("/api/drones", json={"name": "X", "type": "quad_medium", "battery_pct": 80,
                                          "health": 0.9, "home_lat": 12.97, "home_lon": 77.59})
    assert ok.status_code == 201 and ok.json()["status"] == "idle"
    bad = client.post("/api/drones", json={"name": "X", "type": "rocket", "home_lat": 0, "home_lon": 0})
    assert bad.status_code == 422


def test_create_mission(client):
    r = client.post("/api/missions", json={"name": "m", "tasks": [{"lat": 12.972, "lon": 77.595}]})
    assert r.status_code == 201 and r.json()["tasks"][0]["altitude_m"] == 30.0
    assert client.post("/api/missions", json={"name": "m", "tasks": []}).status_code == 422
    assert len(client.get("/api/missions").json()) == 2


@pytest.mark.parametrize("strategy", ["ml", "baseline"])
def test_plan_assigns_every_task_and_persists(client, strategy):
    plan = client.post(f"/api/missions/1/plan?strategy={strategy}").json()
    assert plan["strategy"] == strategy and not plan["unassigned"]
    assert sorted(a["task_id"] for a in plan["assignments"]) == list(range(1, 9))
    assert plan["routes"] and all(len(r["polyline"]) >= 3 for r in plan["routes"])
    detail = client.get("/api/missions/1").json()
    assert detail["mission"]["status"] == "planned" and detail["mission"]["strategy"] == strategy
    assert len(detail["assignments"]) == 8 and len(detail["routes"]) == len(plan["routes"])


def test_replan_replaces_previous_assignments(client):
    client.post("/api/missions/1/plan?strategy=ml")
    client.post("/api/missions/1/plan?strategy=baseline")
    assert len(client.get("/api/missions/1").json()["assignments"]) == 8


def test_invalid_strategy_and_missing_mission(client):
    assert client.post("/api/missions/1/plan?strategy=magic").status_code == 422
    assert client.post("/api/missions/99/plan").status_code == 404
    assert client.get("/api/missions/99").status_code == 404


def test_compare_ml_vs_baseline(client):
    c = client.get("/api/missions/1/compare").json()
    assert c["ml"]["assigned"] == 8 and c["baseline"]["assigned"] == 8
    assert c["ml"]["actual_energy_pct"] < c["baseline"]["actual_energy_pct"]
    assert c["ml"]["infeasible_assignments"] <= c["baseline"]["infeasible_assignments"]
    assert c["energy_saving_pct"] > 0


def test_low_battery_drone_is_not_overloaded_by_ml(client):
    plan = client.post("/api/missions/1/plan?strategy=ml").json()
    wren = next(d for d in client.get("/api/drones").json() if d["name"] == "Wren-4")
    energy = sum(a["predicted_energy_pct"] for a in plan["assignments"] if a["drone_id"] == wren["id"])
    assert energy + 15 < wren["battery_pct"]  # leaves the reserve


def test_obstacle_is_respected_when_planning(client):
    plan = client.post("/api/missions/1/plan?strategy=ml").json()
    route = plan["routes"][0]["polyline"]
    mid = route[len(route) // 2]
    ob = client.post("/api/missions/1/obstacles", json={"lat": mid[0], "lon": mid[1], "radius_m": 40})
    assert ob.status_code == 201
    replanned = client.post("/api/missions/1/plan?strategy=ml").json()
    assert len(client.get("/api/missions/1").json()["obstacles"]) == 1
    assert replanned["routes"]
    assert client.delete("/api/missions/1/obstacles").status_code == 204
    assert client.get("/api/missions/1").json()["obstacles"] == []


def test_model_info_and_predict(client):
    info = client.get("/api/ai/model-info").json()
    assert info["best_model"] == info["active_model"] and info["models"] and info["feature_importance"]
    body = {"drone_type": "quad_small", "distance_m": 1000, "payload_kg": 1.0, "wind_speed_ms": 8,
            "wind_alignment": -1.0, "battery_health": 0.9, "cruise_speed_ms": 10}
    head = client.post("/api/ai/predict-energy", json=body).json()
    tail = client.post("/api/ai/predict-energy", json={**body, "wind_alignment": 1.0}).json()
    assert head["energy_pct"] > tail["energy_pct"] > 0


def test_start_requires_a_plan(client):
    r = client.post("/api/missions/1/start")
    assert r.status_code == 400 and "plan" in r.json()["detail"]
    assert client.post("/api/missions/99/start").status_code == 404
