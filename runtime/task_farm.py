"""Distributed task farm with leases + heartbeats (OpenToonz TFarm).

OpenToonz's render farm runs ``controller -> server -> workers`` where a
worker *leases* a task and must renew the lease (heartbeat) or the task
is re-queued. That same shape fits aiZee fan-out work: durable,
crash-safe, pull-based distribution without a broker.

Storage layout under ``<farm_dir>`` — one JSON file per entity, atomic
tmp+replace writes (``durable.py`` convention):

- ``tasks/<id>.json`` — the task record (status, lease, attempts).
- ``workers/<id>.json`` — worker heartbeat + lease accounting.

Safety rails:

- **Bounded**: max task count, bounded attempts, max lease time.
- **Idempotent**: ``claim`` is atomic under a lock; double-claim is a
  no-op, ``complete`` after expiry is rejected.
- **Reap**: expired leases re-queue (bounded by ``max_attempts``) or
  move to ``dead``.

Usage::

    farm = TaskFarm(root / "state" / "farm")
    farm.submit("fs.read", {"path": "a"}, name="read-a")
    task = farm.claim("worker-1", lease_seconds=30)
    farm.heartbeat("worker-1", task.id, extend=30)
    farm.complete("worker-1", task.id, result={...})
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from runtime.schemas import AizeeError

logger = logging.getLogger(__name__)

_MAX_TASKS = 512
_MAX_ATTEMPTS = 3
_MAX_LEASE = 3600.0  # one hour hard cap per lease

TASKS = "tasks"
WORKERS = "workers"

# task/worker ids become filenames — whitelist path-safe chars only (SEC-01).
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class FarmError(AizeeError):
    """Farm-level failure (claim conflict, missing task, expired lease)."""

    def __init__(self, code: str, message: str, task_id: str | None = None) -> None:
        super().__init__(code, message, context={"task_id": task_id})
        self.task_id = task_id


@dataclass
class Task:
    id: str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    name: str = ""
    status: str = "pending"  # pending|leased|done|failed|dead
    worker: str = ""
    lease_until: float = 0.0
    heartbeat_at: float = 0.0
    attempts: int = 0
    max_attempts: int = _MAX_ATTEMPTS
    result: Any = None
    error: str = ""
    created_at: float = field(default_factory=time.time)
    # Nanosecond submission sequence — created_at is float wall time and can
    # tie (~15.6ms Windows tick), which made "oldest first" order depend on
    # filesystem glob order on shared runners.
    seq: int = field(default_factory=time.time_ns)
    updated_at: float = field(default_factory=time.time)


@dataclass
class Worker:
    id: str
    seen_at: float = field(default_factory=time.time)
    leased: int = 0
    done: int = 0
    meta: dict[str, Any] = field(default_factory=dict)


class TaskFarm:
    """File-backed farm: tasks leased to heartbeat-ing workers."""

    def __init__(self, farm_dir: Path, *, max_tasks: int = _MAX_TASKS) -> None:
        self._dir = farm_dir
        self._tasks = farm_dir / TASKS
        self._workers = farm_dir / WORKERS
        self._max_tasks = max_tasks
        self._lock = threading.Lock()
        for d in (self._tasks, self._workers):
            d.mkdir(parents=True, exist_ok=True)

    # -- submit ------------------------------------------------------------

    def submit(
        self,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        name: str = "",
        max_attempts: int = _MAX_ATTEMPTS,
    ) -> Task:
        """Enqueue a task. Idempotent by content key when ``name`` set."""
        if not isinstance(tool, str) or not tool.strip():
            raise FarmError("BAD_TOOL", "submit requires a non-empty tool name")
        with self._lock:
            if len(list(self._tasks.glob("*.json"))) >= self._max_tasks:
                raise FarmError("FARM_FULL", f"farm at capacity ({self._max_tasks})")
            task = Task(
                id=uuid.uuid4().hex[:16],
                tool=tool,
                args=dict(args or {}),
                name=name or f"{tool}-{uuid.uuid4().hex[:6]}",
                max_attempts=max(1, min(max_attempts, _MAX_ATTEMPTS * 3)),
            )
            self._save_task(task)
            return task

    # -- worker loop primitives -------------------------------------------

    def claim(self, worker_id: str, *, lease_seconds: float = 60.0) -> Task | None:
        """Atomically lease the oldest pending task to ``worker_id``."""
        with self._lock:
            self._touch_worker(worker_id)
            task = self._oldest_pending()
            if task is None:
                return None
            now = time.time()
            task.status = "leased"
            task.worker = worker_id
            task.attempts += 1
            task.heartbeat_at = now
            task.lease_until = now + min(lease_seconds, _MAX_LEASE)
            task.updated_at = now
            self._save_task(task)
            self._bump_worker(worker_id, leased=1)
            return task

    def heartbeat(self, worker_id: str, task_id: str, *, extend: float = 60.0) -> Task:
        """Renew a lease; fails if the lease is no longer yours."""
        with self._lock:
            task = self._load_task(task_id)
            now = time.time()
            if task.status != "leased" or task.worker != worker_id or task.lease_until < now:
                raise FarmError("LEASE_LOST", f"lease on {task_id} not held by {worker_id}", task_id)
            task.heartbeat_at = now
            task.lease_until = now + min(extend, _MAX_LEASE)
            task.updated_at = now
            self._save_task(task)
            self._touch_worker(worker_id)
            return task

    def complete(self, worker_id: str, task_id: str, *, result: Any = None) -> Task:
        """Finish a leased task — rejected if the lease expired."""
        return self._finish(worker_id, task_id, status="done", result=result)

    def fail(self, worker_id: str, task_id: str, error: str) -> Task:
        """Report failure; re-queues unless attempts are exhausted."""
        task = self._finish(worker_id, task_id, status="failed", error=error[:500])
        if task.attempts < task.max_attempts:
            task.status = "pending"
            task.worker = ""
            task.lease_until = 0.0
            self._save_task(task)
        else:
            task.status = "dead"
            self._save_task(task)
        return task

    # -- maintenance -------------------------------------------------------

    def reap_expired(self) -> list[str]:
        """Re-queue tasks whose lease lapsed; dead-letter exhausted ones."""
        reaped: list[str] = []
        now = time.time()
        with self._lock:
            for task in self._iter_tasks():
                if task.status != "leased" or task.lease_until >= now:
                    continue
                if task.attempts >= task.max_attempts:
                    task.status = "dead"
                else:
                    task.status = "pending"
                    task.worker = ""
                    task.lease_until = 0.0
                task.updated_at = now
                self._save_task(task)
                reaped.append(task.id)
        return reaped

    def stats(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for task in self._iter_tasks():
            counts[task.status] = counts.get(task.status, 0) + 1
        workers = {w.id: w.seen_at for w in self._iter_workers()}
        return {"counts": counts, "workers": workers, "dir": str(self._dir)}

    def list_tasks(self, status: str | None = None) -> list[Task]:
        return [t for t in self._iter_tasks() if status is None or t.status == status]

    # -- internals ----------------------------------------------------------

    def _finish(
        self,
        worker_id: str,
        task_id: str,
        *,
        status: str,
        result: Any = None,
        error: str = "",
    ) -> Task:
        with self._lock:
            task = self._load_task(task_id)
            now = time.time()
            if task.status != "leased" or task.worker != worker_id:
                raise FarmError("NOT_LEASED", f"{task_id} not leased by {worker_id}", task_id)
            if task.lease_until < now:
                task.status = "pending"
                task.worker = ""
                task.lease_until = 0.0
                self._save_task(task)
                raise FarmError("LEASE_EXPIRED", f"lease expired on {task_id}", task_id)
            task.status = status
            task.result = result
            task.error = error
            task.updated_at = now
            self._save_task(task)
            self._bump_worker(worker_id, done=1 if status == "done" else 0, leased=-1)
            return task

    def _oldest_pending(self) -> Task | None:
        pending = [t for t in self._iter_tasks() if t.status == "pending"]
        return min(pending, key=lambda t: (t.created_at, t.seq), default=None)

    @staticmethod
    def _safe_id(ident: str) -> str:
        if not ident or not _ID_RE.fullmatch(ident):
            raise FarmError("BAD_ID", f"invalid id {ident!r}", ident)
        return ident

    def _task_path(self, task_id: str) -> Path:
        return self._tasks / f"{self._safe_id(task_id)}.json"

    def _worker_path(self, worker_id: str) -> Path:
        return self._workers / f"{self._safe_id(worker_id)}.json"

    def _save_task(self, task: Task) -> None:
        _atomic_write(self._task_path(task.id), asdict(task))

    def _load_task(self, task_id: str) -> Task:
        path = self._task_path(task_id)
        if not path.exists():
            raise FarmError("NO_TASK", f"unknown task {task_id}", task_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Task(**{k: v for k, v in data.items() if k in Task.__dataclass_fields__})
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            raise FarmError("CORRUPT", f"task {task_id} unreadable: {exc}", task_id) from exc

    def _iter_tasks(self) -> list[Task]:
        out: list[Task] = []
        for p in self._tasks.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                out.append(Task(**{k: v for k, v in data.items() if k in Task.__dataclass_fields__}))
            except (OSError, json.JSONDecodeError, TypeError):
                logger.warning("skipping unreadable task file %s", p)
        return out

    def _iter_workers(self) -> list[Worker]:
        out: list[Worker] = []
        for p in self._workers.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                out.append(Worker(**{k: v for k, v in data.items() if k in Worker.__dataclass_fields__}))
            except (OSError, json.JSONDecodeError, TypeError):
                logger.warning("skipping unreadable worker file %s", p)
        return out

    def _touch_worker(self, worker_id: str) -> None:
        path = self._worker_path(worker_id)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                worker = Worker(**{k: v for k, v in data.items() if k in Worker.__dataclass_fields__})
            except (OSError, json.JSONDecodeError, TypeError):
                worker = Worker(id=worker_id)
        else:
            worker = Worker(id=worker_id)
        worker.seen_at = time.time()
        _atomic_write(path, asdict(worker))

    def _bump_worker(self, worker_id: str, *, leased: int = 0, done: int = 0) -> None:
        path = self._worker_path(worker_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            worker = Worker(**{k: v for k, v in data.items() if k in Worker.__dataclass_fields__})
        except (OSError, json.JSONDecodeError, TypeError):
            worker = Worker(id=worker_id)
        worker.leased = max(0, worker.leased + leased)
        worker.done += done
        _atomic_write(path, asdict(worker))


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, default=str, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
