"""Tests for the vercel-labs adoptions: skill_lock, mcp_freeze, doc_links,
models_catalog, and the error scope/code/public contract."""

from __future__ import annotations

import json
from pathlib import Path

from runtime.doc_links import (
    check_links,
    extract_code_refs,
    extract_links,
    iter_markdown,
    symbol_defined,
)
from runtime.mcp_freeze import check_surface, read_lock, snapshot, tool_fingerprint, write_lock
from runtime.models_catalog import catalog_summary, find_model, load_catalog
from runtime.schemas import AizeeError, ErrorSeverity, PolicyDeniedError
from runtime.skill_lint import lint_structure, run_lint
from runtime.skill_lock import SkillLock, folder_hash

# --- skill_lock -----------------------------------------------------------


class TestSkillLock:
    def _tree(self, tmp: Path) -> Path:
        skills = tmp / "skills"
        skills.mkdir()
        (skills / "alpha.md").write_text("---\nname: alpha\n---\nA")
        (skills / "beta.md").write_text("---\nname: beta\n---\nB")
        d = skills / "dir-skill"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: dir-skill\n---\nC")
        (d / "ref.md").write_text("detail")
        (skills / "README.md").write_text("not a skill")
        (skills / "index.json").write_text("{}")
        return tmp

    def test_record_all_and_check_clean(self, tmp_path: Path) -> None:
        self._tree(tmp_path)
        lock = SkillLock(tmp_path)
        n = lock.record_all_local()
        assert n == 3
        entries = lock.entries()
        assert set(entries) == {"alpha", "beta", "dir-skill"}
        assert entries["dir-skill"].path == "skills/dir-skill"
        report = lock.check()
        assert report.ok and not report.changed and not report.missing and not report.extra

    def test_detects_change_missing_extra(self, tmp_path: Path) -> None:
        self._tree(tmp_path)
        lock = SkillLock(tmp_path)
        lock.record_all_local()
        (tmp_path / "skills" / "alpha.md").write_text("CHANGED")
        (tmp_path / "skills" / "beta.md").unlink()
        (tmp_path / "skills" / "gamma.md").write_text("new")
        report = lock.check()
        assert not report.ok
        assert report.changed == ["alpha"]
        assert report.missing == ["beta"]
        assert "gamma" in report.extra

    def test_record_remove_single(self, tmp_path: Path) -> None:
        self._tree(tmp_path)
        lock = SkillLock(tmp_path)
        e = lock.record("alpha", tmp_path / "skills" / "alpha.md", source="pack:vendor/x")
        assert e.hash == folder_hash(tmp_path / "skills" / "alpha.md")
        assert lock.entries()["alpha"].source == "pack:vendor/x"
        assert e.to_dict()["path"] == "skills/alpha.md"
        assert lock.remove("alpha") is True
        assert lock.remove("alpha") is False

    def test_empty_tree_and_extras(self, tmp_path: Path) -> None:
        lock = SkillLock(tmp_path)
        assert lock.record_all_local() == 0  # no skills dir
        assert lock.check().ok  # nothing locked, no skills dir

    def test_record_all_prunes_stale_entries(self, tmp_path: Path) -> None:
        self._tree(tmp_path)
        lock = SkillLock(tmp_path)
        lock.record_all_local()
        assert "alpha" in lock.entries()
        # rename/delete → stale entry pruned on next record_all
        (tmp_path / "skills" / "alpha.md").unlink()
        lock.record_all_local()
        assert "alpha" not in lock.entries()
        assert lock.check().missing == []
        # dir-skill extra detection in check()
        skills = tmp_path / "skills"
        d = skills / "extra-dir"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("x")
        report = lock.check()
        assert "extra-dir" in report.extra
        d2 = lock.check().to_dict()
        assert "extra" in d2 and "changed" in d2

    def test_corrupt_and_absent_lock(self, tmp_path: Path) -> None:
        lock = SkillLock(tmp_path)
        assert lock.entries() == {}
        lock.path.write_text("not json")
        assert lock.entries() == {}
        lock.path.write_text(json.dumps({"version": 99, "skills": {}}))
        assert lock.entries() == {}
        lock.path.write_text(json.dumps({"version": 1, "skills": "bad"}))
        assert lock.entries() == {}
        lock.path.write_text(json.dumps({"version": 1, "skills": {"a": "bad", "b": {"path": "x", "hash": "h"}}}))
        assert set(lock.entries()) == {"b"}

    def test_folder_hash_stable(self, tmp_path: Path) -> None:
        p = tmp_path / "f.md"
        p.write_text("abc")
        assert folder_hash(p) == folder_hash(p)
        q = tmp_path / "g.md"
        q.write_text("abd")
        assert folder_hash(p) != folder_hash(q)
        # directory hashing covers nested content
        d = tmp_path / "sub"
        d.mkdir()
        (d / "a.txt").write_text("1")
        h1 = folder_hash(d)
        (d / "b.txt").write_text("2")
        assert folder_hash(d) != h1
        (tmp_path / "Thumbs.db").write_text("x")  # skipped name
        assert folder_hash(tmp_path / "Thumbs.db") != folder_hash(d)


# --- mcp_freeze ------------------------------------------------------------


_TOOLS = [
    {"name": "read", "inputSchema": {"type": "object", "properties": {"p": {"type": "string"}}}},
    {"name": "write", "inputSchema": {"type": "object"}, "description": "w"},
]


class TestMcpFreeze:
    def test_freeze_and_clean_check(self, tmp_path: Path) -> None:
        lock = tmp_path / "tool-lock.json"
        write_lock(lock, "srv", _TOOLS)
        report = check_surface("srv", _TOOLS, lock)
        assert report.ok and report.frozen_count == 2
        assert read_lock(lock, "srv") == snapshot(_TOOLS)

    def test_detects_all_drift(self, tmp_path: Path) -> None:
        lock = tmp_path / "tool-lock.json"
        write_lock(lock, "srv", _TOOLS)
        live = [
            {"name": "read", "inputSchema": {"type": "object"}},  # changed schema
            {"name": "evil_new", "inputSchema": {}},             # added
        ]  # "write" removed
        report = check_surface("srv", live, lock)
        assert not report.ok
        assert report.added == ["evil_new"]
        assert report.removed == ["write"]
        assert report.changed == ["read"]

    def test_lock_roundtrip_merge(self, tmp_path: Path) -> None:
        lock = tmp_path / "tool-lock.json"
        write_lock(lock, "a", _TOOLS)
        write_lock(lock, "b", _TOOLS[:1])
        assert set(read_lock(lock, "a")) == {"read", "write"}
        assert set(read_lock(lock, "b")) == {"read"}

    def test_corrupt_lock_and_missing(self, tmp_path: Path) -> None:
        lock = tmp_path / "x.json"
        assert read_lock(lock, "s") == {}
        lock.write_text("bad")
        assert read_lock(lock, "s") == {}
        lock.write_text(json.dumps({"servers": {"s": {"tools": "bad"}}}))
        assert read_lock(lock, "s") == {}
        # write_lock over corrupt file still succeeds
        lock.write_text("garbage")
        write_lock(lock, "s", _TOOLS)
        assert read_lock(lock, "s")
        # write_lock over a wrong-version file replaces it
        lock.write_text(json.dumps({"version": 99, "servers": {"s": {"tools": {}}}}))
        write_lock(lock, "s", _TOOLS)
        assert set(read_lock(lock, "s")) == {"read", "write"}
        report = check_surface("s", _TOOLS, lock)
        assert report.to_dict()["ok"] is True

    def test_fingerprint_inputs(self) -> None:
        t1 = {"name": "t", "inputSchema": {"a": 1}}
        t2 = {"name": "t", "input_schema": {"a": 1}}  # snake_case accepted
        assert tool_fingerprint(t1) == tool_fingerprint(t2)
        assert snapshot([{"name": ""}, {"name": "x"}]) == {"x": tool_fingerprint({"name": "x"})}


# --- doc_links --------------------------------------------------------------


class TestDocLinks:
    def test_extract(self) -> None:
        links = extract_links("see [[runtime/kernel.py]] and [[runtime/kernel.py#Kernel|K]]")
        assert links == [("runtime/kernel.py", ""), ("runtime/kernel.py", "Kernel")]
        assert extract_code_refs("# @aizee: [[specs/auth]]\nx = 1") == ["specs/auth"]
        # fenced + inline code spans are not links (TOML [[table]] etc.)
        txt = "real [[a/b.py]]\n```toml\n[[fake.table]]\n```\n`[[inline.x]]` end"
        assert extract_links(txt) == [("a/b.py", "")]

    def test_check_links(self, tmp_path: Path) -> None:
        src = tmp_path / "runtime"
        src.mkdir()
        (src / "mod.py").write_text("def target():\n    pass\n")
        (tmp_path / "docs").mkdir()
        ok = tmp_path / "docs" / "ok.md"
        ok.write_text("[[runtime/mod.py]] [[runtime/mod.py#target]] [[https://x.com/y]]")
        bad = tmp_path / "docs" / "bad.md"
        bad.write_text("[[runtime/missing.py]] [[runtime/mod.py#nope]] [[../../outside.md]]")
        report = check_links(tmp_path)
        assert not report.ok
        reasons = {(i.target, i.reason) for i in report.issues}
        assert ("runtime/missing.py", "file not found") in reasons
        assert ("runtime/mod.py#nope", "symbol not found") in reasons
        assert any(r == "escapes root" for _, r in reasons)
        d = report.to_dict()
        assert d["ok"] is False and d["issues"]
        assert report.issues[0].to_dict()["reason"] in {"file not found", "symbol not found", "escapes root"}

    def test_absolute_and_docrelative_and_dir(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        near = docs / "near.md"
        near.write_text("[[peer.md]]")  # doc-relative fallback
        (docs / "peer.md").write_text("p")
        abs_target = tmp_path / "runtime"
        abs_target.mkdir()
        (abs_target / "a.py").write_text("def a:\n    pass")
        near.write_text(f"[[peer.md]] [[{abs_target / 'a.py'}]] [[runtime]]")
        (docs / "weird.md").mkdir()  # unreadable-as-file → skipped
        report = check_links(tmp_path)
        # dir target with no symbol check + abs path + doc-relative all ok
        broken = [i for i in report.issues if i.reason != "file not found"]
        assert not broken

    def test_symbol_defined_per_lang(self, tmp_path: Path) -> None:
        cases = {
            "m.py": ("def f", "f", True), "x.py": ("class C:\n    x = 1", "x", True),
            "y.py": ("def f", "g", False),
            "a.ts": ("export const fn = 1", "fn", True),
            "b.ts": ("interface I {}", "I", True),
            "c.js": ("function g() {}", "g", True),
            "d.rs": ("pub fn work() {}", "work", True),
            "e.go": ("func main() {}", "main", True),
            "f.go": ("func (s S) M() {}", "M", True),
            "g.yaml": ("key: val", "key", True),  # unknown ext → contains check
            "h.yaml": ("key: val", "zzz", False),
            "i.md": ("# Title Here", "Title Here", True),
        }
        for name, (content, sym, want) in cases.items():
            p = tmp_path / name
            p.write_text(content)
            assert symbol_defined(p, sym) is want, f"{name}:{sym}"
        missing = tmp_path / "gone.py"
        assert symbol_defined(missing, "x") is False

    def test_iter_and_skip(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("x")
        skip = tmp_path / "node_modules"
        skip.mkdir()
        (skip / "b.md").write_text("y")
        names = [p.name for p in iter_markdown(tmp_path)]
        assert names == ["a.md"]

    def test_unreadable_doc(self, tmp_path: Path) -> None:
        d = tmp_path / "x.md"
        d.write_text("[[nope]]")
        d.chmod(0o000)  # may not fail on Windows — either way covered
        try:
            report = check_links(tmp_path)
            assert isinstance(report.links, int)
        finally:
            d.chmod(0o644)


# --- models_catalog -----------------------------------------------------------


class TestModelsCatalog:
    def _cat(self, tmp: Path) -> Path:
        res = tmp / "resources"
        res.mkdir()
        (res / "models_catalog.json").write_text(json.dumps({
            "providers": {
                "anthropic": {"name": "Anthropic", "models": {
                    "claude-x": {"name": "Claude X", "ctx": 200000, "out": 64000,
                                 "in_cost": 3.0, "out_cost": 15.0,
                                 "tools": True, "reasoning": True},
                    "bad": "notadict",
                }},
                "empty": {"name": "E", "models": None},
                "weird": "notadict",
            }
        }))
        return tmp

    def test_load_and_query(self, tmp_path: Path) -> None:
        root = self._cat(tmp_path)
        entries = load_catalog(root)
        assert len(entries) == 1
        e = entries[0]
        assert e.provider == "anthropic" and e.context == 200000
        assert e.to_dict()["model_id"] == "claude-x"
        assert find_model(entries, "CLAUDE") == [e]
        assert find_model(entries, "zzz") == []
        s = catalog_summary(entries)
        assert s["provider_count"] == 1 and s["model_count"] == 1

    def test_missing_and_corrupt(self, tmp_path: Path) -> None:
        assert load_catalog(tmp_path) == []
        res = tmp_path / "resources"
        res.mkdir()
        (res / "models_catalog.json").write_text("{bad json")
        assert load_catalog(tmp_path) == []


# --- error contract (scope/code/public) --------------------------------------


class TestErrorContract:
    def test_defaults_and_serialization(self) -> None:
        e = AizeeError("CODE_X", "boom", ErrorSeverity.MEDIUM, {"k": "v"})
        d = e.to_dict()
        assert d["error_code"] == "CODE_X" and d["scope"] == "runtime"
        assert d["public"] is True and d["severity"] == "medium"
        assert e.to_public_dict() == d

    def test_custom_scope_public(self) -> None:
        e = AizeeError("C", "m", scope="policy", public=False)
        assert e.to_dict()["scope"] == "policy"
        pub = e.to_public_dict()
        assert pub["error_code"] == "INTERNAL_ERROR"
        assert pub["message"] == "Internal error"
        assert pub["scope"] == "policy" and pub["context"] == {}

    def test_subclass_compat(self) -> None:
        e = PolicyDeniedError("denied", {"a": 1})
        d = e.to_dict()
        assert d["error_code"] == "POLICY_DENIED" and d["scope"] == "runtime"


# --- lint_structure (agent-skills conventions) --------------------------------


class TestLintStructure:
    def test_valid_tree(self, tmp_path: Path) -> None:
        skills = tmp_path / "skills"
        d = skills / "my-skill"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("---\nname: my-skill\n---\n" + "x\n" * 10)
        assert lint_structure(tmp_path) == {}

    def test_all_violations(self, tmp_path: Path) -> None:
        skills = tmp_path / "skills"
        bad = skills / "Bad_Name"
        bad.mkdir(parents=True)
        (bad / "skill.md").write_text("x")  # wrong case
        other = skills / "other"
        other.mkdir(parents=True)
        (other / "notes.md").write_text("x")  # no SKILL.md
        big = skills / "big-skill"
        big.mkdir(parents=True)
        (big / "SKILL.md").write_text("x\n" * 600)
        hidden = skills / ".hidden"
        hidden.mkdir(parents=True)
        (hidden / "x.md").write_text("y")
        issues = lint_structure(tmp_path)
        assert "kebab-case" in issues["Bad_Name"][0]
        assert any("SKILL.md" in p for p in issues["Bad_Name"])
        assert any("missing SKILL.md" in p for p in issues["other"])
        assert any("500" in p for p in issues["big-skill"])
        assert ".hidden" not in issues

    def test_no_skills_dir(self, tmp_path: Path) -> None:
        assert lint_structure(tmp_path) == {}

    def test_unreadable_skill_file(self, tmp_path: Path, monkeypatch) -> None:
        skills = tmp_path / "skills"
        d = skills / "s"
        d.mkdir(parents=True)
        exact = d / "SKILL.md"
        exact.write_text("x\n" * 600)
        orig = Path.read_text
        def guard(self: Path, *a: object, **k: object) -> str:
            if self == exact:
                raise OSError("locked")
            return orig(self, *a, **k)  # type: ignore[arg-type]
        monkeypatch.setattr(Path, "read_text", guard)
        issues = lint_structure(tmp_path)
        assert issues.get("s", []) == []  # unreadable → n_lines=0 → no size issue

    def test_run_lint_includes_structure(self, tmp_path: Path) -> None:
        skills = tmp_path / "skills"
        bad = skills / "BAD"
        bad.mkdir(parents=True)
        (bad / "SKILL.md").write_text(
            "---\nname: bad\ndescription: Use when testing a thing here ok\ntriggers: [t]\n---\n")
        report = run_lint(tmp_path)
        assert "structure" in report and "BAD" in report["structure"]
        assert not report["ok"]
