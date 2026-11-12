"""Tests for runtime/event_bus.py — typed pubsub channels."""

from __future__ import annotations

import json
from pathlib import Path

from runtime.event_bus import (
    ActionEvent,
    EventBus,
    EventMessage,
    InfoEvent,
    StepEvent,
    TaskEvent,
    TopicRegistry,
    get_event_bus,
)


def test_topics_auto_register() -> None:
    topics = TopicRegistry.topics()
    assert "plan.step" in topics
    assert "action.checked" in topics
    assert "farm.task" in topics
    assert "info" in topics
    assert TopicRegistry.get("plan.step") is StepEvent


def test_publish_subscribe_roundtrip() -> None:
    bus = EventBus()
    seen: list[StepEvent] = []
    bus.subscribe("plan.step", seen.append)  # type: ignore[arg-type]
    bus.publish(StepEvent(step="s0", op="call", status="settled"))
    assert len(seen) == 1
    assert seen[0].step == "s0"
    assert seen[0].topic == "plan.step"


def test_wildcard_subscriber() -> None:
    bus = EventBus()
    seen: list[EventMessage] = []
    bus.subscribe("*", seen.append)
    bus.publish(ActionEvent(action="ReadFile", decision="allow"))
    bus.publish(InfoEvent(source="t", message="hi"))
    assert len(seen) == 2


def test_history_bounded_and_ordered() -> None:
    bus = EventBus(history_size=3)
    for i in range(5):
        bus.publish(InfoEvent(source="t", message=str(i)))
    hist = bus.history()
    assert len(hist) == 3  # ring keeps the newest 3
    assert [m["message"] for m in hist] == ["2", "3", "4"]


def test_drain_clears() -> None:
    bus = EventBus()
    bus.publish(InfoEvent(source="t", message="x"))
    assert len(bus.drain()) == 1
    assert bus.drain() == []


def test_subscriber_failure_isolated() -> None:
    bus = EventBus()
    good: list[EventMessage] = []

    def _bad(_m: EventMessage) -> None:
        raise RuntimeError("boom")

    bus.subscribe("info", _bad)
    bus.subscribe("info", good.append)
    bus.publish(InfoEvent(source="t", message="m"))
    assert len(good) == 1
    assert bus.errors == 1


def test_unsubscribe() -> None:
    bus = EventBus()
    seen: list[EventMessage] = []
    unsub = bus.subscribe("info", seen.append)
    unsub()
    bus.publish(InfoEvent(source="t", message="m"))
    assert seen == []


def test_persist_sink(tmp_path: Path) -> None:
    sink = tmp_path / "events.jsonl"
    bus = EventBus(persist=sink)
    bus.publish(TaskEvent(task_id="t1", worker="w1", status="done"))
    lines = sink.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["topic"] == "farm.task"
    assert row["task_id"] == "t1"


def test_default_bus_singleton() -> None:
    assert get_event_bus() is get_event_bus()


def test_drain_atomic_take() -> None:
    """REGRESSION: drain used items_recent+clear — events published mid-drain
    were silently dropped; take_recent keeps read+remove atomic."""
    bus = EventBus()
    for i in range(3):
        bus.publish(InfoEvent(source="t", message=str(i)))
    assert len(bus.drain()) == 3
    bus.publish(InfoEvent(source="t", message="late"))
    assert [m["message"] for m in bus.drain()] == ["late"]


def test_untyped_subclass_not_registered() -> None:
    """Subclasses keeping the base "event" topic are not registered."""

    class _Plain(EventMessage):
        pass

    assert _Plain.topic == "event"


def test_unsubscribe_second_call_is_noop() -> None:
    bus = EventBus()
    seen: list = []
    unsub = bus.subscribe("info", seen.append)
    bus.publish(InfoEvent(source="t", message="1"))
    unsub()
    unsub()  # handler already gone — must not raise
    bus.publish(InfoEvent(source="t", message="2"))
    assert len(seen) == 1


def test_persist_sink_failure_counts_error(tmp_path: Path) -> None:
    sink = tmp_path / "asdir"
    sink.mkdir()  # open("a") on a directory raises OSError
    bus = EventBus(persist=sink)
    bus.publish(InfoEvent(source="t", message="x"))
    assert bus.errors == 1
    assert bus.stats()["errors"] == 1


def test_stats_reports_subscribers_and_buffered() -> None:
    bus = EventBus()
    bus.subscribe("info", lambda m: None)
    bus.publish(InfoEvent(source="t", message="m"))
    stats = bus.stats()
    assert stats["subscribers"]["info"] == 1
    assert stats["buffered"] == 1


def test_get_event_bus_lost_lock_race(monkeypatch) -> None:
    """Cover the inner check of double-checked locking: another 'thread' set
    the bus between the outer check and lock acquisition."""
    import runtime.event_bus as eb

    class _RaceLock:
        def __enter__(self) -> None:
            eb._default_bus = EventBus()

        def __exit__(self, *a: object) -> bool:
            return False

    monkeypatch.setattr(eb, "_default_bus", None)
    monkeypatch.setattr(eb, "_default_lock", _RaceLock())
    bus = eb.get_event_bus()
    assert bus is eb._default_bus
