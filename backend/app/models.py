"""ORM entities (SQLAlchemy 2.x typed mappings)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Drone(Base):
    __tablename__ = "drones"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(32))  # quad_small | quad_medium | hex_heavy
    battery_pct: Mapped[float] = mapped_column(Float, default=100.0)
    health: Mapped[float] = mapped_column(Float, default=1.0)  # battery health factor 0.70-1.00
    home_lat: Mapped[float] = mapped_column(Float)
    home_lon: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="idle")  # idle | flying


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft|planned|running|completed|stopped
    strategy: Mapped[str | None] = mapped_column(String(16), nullable=True)  # last plan: ml | baseline
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    tasks: Mapped[list["Task"]] = relationship(cascade="all, delete-orphan", order_by="Task.id")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    altitude_m: Mapped[float] = mapped_column(Float, default=30.0)
    payload_kg: Mapped[float] = mapped_column(Float, default=0.0)


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    drone_id: Mapped[int] = mapped_column(ForeignKey("drones.id"))
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    # "order" is an SQL keyword, so the column is named task_order.
    order: Mapped[int] = mapped_column("task_order", Integer)
    predicted_energy_pct: Mapped[float] = mapped_column(Float)


class Obstacle(Base):
    __tablename__ = "obstacles"

    id: Mapped[int] = mapped_column(primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    radius_m: Mapped[float] = mapped_column(Float, default=30.0)


class TelemetrySample(Base):
    __tablename__ = "telemetry_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    drone_id: Mapped[int] = mapped_column(ForeignKey("drones.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    alt: Mapped[float] = mapped_column(Float)
    battery_pct: Mapped[float] = mapped_column(Float)
    state: Mapped[str] = mapped_column(String(24))
