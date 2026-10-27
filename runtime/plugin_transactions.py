"""Lockfile-serialized transactions for plugin state.

Adopted from DeepTutor's ``plugins/transactions`` pattern: plugin lifecycle
mutations (enable/disable/config edits) must not interleave — two writers on
``plugins.yaml`` can lose updates or leave torn YAML. This module owns a
nonblocking lease file beside the state file plus an atomic write-back, so a
failed mutation never leaves a half-written config.

The lock is *nonblocking*: a second transaction raises ``PluginStateError``
immediately rather than queueing — surface the contention to the caller
instead of silently serializing a human's manual edit against a CLI write.
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
import tempfile
from collections.abc import Callable, Iterator
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

from runtime.schemas import AizeeError, ErrorSeverity

logger = logging.getLogger(__name__)

_T = TypeVar("_T")
_F = TypeVar("_F", bound=Callable[..., Any])


class PluginStateError(AizeeError):
    """Raised when a plugin state transaction cannot proceed."""

    def __init__(self, message: str) -> None:
        super().__init__("PLUGIN_STATE_ERROR", message, ErrorSeverity.MEDIUM)


def _lock_lease(lease: Any) -> None:
    """Acquire the nonblocking lease; raise PluginStateError on contention."""
    if sys.platform == "win32":
        import msvcrt

        lease.seek(0)
        if not lease.read(1):
            lease.write(b"0")
            lease.flush()
        lease.seek(0)
        msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
        return
    import fcntl

    fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_lease(lease: Any) -> None:
    if sys.platform == "win32":
        import msvcrt

        lease.seek(0)
        msvcrt.locking(lease.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(lease.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def plugin_state_lock(state_path: Path) -> Iterator[None]:
    """Exclusive nonblocking lease on ``<state_path>.lock`` for the body duration."""
    lock_path = state_path.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lease:
        try:
            _lock_lease(lease)
        except OSError as exc:
            raise PluginStateError(
                "Another plugin state transaction is active; retry after it finishes."
            ) from exc
        try:
            yield
        finally:
            _unlock_lease(lease)


def serialized(fn: _F) -> _F:
    """Decorator: run a registry/state method inside ``plugin_state_lock``.

    The wrapped object must expose ``state_path`` (a ``Path``) — either the
    instance attribute or ``self.state_path`` on a registry argument.
    """

    @wraps(fn)
    def call(self: Any, *args: Any, **kwargs: Any) -> Any:
        with plugin_state_lock(Path(self.state_path)):
            return fn(self, *args, **kwargs)

    return call  # type: ignore[return-value]


def _atomic_write(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` via a sibling tmp file + os.replace."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def mutate_plugins_yaml(root: Path, mutator: Callable[[dict[str, Any]], _T]) -> _T:
    """Load ``plugins.yaml`` under the lease, apply ``mutator``, write back atomically.

    ``mutator`` receives the parsed config dict (guaranteed ``{"plugins": {...}}``
    shaped) and returns any value, which becomes this function's result.
    Returning ``None`` from the mutator skips the write — a read-only probe.
    """
    import yaml

    cfg_path = root / "plugins.yaml"
    with plugin_state_lock(cfg_path):
        try:
            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else None
        except (OSError, yaml.YAMLError) as exc:
            raise PluginStateError(f"plugins.yaml unreadable: {exc}") from exc
        if not isinstance(data, dict):
            data = {}
        plugins = data.get("plugins")
        if not isinstance(plugins, dict):
            data["plugins"] = {}
        result = mutator(data)
        if result is not None:
            _atomic_write(cfg_path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
        return result


def set_plugin_enabled(root: Path, name: str, enabled: bool) -> bool:
    """Flip ``plugins.<name>.enabled`` under the transaction. Returns the prior state."""

    def _flip(cfg: dict[str, Any]) -> bool:
        entry = cfg["plugins"].setdefault(name, {})
        prior = bool(entry.get("enabled", False))
        entry["enabled"] = bool(enabled)
        return prior

    return bool(mutate_plugins_yaml(root, _flip))
