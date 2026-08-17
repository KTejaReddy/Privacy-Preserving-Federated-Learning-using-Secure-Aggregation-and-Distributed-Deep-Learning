"""Lightweight in-process event bus.

The federated engine, monitor simulator and audit service publish events here;
the WebSocket manager subscribes and forwards them to connected dashboards.
"""
from __future__ import annotations

import asyncio
import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List

Listener = Callable[[str, Dict[str, Any]], None]


class EventBus:
    def __init__(self) -> None:
        self._listeners: Dict[str, List[Listener]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, listener: Listener) -> None:
        with self._lock:
            self._listeners[event_type].append(listener)

    def unsubscribe(self, event_type: str, listener: Listener) -> None:
        with self._lock:
            if listener in self._listeners[event_type]:
                self._listeners[event_type].remove(listener)

    def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            listeners = list(self._listeners.get(event_type, [])) + list(self._listeners.get("*", []))
        for listener in listeners:
            try:
                listener(event_type, payload)
            except Exception:
                pass

    def publish_async(self, event_type: str, payload: Dict[str, Any]) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self.publish, event_type, payload)
        except RuntimeError:
            self.publish(event_type, payload)


bus = EventBus()
