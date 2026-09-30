import time

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.seed import seed


def test_ws_sends_snapshot_then_live_ticks(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'ws.db'}", auto_tick=True, tick_s=0.05, speedup=6.0)
    seed(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        client.post("/api/missions/1/plan?strategy=ml")
        with client.websocket_connect("/ws/telemetry") as ws:
            first = ws.receive_json()
            assert first["type"] == "snapshot" and len(first["drones"]) == 4
            client.post("/api/missions/1/start")
            ticks = [ws.receive_json() for _ in range(6)]
            assert all(t["type"] == "tick" for t in ticks)
            assert ticks[-1]["sim_time_s"] > ticks[0]["sim_time_s"]
            assert {"id", "name", "lat", "lon", "battery_pct", "state"} <= set(ticks[-1]["drones"][0])
            client.post("/api/missions/1/stop")


def test_ws_ticks_flow_even_when_idle(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'ws2.db'}", auto_tick=True, tick_s=0.05)
    seed(settings)
    with TestClient(create_app(settings)) as client, client.websocket_connect("/ws/telemetry") as ws:
        ws.receive_json()
        msg = ws.receive_json()
        assert msg["type"] == "tick" and not msg["running"] and len(msg["drones"]) == 4
