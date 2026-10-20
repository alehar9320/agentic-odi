# First-Run Onboarding (PM Baseline) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On first interactive launch, the CLI captures a PM baseline via URL auto-detect with typed fallback, persists it to `~/.config/agentic-odi/baseline.json`, and exposes `setup`/`profile` commands; the first-run hook never fires again once the file exists.

**Architecture:** Three new modules in the `cli` package: `profile.py` (baseline model, XDG config path, atomic load/save, `setup`/`profile` Typer sub-app), `infer.py` (deterministic keyword-based domain/business-model inference from page text), `onboard.py` (httpx fetch + stdlib HTML signal extraction, confirmation card, typed fallback, first-run hook). The hook is wired into the existing root Typer callback in `cli.py`.

**Tech Stack:** Python 3.10+, Typer, httpx (new declared `cli` dependency), stdlib `html.parser`, pytest, uv.

**Spec:** `docs/superpowers/specs/2026-10-16-first-run-onboarding-design.md`

## Global Constraints

- Python `>= 3.10`; CLI package `agentic-odi-cli`, entry `cli.cli:app`.
- Config dir: `XDG_CONFIG_HOME/agentic-odi` → `~/.config/agentic-odi` (Windows: `%APPDATA%\agentic-odi`); baseline file `baseline.json`.
- All user-facing copy renders the invoked program name via `Path(sys.argv[0]).name` (helper `cli.cli_name()`), never a hard-coded `odi`/`agentic-odi`.
- No LLM calls, no network in tests (httpx `MockTransport` only), no writes outside the XDG config dir (tests override `XDG_CONFIG_HOME` / `HOME` via monkeypatch + tmp_path).
- Schema: only `schema_version` is required; all other fields may be `null`/empty; confirmation card renders only non-null lines. JSON keys are **flat** (`product_name`, `product_url`) rather than the spec's nested `product` object — simpler for the dataclass round-trip (builder call).
- `--version` needs no guard in the hook: the eager Typer option callback raises `Exit` during parsing, before the root callback body runs.
- Inference is deterministic pure Python; `confidence` is `"high"` iff top domain keyword score `>= 3`, else `"low"`.
- Fetch: timeout 8.0s, `max_redirects=3`, UA `agentic-odi/<version>`; fetch failure or low confidence → typed path (one soft line, no traceback).
- Ruff line-length 100, lint rules per `cli/pyproject.toml` (incl. `BLE` — use `# noqa: BLE001` where a broad catch is intentional, as `outcomes.py` does).
- Commands are `setup` and `profile` (plain language, decided). `profile` supports `--json`.
- First-run hook skips when: baseline exists, TTYs absent, `--no-onboard` passed, env `AGENTIC_ODI_NO_ONBOARD=1`, or command is `--version`/`version`/`setup`/`profile`/`connectors`/`outcomes`.

## Review Focus

Uncovered inputs/conditions most likely to bite a user — each has a test in the task that owns the code:

1. **Slow/hanging site** — 8s timeout fires, user lands in typed path with a soft line, no traceback. (Task 3)
2. **Non-interactive first run (CI, pipes)** — one hint line, command continues, never blocks. (Task 5)
3. **Confidently wrong inference** — card always shown; nothing written to disk before the user confirms. (Task 5)
4. **Concurrent first runs** — atomic temp-file + `os.replace` write; no partial `baseline.json`. (Task 1)
5. **`--version` / `--help`** — never trigger onboarding. (Task 5)

---

### Task 1: Baseline model, config path, atomic persistence

**Files:**
- Create: `cli/src/cli/profile.py`
- Test: `cli/tests/test_profile.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `profile.config_dir() -> Path`
  - `profile.baseline_file() -> Path`
  - `@dataclasses.dataclass Baseline` with fields: `schema_version: int = 1`, `created_at: str | None`, `source: str | None` (`"url"` | `"typed"`), `product_name: str | None`, `product_url: str | None`, `domain: str | None`, `primary_user: str | None`, `business_model: str | None`, `core_problem: str | None`, `current_focus: str | None`, `confidence: str | None` (`"high"` | `"low"`)
  - `Baseline.to_dict() -> dict` / `Baseline.from_dict(d: dict) -> Baseline` (missing keys → `None`; `schema_version` defaults to 1)
  - `baseline_exists() -> bool`
  - `load_baseline() -> Baseline | None` (returns `None` when file absent; raises `ValueError` on unparseable JSON)
  - `save_baseline(b: Baseline) -> Path` (sets `created_at` ISO-8601 UTC when `None`; writes atomically: `baseline.json.tmp` in same dir then `os.replace`)
  - `backup_baseline() -> Path | None` (copies existing file to `baseline.json.bak-YYYYMMDDTHHMMSSZ`; returns path; `None` if no existing file)

- [ ] **Step 1: Write the failing tests**

```python
# cli/tests/test_profile.py
import json
import os
from pathlib import Path

from cli import profile


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.delenv("AGENTIC_ODI_BASELINE_FILE", raising=False)


def test_config_dir_uses_xdg_config_home(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    assert profile.config_dir() == tmp_path / "cfg" / "agentic-odi"


def test_config_dir_defaults_to_home(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    if os.name == "nt":
        monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
        assert profile.config_dir() == tmp_path / "appdata" / "agentic-odi"
    else:
        assert profile.config_dir() == tmp_path / ".config" / "agentic-odi"


def test_baseline_file_name(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    assert profile.baseline_file().name == "baseline.json"


def test_save_and_load_roundtrip(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    b = profile.Baseline(source="url", product_name="Sentry", domain="DevTools")
    path = profile.save_baseline(b)
    assert path.exists()
    loaded = profile.load_baseline()
    assert loaded is not None
    assert loaded.product_name == "Sentry"
    assert loaded.domain == "DevTools"
    assert loaded.created_at is not None
    assert profile.baseline_exists() is True


def test_load_returns_none_when_absent(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    assert profile.load_baseline() is None
    assert profile.baseline_exists() is False


def test_from_dict_defaults_missing_keys():
    b = profile.Baseline.from_dict({"schema_version": 1})
    assert b.domain is None
    assert b.product_name is None


def test_save_creates_dirs_and_is_atomic(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    profile.save_baseline(profile.Baseline(source="typed"))
    f = profile.baseline_file()
    assert not (f.parent / "baseline.json.tmp").exists()
    json.loads(f.read_text())  # valid JSON on disk


def test_backup_creates_timestamped_copy(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    profile.save_baseline(profile.Baseline(product_name="A"))
    bak = profile.backup_baseline()
    assert bak is not None and bak.exists()
    assert bak.name.startswith("baseline.json.bak-")
    assert profile.backup_baseline() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory cli pytest tests/test_profile.py -v`
Expected: FAIL (no module `cli.profile`).

- [ ] **Step 3: Implement `cli/src/cli/profile.py`**

Dataclass `Baseline` with the fields and defaults from the Interfaces block; `to_dict` via `dataclasses.asdict`; `from_dict` builds with `d.get(...)` for every field. `config_dir()` resolves `AGENTIC_ODI_BASELINE_FILE`'s parent if that env var is set — no: env override of the *file* is not in scope; resolve `XDG_CONFIG_HOME`/`HOME` (POSIX) or `APPDATA` (Windows). `save_baseline` creates dirs (`mkdir(parents=True, exist_ok=True)`), writes JSON to `baseline_file().with_suffix(".json.tmp")`, then `os.replace`. `backup_baseline` uses `shutil.copy2` with strftime `"%Y%m%dT%H%M%SZ"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory cli pytest tests/test_profile.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/src/cli/profile.py cli/tests/test_profile.py
git commit -m "feat(cli): PM baseline model and atomic persistence"
```

---

### Task 2: Deterministic inference engine

**Files:**
- Create: `cli/src/cli/infer.py`
- Test: `cli/tests/test_infer.py`

**Interfaces:**
- Consumes: `profile.Baseline` (fields only; construct with `source="url"`, `confidence` set here).
- Produces:
  - `infer.PageSignals` (dataclass): `url: str`, `title: str | None`, `meta_description: str | None`, `headings: list[str]`, `body_text: str` (may be `""`)
  - `infer.text_blob(s: PageSignals) -> str` (lowercased title + meta + headings + first 2000 chars of body)
  - `infer.DOMAIN_KEYWORDS: dict[str, list[str]]` — seed dictionary, keys are display domains, values lowercase keyword lists:
    - `"Developer Tools / DevOps"`: `["code", "developer", "api", "ci/cd", "deploy", "repository", "git", "debug", "observability", "open source"]`
    - `"FinTech / Payments"`: `["payment", "billing", "bank", "finance", "invoice", "checkout", "fraud"]`
    - `"HealthTech"`: `["patient", "health", "clinical", "ehr", "hipaa", "medical"]`
    - `"MarTech / Analytics"`: `["marketing", "analytics", "campaign", "conversion", "attribution", "crm"]`
    - `"Marketplace / E-commerce"`: `["marketplace", "shop", "store", "seller", "buyer", "cart", "catalog"]`
    - `"B2B SaaS"`: `["team", "workspace", "saas", "enterprise", "integration", "workflow", "per seat"]`
  - `infer.infer_baseline(signals: PageSignals) -> tuple[profile.Baseline, dict[str, int]]` — scores every domain by keyword occurrences in the blob; fills `domain` with the top domain (or `None` if all scores are 0); `product_name` from `signals.title` up to the first `" — "`/`" - "`/`" | "` (whole title if no separator; `None` when no title); `business_model` is `"Product-led (freemium/consumption hints)"` if blob contains `"free"` or `"pricing"` or `"per seat"`, else `None`; `core_problem` is the meta description (trimmed to 200 chars) or `None`; `primary_user` is `None` (left for just-in-time); `confidence` is `"high"` if top score `>= 3` else `"low"`; returns `(baseline, scores)`.

- [ ] **Step 1: Write the failing tests**

```python
# cli/tests/test_infer.py
from cli import profile
from cli.infer import PageSignals, infer_baseline, text_blob


def _signals(**kwargs):
    defaults = dict(
        url="https://x.io", title=None, meta_description=None, headings=[], body_text=""
    )
    defaults.update(kwargs)
    return PageSignals(**defaults)


def test_blob_lowercases_and_joins():
    s = _signals(title="Sentry", headings=["Debug"], body_text="ERROR TRACKING")
    assert "sentry" in text_blob(s)
    assert "error tracking" in text_blob(s)


def test_infer_devtools_high_confidence():
    s = _signals(
        title="Sentry — Developer Tools",
        meta_description="Application observability and debugging for developers.",
        body_text="code debugging observability api deploy ci/cd git repository",
    )
    b, scores = infer_baseline(s)
    assert b.domain == "Developer Tools / DevOps"
    assert b.confidence == "high"
    assert scores["Developer Tools / DevOps"] >= 3


def test_infer_low_confidence_when_thin():
    s = _signals(title="Acme", body_text="Welcome to Acme.")
    b, scores = infer_baseline(s)
    assert b.domain is None or b.confidence == "low"


def test_infer_fintech_and_plg_hint():
    s = _signals(
        title="PayFlow",
        body_text="payment checkout billing fraud free tier per seat pricing",
    )
    b, _ = infer_baseline(s)
    assert b.domain == "FinTech / Payments"
    assert b.business_model is not None
    assert b.confidence == "high"


def test_core_problem_from_meta_and_name_from_title():
    s = _signals(
        title="Sentry — Error Tracking",
        meta_description="Real-time error tracking for apps.",
    )
    b, _ = infer_baseline(s)
    assert b.core_problem.startswith("Real-time error tracking")
    assert b.product_name == "Sentry"
    assert b.source == "url"
    assert profile.Baseline.from_dict(b.to_dict()).product_name == "Sentry"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory cli pytest tests/test_infer.py -v`
Expected: FAIL (no module `cli.infer`).

- [ ] **Step 3: Implement `cli/src/cli/infer.py`**

As specified in Interfaces: `text_blob` concatenates fields lowercased; scoring counts `blob.count(kw)` summed per domain; business-model hint checks membership of `"free"`, `"pricing"`, `"per seat"` in the blob; `core_problem = (meta_description or "")[:200] or None`; `primary_user = None`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory cli pytest tests/test_infer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/src/cli/infer.py cli/tests/test_infer.py
git commit -m "feat(cli): deterministic domain inference from page signals"
```

---

### Task 3: Page fetch + HTML signal extraction

**Files:**
- Create: `cli/src/cli/onboard.py`
- Test: `cli/tests/test_onboard_fetch.py`

**Interfaces:**
- Consumes: `infer.PageSignals`, `cli.version.__version__`.
- Produces:
  - `onboard.normalize_url(text: str) -> str` — strips whitespace; prepends `https://` when no scheme; strips trailing slashes.
  - `onboard.extract_signals(url: str, html: str) -> PageSignals` — stdlib `html.parser.HTMLParser` subclass collecting: `<title>` text; `meta name="description"`, `og:title`/`og:description` content; all `h1`/`h2` visible text into `headings`; all visible text (skip `script`/`style`) into `body_text`, capped at 50_000 chars.
  - `onboard.fetch_signals(url: str, client: httpx.Client | None = None) -> PageSignals` — GET `normalize_url(url)` with `timeout=8.0`, `max_redirects=3`, UA `agentic-odi/<__version__>`; on `httpx.HTTPError` raise `FetchError` (new exception class in this module); caller-owned `client` parameter exists for tests; when `client is None`, opens/closes its own.

- [ ] **Step 1: Write the failing tests**

```python
# cli/tests/test_onboard_fetch.py
import httpx
import pytest

from cli.onboard import FetchError, extract_signals, fetch_signals, normalize_url


def test_normalize_url_adds_scheme_and_strips_slash():
    assert normalize_url("acme.com/") == "https://acme.com"
    assert normalize_url(" https://acme.com ") == "https://acme.com"


def test_extract_signals_reads_title_meta_headings():
    html = """
    <html><head>
      <title>Acme — Payments</title>
      <meta name="description" content="Checkout for online stores.">
      <meta property="og:description" content="Sell more.">
    </head><body>
      <h1>Acme</h1><h2>For sellers</h2>
      <script>var x = "ignored";</script>
      <p>Marketplace catalog cart checkout.</p>
    </body></html>
    """
    s = extract_signals("https://acme.com", html)
    assert s.title == "Acme — Payments"
    assert s.meta_description == "Checkout for online stores."
    assert "Acme" in s.headings and "For sellers" in s.headings
    assert "ignored" not in s.body_text
    assert "Marketplace catalog" in s.body_text


def test_fetch_signals_uses_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"].startswith("agentic-odi/")
        return httpx.Response(200, text="<title>Acme</title><p>team workspace saas</p>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    s = fetch_signals("acme.com", client=client)
    assert s.title == "Acme"


def test_fetch_signals_timeout_raises_fetch_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(FetchError):
        fetch_signals("slow.example", client=client)


def test_fetch_signals_http_error_raises_fetch_error():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(FetchError):
        fetch_signals("boom.example", client=client)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory cli pytest tests/test_onboard_fetch.py -v`
Expected: FAIL (no module `cli.onboard`).

- [ ] **Step 3: Add `httpx` dependency and implement `cli/src/cli/onboard.py`**

Add `"httpx"` to `dependencies` in `cli/pyproject.toml`, then run `uv lock` from the repo root (workspace lockfile). Implement `normalize_url`, `_SignalParser(HTMLParser)` (track in-title / in-script / in-style / in-heading state; capture meta attrs), `extract_signals`, `FetchError(Exception)`, and `fetch_signals` per the Interfaces block. Catch `httpx.HTTPError` (covers timeout/connect/protocol) and raise `FetchError` from it; do not catch beyond that. `body_text` is `" ".join(visible_chunks)[:50_000]`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory cli pytest tests/test_onboard_fetch.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/pyproject.toml cli/src/cli/onboard.py cli/tests/test_onboard_fetch.py uv.lock
git commit -m "feat(cli): page fetch and HTML signal extraction"
```

---

### Task 4: Confirmation card + typed fallback questionnaire

**Files:**
- Modify: `cli/src/cli/onboard.py` (append UI functions)
- Test: `cli/tests/test_onboard_ui.py`

**Interfaces:**
- Consumes: `profile.Baseline`.
- Produces (all in `onboard.py`; input via the `input()` builtin so tests can monkeypatch; output via `typer.echo`):
  - `FOCUS_OPTIONS = ["launch", "activation", "retention", "scaling", "discovery"]`
  - `cli_name() -> str` — `Path(sys.argv[0]).name or "agentic-odi"`
  - `render_card(b: profile.Baseline) -> str` — multi-line string, no ANSI; header `Based on {b.product_url or "your answers"} — does this look right?`; then only non-null lines in fixed order: `Domain`, `Users` (primary_user), `Business` (business_model), `Solves` (core_problem); footer `  [Enter] confirm   [e] edit   [r] retry URL   [q] quit`.
  - `ask_typed(prefill: profile.Baseline | None = None) -> profile.Baseline` — three questions in order:
    1. `Domain [B2B SaaS, DevTools, FinTech, HealthTech, Marketplace, …]:` (free text; default = `prefill.domain`; Enter with no value → domain `None`)
    2. `Who uses it (and for what job)?:` (free text; default = `prefill.primary_user`; Enter → `None`)
    3. numbered menu over `FOCUS_OPTIONS` plus `[Enter] skip`; returns `current_focus` or `None`
    Returns a `Baseline` with `source="typed"` and `confidence=None`; preserves `product_name`/`product_url` from `prefill` when given.
  - `edit_lines(b: profile.Baseline) -> profile.Baseline` — lists the non-null card lines numbered; asks which line number to edit; re-prompts that one field with current value as default; loops until user presses Enter at the "which line?" prompt.
  - `confirm_or_edit(b: profile.Baseline, *, input_fn=input) -> profile.Baseline | None` — prints `render_card(b)`; loop on `input_fn`: empty/`y` → return `b`; `e` → `b = edit_lines(b)`; `q` → return `None`; anything else → re-prompt. (`r` is handled by the caller — raise/retry via a dedicated return; simplest: caller passes `retry_input` sentinel — no: keep `confirm_or_edit` returning `b` on confirm, `None` on quit, and the string `"retry"` on `r`.) Signature returns `profile.Baseline | None | str` where the only valid `str` is `"retry"`.

- [ ] **Step 1: Write the failing tests**

```python
# cli/tests/test_onboard_ui.py
from cli import onboard, profile


def test_render_card_only_non_null_lines():
    b = profile.Baseline(
        source="url",
        product_url="https://sentry.io",
        domain="Developer Tools / Observability",
        primary_user="Software engineers",
        business_model=None,
        core_problem=None,
    )
    card = onboard.render_card(b)
    assert "Based on https://sentry.io" in card
    assert "Domain" in card and "Developer Tools" in card
    assert "Users" in card and "Software engineers" in card
    assert "Business" not in card
    assert "Solves" not in card
    assert "[Enter] confirm" in card


def test_ask_typed_defaults_and_skip(monkeypatch):
    answers = iter(["DevTools", "", ""])  # domain, user (empty), focus skip
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    b = onboard.ask_typed()
    assert b.source == "typed"
    assert b.domain == "DevTools"
    assert b.primary_user is None
    assert b.current_focus is None


def test_ask_typed_focus_menu(monkeypatch):
    answers = iter(["FinTech", "Accountants", "2"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    b = onboard.ask_typed()
    assert b.domain == "FinTech"
    assert b.primary_user == "Accountants"
    assert b.current_focus == "activation"


def test_ask_typed_preserves_prefill_product():
    prefill = profile.Baseline(
        product_name="Acme", product_url="https://acme.com", domain="B2B SaaS"
    )
    answers = iter(["", "", ""])
    import builtins

    real_input = builtins.input
    builtins.input = lambda *_: next(answers)
    try:
        b = onboard.ask_typed(prefill)
    finally:
        builtins.input = real_input
    assert b.product_name == "Acme"
    assert b.product_url == "https://acme.com"
    assert b.domain == "B2B SaaS"  # default kept on Enter


def test_confirm_or_edit_confirm_quit_retry():
    b = profile.Baseline(source="url", product_url="https://x.io", domain="B2B SaaS")
    assert onboard.confirm_or_edit(b, input_fn=lambda _: "") == b
    assert onboard.confirm_or_edit(b, input_fn=lambda _: "q") is None
    assert onboard.confirm_or_edit(b, input_fn=lambda _: "r") == "retry"


def test_confirm_or_edit_edits_one_line():
    responses = iter(["e", "1", "FinTech", ""])  # edit, line 1 = domain, new value, confirm
    b = profile.Baseline(source="url", product_url="https://x.io", domain="B2B SaaS")
    result = onboard.confirm_or_edit(b, input_fn=lambda _: next(responses))
    assert result.domain == "FinTech"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory cli pytest tests/test_onboard_ui.py -v`
Expected: FAIL (`ask_typed`/`render_card`/`confirm_or_edit` not defined).

- [ ] **Step 3: Implement the four functions in `cli/src/cli/onboard.py`**

Per Interfaces. `ask_typed` prints each prompt with `typer.echo` and reads with `input()` (no default-argument injection — tests monkeypatch `builtins.input`). Numbered focus menu is printed as `1) launch` … `5) discovery` plus `Enter) skip`; a non-numeric or out-of-range answer re-prompts. `edit_lines` maps displayed line numbers to the field names in the card order (domain, primary_user, business_model, core_problem).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory cli pytest tests/test_onboard_ui.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/src/cli/onboard.py cli/tests/test_onboard_ui.py
git commit -m "feat(cli): confirmation card and typed fallback"
```

---

### Task 5: First-run hook + `setup`/`profile` commands

**Files:**
- Modify: `cli/src/cli/onboard.py` (orchestration)
- Modify: `cli/src/cli/cli.py` (root callback + new `setup_app` registration)
- Create: commands inside `cli/src/cli/profile.py` (`setup_app = typer.Typer(...)`, `profile_app = typer.Typer(...)`)
- Test: `cli/tests/test_onboard_hook.py`, extend `cli/tests/test_cli.py`

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces:
  - `onboard.run_onboarding(*, input_fn=input, fetch_fn=None) -> profile.Baseline | None` — full flow: opening two lines (`Agentic ODI — your ODI/JTBD + PM-skills workspace.` / `Let's set up your context so every skill starts smart.` / `First: what product are you working on?` then reads URL-or-name; empty or `skip` → typed path); URL path: `fetch_signals` (or injected `fetch_fn`) → `infer_baseline` → on `FetchError` print `Couldn't read that site — a few quick questions instead.` → typed; card via `confirm_or_edit`; `"retry"` loops to the URL prompt; `None` (quit) returns `None` without saving; confirm → `profile.save_baseline(b)` and print `Saved to {profile.baseline_file()} — you're set. Try: {cli_name()} outcomes list`. Low confidence still shows the card (inferred values editable); it does **not** auto-jump to typed path.
  - `onboard.maybe_run_first_launch(*, no_onboard: bool = False, invoked_subcommand: str | None = None, input_fn=input, fetch_fn=None) -> None` — returns immediately unless all of: `not no_onboard`, `not profile.baseline_exists()`, stdin & stdout are TTYs (`sys.stdin.isatty() and sys.stdout.isatty()`), env `AGENTIC_ODI_NO_ONBOARD` unset, and `invoked_subcommand not in {"setup", "profile"}` (no `sys.argv` inspection — Click's eager `--version` callback exits before the root body, and the invoked subcommand comes from the Typer context). Non-TTY with missing baseline: print `Run '{cli_name()} setup' to create your PM baseline.` and return. Otherwise call `run_onboarding(input_fn=input_fn, fetch_fn=fetch_fn)`.
  - `cli.py` root callback: new `--no-onboard` flag (`--no-onboard` help: "Skip first-run onboarding"); reads `ctx.invoked_subcommand` via `typer.Context` and calls `onboard.maybe_run_first_launch(no_onboard=no_onboard, invoked_subcommand=ctx.invoked_subcommand)` as the first statement of the body.
  - `profile.setup_cmd()` — always runs onboarding: if a baseline exists, `backup_baseline()` first, then `onboard.run_onboarding()`; quitting without confirm leaves the old baseline in place (backup already made is harmless).
  - `profile.profile_cmd(json_out: bool = typer.Option(False, "--json"))` — when no baseline exists, print `No baseline yet — run '{cli_name()} setup'.` and exit 0; otherwise print `render_card(b)`; with `--json`, print `json.dumps(b.to_dict(), indent=2)` instead.
  - `cli.py` wiring: `app.command("setup")(profile.setup_cmd)` and `app.command("profile")(profile.profile_cmd)` after the existing `add_typer` calls. (Plain functions, not nested Typer apps — keeps the flat `{prog} setup` / `{prog} profile` surface.)

- [ ] **Step 1: Write the failing tests**

```python
# cli/tests/test_onboard_hook.py
from typer.testing import CliRunner

from cli import onboard, profile
from cli.cli import app
from cli.infer import PageSignals


def _cfg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))


def _tty(monkeypatch, yes: bool):
    monkeypatch.setattr("sys.stdin", type("T", (), {"isatty": lambda self: yes})())
    monkeypatch.setattr("sys.stdout", type("T", (), {"isatty": lambda self: yes})())


def _fake_fetch(url, client=None):
    return PageSignals(
        url=url,
        title="Acme",
        meta_description="Team workspace.",
        headings=[],
        body_text="team workspace saas integration workflow",
    )


def test_run_onboarding_url_happy_path(monkeypatch, tmp_path):
    _cfg(monkeypatch, tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: next(iter(["acme.com", ""])))
    b = onboard.run_onboarding(fetch_fn=_fake_fetch)
    assert b is not None
    assert b.source == "url"
    assert b.confidence == "high"
    saved = profile.load_baseline()
    assert saved is not None and saved.product_url == "https://acme.com"


def test_run_onboarding_fetch_failure_falls_back_to_typed(monkeypatch, tmp_path):
    _cfg(monkeypatch, tmp_path)

    def boom(url, client=None):
        raise onboard.FetchError("nope")

    answers = iter(["bad.example", "DevTools", "Engineers", "1", ""])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    b = onboard.run_onboarding(fetch_fn=boom)
    assert b is not None
    assert b.source == "typed"
    assert b.domain == "DevTools"
    assert b.product_url == "https://bad.example"


def test_run_onboarding_quit_saves_nothing(monkeypatch, tmp_path):
    _cfg(monkeypatch, tmp_path)
    answers = iter(["skip", "DevTools", "", "q"])  # typed answers, quit at card
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    b = onboard.run_onboarding(fetch_fn=_fake_fetch)
    assert b is None
    assert not profile.baseline_exists()


def test_maybe_run_skips_when_baseline_exists(monkeypatch, tmp_path):
    _cfg(monkeypatch, tmp_path)
    profile.save_baseline(profile.Baseline(product_name="Done"))
    called = []
    monkeypatch.setattr(onboard, "run_onboarding", lambda **kw: called.append(1))
    _tty(monkeypatch, yes=True)
    onboard.maybe_run_first_launch()
    assert called == []


def test_maybe_run_skips_setup_and_profile(monkeypatch, tmp_path):
    _cfg(monkeypatch, tmp_path)
    called = []
    monkeypatch.setattr(onboard, "run_onboarding", lambda **kw: called.append(1))
    _tty(monkeypatch, yes=True)
    for sub in ("setup", "profile"):
        onboard.maybe_run_first_launch(invoked_subcommand=sub)
    assert called == []


def test_maybe_run_non_tty_prints_hint(monkeypatch, tmp_path, capsys):
    _cfg(monkeypatch, tmp_path)
    _tty(monkeypatch, yes=False)
    onboard.maybe_run_first_launch()
    out = capsys.readouterr().out
    assert "setup" in out
    assert not profile.baseline_exists()


def test_version_flag_never_triggers_onboarding(monkeypatch, tmp_path):
    _cfg(monkeypatch, tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert not profile.baseline_exists()


def test_help_flag_never_triggers_onboarding(monkeypatch, tmp_path):
    _cfg(monkeypatch, tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert not profile.baseline_exists()


def test_profile_command_shows_card_and_json(monkeypatch, tmp_path):
    _cfg(monkeypatch, tmp_path)
    profile.save_baseline(profile.Baseline(source="typed", domain="DevTools", product_name="Acme"))
    runner = CliRunner()
    r1 = runner.invoke(app, ["profile"])
    assert r1.exit_code == 0
    assert "DevTools" in r1.output
    r2 = runner.invoke(app, ["profile", "--json"])
    assert r2.exit_code == 0
    assert '"domain": "DevTools"' in r2.output


def test_profile_command_without_baseline_prints_hint(monkeypatch, tmp_path):
    _cfg(monkeypatch, tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["profile"])
    assert result.exit_code == 0
    assert "setup" in result.output


def test_setup_backs_up_existing_baseline_and_saves_new(monkeypatch, tmp_path):
    _cfg(monkeypatch, tmp_path)
    profile.save_baseline(profile.Baseline(product_name="Old"))
    runner = CliRunner()
    result = runner.invoke(app, ["setup"], input="skip\nFinTech\nOps\n1\n\n")
    assert result.exit_code == 0
    baks = list(profile.config_dir().glob("baseline.json.bak-*"))
    assert len(baks) == 1
    saved = profile.load_baseline()
    assert saved is not None
    assert saved.domain == "FinTech"
    assert saved.product_name is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory cli pytest tests/test_onboard_hook.py -v`
Expected: FAIL (missing orchestration/commands).

- [ ] **Step 3: Implement orchestration, commands, and hook wiring**

Implement `run_onboarding` and `maybe_run_first_launch` in `onboard.py` and `setup_cmd`/`profile_cmd` in `profile.py` exactly per Interfaces; wire in `cli.py`: import `onboard`, `profile`; change the root callback to accept `ctx: typer.Context` and `--no-onboard: bool`; first statement of the body: `onboard.maybe_run_first_launch(no_onboard=no_onboard, invoked_subcommand=ctx.invoked_subcommand)`; register `app.command("setup")(profile.setup_cmd)` and `app.command("profile")(profile.profile_cmd)` after the existing `add_typer` calls. `run_onboarding` accepts `fetch_fn: Callable[[str], Any] | None = None` (defaults to `onboard.fetch_signals`); low-confidence inference still shows the card; `product_name` comes from `infer_baseline` (title-derived) on the URL path and stays `None` on the typed path.

- [ ] **Step 4: Run tests to verify they pass, then the whole suite**

Run: `uv run --directory cli pytest -v`
Expected: ALL PASS (including pre-existing `test_cli.py`, `test_outcomes_cli.py`, `test_connectors_cli.py`).

- [ ] **Step 5: Lint**

Run: `uv run --directory cli ruff check src tests`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add cli/src/cli/onboard.py cli/src/cli/profile.py cli/src/cli/cli.py cli/tests/test_onboard_hook.py cli/tests/test_cli.py
git commit -m "feat(cli): first-run onboarding hook with setup/profile commands"
```
