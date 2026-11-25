[TECH] pytest-9
[OBJ] pytest 9.x testing standards for aiZee test suites.
[RULES]
1. [REQ] AAA pattern (Arrange-Act-Assert). One behavior per test (`[TEST-02]`).
2. [REQ] Fixtures for shared setup. `conftest.py` for cross-file fixtures. Factory functions, not hardcoded IDs (`[TEST-03]`).
3. [REQ] `pytest.approx(expected, abs=tol)` for float comparisons. NEVER `==` on time-dependent floats.
4. [REQ] `pytest.importorskip("tkinter")` for optional dependencies. Never let collection break on missing modules.
5. [REQ] `pytest.raises(ExcType, match="regex")` for expected exceptions. Assert on message when relevant.
6. [REQ] Markers: `slow`, `integration`, `unit`, `fast`, `mcp`, `dashboard`, `vector`. Use `@pytest.mark.slow` for E2E.
7. [REQ] `asyncio.run(coro())` for async tests. NEVER `asyncio.get_event_loop().run_until_complete()` (removed in 3.14).
8. [REQ] `@pytest.mark.asyncio` only with `pytest-asyncio` installed. Prefer sync wrappers for simple cases.
9. [REQ] `tmp_path` fixture for filesystem tests. Never write to real cwd.
10. [REQ] `monkeypatch` for env vars and attributes. Restore in `finally` or use `monkeypatch.delenv`.
11. [REQ] Two-tier (`[TEST-07]`): FAST = `pytest <file> --no-cov` (~5s). FULL = `pytest --cov` (before done).
12. [REQ] `pytest-asyncio` auto mode: set `asyncio_mode = "auto"` in `pyproject.toml` `[tool.pytest.ini_options]`. Eliminates need for `@pytest.mark.asyncio` on every async test.
13. [REQ] `@pytest.mark.parametrize("param,expected", [(...), ...])` for data-driven tests. Use `pytest.param(..., id="descriptive_name")` for readable test IDs. Use `ids=` callback for dynamic ID generation.
14. [REQ] `--last-failed-no-failures all` in `pyproject.toml` `[tool.pytest.ini_options]` `addopts`. When `--last-failed` is used and no failures exist, run the full suite. Prevents empty test runs after fixing all failures.
15. [REQ] `tmp_path_factory` fixture for session-scoped temp directories. Use `tmp_path_factory.mktemp("session_data")` for expensive setup shared across test modules. Never use `tmp_path` for session-scoped resources.
16. [REQ] Custom markers via `pyproject.toml`: register markers in `[tool.pytest.ini_options]` `markers` list: `slow: marks tests as slow`, `integration: marks integration tests`. Enables `--strict-markers` validation — unregistered markers cause collection errors.
17. [REQ] Use `@pytest.fixture(scope="session")` for expensive resources (database connections, model loading). Use `scope="function"` (default) for isolated state.
18. [REQ] `pytest -x` (stop on first failure) during FAST iteration. `pytest --lf` (last failed only) for rapid fix cycles. `pytest --sw` (stepwise) for sequential debugging.
19. [REQ] Use `pytest.Config` and `pytest.HookimplMarker` for plugin development. Never use deprecated `pytest.config` global (removed in pytest 8).
20. [REQ] pytest 9 migration: `PytestRemovedIn9Warning` is an error by default in 9.0 and the affected deprecated features are removed in 9.1. Do not silence these warnings; update the test/plugin code.
21. [REQ] Do not apply pytest marks to fixture functions — this never had an effect and is removed/erroring in pytest 9. Put marks on test items or use fixtures explicitly.
22. [REQ] pytest 9.2 deprecates module/package/session-scoped fixtures defined as instance methods, matching the earlier class-scoped deprecation. Define higher-scoped fixtures as module-level functions or static/class methods as appropriate.
23. [REQ] Collection order is alphabetical across files and directories jointly (pytest 8+ behavior). Do not depend on files being collected before directories; use explicit ordering plugins only when truly required.
24. [REQ] `pytest pkg/__init__.py` collects only that module in pytest 8+; use `pytest pkg` to collect an entire package.
25. [PROHIBIT] `assert x == 7.0` on floats without `approx` (time drift causes flaky failures).
26. [PROHIBIT] `asyncio.get_event_loop()` (removed Python 3.14).
27. [PROHIBIT] Hardcoded paths/dates (`[TEST-03]`). Use fixtures/factories.
28. [PROHIBIT] Empty `except`. Use `pytest.raises` or assert on outcome.
29. [PROHIBIT] `pytest.config` global (removed in pytest 8). Use `request.config` or `pytest.Config`.
30. [REQ] `--cov` sources MUST be path-form (`--cov=src/`), never dotted module names (`--cov=src`). Dotted names make coverage resolve them via `importlib.util.find_spec`, which executes parent package initializers in a fragile reentrant import context. Path-form sources skip module resolution entirely.
31. [REQ] Optional heavy deps (sentence_transformers/torch, transformers) MUST be lazy-imported inside the function that uses them — never module-level try/except. Root `conftest.py` imports `memory.store` on every run; a module-level ST import cost ~7.6s cold per process (and per xdist worker). Keep a patchable module attribute + `_UNSET` sentinel so tests can still `patch.object(mod, "Dep", None)`.
32. [REQ] NEVER run `gc.collect()` in a per-test autouse fixture — a full collect costs ~0.1s+ on a large heap (~11 min across a 6.7k-test suite). Amortize (every N tests) or rely on refcounting; cyclic garbage tolerates delay.
33. [REQ] GC boot window for large suites: `gc.disable()` at conftest import, then in `pytest_collection_modifyitems` run `gc.freeze(); gc.set_threshold(50_000, 20, 20); gc.enable()`. Freezes permanent collection-time objects so later sweeps skip them.
34. [REQ] Use `--ignore=<dir>` for whole-dir exclusions; `-m` deselect still imports the modules (module-level code runs at collection). aiZee fast tier ignores `tests/mcp`, `tests/dashboard`, `tests/e2e`, `tests/memory/test_vector.py`.
35. [REQ] pytest-xdist `-n` is a win on Windows for large suites once heavy imports are lazy. Each worker re-pays import cost via spawn — keep module imports cheap. `-n logical` uses logical cores when psutil is installed.
36. [REQ] `pytest-testmon` (`--testmon`) selects only tests affected by changed code via a coverage-derived dependency DB — ideal for FAST tier on large suites when installed. Requires one baseline run to build `.testmondata`.
37. [REQ] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` + explicit `-p xdist -p timeout` trims startup ~40% for single-test invocations (auto-loaded plugins: cov, anyio, xdist, timeout...).
38. [REQ] Never assume an optional dep is absent in tests — transitive deps (e.g. `opentelemetry-api` via litellm) may install the API surface without the SDK. Simulate absence with `monkeypatch.setitem(sys.modules, "pkg", None)` and reset warn-once globals.
39. [REQ] Both tiers parallelize by default via pytest-xdist when installed (`aizee test`, `aizee test --full`); `--no-xdist` is the opt-out escape hatch. Workers = `os.cpu_count() - 2` (floor 2), optionally capped by declarative driver patches — max out the box, leave the OS breathing room. pytest-cov merges per-worker coverage automatically.
40. [REQ] GPU is NOT a test-suite lever by default — decide by measurement, not hope. Install CUDA builds only when tests run real GPU-bound code, verify utilization with `nvidia-smi`, and remember CUDA contexts cost VRAM per worker. Fully mocked suites gain nothing and can run slower.
41. [REQ] When C: is full or roaming-installs are heavy, install experiment packages to a scratch dir on another drive (`pip install --target <dir> --no-deps`, env `TMPDIR=<dir>`) and run via `PYTHONPATH=<dir>` — zero env pollution, delete when done.
[COMPAT]
- v9.2.0: current installed. `pytest-xdist` 3.8.0 and `pytest-cov` 7.1.0 verified with the full suite on Windows/Python 3.14.
- Plugins: `pytest-asyncio` 1.4.x (auto mode), `pytest-xdist` 3.8.x, `pytest-timeout` 2.4.x, `pytest-cov` 7.1.x.
- Config: `pyproject.toml` `[tool.pytest.ini_options]` is the canonical config location.
- `config.inicfg` private-attribute compatibility shim exists in 9.0.x but is deprecated; do not use private pytest internals in new code.
[REFS]
- https://docs.pytest.org/en/stable/
- https://docs.pytest.org/en/stable/changelog.html
- https://docs.pytest.org/en/stable/deprecations.html
- https://docs.pytest.org/en/stable/how-to/parametrize.html
- https://pytest-asyncio.readthedocs.io/en/latest/auto_mode.html
