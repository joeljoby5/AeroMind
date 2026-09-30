from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import schemas
from app.api.deps import get_container, get_db
from app.container import Container

router = APIRouter(prefix="/api/drones", tags=["drones"])


@router.get("", response_model=list[schemas.DroneOut])
def list_drones(db: Session = Depends(get_db), c: Container = Depends(get_container)):
    return c.missions.list_drones(db)


@router.post("", response_model=schemas.DroneOut, status_code=201)
def create_drone(body: schemas.DroneCreate, db: Session = Depends(get_db), c: Container = Depends(get_container)):
    return c.missions.create_drone(db, body)


@router.post("/{drone_id}/drain", status_code=202)
def inject_battery_fault(drone_id: int, pct: float = Query(20.0, gt=0, le=100),
                         c: Container = Depends(get_container)):
    """Demo control: instantly drop a flying drone's battery to trigger return-to-launch."""
    c.runtime.drain_battery(drone_id, pct)
    return {"drone_id": drone_id, "drained_pct": pct}
