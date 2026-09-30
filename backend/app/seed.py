"""Seed 4 drones and one sample mission:  python -m app.seed  (or `make seed`).

Idempotent: does nothing if drones already exist. Pass --reset to wipe and re-seed.
"""
from __future__ import annotations

import argparse
import logging

from sqlalchemy import delete

from ai.geo import LocalFrame
from app import models
from app.config import Settings, get_settings
from app.db import init_db, make_engine, make_session_factory

# name, type, battery %, battery health, (north m, east m) launch-pad offset from the base
DRONES = [
    ("Falcon-1", "quad_small", 92.0, 0.95, (0, 0)),
    ("Hawk-2", "quad_medium", 78.0, 0.90, (0, 14)),
    ("Atlas-3", "hex_heavy", 85.0, 0.97, (-14, 0)),
    ("Wren-4", "quad_small", 38.0, 0.80, (-14, 14)),  # deliberately low battery
]

# (north m, east m, altitude m, payload kg) relative to the base
WAYPOINTS = [
    (220, 140, 35, 0.0),
    (380, -120, 40, 1.2),
    (520, 260, 45, 2.0),
    (-180, 300, 30, 0.0),
    (-360, -200, 35, 0.6),
    (90, -380, 50, 2.3),
    (640, -40, 40, 0.0),
    (-520, 120, 30, 1.5),
]


def seed(settings: Settings | None = None, reset: bool = False) -> dict:
    settings = settings or get_settings()
    engine = make_engine(settings.database_url)
    init_db(engine)
    frame = LocalFrame(settings.home_lat, settings.home_lon)
    with make_session_factory(engine)() as db:
        if reset:
            for table in (models.TelemetrySample, models.Assignment, models.Obstacle, models.Task,
                          models.Mission, models.Drone):
                db.execute(delete(table))
            db.commit()
        if db.query(models.Drone).count() > 0:
            return {"seeded": False, "reason": "drones already exist (use --reset to re-seed)"}
        for name, dtype, battery, health, (north, east) in DRONES:
            lat, lon = frame.to_latlon(east, north)
            db.add(models.Drone(name=name, type=dtype, battery_pct=battery, health=health,
                                home_lat=lat, home_lon=lon))
        mission = models.Mission(name="Campus survey (sample)", status="draft")
        for north, east, alt, payload in WAYPOINTS:
            lat, lon = frame.to_latlon(east, north)
            mission.tasks.append(models.Task(lat=lat, lon=lon, altitude_m=alt, payload_kg=payload))
        db.add(mission)
        db.commit()
        return {"seeded": True, "drones": len(DRONES), "waypoints": len(WAYPOINTS)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    print(seed(reset=ap.parse_args().reset))
