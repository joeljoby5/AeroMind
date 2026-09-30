"""Shared builders for AI tests (plain module, imported via pytest's rootdir-relative path)."""
import random

from ai.types import DroneState, Task

HOME = (12.9716, 77.5946)


def offset(lat, lon, north_m, east_m):
    return lat + north_m / 111_320.0, lon + east_m / (111_320.0 * 0.9744)


def make_drone(i, type_="quad_medium", battery=90.0, health=0.95, north=0.0, east=0.0):
    lat, lon = offset(*HOME, north, east)
    return DroneState(id=i, name=f"D{i}", type=type_, lat=lat, lon=lon, battery_pct=battery,
                      health=health, home_lat=lat, home_lon=lon)


def make_task(i, north, east, alt=30.0, payload=0.0):
    lat, lon = offset(*HOME, north, east)
    return Task(id=i, lat=lat, lon=lon, altitude_m=alt, payload_kg=payload)


def random_scenario(seed, n_drones=3, n_tasks=3):
    rnd = random.Random(seed)
    drones = [make_drone(i + 1, rnd.choice(["quad_small", "quad_medium", "hex_heavy"]),
                         battery=rnd.uniform(60, 100), health=rnd.uniform(0.75, 1.0),
                         north=rnd.uniform(-50, 50), east=rnd.uniform(-50, 50))
              for i in range(n_drones)]
    tasks = [make_task(j + 1, rnd.uniform(-600, 600), rnd.uniform(-600, 600),
                       alt=rnd.uniform(20, 60), payload=rnd.uniform(0, 2.5))
             for j in range(n_tasks)]
    return drones, tasks
