# Design: The local model must be real (#94)

**Source issue:** https://github.com/alehar9320/agentic-odi/issues/94  
**Date:** 2026-10-31  
**Status:** groomed, ready to implement (amended 2026-10-31 — see below)  
**Labels carried over:** `spec`, `opportunity`, `priority/medium`, `area/studio`, `area/core`, `anti-fabrication`, `jules`

---

## 1. Value score: 4 / 5

The "no model? no problem" brand promise. Today `OnDeviceLLMEngine.is_available()` returns `True` unconditionally with no model installed — the tier claims availability it doesn't have, and its output fabricates a hardcoded "Opportunity Score of 15.3." After this issue, the Studio degrades honestly: remote model → locally-served model → deterministic tier, never lies about which one answered, never fabricates scores, and tells the user which tier answered.

**One value increment:** With no model reachable, the Studio says so and still lets the user capture outcomes and read the job map (deterministic tier, honest about what it can and cannot do). With a local model server running, it uses it and badges "Local model." If a model call fails mid-answer, it demotes to the next tier and says so visibly. No tier invents a number.

---

## 2. Preconditions / external dependencies

| Dependency | Issue | Notes |
|------------|-------|-------|
| Scoring rules the fallback must not bypass | #83 | The deterministic tier must not compute an opportunity score; it points at `compute_opportunity`. |

## 2026-10-31 spec amendments (binding)

Reviewed against `main` (@ `ece6529`):
- **`router.py` is already on `main`**, not just on PR #65's branch. `OnDeviceLLMEngine` (`:33`), `is_available() -> True` (`:39-41`), `generate_stream` delegating to `generate_steve_jobs_response` (`:45-52`), `ModelRouter` (`:55+`), `resolve_tier` (`:70-85`). Exported from `agentic_odi_core/__init__.py`; test `packages/core/tests/test_router.py:62-64` asserts `is_available() is True` — **this test pins the bug in place and must be rewritten with the fix.**
- **Tier-2 unreachability confirmed:** `remote_health_checker` is an injected `Callable` with no caller supplying it, so `remote_available` is always `False` in production.
- **This issue fixes shipped code; the salvage is done.** Do not re-specify the salvage. Rewrite the problem statement against `main`.
- **Choose Option B** (honest local OpenAI-compatible client, no bundled model) for this issue; file Option A (real engine + model lifecycle) separately. Option B is smaller, honest, and sufficient for this milestone.
- Make `offline_fallback` the single Tier-0 implementation; `steve_jobs.py` either deleted or a thin wrapper.
- Keep the runtime-demotion requirement (no resolve-once) — that's what users feel.
- Rewrite `docs/local-llm.md` §6 to match, in the same PR (README/doc guardrail).

---

## 3. Atomic implementation steps

### Step 1 — Three honest tiers in `router.py`

Rewrite `packages/core/src/agentic_odi_core/router.py` so the tiers are:

| Tier | Name | What it is | Availability probe |
|------|------|------------|-------------------|
| 0 | `deterministic` | Existing rule-based responder, honestly named. No LLM. | Always available |
| 1 | `local` | Honest OpenAI-compatible client for a local model server you run yourself | Probe actually connects + lists models (2 s timeout, 30 s TTL cache) |
| 2 | `remote` | Configured OpenAI-compatible endpoint | Existing `check_llm_health` probe |

**Status:** IMPLEMENTED (PR in progress)

Rename `OnDeviceLLMEngine` → `LocalOpenAIEngine` (Option B: a client, not a bundled engine). Done: `LocalOpenAIEngine` probes the endpoint with a 2s timeout and 30s TTL cache; returns `False` when nothing answers.

**Test:** `packages/core/tests/test_router.py`:
- `is_available()` returns `False` when the endpoint is unreachable (rewrite the test that currently asserts `True`)
- the TTL caches the probe (probe not run on every turn)
- the engine reports the endpoint and model id it's talking to

**Definition of done:** Three tiers named `deterministic`, `local`, `remote`; class is not `OnDeviceLLMEngine` unless it genuinely runs a model; probe is real with timeout + TTL; returns `False` when nothing answers.

---

### Step 2 — Delete fabrication from Tier 0

Rewrite `steve_jobs.py` (or make it a thin wrapper) so Tier 0:
- Deletes the hardcoded "Opportunity Score of 15.3."
- Deletes the score parser (`re.findall(r"\b([0-9]|10)(?:\.0)?\b", …)` dropping decimals). Tier 0 does not compute an opportunity score; it points at `compute_opportunity` and asks for the numbers.
- Every response is a list of things the person can actually do (tool names and surfaces), never a fabricated answer.
- `offline_fallback` in `chat.py:64-112` is the reference implementation ("Deterministic, honest guidance when no LLM backend is reachable. No fabricated customer data, no invented scores."). Tier 0 reuses it — one implementation, not two. Either `steve_jobs.py` calls `offline_fallback`, or it's deleted.

**Test:** `packages/core/tests/test_deterministic.py` (new) — the deterministic tier's output contains no numbers that did not come from the input; there is no hardcoded score.

**Definition of done:** No hardcoded score, no score parser, Tier 0 reuses `offline_fallback`, no fabricated numbers.

---

### Step 3 — Runtime demotion, not resolve-once

`ModelRouter` must demote at runtime:
- If a tier fails mid-stream, the router retries on the next tier and reports the demotion. The turn is not lost.
- The demotion is reported to the person: "The remote model stopped responding. I continued with the local one." — as a visible line in the transcript, not a silent substitution.
- A demotion is recorded in the turn's structured log line (#91) and in the `Execution` record (#82).
- The router must not demote mid-message in a way that corrupts a partial answer; a tier switch produces two visible messages, not one spliced one.
- `RoutingMode.FORCE_ON_DEVICE` and `FORCE_REMOTE` are selectable and persisted; a forced mode that fails must say so and not silently fall back.

**Test:** `packages/core/tests/test_router.py` — a tier failure demotes; a forced mode does not demote (it fails and says so).

**Definition of done:** Runtime demotion works; demotion visible in transcript; forced modes fail loudly; no silent fallback.

---

### Step 4 — Routing mode selectable and persisted

The routing mode (auto / local / remote) is selectable in the Studio's Settings, persisted server-side (#81's settings entity, or the CLI's `llm_profile.json` at `~/.config/agentic-odi/`), and honored by the CLI too.

- `apps/cli/src/agentic_odi_cli/profile.py` — `LLMProfile` and atomic XDG save/load already exist; persist the routing mode there.
- `apps/cli/src/agentic_odi_cli/chat.py:28-37` — the CLI's chat uses the same router and same fallback as the Studio.
- CLI `/status` command reports the tier in use.

**Test:** `apps/cli/tests/test_chat_runtime.py` — the CLI reports the tier in `/status` and uses the same fallback.

**Definition of done:** Routing mode selectable in Settings + CLI; persisted; CLI `/status` reports tier; CLI and Studio share router + fallback.

---

### Step 5 — Studio shows which tier answered

- A quiet indicator (top bar or next to the composer) shows the tier in use: Local / Remote / Offline (no model). Real `aria-label`; state change announced (#92).
- `apps/studio/src/components/SettingsPanel.tsx` — a Model section: current tier, configured endpoint, model id, routing mode, and a **Test connection** button that runs the probe and reports the result.
- `apps/studio/src/components/chat/OfflineNotice.tsx` — when there is no model at all, the notice is the honest one from `chat.py:64-112` and links to the settings that would fix it.

**Test:** `apps/studio/src/components/SettingsPanel.test.tsx` — Model section and Test connection button; probe result reported.

**Definition of done:** Tier indicator visible with accessible label; Settings Model section works; Test connection runs the probe; OfflineNotice honest and links to settings.

---

### Step 6 — Documentation: `docs/local-llm.md` §6

Rewrite §6 to describe only what exists:
- "The local tier is used only when a local model server answers. The Studio does not bundle a model."
- State availability probe behavior.
- Say what happens with no model: the deterministic tier, exactly what it can and cannot do.
- Remove claims about a Settings UI and config file unless they now exist (they do, from Step 4).

Every claim in the file is checked against the code.

**Definition of done:** `docs/local-llm.md` describes only implemented behavior; no fabricated claims.

---

## 4. Non-negotiable constraints

- No tier may fabricate a number, a score, a quote, or a customer name.
- `is_available()` is a probe, never an unconditional `True`.
- The router demotes at runtime and reports the demotion visibly.
- The routing mode is selectable and persisted.
- `docs/local-llm.md` describes only what exists; every claim checked against code.
- The CLI and Studio use the same router and the same fallback.
- Tier 0 and `offline_fallback` are one implementation, not two.

---

## 5. Out of scope

- Fine-tuning, model evaluation, or a benchmark suite.
- Provider-specific adapters beyond OpenAI-compatible.
- Streaming token-by-token on the local tier if the server doesn't support it — a non-streaming local tier returning a complete message is acceptable and labeled.
- Option A (bundled model + model lifecycle: warmup, memory budget, context window) — file as a separate follow-up issue.

---

## 6. Verification

```bash
uv run --directory packages/core pytest
uv run --directory apps/studio-api pytest
uv run --directory apps/cli pytest
npm --prefix apps/studio test -- --run
uv run --directory packages/core mypy .

# With no model reachable:
AGENTIC_ODI_BASE_URL=http://127.0.0.1:9/v1 uv run python -m agentic_odi_cli chat
# must report the deterministic tier and fabricate nothing
```

Tests to add:
- `packages/core/tests/test_router.py` — probe returns `False` when unreachable; TTL caches probe; tier failure demotes; forced mode does not demote
- `packages/core/tests/test_deterministic.py` (new) — no fabricated numbers; no hardcoded score
- `apps/studio-api/tests/test_studio_model_router.py` — tier reported in response; demotion message emitted; indicator payload correct
- `apps/cli/tests/test_chat_runtime.py` — `/status` reports tier; same fallback as Studio
- `apps/studio/src/components/SettingsPanel.test.tsx` — Model section + Test connection button

## Context an implementing agent must read

- `packages/core/src/agentic_odi_core/router.py` and `steve_jobs.py` — as they exist on `main` (`ece6529`): `:33`, `:39-41`, `:45`, `:70-85`, whole of `steve_jobs.py`
- `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py:64-112` — `offline_fallback`, the reference Tier-0 implementation
- `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py:28-38` — Studio system prompt
- `apps/studio-api/src/agentic_odi_studio_api/studio/probes.py:81-92` — `check_llm_health`, the probe to copy
- `apps/cli/src/agentic_odi_cli/chat.py:28-37` — CLI prompt; `:62-104` — `ChatConfig.from_env` resolution order
- `apps/cli/src/agentic_odi_cli/profile.py` — `LLMProfile`, atomic XDG save/load (persistence pattern)
- `apps/studio/src/components/SettingsPanel.tsx` — Model section goes here
- `apps/studio/src/components/chat/OfflineNotice.tsx` — offline surface
- `docs/local-llm.md` — §6 must become true
- `packages/core/src/agentic_odi_core/models.py:28-30` — the one opportunity-score formula Tier 0 may point at
- #78 — truthfulness rules the deterministic tier must obey
- #83 — scoring rules the fallback must not bypass
- #87 — the salvage this issue supersedes (already done)

## Open question for the human

None beyond the recorded decision (Option B). The spec is self-contained against `main`.
