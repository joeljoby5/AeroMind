from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.container import Container


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_db(request: Request) -> Iterator[Session]:
    db = request.app.state.container.session_factory()
    try:
        yield db
    finally:
        db.close()
