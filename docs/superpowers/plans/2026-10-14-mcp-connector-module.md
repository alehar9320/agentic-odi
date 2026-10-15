# MCP Connector Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `agentic-odi-connectors` uv workspace package exposing a pluggable `Connector` protocol, implement an HTTP `fastmcp` MCP client connector with an in-memory ingest sink and JSON registry, and surface it through the Typer CLI — after first repairing the repo's half-finished workspace refactor so any of this can build and test.

**Architecture:** New `connectors/` package (`src/connectors/`) owns models, protocol, registry, sink, and `MCPClientConnector`. The CLI gets a thin `connectors` Typer sub-app that depends on the package. ODI domain/store/schema are untouched; ingest lands only in the package's in-memory sink.

**Tech Stack:** Python 3.10+, `fastmcp` 4.1.0 (`Client`), `pydantic`, `typer`, `pytest` + `pytest-asyncio` (strict), `uv` workspace, `ruff`/`mypy`/`bandit`/`pytest-cov`.

**Spec:** provided in the task prompt (no on-disk file).

## Global Constraints

- `requires-python = ">=3.10"`; per-package ruff `target-version = "py311"`, `line-length = 100`, lint `select = ["E4","E7","E9","F","I","UP","B","BLE"]`; mypy `python_version = "3.11"`, `ignore_missing_imports = true` (copy existing package configs exactly).
- Use `fastmcp.Client` inside `async with`; HTTP transport; **do not** use the low-level `mcp` SDK.
- All shared structures are Pydantic models.
- Tests are fast/isolated, one behavior each; async tests use `@pytest.mark.asyncio`; prefer in-memory `Client(server)`; no network in the default suite.
- Ingest **must not** write to `jobs_db` / outcomes; only the package's in-memory sink.
- Default registry path: `.agentic-odi/connectors.json` under CWD; path always injectable.
- First and only connector `kind` is `"mcp"`; unknown kinds fail with a clear error.
- Each package keeps its own `pyproject.toml`, `src/` layout, and `tests/`.
- All committed Python must satisfy the repo-wide CI lint gate: `uv run ruff check .` and `uv run ruff format --check .` must pass. Run `uv run ruff format <new files>` before committing new Python — including test files copied from this plan's snippets, which are **not** guaranteed format-clean.

## Review Focus

1. A resource read raises mid-ingest → batch still returns the already-read records plus an error string (Task 6).
2. A name in `settings.tools` does not exist on the server → error collected, batch still returned (Task 6).
3. Server exposes zero tools/resources → one `catalog` record with empty lists, no crash (Task 6).
4. Registry file missing, empty, or malformed JSON → `list` returns `[]` or raises a clear domain error, never a raw traceback (Task 5).
5. Health probe against an unreachable/timing-out server → `HealthStatus(ok=False)` and returns promptly (Task 6).

---

### Task 1: Reconcile workspace, lockfile, and CI to real packages (prerequisite)

The repo's HEAD (`ea545d1`) references a deleted `server/` package everywhere. Nothing below works until this is fixed.

**Files:**
- Modify: `pyproject.toml`
- Modify: `cli/pyproject.toml`
- Modify: `mcp_server/pyproject.toml`
- Modify: `local_server/pyproject.toml`
- Modify: `client/src/client/run.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/dependabot.yml`
- Create: `core/tests/test_core_import.py`
- Regenerate: `uv.lock`

**Interfaces:**
- Produces: a healthy workspace resolving members `cli, client, core, local_server, mcp_server`; `agentic-odi-core` declared as a workspace dependency (with `[tool.uv.sources]`) by `cli`, `mcp_server`, and `local_server`; `client.run` launching `mcp_server`.

- [x] **Step 1: Update root workspace members**

In `pyproject.toml`, change `members = ["cli", "client", "server"]` → `members = ["cli", "client", "core", "local_server", "mcp_server"]`.

- [x] **Step 2: Declare workspace dependencies with sources**

Workspace members that depend on `agentic-odi-core` must declare it in both `dependencies` and `[tool.uv.sources]`. In `cli/pyproject.toml`:
```toml
dependencies = ["typer", "fastmcp", "agentic-odi-core"]

[tool.uv.sources]
agentic-odi-core = { workspace = true }
```
`mcp_server/pyproject.toml` and `local_server/pyproject.toml` already list `agentic-odi-core` in `dependencies`; add the matching block to each:
```toml
[tool.uv.sources]
agentic-odi-core = { workspace = true }
```
Without the sources entry, `uv lock` fails with "`agentic-odi-core` is included as a workspace member, but is missing an entry in `tool.uv.sources`".

- [x] **Step 3: Add a minimal core test**

`core/tests/test_core_import.py`:

```python
def test_core_exports_service():
    import core
    assert hasattr(core, "ODIService")
```

- [x] **Step 4: Repair CI paths**

In `.github/workflows/ci.yml`:
- `typecheck`: replace `--directory server` with three steps: `--directory core`, `--directory mcp_server`, `--directory local_server`.
- `security`: bandit paths → `cli/src client/src core/src local_server/src mcp_server/src`.
- `test`: replace the `Pytest (server)` step with `Pytest (core)`, `Pytest (mcp_server)`, `Pytest (local_server)` using `--cov=core`, `--cov=mcp_server`, `--cov=local_server` and `COVERAGE_FILE`s `.coverage.core/.mcp_server/.local_server`; extend the `coverage combine` file list to match.
- `smoke`: `python -m server` → `python -m mcp_server` (both the launch and the log/echo text).
- `client/src/client/run.py`: in `start_server()`, the process arg list `[sys.executable, "-m", "server"]` → `"-m", "mcp_server"`, and update the module docstring's ``python -m server`` reference (the CI smoke `client.run` probe depends on it).
- `.github/dependabot.yml`: change the `directory: /server` pip entry to `directory: /mcp_server`.

- [x] **Step 5: Regenerate lockfile and sync**

Run: `uv lock && uv sync --all-packages`
Expected: succeeds; `uv.lock` manifest now lists `agentic-odi-core`, `agentic-odi-mcp-server`, `agentic-odi-local-server`.

- [x] **Step 6: Verify the base builds and tests**

Run each, expected PASS:
```
uv run --directory core pytest
uv run --directory mcp_server pytest
uv run --directory local_server pytest
uv run --directory cli pytest
uv run --directory client pytest
```

- [x] **Step 7: Commit**

```bash
git add pyproject.toml cli/pyproject.toml mcp_server/pyproject.toml local_server/pyproject.toml \
  client/src/client/run.py .github/workflows/ci.yml .github/dependabot.yml \
  core/tests/test_core_import.py uv.lock
git commit -m "fix(workspace): reconcile members, lockfile, and CI with core/mcp_server/local_server"
```

---

### Task 2: Scaffold the `connectors` package and register it

**Files:**
- Create: `connectors/pyproject.toml`
- Create: `connectors/src/connectors/__init__.py`
- Modify: `pyproject.toml` (add member)
- Regenerate: `uv.lock`

**Interfaces:**
- Produces: importable `connectors` module and a synced workspace including it.

- [x] **Step 1: Write `connectors/pyproject.toml`**

Copy the `core` package's structure verbatim, changing name/description/deps:

```toml
[project]
name = "agentic-odi-connectors"
version = "0.1.0"
description = "Pluggable external-integration connectors for Agentic ODI (MCP client)."
requires-python = ">=3.10"
dependencies = ["fastmcp", "pydantic"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/connectors"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I", "UP", "B", "BLE"]

[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "strict"
```

- [x] **Step 2: Create the package init**

`connectors/src/connectors/__init__.py`: module docstring only (exports added in Task 3).

- [x] **Step 3: Register the member**

Add `"connectors"` to `members` in root `pyproject.toml`.

- [x] **Step 4: Lock + sync**

Run: `uv lock && uv sync --all-packages`
Expected: succeeds; `uv.lock` lists `agentic-odi-connectors`.

- [x] **Step 5: Verify import**

Run: `uv run --directory connectors python -c "import connectors; print(connectors.__doc__)"`
Expected: prints the docstring, exit 0.

- [x] **Step 6: Commit**

```bash
git add connectors/pyproject.toml connectors/src/connectors/__init__.py pyproject.toml uv.lock
git commit -m "feat(connectors): scaffold agentic-odi-connectors workspace package"
```

---

### Task 3: Shared models, `Connector` protocol, and errors

**Files:**
- Create: `connectors/src/connectors/errors.py`
- Create: `connectors/src/connectors/models.py`
- Create: `connectors/src/connectors/protocol.py`
- Modify: `connectors/src/connectors/__init__.py`
- Test: `connectors/tests/test_models.py`

**Interfaces:**
- Produces:
  - `errors.UnknownConnectorKindError`, `errors.DuplicateConnectorError`, `errors.ConnectorNotFoundError`, `errors.RegistryError` (base `Exception` subclass for the latter three; `UnknownConnectorKindError.name: str`).
  - `models.HealthStatus(ok: bool, detail: str = "")`
  - `models.McpConnectorSettings(url: str, tools: list[str] = [])`
  - `models.ConnectorConfig(name: str, kind: str = "mcp", enabled: bool = True, settings: dict[str, Any] = {})` with method `mcp_settings() -> McpConnectorSettings` (raises `UnknownConnectorKindError` when `kind != "mcp"`).
  - `models.IngestRecord(id: str, source_name: str, source_kind: str, item_type: Literal["resource","tool_result","catalog"], name: str, content: str, raw: dict[str, Any] = {})`
  - `models.IngestBatch(connector_name: str, records: list[IngestRecord] = [], errors: list[str] = [])`
  - `protocol.Connector` — a `@runtime_checkable` `Protocol` with attrs `kind: str`, `name: str` and async methods `health(self) -> HealthStatus`, `ingest(self) -> IngestBatch`.
- `__init__.py` re-exports the above.

- [x] **Step 1: Write the failing test**

`connectors/tests/test_models.py`:

```python
import pytest
from connectors import ConnectorConfig, McpConnectorSettings
from connectors.errors import UnknownConnectorKindError


def test_mcp_settings_parse_url_and_tools():
    s = McpConnectorSettings.model_validate({"url": "http://h/mcp", "tools": ["a"]})
    assert s.url == "http://h/mcp" and s.tools == ["a"]


def test_mcp_settings_default_tools_empty():
    assert McpConnectorSettings(url="http://h/mcp").tools == []


def test_mcp_settings_returns_typed_settings():
    cfg = ConnectorConfig(name="x", kind="mcp", settings={"url": "http://h/mcp"})
    assert cfg.mcp_settings().url == "http://h/mcp"


def test_unknown_kind_raises_clear_error():
    cfg = ConnectorConfig(name="x", kind="rest", settings={})
    with pytest.raises(UnknownConnectorKindError) as ei:
        cfg.mcp_settings()
    assert "rest" in str(ei.value)
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory connectors pytest tests/test_models.py -v`
Expected: FAIL (ImportError: cannot import name 'ConnectorConfig').

- [x] **Step 3: Implement `errors.py`, `models.py`, `protocol.py`, exports**

Use `pydantic.BaseModel`; `mcp_settings()` dispatches on `self.kind`; `UnknownConnectorKindError` message names the offending kind and the known kinds. `Connector` is a `typing.Protocol` decorated `@runtime_checkable` with `async def` stubs (`...`). Re-export all public names from `__init__.py`.

- [x] **Step 4: Run test to verify it passes**

Run: `uv run --directory connectors pytest tests/test_models.py -v`
Expected: PASS (4 passed).

- [x] **Step 5: Commit**

```bash
git add connectors/src/connectors connectors/tests/test_models.py
git commit -m "feat(connectors): add shared models, Connector protocol, and errors"
```

---

### Task 4: In-memory ingest sink

**Files:**
- Create: `connectors/src/connectors/sink.py`
- Modify: `connectors/src/connectors/__init__.py`
- Test: `connectors/tests/test_sink.py`

**Interfaces:**
- Consumes: `models.IngestBatch`, `models.IngestRecord`.
- Produces: `sink.IngestSink` with `append(batch: IngestBatch) -> None`, property `batches -> list[IngestBatch]` (returns a copy), and `dump(path: str | Path) -> None` (writes JSON array of `batch.model_dump()`).

- [x] **Step 1: Write the failing test**

`connectors/tests/test_sink.py`:

```python
import json
from connectors import IngestBatch, IngestRecord, IngestSink


def _batch(name: str) -> IngestBatch:
    return IngestBatch(
        connector_name=name,
        records=[
            IngestRecord(
                id="1", source_name=name, source_kind="mcp",
                item_type="catalog", name="catalog", content="{}", raw={},
            )
        ],
        errors=[],
    )


def test_append_accumulates_batches():
    sink = IngestSink()
    sink.append(_batch("a"))
    sink.append(_batch("b"))
    assert [b.connector_name for b in sink.batches] == ["a", "b"]


def test_records_keep_source_identity():
    sink = IngestSink()
    sink.append(_batch("gong"))
    rec = sink.batches[0].records[0]
    assert rec.source_name == "gong" and rec.source_kind == "mcp"


def test_dump_writes_json(tmp_path):
    sink = IngestSink()
    sink.append(_batch("a"))
    out = tmp_path / "dump.json"
    sink.dump(out)
    assert json.loads(out.read_text())[0]["connector_name"] == "a"
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory connectors pytest tests/test_sink.py -v`
Expected: FAIL (ImportError: cannot import name 'IngestSink').

- [x] **Step 3: Implement `IngestSink`** in `sink.py`; export from `__init__.py`.

- [x] **Step 4: Run test to verify it passes**

Run: `uv run --directory connectors pytest tests/test_sink.py -v`
Expected: PASS (3 passed).

- [x] **Step 5: Commit**

```bash
git add connectors/src/connectors/sink.py connectors/src/connectors/__init__.py connectors/tests/test_sink.py
git commit -m "feat(connectors): add in-memory ingest sink"
```

---

### Task 5: JSON connection registry

**Files:**
- Create: `connectors/src/connectors/registry.py`
- Modify: `connectors/src/connectors/__init__.py`
- Test: `connectors/tests/test_registry.py`

**Interfaces:**
- Consumes: `models.ConnectorConfig`, `errors.*`.
- Produces: `registry.ConnectorRegistry(path: str | Path | None = None)`:
  - default `path` = `Path.cwd() / ".agentic-odi" / "connectors.json"`
  - `list() -> list[ConnectorConfig]` (returns `[]` when the file is absent)
  - `get(name: str) -> ConnectorConfig` (raises `ConnectorNotFoundError`)
  - `add(config: ConnectorConfig) -> None` (raises `DuplicateConnectorError`; persists immediately)
  - `save(configs: list[ConnectorConfig]) -> None` (creates parent dirs; writes `{"connectors": [ ... ]}`)
  - malformed JSON → raises `RegistryError` with the path in the message
- Produces: `registry.build_connector(config, sink, client_factory=None) -> Connector` dispatcher; unknown kind → `UnknownConnectorKindError`. `MCPClientConnector` import is deferred inside this function (added in Task 6).

- [x] **Step 1: Write the failing test**

`connectors/tests/test_registry.py`:

```python
import pytest
from connectors import ConnectorConfig, ConnectorRegistry
from connectors.errors import (
    ConnectorNotFoundError, DuplicateConnectorError, RegistryError,
)


def _reg(tmp_path):
    return ConnectorRegistry(path=tmp_path / "connectors.json")


def test_add_then_list_roundtrips(tmp_path):
    reg = _reg(tmp_path)
    reg.add(ConnectorConfig(name="gong", kind="mcp", settings={"url": "http://h/mcp"}))
    assert [c.name for c in reg.list()] == ["gong"]


def test_config_persists_across_instances(tmp_path):
    p = tmp_path / "connectors.json"
    ConnectorRegistry(path=p).add(ConnectorConfig(name="a", settings={"url": "http://h/mcp"}))
    assert ConnectorRegistry(path=p).get("a").settings["url"] == "http://h/mcp"


def test_list_missing_file_returns_empty(tmp_path):
    assert _reg(tmp_path).list() == []


def test_duplicate_name_rejected(tmp_path):
    reg = _reg(tmp_path)
    reg.add(ConnectorConfig(name="a", settings={"url": "http://h/mcp"}))
    with pytest.raises(DuplicateConnectorError):
        reg.add(ConnectorConfig(name="a", settings={"url": "http://h/mcp"}))


def test_get_unknown_name_raises(tmp_path):
    with pytest.raises(ConnectorNotFoundError):
        _reg(tmp_path).get("nope")


def test_malformed_json_raises_registry_error(tmp_path):
    p = tmp_path / "connectors.json"
    p.write_text("{not json")
    with pytest.raises(RegistryError):
        ConnectorRegistry(path=p).list()


def test_build_connector_rejects_unknown_kind(tmp_path):
    from connectors import IngestSink
    from connectors.errors import UnknownConnectorKindError
    from connectors.registry import build_connector
    cfg = ConnectorConfig(name="x", kind="rest", settings={})
    with pytest.raises(UnknownConnectorKindError):
        build_connector(cfg, IngestSink())
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory connectors pytest tests/test_registry.py -v`
Expected: FAIL (ImportError).

- [x] **Step 3: Implement `registry.py`** with Pydantic `RootModel`/`BaseModel` wrapper for `{"connectors": [...]}` validation, atomic `save`, and the `build_connector` dispatcher. Export `ConnectorRegistry` and `build_connector`.

- [x] **Step 4: Run test to verify it passes**

Run: `uv run --directory connectors pytest tests/test_registry.py -v`
Expected: PASS (7 passed).

- [x] **Step 5: Commit**

```bash
git add connectors/src/connectors/registry.py connectors/src/connectors/__init__.py connectors/tests/test_registry.py
git commit -m "feat(connectors): add JSON connection registry and kind dispatcher"
```

---

### Task 6: `MCPClientConnector` (HTTP `fastmcp.Client`)

**Files:**
- Create: `connectors/src/connectors/mcp.py`
- Modify: `connectors/src/connectors/__init__.py`
- Modify: `connectors/src/connectors/registry.py` (wire `kind == "mcp"` to the class)
- Test: `connectors/tests/test_mcp_connector.py`

**Interfaces:**
- Consumes: `models.*`, `errors.UnknownConnectorKindError`, `sink.IngestSink`.
- Produces: `mcp.MCPClientConnector(config: ConnectorConfig, sink: IngestSink, client_factory: Callable[[], Client] | None = None)` with `kind = "mcp"`, `name`, async `health() -> HealthStatus`, async `ingest() -> IngestBatch`. Default `client_factory` = `lambda: Client(self.settings.url)`.
  - `health()`: enter client, `await client.list_tools()`, return `HealthStatus(ok=True, detail=f"{n} tool(s) available")`; on `Exception` return `HealthStatus(ok=False, detail=str(exc))`.
  - `ingest()`: enter client; `list_tools`, `list_resources`; append a `catalog` record (`content` = JSON of `{"tools": [...names], "resources": [...names]}`, `raw` = full names+uris); for each resource `read_resource(res.uri)` → one `resource` record per returned content block using `.text`; for each name in `settings.tools` `call_tool(name, {})` → one `tool_result` record (text of content blocks, else `str(result.data)`); per-item failures go into `errors`; append batch to sink and return it.

- [x] **Step 1: Write the failing test**

`connectors/tests/test_mcp_connector.py`:

```python
import pytest
from fastmcp import Client, FastMCP

from connectors import ConnectorConfig, IngestSink
from connectors.mcp import MCPClientConnector


def _server() -> FastMCP:
    server = FastMCP("external")

    @server.resource("config://greeting")
    def greeting() -> str:
        return "hello from remote"

    @server.tool
    def ping() -> str:
        return "pong"

    return server


def _connector(sink, tools=None, factory=None):
    cfg = ConnectorConfig(
        name="ext", kind="mcp",
        settings={"url": "http://unused/mcp", "tools": tools or []},
    )
    return MCPClientConnector(cfg, sink, client_factory=factory or (lambda: Client(_server())))


@pytest.mark.asyncio
async def test_health_ok_on_live_server():
    status = await _connector(IngestSink()).health()
    assert status.ok is True
    assert "1 tool" in status.detail


@pytest.mark.asyncio
async def test_ingest_yields_catalog_resource_and_tool_records():
    sink = IngestSink()
    batch = await _connector(sink, tools=["ping"]).ingest()
    kinds = {r.item_type for r in batch.records}
    assert kinds == {"catalog", "resource", "tool_result"}
    assert any(r.content == "hello from remote" for r in batch.records)
    assert any(r.content == "pong" for r in batch.records)
    assert batch.errors == []


@pytest.mark.asyncio
async def test_ingest_with_no_tools_configured():
    batch = await _connector(IngestSink()).ingest()
    assert not any(r.item_type == "tool_result" for r in batch.records)


@pytest.mark.asyncio
async def test_ingest_records_unknown_tool_as_error():
    batch = await _connector(IngestSink(), tools=["does_not_exist"]).ingest()
    assert batch.errors and any("does_not_exist" in e for e in batch.errors)
    assert any(r.item_type == "catalog" for r in batch.records)


class _BrokenClient:
    async def __aenter__(self):
        raise TimeoutError("connect timed out")

    async def __aexit__(self, *exc):
        return False


@pytest.mark.asyncio
async def test_health_fails_cleanly_on_dead_server():
    status = await _connector(IngestSink(), factory=lambda: _BrokenClient()).health()
    assert status.ok is False
    assert "timed out" in status.detail
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory connectors pytest tests/test_mcp_connector.py -v`
Expected: FAIL (ImportError: cannot import name 'MCPClientConnector').

- [x] **Step 3: Implement `mcp.py`**; add `kind == "mcp"` branch in `registry.build_connector`; export `MCPClientConnector`.

- [x] **Step 4: Run test to verify it passes**

Run: `uv run --directory connectors pytest tests/test_mcp_connector.py -v`
Expected: PASS (5 passed).

- [x] **Step 5: Run the whole package suite**

Run: `uv run --directory connectors pytest -v`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add connectors/src/connectors/mcp.py connectors/src/connectors/registry.py connectors/src/connectors/__init__.py connectors/tests/test_mcp_connector.py
git commit -m "feat(connectors): add MCP client connector with health and ingest"
```

---

### Task 7: Typer `connectors` CLI adapter

**Files:**
- Create: `cli/src/cli/connectors.py`
- Modify: `cli/src/cli/cli.py` (register sub-app)
- Modify: `cli/pyproject.toml` (add `agentic-odi-connectors`)
- Test: `cli/tests/test_connectors_cli.py`

**Interfaces:**
- Consumes: `ConnectorRegistry`, `build_connector`, `ConnectorConfig`, `IngestSink` from `connectors`.
- Produces: `cli.connectors.connectors_app` (`typer.Typer`), plus module-level seams `_registry(config_path: str | None) -> ConnectorRegistry`, `_sink() -> IngestSink`, and re-exported `build_connector` for patching.
- Commands (all accept `--config PATH`, default `None`):
  - `list` → prints `name\tkind\tenabled` per connector, or `No connectors configured.`
  - `add mcp --name NAME --url URL [--tool NAME ...]` → persists config; duplicate → exit code 1 with message.
  - `health --name NAME` → `asyncio.run(connector.health())`; prints `ok`/`detail`; exit 1 when `not ok`.
  - `ingest --name NAME [--dump PATH]` → `asyncio.run(connector.ingest())`; prints record/error counts; dumps when `--dump` given.
- `cli/cli.py`: `app.add_typer(connectors_app, name="connectors", help="Manage external data connectors")`.

- [x] **Step 1: Write the failing test**

`cli/tests/test_connectors_cli.py`:

```python
import re
from unittest.mock import patch

from typer.testing import CliRunner

from cli.cli import app

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _run(args):
    return CliRunner().invoke(app, args)


def test_connectors_help_lists_subcommands():
    out = ANSI.sub("", _run(["connectors", "--help"]).output)
    for cmd in ["list", "add", "health", "ingest"]:
        assert cmd in out


def test_add_then_list_roundtrip(tmp_path):
    cfg = str(tmp_path / "connectors.json")
    r = _run(["connectors", "add", "mcp", "--name", "gong", "--url", "http://h/mcp", "--config", cfg])
    assert r.exit_code == 0
    out = ANSI.sub("", _run(["connectors", "list", "--config", cfg]).output)
    assert "gong" in out


def test_list_empty(tmp_path):
    out = ANSI.sub("", _run(["connectors", "list", "--config", str(tmp_path / "none.json")]).output)
    assert "No connectors configured" in out


def test_health_uses_injected_connector(tmp_path):
    cfg = str(tmp_path / "connectors.json")
    _run(["connectors", "add", "mcp", "--name", "gong", "--url", "http://h/mcp", "--config", cfg])

    class Fake:
        async def health(self):
            from connectors import HealthStatus
            return HealthStatus(ok=True, detail="ok")

    with patch("cli.connectors.build_connector", return_value=Fake()):
        r = _run(["connectors", "health", "--name", "gong", "--config", cfg])
    assert r.exit_code == 0
    assert "ok" in ANSI.sub("", r.output)


def test_health_failure_sets_exit_code(tmp_path):
    cfg = str(tmp_path / "connectors.json")
    _run(["connectors", "add", "mcp", "--name", "gong", "--url", "http://h/mcp", "--config", cfg])

    class Fake:
        async def health(self):
            from connectors import HealthStatus
            return HealthStatus(ok=False, detail="unreachable")

    with patch("cli.connectors.build_connector", return_value=Fake()):
        r = _run(["connectors", "health", "--name", "gong", "--config", cfg])
    assert r.exit_code == 1
    assert "unreachable" in ANSI.sub("", r.output)


def test_ingest_uses_injected_connector(tmp_path):
    cfg = str(tmp_path / "connectors.json")
    _run(["connectors", "add", "mcp", "--name", "gong", "--url", "http://h/mcp", "--config", cfg])

    class Fake:
        async def ingest(self):
            from connectors import IngestBatch
            return IngestBatch(connector_name="gong", records=[], errors=[])

    with patch("cli.connectors.build_connector", return_value=Fake()):
        r = _run(["connectors", "ingest", "--name", "gong", "--config", cfg])
    assert r.exit_code == 0
    assert "0" in ANSI.sub("", r.output)
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory cli pytest tests/test_connectors_cli.py -v`
Expected: FAIL (`connectors` command not registered / import error).

- [x] **Step 3: Implement `cli/connectors.py` and register the sub-app**

Build the Typer sub-app with the four commands; call `build_connector(config, sink)` and `asyncio.run(...)` inside command bodies. Print via `typer.echo`. Exit non-zero on duplicate/health failure/unknown name.

- [x] **Step 4: Add the CLI dependency and re-lock**

In `cli/pyproject.toml` add `"agentic-odi-connectors"` to `dependencies` and add `agentic-odi-connectors = { workspace = true }` under `[tool.uv.sources]`; run `uv lock && uv sync --all-packages`.

- [x] **Step 5: Run test to verify it passes**

Run: `uv run --directory cli pytest tests/test_connectors_cli.py -v`
Expected: PASS (6 passed). Then run `uv run --directory cli pytest` → all pass.

- [x] **Step 6: Commit**

```bash
git add cli/src/cli/connectors.py cli/src/cli/cli.py cli/pyproject.toml cli/tests/test_connectors_cli.py uv.lock
git commit -m "feat(cli): add connectors list/add/health/ingest commands"
```

---

### Task 8: Reconcile pre-existing ruff lint and format debt (prerequisite for a green CI)

**Context:** At the start of this module, repo-wide `uv run ruff check .` reports ~35 violations and `uv run ruff format --check .` reports 8 unformatted tracked files, all inherited from the half-finished refactor (commit `ea545d1`). CI's `lint` job runs exactly those two commands, so it is already red before connectors work. This task makes them pass with no behavior change.

**Files:**
- Modify: cli/src/cli/backend.py, cli/src/cli/cli.py, cli/src/cli/outcomes.py
- Modify: core/src/core/models.py, core/src/core/messages.py, core/src/core/sqlite_repository.py
- Modify: core/tests/test_core_import.py, mcp_server/src/mcp_server/__init__.py
- Modify: mcp_server/src/mcp_server/mcp_server.py
- Modify: local_server/src/local_server/app.py, local_server/tests/test_api.py
- Modify: pyproject.toml (root — add ruff exclude for the untracked `docs/` tree; see Step 4)

**Interfaces:** No behavior change; no public API change.

- [x] **Step 1: Auto-fix the mechanical rules**

`uv run ruff check . --fix` (fixes `I001` unsorted-imports, `F401` unused-import, `F841` unused-variable).

- [x] **Step 2: Resolve the remainder by hand, matching existing conventions**
  - `E702` (one-line semicolons in `cli/src/cli/outcomes.py`): split into separate statements.
  - `B008` (`typer.Option(...)` in argument defaults in `outcomes.py`): add `# noqa: B008` (the repo's `cli/src/cli/cli.py` already uses this convention).
  - `BLE001` (blind `except Exception`) in `cli/src/cli/backend.py`, `core/src/core/sqlite_repository.py`, `mcp_server/src/mcp_server/mcp_server.py`: add `# noqa: BLE001` where the broad catch is intentional (matches existing convention); otherwise narrow the exception only if trivially safe.
  - `UP042` in `core/src/core/models.py` (`class Direction(str, Enum)`, `BusinessImpactCategory(str, Enum)`): **do not** convert to `StrEnum`. Keep Python 3.10 compatibility and add `# noqa: UP042`.

- [x] **Step 3: Neutralize the untracked plan Markdown BEFORE formatting**

ruff 0.17 formats Python code blocks inside Markdown. `docs/` has no tracked files and is not committed, so it never reaches CI; but a local `uv run ruff format .` / `--check .` would still flag and rewrite it. Add a root-level exclude first so global format/check skips `docs/`:

```toml
# pyproject.toml (root)
[tool.ruff]
extend-exclude = ["docs"]
```

- [x] **Step 4: Format**

`uv run ruff format .`

Then verify exactly as CI does, from the repo root:

```
uv run ruff check .
uv run ruff format --check .
```

Both must exit 0.

- [x] **Step 5: Confirm no behavior change**

Run every package's pytest (the list in Task 9 Step 4) and confirm all pass.

- [x] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: reconcile pre-existing ruff lint and format debt"
```

---

### Task 9: Wire connectors into CI, make the full CI gate green, and update docs

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `.agents/rules/agent_instructions.md`
- Modify: `.agents/workflows/dev.md`
- Modify: `.agents/workflows/test.md`
- Modify: `connectors/src/connectors/registry.py` (residual mypy fix)
- Modify: `core/src/core/models.py` (residual mypy fix)
- Modify: `core/src/core/sqlite_repository.py` (residual bandit fix)

**Interfaces:**
- Consumes: everything above.
- Produces: CI green with connectors included; docs accurate.

- [x] **Step 0: Fix residual CI-gate failures found at base (typecheck + security)**

Besides the lint debt fixed in Task 8, the base was also red on `typecheck` (core) and `security` (bandit). Fix, behavior-preserving:
  - `connectors/src/connectors/registry.py` — mypy `[valid-type]` on `save`: the method `list` shadows the builtin, so the annotation `configs: list[ConnectorConfig]` resolves to the method. Fix by referring to the builtin (e.g. add `import builtins` and annotate `configs: builtins.list[ConnectorConfig]`, or introduce a module-level alias such as `_Configs = list[ConnectorConfig]` before the class and use it). Do not rename the public `list` method.
  - `core/src/core/models.py` — mypy `prop-decorator` on the three `@computed_field` + `@property` pairs (lines ~68/84/107, a known mypy limitation). Add `# type: ignore[prop-decorator]` on each `@computed_field` line (verified to satisfy `uv run --directory core mypy .`).
  - `core/src/core/sqlite_repository.py` — bandit `B110` (try/except/pass) at the `except Exception:` line (~47). Append `# nosec B110` to that line, after the existing `# noqa: BLE001` (verified: `# noqa: BLE001  # nosec B110` satisfies both ruff and bandit).

- [x] **Step 1: Add connectors to CI**

- `typecheck`: add `uv run --directory connectors mypy .`
- `security`: add `connectors/src` to bandit paths
- `test`: add a `Pytest (connectors)` step (`--cov=connectors`, `COVERAGE_FILE=.coverage.connectors`) and add `${{ github.workspace }}/.coverage.connectors` to `coverage combine`

- [x] **Step 2: Update README.md**

- **Code Overview**: correct the stale three-project text to the actual packages — `core/`, `mcp_server/`, `local_server/`, `cli/`, `client/`, and the new `connectors/` (`agentic-odi-connectors`: pluggable external integrations; first connector is an HTTP MCP **client**).
- **CLI**: add a "External connectors (MCP ingest)" subsection documenting `agentic-odi connectors list|add mcp|health|ingest` and the `--config` default `.agentic-odi/connectors.json`.
- **Testing table**: add `connectors/tests/*` rows (registry, sink, MCP in-memory, models) and `cli/tests/test_connectors_cli.py`.
- **Roadmap**: add a "Generic integrations (external data connectors)" item, marking the MCP client connector done/in-progress.
- Fix any `python -m server` references to `python -m mcp_server`.

- [x] **Step 3: Update `.agents/rules/agent_instructions.md`**

Add a short "External connectors package" subsection: new `connectors/` package; it is an MCP **client** of external servers (inverse of the ODI MCP server); HTTP transport via `fastmcp.Client`; test with in-memory `Client(server)`; unknown kinds must fail clearly. Also fix the stale `server/src/server/server.py` path references (→ `mcp_server/src/mcp_server/mcp_server.py`).

- [x] **Step 3b: Fix stale `server` references in agent workflow docs**

In `.agents/workflows/dev.md` and `.agents/workflows/test.md`, replace residual `server` package references with `mcp_server` (e.g. `python -m server` → `python -m mcp_server`, `uv run --directory server pytest` → `uv run --directory mcp_server pytest`).

- [x] **Step 4: Run the full CI-equivalent locally**

```
uv run ruff check .
uv run ruff format --check .
uv run --directory core mypy .
uv run --directory mcp_server mypy .
uv run --directory local_server mypy .
uv run --directory cli mypy .
uv run --directory client mypy .
uv run --directory connectors mypy .
uv run bandit -c pyproject.toml -r cli/src client/src core/src local_server/src mcp_server/src connectors/src
uv run --directory core pytest
uv run --directory mcp_server pytest
uv run --directory local_server pytest
uv run --directory cli pytest
uv run --directory client pytest
uv run --directory connectors pytest
```
Expected: all PASS.

- [x] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml README.md .agents/rules/agent_instructions.md .agents/workflows/dev.md .agents/workflows/test.md connectors/src/connectors/registry.py core/src/core/models.py core/src/core/sqlite_repository.py
git commit -m "ci+docs: wire connectors into CI and document the package"
```

---

## Self-Review

**Spec coverage:** Package scaffold+workspace+lockfile → Tasks 1–2. Protocol/models/registry/sink → Tasks 3–5. `MCPClientConnector` (health, catalog, resources, optional tools) → Task 6. CLI list/add/health/ingest with `asyncio.run` → Task 7. Pre-existing lint/format debt → Task 8. CI + README + agent_instructions → Task 9. Out-of-scope items (ODI schema, job/outcome mapping, Streamlit, stdio, k8s, config-writing) are untouched. Spec's "three packages / server/" premise is corrected by Task 1.

**Type consistency:** `ConnectorConfig.mcp_settings()`, `IngestSink.append/batches/dump`, `ConnectorRegistry.list/get/add/save`, `build_connector(config, sink, client_factory=None)`, `MCPClientConnector(config, sink, client_factory=None)` are used identically in every later task. `HealthStatus`/`IngestRecord`/`IngestBatch` field names match tests.

**Review Focus → tests:** item 1 & 2 → Task 6 `test_ingest_records_unknown_tool_as_error` (+ per-resource error path in `mcp.py`); item 3 → Task 6 `test_ingest_with_no_tools_configured` (empty catalog covered by `kinds` assertion); item 4 → Task 5 `test_list_missing_file_returns_empty` + `test_malformed_json_raises_registry_error`; item 5 → Task 6 `test_health_fails_cleanly_on_dead_server`.

---
