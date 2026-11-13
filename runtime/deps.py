"""External dependency manifest — declarative check + install.

``deps.yaml`` at the OS root declares software that aiZee features need but
that lives outside the repo: binaries, pip packages, git-cloned media
kits/apps, docker images, env keys. Consumed by ``aizee deps`` (CLI),
``aizee doctor`` (folded into the health report), and ``scripts/update.py``
(post-install hook that offers to install what is missing).

Adding an entry to the manifest is the supported way to stop a feature from
shipping with silent missing requirements — see the schema comment at the
top of ``deps.yaml``.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

MANIFEST_NAME = "deps.yaml"
_CHECK_TIMEOUT = 20
_INSTALL_TIMEOUT = 1800


class Kind(str, Enum):
    """Supported dependency kinds in the manifest."""

    BINARY = "binary"
    PIP = "pip"
    GIT_REPO = "git-repo"
    DOCKER_DAEMON = "docker-daemon"
    DOCKER_IMAGE = "docker-image"
    ENV = "env"
    ANY_PATH = "any-path"
    COMMAND = "command"


class State(str, Enum):
    """Check outcome for a single dep."""

    OK = "ok"
    MISSING = "missing"
    OUTDATED = "outdated"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DepSpec:
    """One parsed entry from deps.yaml."""

    id: str
    name: str
    kind: Kind
    severity: str  # required | recommended | optional
    required_by: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    bin: str = ""
    version_cmd: tuple[str, ...] = ()
    version_regex: str = ""
    min_version: str = ""
    package: str = ""
    path: str = ""
    repo: str = ""
    image: str = ""
    env_vars: tuple[str, ...] = ()
    env_any_of: bool = False
    paths: tuple[str, ...] = ()
    check_cmd: dict[str, tuple[str, ...]] = field(default_factory=dict)
    expect_regex: str = ""
    install: dict[str, str] = field(default_factory=dict)
    update: dict[str, str] = field(default_factory=dict)
    guidance: str = ""


@dataclass(frozen=True)
class DepStatus:
    """Result of checking one dep against this machine."""

    spec: DepSpec
    ok: bool
    state: State
    version: str = ""
    detail: str = ""
    can_install: bool = False
    fix_cmd: str = ""


@dataclass(frozen=True)
class InstallResult:
    """Outcome of one install/update attempt."""

    dep_id: str
    ok: bool
    command: str
    detail: str = ""


Runner = Callable[[str], tuple[int, str]]


def os_key() -> str:
    """Manifest key for the current OS."""
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def media_dir(manifest: dict[str, Any]) -> Path:
    """Resolve the media kits/apps dir: env override wins, else the default."""
    env_name = str(manifest.get("media_dir_env", "AIZEE_MEDIA_DIR"))
    env_val = os.environ.get(env_name, "").strip()
    raw = env_val or str(manifest.get("media_dir_default", "~/.aizee/media"))
    return Path(os.path.expandvars(os.path.expanduser(raw)))


def manifest_path(root: Path) -> Path:
    return root / MANIFEST_NAME


def load_manifest(root: Path) -> tuple[list[DepSpec], dict[str, Any]]:
    """Parse deps.yaml. Returns (specs, manifest_meta). Missing file → []."""
    path = manifest_path(root)
    if not path.exists():
        return [], {}
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    specs = [_to_spec(d) for d in data.get("deps", []) if isinstance(d, dict)]
    return specs, data


def _check_cmd_map(raw: Any) -> dict[str, tuple[str, ...]]:
    """Normalize check_cmd: a flat argv list → {"all": argv}; an OS map stays a map."""
    if isinstance(raw, list):
        return {"all": tuple(str(x) for x in raw)}
    if isinstance(raw, dict):
        return {str(k): tuple(str(x) for x in v) for k, v in raw.items() if isinstance(v, list)}
    return {}


def _to_spec(d: dict[str, Any]) -> DepSpec:
    return DepSpec(
        id=str(d.get("id", "")),
        name=str(d.get("name") or d.get("id", "")),
        kind=Kind(str(d.get("kind", "binary"))),
        severity=str(d.get("severity", "optional")),
        required_by=tuple(str(x) for x in d.get("required_by", []) or []),
        tags=tuple(str(x) for x in d.get("tags", []) or []),
        bin=str(d.get("bin", "")),
        version_cmd=tuple(str(x) for x in d.get("version_cmd", []) or []),
        version_regex=str(d.get("version_regex", "")),
        min_version=str(d.get("min_version", "")),
        package=str(d.get("package", "")),
        path=str(d.get("path", "")),
        repo=str(d.get("repo", "")),
        image=str(d.get("image", "")),
        env_vars=tuple(str(x) for x in d.get("env_vars", []) or []),
        env_any_of=bool(d.get("env_any_of", False)),
        paths=tuple(str(x) for x in d.get("paths", []) or []),
        check_cmd=_check_cmd_map(d.get("check_cmd")),
        expect_regex=str(d.get("expect_regex", "")),
        install={str(k): str(v) for k, v in (d.get("install") or {}).items()},
        update={str(k): str(v) for k, v in (d.get("update") or {}).items()},
        guidance=str(d.get("guidance", "")),
    )


def check_all(root: Path, ids: set[str] | None = None, tags: set[str] | None = None) -> list[DepStatus]:
    """Check every dep in the manifest (optionally filtered by id/tag)."""
    specs, meta = load_manifest(root)
    ctx = _Ctx(root=root, media=media_dir(meta))
    out: list[DepStatus] = []
    for spec in specs:
        if ids and spec.id not in ids:
            continue
        if tags and not (set(spec.tags) & tags):
            continue
        out.append(check_dep(spec, ctx))
    return out


@dataclass(frozen=True)
class _Ctx:
    root: Path
    media: Path


def check_dep(spec: DepSpec, ctx: _Ctx) -> DepStatus:
    """Dispatch to the kind-specific checker."""
    checker = {
        Kind.BINARY: _check_binary,
        Kind.PIP: _check_pip,
        Kind.GIT_REPO: _check_git_repo,
        Kind.DOCKER_DAEMON: _check_docker_daemon,
        Kind.DOCKER_IMAGE: _check_docker_image,
        Kind.ENV: _check_env,
        Kind.ANY_PATH: _check_any_path,
        Kind.COMMAND: _check_command,
    }[spec.kind]
    state, version, detail = checker(spec, ctx)
    can_install = _resolve(spec.install, spec, ctx, update=False) is not None
    if state is State.OUTDATED:
        can_install = can_install or _resolve(spec.update, spec, ctx, update=True) is not None
    return DepStatus(
        spec=spec,
        ok=state is State.OK,
        state=state,
        version=version,
        detail=detail,
        can_install=can_install,
        fix_cmd=f"aizee deps install {spec.id}" if (state is not State.OK and can_install) else "",
    )


def _check_binary(spec: DepSpec, ctx: _Ctx) -> tuple[State, str, str]:
    exe = shutil.which(spec.bin)
    if not exe:
        return State.MISSING, "", f"{spec.bin} not on PATH"
    version = _detect_version(spec)
    if spec.min_version and version and _version_tuple(version) < _version_tuple(spec.min_version):
        return State.OUTDATED, version, f"{version} < required {spec.min_version}"
    return State.OK, version, exe


def _detect_version(spec: DepSpec) -> str:
    if not spec.version_cmd or not spec.version_regex:
        return ""
    try:
        proc = subprocess.run(
            list(spec.version_cmd), capture_output=True, text=True,
            timeout=_CHECK_TIMEOUT, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    match = re.search(spec.version_regex, proc.stdout + proc.stderr)
    return match.group(1) if match else ""


def _version_tuple(raw: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", raw)[:4])


def _check_pip(spec: DepSpec, ctx: _Ctx) -> tuple[State, str, str]:
    from importlib.metadata import PackageNotFoundError, version

    try:
        installed = version(spec.package)
    except PackageNotFoundError:
        return State.MISSING, "", f"pip package {spec.package} not installed"
    if spec.min_version and _version_tuple(installed) < _version_tuple(spec.min_version):
        return State.OUTDATED, installed, f"{installed} < required {spec.min_version}"
    return State.OK, installed, ""


def _check_git_repo(spec: DepSpec, ctx: _Ctx) -> tuple[State, str, str]:
    path = _expand(spec.path, spec, ctx)
    if path.is_dir() and any(path.iterdir()):
        return State.OK, "", str(path)
    return State.MISSING, "", f"{path} not cloned"


def _check_docker_daemon(spec: DepSpec, ctx: _Ctx) -> tuple[State, str, str]:
    if not shutil.which("docker"):
        return State.MISSING, "", "docker not on PATH"
    try:
        proc = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=_CHECK_TIMEOUT, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return State.MISSING, "", "docker info failed"
    if proc.returncode == 0 and proc.stdout.strip():
        return State.OK, proc.stdout.strip(), "daemon up"
    return State.MISSING, "", "daemon not running (start Docker Desktop)"


def _check_docker_image(spec: DepSpec, ctx: _Ctx) -> tuple[State, str, str]:
    if not shutil.which("docker"):
        return State.MISSING, "", "docker not on PATH"
    try:
        proc = subprocess.run(
            ["docker", "images", "-q", spec.image],
            capture_output=True, text=True, timeout=_CHECK_TIMEOUT, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return State.UNKNOWN, "", "docker query failed"
    if proc.returncode != 0:
        return State.UNKNOWN, "", "daemon unreachable"
    if proc.stdout.strip():
        return State.OK, "", spec.image
    return State.MISSING, "", f"image {spec.image} not built"


def _registry_env_has(name: str) -> bool:
    """True when a var is persisted in Windows User/Machine env (registry).

    Process env only reflects what the *parent* had at spawn — a var the
    user persisted mid-session is invisible to already-running processes,
    yet every fresh shell will see it. Registry is the honest source for
    "is the machine configured". POSIX: no equivalent; returns False.
    """
    if sys.platform != "win32":
        return False
    import winreg

    for hive, sub in (
        (winreg.HKEY_CURRENT_USER, "Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    ):
        try:
            with winreg.OpenKey(hive, sub) as key:
                value, _ = winreg.QueryValueEx(key, name)
                if value:
                    return True
        except OSError:
            continue
    return False


def _env_present(name: str) -> bool:
    return bool(os.environ.get(name)) or _registry_env_has(name)


def _check_env(spec: DepSpec, ctx: _Ctx) -> tuple[State, str, str]:
    present = [v for v in spec.env_vars if _env_present(v)]
    ok = bool(present) if spec.env_any_of else len(present) == len(spec.env_vars)
    if ok:
        return State.OK, "", f"{len(present)} key(s) set"
    return State.MISSING, "", f"need {'any of' if spec.env_any_of else 'all of'}: {', '.join(spec.env_vars)}"


def _check_any_path(spec: DepSpec, ctx: _Ctx) -> tuple[State, str, str]:
    for raw in spec.paths:
        p = _expand(raw, spec, ctx)
        if p.exists():
            return State.OK, "", str(p)
    return State.MISSING, "", "none of the expected paths exist"


def _check_command(spec: DepSpec, ctx: _Ctx) -> tuple[State, str, str]:
    cmd = spec.check_cmd.get(os_key()) or spec.check_cmd.get("all")
    if not cmd:
        return State.UNKNOWN, "", "no check command for this OS"
    try:
        proc = subprocess.run(
            list(cmd), capture_output=True, text=True,
            timeout=_CHECK_TIMEOUT, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return State.MISSING, "", "check command failed to run"
    if proc.returncode == 0 and re.search(spec.expect_regex or ".", proc.stdout + proc.stderr):
        return State.OK, "", ""
    return State.MISSING, "", "check output did not match expected capability"


def _expand(raw: str, spec: DepSpec, ctx: _Ctx) -> Path:
    expanded = _placeholders(raw, spec, ctx)
    return Path(os.path.expandvars(os.path.expanduser(expanded)))


def _placeholders(text: str, spec: DepSpec, ctx: _Ctx) -> str:
    """Expand {media} {root} {python} {path} {repo} {image} {package} {bin}."""
    resolved_path = spec.path.replace("{media}", str(ctx.media)) if spec.path else ""
    mapping = {
        "{media}": str(ctx.media),
        "{root}": str(ctx.root),
        "{python}": sys.executable,
        "{path}": resolved_path,
        "{repo}": spec.repo,
        "{image}": spec.image,
        "{package}": spec.package,
        "{bin}": spec.bin,
        "{user_profile}": str(Path.home()),
    }
    for key, value in mapping.items():
        text = text.replace(key, value)
    return text


def _resolve(cmds: dict[str, str], spec: DepSpec, ctx: _Ctx, update: bool) -> str | None:
    """Resolve the install/update command for this OS, with defaults per kind."""
    if spec.kind is Kind.GIT_REPO and not cmds:
        target = _expand(spec.path, spec, ctx)
        if update:
            return f"git -C {shlex.quote(str(target))} pull --ff-only"
        return f"git clone --depth 1 {shlex.quote(spec.repo)} {shlex.quote(str(target))}"
    cmd = cmds.get(os_key()) or cmds.get("all") or ""
    return _placeholders(cmd, spec, ctx) if cmd else None


def install_command(spec: DepSpec, ctx: _Ctx, outdated: bool = False) -> str | None:
    """Command that would fix this dep on this OS (None if manual-only)."""
    if outdated:
        return _resolve(spec.update or spec.install, spec, ctx, update=True)
    return _resolve(spec.install, spec, ctx, update=False)


def _default_runner(cmd: str) -> tuple[int, str]:
    """Run a manifest install command. Trusted repo content — shell for && support."""
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=_INSTALL_TIMEOUT, check=False,
        )
    except subprocess.TimeoutExpired:
        return 124, "timed out"
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def install_statuses(
    root: Path,
    statuses: list[DepStatus],
    *,
    dry_run: bool = False,
    runner: Runner | None = None,
) -> list[InstallResult]:
    """Install (or update) each failed dep that has a resolvable command."""
    run = runner or _default_runner
    _, meta = load_manifest(root)
    ctx = _Ctx(root=root, media=media_dir(meta))
    results: list[InstallResult] = []
    for status in statuses:
        if status.ok:
            continue
        cmd = install_command(status.spec, ctx, outdated=status.state is State.OUTDATED)
        if not cmd:
            results.append(InstallResult(status.spec.id, False, "", "no install command — manual step needed"))
            continue
        if dry_run:
            results.append(InstallResult(status.spec.id, True, cmd, "dry-run"))
            continue
        _ensure_parent(status.spec, ctx)
        rc, out = run(cmd)
        ok = rc == 0 and _recheck(status.spec, ctx)
        detail = "installed" if ok else (out[-300:] or f"exit {rc}")
        results.append(InstallResult(status.spec.id, ok, cmd, detail))
    return results


def _ensure_parent(spec: DepSpec, ctx: _Ctx) -> None:
    """Create the parent dir for path-targeted deps before cloning/installing."""
    if spec.kind in (Kind.GIT_REPO, Kind.ANY_PATH) and spec.path:
        _expand(spec.path, spec, ctx).parent.mkdir(parents=True, exist_ok=True)


def _recheck(spec: DepSpec, ctx: _Ctx) -> bool:
    """Verify the dep actually checks out after the install ran."""
    try:
        return check_dep(spec, ctx).ok
    except Exception:
        return False
