from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["telemetry"])


@router.websocket("/ws/telemetry")
async def telemetry(ws: WebSocket) -> None:
    """Live ticks (every tick_s): drones, events and obstacles. First message is a full snapshot."""
    c = ws.app.state.container
    await c.manager.connect(ws)
    try:
        await ws.send_json(c.runtime.snapshot(with_history=True))
        while True:
            await ws.receive_text()  # keep-alive; clients send nothing meaningful
    except WebSocketDisconnect:
        pass
    finally:
        c.manager.disconnect(ws)
