"""Typed in-process event bus (FreeMoCap pubsub adoption).

Decouples producers (kernel gates, plan runner, farm) from consumers
(dashboard SSE, audit taps, MCP progress). Each message + topic pair is a
typed channel: topic classes auto-register via ``__init_subclass__`` so
the ``TopicRegistry`` discovers them at import time — the FreeMoCap
``pubsub_topics.py`` pattern.

Design:

- **Typed channels**: publish a dataclass instance; the topic name comes
  from the class (``StepEvent.topic == "plan.step"``).
- **Bounded history**: a ``WorkingSet`` ring keeps the newest N events
  for ``drain()``/``history()`` — the dashboard SSE endpoint merges them
  into its 5s payload.
- **Fail-soft**: a failing subscriber never breaks ``publish()`` — the
  error is logged and counted, matching aiZee's no-crash-in-hot-path
  logging policy.
- **Optional file sink**: ``persist=state/events.jsonl`` appends each
  event for cross-process ``aizee events tail`` visibility.

Usage::

    bus = EventBus()
    bus.subscribe("plan.step", lambda msg: print(msg.step))
    bus.publish(StepEvent(step="s0", op="call", status="settled"))
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from runtime.working_set import WorkingSet

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Topics — auto-registering typed channels (FreeMoCap pubsub_topics pattern)
# ---------------------------------------------------------------------------


class TopicRegistry:
    """Discovers ``EventMessage`` subclasses via ``__init_subclass__``."""

    _topics: ClassVar[dict[str, type[EventMessage]]] = {}

    @classmethod
    def register(cls, msg_cls: type[EventMessage]) -> None:
        cls._topics[msg_cls.topic] = msg_cls

    @classmethod
    def get(cls, topic: str) -> type[EventMessage] | None:
        return cls._topics.get(topic)

    @classmethod
    def topics(cls) -> list[str]:
        return sorted(cls._topics)


@dataclass
class EventMessage:
    """Base event message. Subclasses set ``topic`` and auto-register."""

    topic: ClassVar[str] = "event"
    ts: float = field(default_factory=time.time)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if getattr(cls, "topic", "event") != "event":
            TopicRegistry.register(cls)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["topic"] = type(self).topic
        return d


@dataclass
class ActionEvent(EventMessage):
    """Kernel gate decision on an action (allow/deny/ask)."""

    topic: ClassVar[str] = "action.checked"
    action: str = ""
    decision: str = ""
    dry_run: bool = False


@dataclass
class StepEvent(EventMessage):
    """Plan step lifecycle (settled/cached/suspended/failed)."""

    topic: ClassVar[str] = "plan.step"
    step: str = ""
    op: str = ""
    status: str = ""
    detail: str = ""


@dataclass
class TaskEvent(EventMessage):
    """Farm task lifecycle (submitted/leased/done/failed/requeued)."""

    topic: ClassVar[str] = "farm.task"
    task_id: str = ""
    worker: str = ""
    status: str = ""


@dataclass
class InfoEvent(EventMessage):
    """Free-form informational channel (ingest, snapshot, misc)."""

    topic: ClassVar[str] = "info"
    source: str = ""
    message: str = ""


# ---------------------------------------------------------------------------
# Bus
# ---------------------------------------------------------------------------

Subscriber = Callable[[EventMessage], None]


class EventBus:
    """In-process publish/subscribe with bounded history + optional sink."""

    def __init__(
        self,
        *,
        history_size: int = 256,
        persist: Path | None = None,
    ) -> None:
        self._subs: dict[str, list[Subscriber]] = {}
        self._history = WorkingSet(max_entries=history_size)
        self._seq = 0
        self._lock = threading.Lock()
        self._persist = persist
        self.errors = 0

    # -- pub/sub ----------------------------------------------------------

    def subscribe(self, topic: str, handler: Subscriber) -> Callable[[], None]:
        """Subscribe to a topic (``"*"`` for all). Returns an unsubscribe."""
        with self._lock:
            self._subs.setdefault(topic, []).append(handler)

        def _unsub() -> None:
            with self._lock:
                handlers = self._subs.get(topic, [])
                if handler in handlers:
                    handlers.remove(handler)

        return _unsub

    def publish(self, msg: EventMessage) -> None:
        """Dispatch to topic + wildcard subscribers; buffer + sink."""
        with self._lock:
            self._seq += 1
            seq = self._seq
            self._history.put(seq, msg)
            handlers = list(self._subs.get(msg.topic, ()))
            handlers += self._subs.get("*", [])
        for handler in handlers:
            try:
                handler(msg)
            except Exception as exc:  # subscriber failures must not break publish
                self.errors += 1
                logger.warning("event_bus subscriber error on %s: %s", msg.topic, exc)
        if self._persist is not None:
            try:
                self._persist.parent.mkdir(parents=True, exist_ok=True)
                with self._persist.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(msg.to_dict(), default=str) + "\n")
            except OSError as exc:
                self.errors += 1
                logger.warning("event_bus sink write failed: %s", exc)

    # -- reads ------------------------------------------------------------

    def history(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Buffered events oldest -> newest (ring tail)."""
        return [m.to_dict() for _, m in self._history.items_recent(limit)]

    def drain(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Atomically take buffered events (SSE poll pattern).

        Uses ``WorkingSet.take_recent`` — a ``items_recent`` + ``clear``
        pair would silently drop events published mid-drain.
        """
        return [m.to_dict() for _, m in self._history.take_recent(limit)]

    def stats(self) -> dict[str, Any]:
        return {
            "topics": TopicRegistry.topics(),
            "subscribers": {t: len(h) for t, h in self._subs.items()},
            "buffered": len(self._history),
            "errors": self.errors,
            "persist": str(self._persist) if self._persist else None,
        }


# ---------------------------------------------------------------------------
# Module-level shared bus (kernel wires a persisted one; tests use fresh)
# ---------------------------------------------------------------------------

_default_bus: EventBus | None = None
_default_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """Process-wide default bus (no sink — kernel wires the persisted one)."""
    global _default_bus
    if _default_bus is None:
        with _default_lock:
            if _default_bus is None:
                _default_bus = EventBus()
    return _default_bus
