"""Runtime configuration (env vars / .env)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SQLite works with zero setup; docker-compose points this at PostgreSQL.
    database_url: str = "sqlite:///./aeromind.db"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Sample campus location used by the seed script (change via HOME_LAT / HOME_LON).
    home_lat: float = 12.9716
    home_lon: float = 77.5946

    # Steady wind over the mission area (feeds the energy model).
    wind_speed_ms: float = 6.0
    wind_to_deg: float = 60.0  # direction the wind blows TOWARDS (compass degrees)

    reserve_pct: float = 15.0  # battery reserve that must remain after returning home

    # Simulation clock: each tick advances `tick_s * speedup` simulated seconds.
    tick_s: float = 0.5
    speedup: float = 2.0
    task_dwell_s: float = 6.0  # simulated seconds spent executing each task
    sim_seed: int = 42
    auto_tick: bool = True  # tests switch this off and drive the clock by hand

    energy_model_path: str | None = None


def get_settings() -> Settings:
    return Settings()
