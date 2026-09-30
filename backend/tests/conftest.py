import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.seed import seed


@pytest.fixture()
def settings(tmp_path):
    return Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", auto_tick=False, speedup=3.0)


@pytest.fixture()
def client(settings):
    seed(settings)
    app = create_app(settings)
    with TestClient(app) as c:
        c.app_ = app
        yield c


@pytest.fixture()
def runtime(client):
    return client.app_.state.container.runtime


def run_until(runtime, predicate, max_ticks=2000):
    """Tick the simulation until predicate(snapshot) is true; returns (snapshot, ticks)."""
    snap = runtime.snapshot()
    for n in range(1, max_ticks + 1):
        snap = runtime.tick()
        if predicate(snap):
            return snap, n
    raise AssertionError(f"condition not met within {max_ticks} ticks; last states: "
                         f"{[(d['name'], d['state']) for d in snap['drones']]}")


def drone(snap, name):
    return next(d for d in snap["drones"] if d["name"] == name)
