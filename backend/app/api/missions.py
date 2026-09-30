from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import schemas
from app.api.deps import get_container, get_db
from app.container import Container

router = APIRouter(prefix="/api/missions", tags=["missions"])


@router.get("", response_model=list[schemas.MissionOut])
def list_missions(db: Session = Depends(get_db), c: Container = Depends(get_container)):
    return c.missions.list_missions(db)


@router.post("", response_model=schemas.MissionDetail, status_code=201)
def create_mission(body: schemas.MissionCreate, db: Session = Depends(get_db),
                   c: Container = Depends(get_container)):
    mission = c.missions.create_mission(db, body)
    return c.planning.mission_detail(db, mission.id)


@router.get("/{mission_id}", response_model=schemas.MissionDetail)
def get_mission(mission_id: int, db: Session = Depends(get_db), c: Container = Depends(get_container)):
    return c.planning.mission_detail(db, mission_id)


@router.post("/{mission_id}/plan", response_model=schemas.PlanOut)
def plan_mission(mission_id: int, strategy: schemas.Strategy = Query("ml"),
                 db: Session = Depends(get_db), c: Container = Depends(get_container)):
    """Run allocation (`ml` = energy-aware, `baseline` = distance-only) and A* routing."""
    return c.planning.plan(db, mission_id, strategy)


@router.get("/{mission_id}/compare", response_model=schemas.CompareOut)
def compare_strategies(mission_id: int, db: Session = Depends(get_db), c: Container = Depends(get_container)):
    return c.planning.compare(db, mission_id)


@router.post("/{mission_id}/start")
def start_mission(mission_id: int, c: Container = Depends(get_container)):
    return c.runtime.start(mission_id)


@router.post("/{mission_id}/stop")
def stop_mission(mission_id: int, c: Container = Depends(get_container)):
    return c.runtime.stop()


@router.post("/{mission_id}/obstacles", response_model=schemas.ObstacleOut, status_code=201)
def inject_obstacle(mission_id: int, body: schemas.ObstacleIn, db: Session = Depends(get_db),
                    c: Container = Depends(get_container)):
    """Add an obstacle. While the mission runs, drones discover it through their LiDAR and replan."""
    return c.missions.add_obstacle(db, mission_id, body)


@router.delete("/{mission_id}/obstacles", status_code=204)
def clear_obstacles(mission_id: int, db: Session = Depends(get_db), c: Container = Depends(get_container)):
    c.missions.clear_obstacles(db, mission_id)
