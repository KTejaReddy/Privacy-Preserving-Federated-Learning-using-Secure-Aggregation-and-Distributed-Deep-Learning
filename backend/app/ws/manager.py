"""WebSocket manager for realtime dashboards (Communication Monitor, Training,
Coordinator). Subscribes to the in-process event bus and forwards events to all
connected clients, tagged by authenticated user.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, Set

from fastapi import WebSocket

from app.core.events import bus


class ConnectionManager:
    def __init__(self) -> None:
        self.active: Set[WebSocket] = set()
        self._sessions: Dict[int, WebSocket] = {}
        self._last_broadcast: Dict[str, float] = {}

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active.discard(ws)

    async def send_personal(self, ws: WebSocket, payload: Dict[str, Any]) -> None:
        try:
            await ws.send_text(json.dumps(payload, default=str))
        except Exception:
            self.disconnect(ws)

    async def broadcast(self, payload: Dict[str, Any], throttle_key: str | None = None) -> None:
        if throttle_key:
            now = time.time()
            if now - self._last_broadcast.get(throttle_key, 0) < 0.25:
                return
            self._last_broadcast[throttle_key] = now
        dead: list = []
        for ws in list(self.active):
            try:
                await ws.send_text(json.dumps(payload, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


def _ws_listener(event_type: str, payload: Dict[str, Any]) -> None:
    async def _push() -> None:
        await manager.broadcast({"event": event_type, "data": payload}, throttle_key=event_type)

    try:
        loop = asyncio.get_running_loop()
        asyncio.create_task(_push())
    except RuntimeError:
        pass


# Bridge: event bus -> websocket broadcast
for _et in (
    "federated",
    "round.start",
    "round.select",
    "node.training",
    "round.complete",
    "round.persisted",
    "job.completed",
    "job.failed",
    "monitor.tick",
    "aggregation",
    "audit",
):
    bus.subscribe(_et, _ws_listener)
