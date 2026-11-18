"""Doctor findings store — notify-once persistence for health issues.

Adopted from ApkStart's autodebug doctrine (``src/core/autodebug.js``):

- **Probe failure is not a problem.** Only checks that actually ran and
  failed become findings; a check that couldn't execute reports "unknown"
  upstream and never enters the store.
- **Notify once.** A finding alerts on first sight; repeats stay silent in
  the store until the check recovers (``resolved_at`` recorded, no re-ping).
- **Auto-recheck.** Each doctor run re-diffs live checks against the store,
  so a fix that landed is marked resolved on the very next pass.

Persistence goes through :class:`StorageFactory` (JsonFileStorage) — never a
hand-rolled file write.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.doctor import Check
from runtime.storage_backend import StorageFactory, StorageMode

STORE_NAME = "doctor_findings"
STORE_FILE = "doctor-findings.json"


@dataclass
class Finding:
    """One persisted health finding keyed by check name."""

    check: str
    severity: str
    first_seen: str
    last_seen: str
    notified: bool = False
    resolved_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Finding:
        return cls(
            check=str(data.get("check", "")),
            severity=str(data.get("severity", "")),
            first_seen=str(data.get("first_seen", "")),
            last_seen=str(data.get("last_seen", "")),
            notified=bool(data.get("notified", False)),
            resolved_at=str(data.get("resolved_at", "")),
        )


@dataclass
class FindingsDiff:
    """Result of diffing a doctor run against the store."""

    new: list[Finding]
    persisting: list[Finding]
    resolved: list[Finding]

    def to_dict(self) -> dict[str, Any]:
        return {
            "new": [asdict(f) for f in self.new],
            "persisting": [asdict(f) for f in self.persisting],
            "resolved": [asdict(f) for f in self.resolved],
        }


def open_store(state_dir: Path) -> tuple[StorageFactory, Any]:
    """Open (or create) the findings backend under ``state_dir``."""
    factory = StorageFactory(base_dir=state_dir, default_mode=StorageMode.JSON)
    backend = factory.create(STORE_NAME, STORE_FILE)
    return factory, backend


def _stored_findings(backend: Any) -> dict[str, Finding]:
    out: dict[str, Finding] = {}
    for key in backend.keys():  # noqa: SIM118 - StorageBackend protocol, not dict
        raw = backend.get(key)
        if isinstance(raw, dict):
            out[str(key)] = Finding.from_dict(raw)
    return out


def diff_and_record(backend: Any, checks: list[Check], now: str | None = None) -> FindingsDiff:
    """Diff failing checks against the store, persist, return the delta.

    ``notified`` is set on every recorded finding — printing/alerting of the
    ``diff.new`` list is the caller's one-shot notification.
    """
    now = now or datetime.now(timezone.utc).isoformat(timespec="seconds")
    stored = _stored_findings(backend)
    failed = {c.name: c for c in checks if not c.ok}
    diff = FindingsDiff(new=[], persisting=[], resolved=[])

    for name, check in failed.items():
        prior = stored.get(name)
        if prior is None or prior.resolved_at:
            finding = Finding(name, check.severity, now, now, notified=True)
            diff.new.append(finding)
        else:
            prior.last_seen = now
            finding = prior
            diff.persisting.append(finding)
        backend.put(name, asdict(finding))

    for name, prior in stored.items():
        if name not in failed and not prior.resolved_at:
            prior.resolved_at = now
            prior.last_seen = now
            backend.put(name, asdict(prior))
            diff.resolved.append(prior)

    backend.flush()
    return diff


def unresolved(backend: Any) -> list[Finding]:
    """All findings still open (seen, not yet resolved)."""
    return [f for f in _stored_findings(backend).values() if not f.resolved_at]
