"""Tests for runtime/drivers.py + runtime/machine_profile.py."""

from __future__ import annotations

import json
from pathlib import Path

from runtime.drivers import (
    DriverPatch,
    active_effects,
    active_patches,
    embedder_preference,
    load_drivers,
    matches,
    xdist_workers_cap,
)
from runtime.machine_profile import MachineProfile, detect


def _profile(**kw: object) -> MachineProfile:
    base: dict[str, object] = {
        "platform": "linux", "ram_gb": 16.0, "cpu_count": 8,
        "gpu": "none", "python": "3.14.0",
    }
    base.update(kw)
    return MachineProfile(**base)  # type: ignore[arg-type]


def _write(tmp_path: Path, name: str, data: dict) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _patch(**kw: object) -> dict:
    base = {
        "format": "aizee-driver/1",
        "id": "p1",
        "match": {},
        "effect": {},
    }
    base.update(kw)
    return base


class TestDetect:
    def test_detect_returns_profile(self) -> None:
        p = detect()
        assert p.platform in ("win32", "linux", "darwin")
        assert p.cpu_count >= 1
        assert p.gpu in ("nvidia", "none")
        assert p.ram_gb > 0


class TestLoadDrivers:
    def test_loads_sorted_by_priority(self, tmp_path: Path) -> None:
        _write(tmp_path, "b.json", _patch(id="b", priority=20))
        _write(tmp_path, "a.json", _patch(id="a", priority=5))
        assert [d.id for d in load_drivers(tmp_path)] == ["a", "b"]

    def test_missing_dir_returns_empty(self, tmp_path: Path) -> None:
        assert load_drivers(tmp_path / "nope") == []

    def test_invalid_json_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
        assert load_drivers(tmp_path) == []

    def test_wrong_format_skipped(self, tmp_path: Path) -> None:
        _write(tmp_path, "x.json", {"format": "other/9", "match": {}})
        assert load_drivers(tmp_path) == []

    def test_malformed_priority_skipped_not_crashing(self, tmp_path: Path) -> None:
        _write(tmp_path, "bad.json", _patch(id="bad", priority="high"))
        _write(tmp_path, "ok.json", _patch(id="ok"))
        assert [d.id for d in load_drivers(tmp_path)] == ["ok"]


class TestMatching:
    def test_scalar_and_list(self) -> None:
        d = DriverPatch.from_dict(
            _patch(match={"platform": ["linux", "darwin"], "gpu": "none"})
        )
        assert d is not None
        assert matches(d, _profile(platform="linux"))
        assert not matches(d, _profile(platform="win32"))
        assert not matches(d, _profile(gpu="nvidia"))

    def test_ranges(self) -> None:
        d = DriverPatch.from_dict(
            _patch(match={"ram_gb_max": 8, "cpu_count_min": 2, "python_min": "3.12"})
        )
        assert d is not None
        assert matches(d, _profile(ram_gb=8.0, cpu_count=4, python="3.14.0"))
        assert not matches(d, _profile(ram_gb=16.0))
        assert not matches(d, _profile(cpu_count=1))
        assert not matches(d, _profile(python="3.10.0"))

    def test_unknown_key_fails_closed(self) -> None:
        d = DriverPatch.from_dict(_patch(match={"hypervisor": "kvm"}))
        assert d is not None
        assert not matches(d, _profile())


class TestEffects:
    def test_whitelist_drops_unknown_effects(self) -> None:
        d = DriverPatch.from_dict(
            _patch(effect={"embedder": "fastembed", "exec": "rm -rf"})
        )
        assert d is not None
        assert d.effect == {"embedder": "fastembed"}

    def test_active_effects_merges_by_priority(self, tmp_path: Path) -> None:
        _write(tmp_path, "a.json", _patch(
            id="a", priority=5, match={}, effect={"xdist_workers": 2}))
        _write(tmp_path, "b.json", _patch(
            id="b", priority=20, match={}, effect={"xdist_workers": 4}))
        assert active_effects(tmp_path, _profile())["xdist_workers"] == 4

    def test_disabled_patch_inactive(self, tmp_path: Path) -> None:
        _write(tmp_path, "a.json", _patch(
            enabled=False, match={}, effect={"embedder": "fastembed"}))
        assert active_patches(tmp_path, _profile()) == []
        assert embedder_preference(tmp_path, _profile()) is None

    def test_embedder_and_workers_helpers(self, tmp_path: Path) -> None:
        _write(tmp_path, "a.json", _patch(
            match={}, effect={"embedder": "fastembed", "xdist_workers": 4}))
        assert embedder_preference(tmp_path, _profile()) == "fastembed"
        assert xdist_workers_cap(tmp_path, _profile()) == 4

    def test_helpers_return_none_without_effects(self, tmp_path: Path) -> None:
        assert embedder_preference(tmp_path, _profile()) is None
        assert xdist_workers_cap(tmp_path, _profile()) is None

    def test_gpu_enabled_helper(self, tmp_path: Path) -> None:
        from runtime.drivers import gpu_enabled

        _write(tmp_path, "a.json", _patch(match={}, effect={"gpu_enabled": False}))
        assert gpu_enabled(tmp_path, _profile()) is False
        assert gpu_enabled(tmp_path / "nope", _profile()) is None
        # Non-bool effect values are rejected, not coerced.
        _write(tmp_path, "b.json", _patch(
            id="b", priority=99, match={}, effect={"gpu_enabled": "no"}))
        assert gpu_enabled(tmp_path, _profile()) is None


class TestRepoDrivers:
    def test_shipped_drivers_are_valid_and_disabled(self) -> None:
        root = Path(__file__).resolve().parents[2]
        patches = load_drivers(root / "drivers")
        assert len(patches) >= 1
        assert all(not d.enabled for d in patches), (
            "shipped examples must be opt-in (enabled: false)"
        )


class TestMachineProfileHelpers:
    def test_norm_platform_all_cases(self) -> None:
        from runtime.machine_profile import norm_platform

        assert norm_platform("linux") == "linux"
        assert norm_platform("linux2") == "linux"
        assert norm_platform("win32") == "win32"
        assert norm_platform("cygwin") == "win32"
        assert norm_platform("darwin") == "darwin"
        assert norm_platform("freebsd13") == "freebsd13"

    def test_gpu_detection(self, monkeypatch) -> None:
        import shutil

        from runtime.machine_profile import _gpu

        monkeypatch.setattr(shutil, "which", lambda _c: "/usr/bin/nvidia-smi")
        assert _gpu() == "nvidia"
        monkeypatch.setattr(shutil, "which", lambda _c: None)
        assert _gpu() == "none"

    def test_detect_cpu_fallback(self, monkeypatch) -> None:
        import os

        from runtime.machine_profile import detect

        monkeypatch.setattr(os, "cpu_count", lambda: None)
        assert detect().cpu_count == 1


class TestLoadDriversEdgeCases:
    def test_non_dict_json_skipped(self, tmp_path: Path) -> None:
        _write(tmp_path, "list.json", [1, 2, 3])  # type: ignore[arg-type]
        assert load_drivers(tmp_path) == []

    def test_read_error_skipped(self, tmp_path: Path, monkeypatch) -> None:
        _write(tmp_path, "a.json", _patch())
        monkeypatch.setattr(
            Path, "read_text",
            lambda *_a, **_k: (_ for _ in ()).throw(OSError("denied")),
        )
        assert load_drivers(tmp_path) == []


class TestMatchingEdgeCases:
    def test_empty_match_is_universal(self) -> None:
        d = DriverPatch.from_dict(_patch(match={}))
        assert d is not None and matches(d, _profile())

    def test_range_suffix_on_scalar_field_fails(self) -> None:
        d = DriverPatch.from_dict(_patch(match={"platform_max": "linux"}))
        assert d is not None and not matches(d, _profile())

    def test_non_numeric_range_condition_fails(self) -> None:
        d = DriverPatch.from_dict(_patch(match={"ram_gb_max": "lots"}))
        assert d is not None and not matches(d, _profile())

    def test_cond_list_membership(self) -> None:
        d = DriverPatch.from_dict(_patch(match={"gpu": ["nvidia", "amd"]}))
        assert d is not None
        assert not matches(d, _profile(gpu="none"))
        assert matches(d, _profile(gpu="nvidia"))


class TestHelperEdgeCases:
    def test_embedder_alias_and_invalid(self, tmp_path: Path) -> None:
        _write(tmp_path, "a.json", _patch(
            match={}, effect={"embedder": "sentence-transformers"}))
        assert embedder_preference(tmp_path, _profile()) == "st"
        _write(tmp_path, "b.json", _patch(
            id="b", priority=99, match={}, effect={"embedder": "tensorrt"}))
        assert embedder_preference(tmp_path, _profile()) is None

    def test_xdist_cap_bounds(self, tmp_path: Path) -> None:
        _write(tmp_path, "a.json", _patch(match={}, effect={"xdist_workers": 0}))
        assert xdist_workers_cap(tmp_path, _profile()) is None
        _write(tmp_path, "b.json", _patch(
            id="b", priority=99, match={}, effect={"xdist_workers": "many"}))
        assert xdist_workers_cap(tmp_path, _profile()) is None

    def test_active_patches_detects_profile_when_omitted(self, tmp_path: Path) -> None:
        _write(tmp_path, "a.json", _patch(match={}, effect={"xdist_workers": 3}))
        from runtime.drivers import active_patches

        assert len(active_patches(tmp_path)) == 1  # detect() path
        assert active_effects(tmp_path)["xdist_workers"] == 3
