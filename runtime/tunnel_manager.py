#!/usr/bin/env python3
"""Governed tunnel lifecycle manager.

Turns workflow ``62-localhost-tunnel`` from prose into an enforceable
capability: every tunnel is a tracked, audited, TTL-bound object instead of
an orphaned shell process.

Design notes:
  * Providers are data, not code: a start-command template plus a regex that
    extracts the public URL from the tool's own output. The provider binary
    is never installed by aiZee — supply-chain stays with the user.
  * Output goes to a per-tunnel log file (not pipes) so the process fully
    detaches from the spawning CLI and survives it.
  * The public URL is a bearer secret: it is stored in the state file
    (local, user-only) but NEVER written to the audit log — audits record
    the tunnel id, provider, and port only.
  * TTL is enforced on read (``status``/``list`` sweep expired tunnels and
    stop them) rather than by a daemon — no background threads outliving
    the CLI.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import psutil

PROVIDERS: dict[str, dict[str, Any]] = {
    "cloudflared": {
        "cmd": ["cloudflared", "tunnel", "--url", "http://127.0.0.1:{port}"],
        "pattern": r"https://[a-zA-Z0-9-]+\.trycloudflare\.com",
    },
    "tunnelto": {
        "cmd": ["tunnelto", "--port", "{port}"],
        "pattern": r"https://[a-zA-Z0-9.-]+\.tunn\.dev",
    },
    "ngrok": {
        "cmd": ["ngrok", "http", "{port}", "--log", "stdout", "--log-format", "term"],
        "pattern": r"https://[a-zA-Z0-9-]+\.[a-zA-Z0-9.-]*ngrok[a-z0-9.-]*",
    },
}

_START_TIMEOUT_S = 15.0
_DEFAULT_TTL_S = 1800
_MAX_TTL_S = 4 * 3600


def _tunnels_dir(root: Path) -> Path:
    return root / "state" / "tunnels"


def _audit(root: Path, kind: str, payload: dict[str, Any]) -> None:
    try:
        from runtime.audit import AuditLogger

        AuditLogger(root).log(kind, payload)
    except Exception:
        pass


def _state_path(root: Path, tunnel_id: str) -> Path:
    return _tunnels_dir(root) / f"{tunnel_id}.json"


def _load(root: Path, tunnel_id: str) -> dict[str, Any] | None:
    if not re.fullmatch(r"[a-f0-9]{12}", tunnel_id):
        return None
    path = _state_path(root, tunnel_id)
    if not path.is_file():
        return None
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data
    except (OSError, ValueError):
        return None


def _save(root: Path, state: dict[str, Any]) -> None:
    _state_path(root, state["id"]).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _pid_alive(pid: int) -> bool:
    try:
        return psutil.Process(pid).is_running()
    except (psutil.Error, OverflowError, OSError):
        return False


def _expired(state: dict[str, Any]) -> bool:
    return time.time() > float(state.get("expires_at", 0))


def start(
    root: Path,
    provider: str,
    port: int,
    ttl_s: int = _DEFAULT_TTL_S,
    providers: dict[str, dict[str, Any]] | None = None,
    timeout_s: float = _START_TIMEOUT_S,
) -> dict[str, Any]:
    """Start a tunnel and block only until the public URL appears."""
    table = providers if providers is not None else PROVIDERS
    spec = table.get(provider)
    if spec is None:
        return {"ok": False, "error": f"unknown provider {provider!r} — supported: {sorted(table)}"}
    if not (1 <= int(port) <= 65535):
        return {"ok": False, "error": f"invalid port {port}"}
    ttl = min(max(int(ttl_s), 60), _MAX_TTL_S)

    tunnel_id = uuid.uuid4().hex[:12]
    tdir = _tunnels_dir(root)
    tdir.mkdir(parents=True, exist_ok=True)
    log_path = tdir / f"{tunnel_id}.log"
    cmd = [part.replace("{port}", str(port)) for part in spec["cmd"]]

    try:
        log_file = open(log_path, "w", encoding="utf-8", errors="replace")  # noqa: SIM115
    except OSError as exc:
        return {"ok": False, "error": f"log file unavailable: {exc}"}
    try:
        proc = subprocess.Popen(
            cmd, stdout=log_file, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True,
        )
    except (OSError, ValueError) as exc:
        log_file.close()
        return {"ok": False, "error": f"failed to start {provider}: {exc}"}
    log_file.close()  # the child holds its own inherited fd; parent drops it

    url = ""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        hit = re.search(spec["pattern"], text)
        if hit:
            url = hit.group(0)
            break
        time.sleep(0.2)

    state: dict[str, Any] = {
        "id": tunnel_id,
        "provider": provider,
        "port": int(port),
        "pid": proc.pid,
        "url": url,
        "started_at": time.time(),
        "expires_at": time.time() + ttl,
        "ttl_s": ttl,
        "status": "active" if url else "no-url",
    }
    if not url:
        _terminate_pid(proc.pid)
        state["status"] = "failed"
        state["error"] = "no public URL within timeout — see log"
        _save(root, state)
        _audit(root, "tunnel.start_failed", {"id": tunnel_id, "provider": provider, "port": int(port)})
        return {"ok": False, "error": state["error"], "id": tunnel_id, "log": str(log_path)}

    _save(root, state)
    _audit(root, "tunnel.start", {"id": tunnel_id, "provider": provider, "port": int(port), "ttl_s": ttl})
    return {"ok": True, **state, "log": str(log_path)}


def _terminate_pid(pid: int) -> bool:
    try:
        proc = psutil.Process(pid)
    except (psutil.Error, OSError):
        return False
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except (psutil.Error, OSError):
        try:
            proc.kill()
        except (psutil.Error, OSError):
            return False
    return True


def stop(root: Path, tunnel_id: str) -> dict[str, Any]:
    """Stop a tunnel by id. Only the recorded pid is ever signaled."""
    state = _load(root, tunnel_id)
    if state is None:
        return {"ok": False, "error": f"unknown tunnel {tunnel_id!r}"}
    if state.get("status") == "stopped":
        return {"ok": True, "id": tunnel_id, "status": "stopped", "already": True}
    stopped = _terminate_pid(int(state.get("pid", 0)))
    state["status"] = "stopped"
    state["stopped_at"] = time.time()
    _save(root, state)
    _audit(root, "tunnel.stop", {"id": tunnel_id, "provider": state.get("provider"), "pid_signaled": stopped})
    return {"ok": True, "id": tunnel_id, "status": "stopped", "pid_signaled": stopped}


def status(root: Path, tunnel_id: str) -> dict[str, Any]:
    """Report one tunnel, sweeping it first if the TTL has expired."""
    state = _load(root, tunnel_id)
    if state is None:
        return {"ok": False, "error": f"unknown tunnel {tunnel_id!r}"}
    if state.get("status") == "active":
        if _expired(state):
            stop(root, tunnel_id)
            state = _load(root, tunnel_id) or state
        elif not _pid_alive(int(state.get("pid", 0))):
            state["status"] = "dead"
            _save(root, state)
    state = dict(state)
    state["ok"] = True
    state["alive"] = _pid_alive(int(state.get("pid", 0))) if state.get("status") == "active" else False
    return state


def list_tunnels(root: Path, sweep: bool = True) -> dict[str, Any]:
    """List all tracked tunnels; expired active ones are stopped first."""
    tdir = _tunnels_dir(root)
    out: list[dict[str, Any]] = []
    if not tdir.is_dir():
        return {"ok": True, "count": 0, "tunnels": out}
    for path in sorted(tdir.glob("*.json")):
        tunnel_id = path.stem
        st = status(root, tunnel_id) if sweep else _load(root, tunnel_id) or {}
        if st.get("id"):
            st.pop("url", None)  # bearer secret stays out of bulk listings
            out.append(st)
    return {"ok": True, "count": len(out), "tunnels": out}
