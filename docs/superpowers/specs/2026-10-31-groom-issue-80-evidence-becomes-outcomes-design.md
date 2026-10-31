# Design: Evidence must become outcomes (#80)

**Source issue:** https://github.com/alehar9320/agentic-odi/issues/80  
**Date:** 2026-10-31  
**Status:** groomed, ready to implement  
**Labels carried over:** `spec`, `opportunity`, `priority/high`, `area/core`, `human-in-the-loop`

---

## 1. Value score: 5 / 5

Mining ingested evidence into scored, approvable outcome proposals **is** the ODI loop and the product's reason to exist. Today a connected source (Gong, Notion, Slack, PostHog) lands as undifferentiated blobs with a single job/step/outcome id stamped on every record. After this issue, connecting a source produces **proposals** — the system reads each record, works out which job and step it belongs to, suggests the desired outcome it implies with importance/satisfaction, shows its reasoning, and asks for approval. Nothing is written to the ODI store without the human's say-so.

**One value increment:** A user connects a source and, for each record containing a real customer struggle, gets a scored candidate outcome in the exact ODI 4-part format (direction + unit + object + clarifier) with a supporting quote, and can approve, edit, or reject it one at a time.

---

## 2. Preconditions / external dependencies

| Dependency | Issue | Notes |
|------------|-------|-------|
| Outcome format + score rules | #83 | The proposal engine must compose statements that pass the shared validator from #83. Do not fork `evaluation.py`. |
| Tool manifest / contract | #84 | Four new MCP tools must be registered in `packages/core/src/agentic_odi_core/contract.py` (`ToolName`, `TOOL_SPECS`, `get_capabilities`). |

These two are open issues outside this batch. Sequence #80 after #83/#84 land, or treat them as preconditions the implementing agent reads first.

---

## 3. Atomic implementation steps

Each step is one testable change. **Write the test first, then make it pass.** Do not skip to the UI before the core engine is tested.

### Step 1 — Core data model: `OutcomeProposal` and `ProposalStatus`

Create `packages/core/src/agentic_odi_core/mapping.py` (in **core**, never connectors) with:

```python
class ProposalStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"

class OutcomeProposal(BaseModel):
    id: str
    evidence_id: str
    job_id: str | None
    step_id: str | None
    statement: str
    direction: Direction
    unit_of_measure: str | None
    object_of_control: str | None
    contextual_clarifier: str | None
    importance: float | None
    satisfaction: float | None
    confidence: float                 # 0.0 - 1.0
    rationale: str                    # why the system thinks this
    quote: str | None                 # exact supporting passage
    source_name: str
    status: ProposalStatus = PROPOSED
    created_at: datetime
```

Export `OutcomeProposal` and `ProposalStatus` from `packages/core/src/agentic_odi_core/__init__.py`.

**Test:** `packages/core/tests/test_mapping.py::test_proposal_model_serializes_and_roundtrips` — construct, dump to JSON, reload, assert all fields equal.

**Definition of done:** Model exists, is exported, round-trips through JSON.

---

### Step 2 — Deterministic proposal strategy (offline, no LLM)

Implement `packages/core/src/agentic_odi_core/mapping.py::HeuristicProposalStrategy` satisfying the protocol:

```python
class ProposalStrategy(Protocol):
    def propose(self, evidence: Evidence, jobs: Sequence[Job], steps: Sequence[Step]) -> OutcomeProposal: ...
```

The default strategy must:

1. **Route to a job:** score each existing job by term overlap between the record's name/content and the job's name/description, weighted by the job's most recent evidence volume. If the top score is below a threshold, propose `job_id=None` and state the record is unmatched — do **not** force a match.
2. **Route to a step** within the job using the shared 8-stage constant; default to the stage whose name shares the most terms with the record; if nothing matches, leave `step_id=None`.
3. **Extract a candidate outcome statement:** find a sentence containing a complaint pattern (`hard`, `slow`, `takes`, `confusing`, `cannot`, `keeps`, `waiting`, `manually`, …) that references an object and a context. Compose into the ODI 4-part format. The composed statement must pass the shared validator from #83 (`evaluate_outcome`); if it cannot be composed validly, no proposal is created and the record is reported as "no candidate outcome found".
4. **Suggest importance and satisfaction** from signals in the record (frequency of the complaint, severity language, presence of a workaround, distinct speakers), mapped to 1–10. These are suggestions with stated confidence, never measurements.
5. **Produce a `rationale`** naming the evidence, the routing decision, and the phrase that triggered extraction.

**Test:** `packages/core/tests/test_mapping.py` covers:
- routing to a job (fixed input → fixed job)
- routing to a step within that job
- statement extraction into the 4-part format
- importance/satisfaction suggestion from a known record
- unmatched record → `job_id=None` and reported as unmatched
- invalid statement → no proposal created

**Definition of done:** Deterministic, requires no network and no LLM; fixed inputs give fixed outputs; fully unit-tested.

---

### Step 3 — Proposal lifecycle on `ODIService`

Add to `packages/core/src/agentic_odi_core/services.py`:

- `propose_outcome_from_evidence(evidence_id: str) -> OutcomeProposal`
- `propose_outcomes_from_batch(evidence_ids: list[str]) -> list[OutcomeProposal]`
- `approve_proposal(proposal_id: str, statement: str | None = None, importance: float | None = None, satisfaction: float | None = None) -> Outcome`
- `reject_proposal(proposal_id: str) -> OutcomeProposal`
- `list_proposals(status: ProposalStatus | None = None) -> list[OutcomeProposal]`

`approve_proposal` must call the **same** `add_outcome` path as any other write, so validation and scoring rules from #83 apply without exception. If the person edits the statement, the edited statement is validated and may be rejected with the reason.

**Test:** `packages/core/tests/test_proposals.py`:
- propose → approve → the outcome exists (and passed `add_outcome` validation)
- propose → reject → nothing was written to the store
- edit on approve → edited statement validated, then written
- re-approve an already-approved proposal is idempotent / rejected cleanly

**Definition of done:** All five service methods exist; approval writes through `add_outcome`; rejection writes nothing.

---

### Step 4 — Persistence: proposals in the repository

Extend the `Repository` protocol, `InMemoryRepository`, and `SQLiteRepository` with:
- `add_proposal`, `get_proposal`, `list_proposals`, `update_proposal`

Add event types `PROPOSAL_CREATED`, `PROPOSAL_UPDATED` in `packages/core/src/agentic_odi_core/sqlite_repository.py:51-112`.

**Constraint:** the evidence record is never mutated by the proposal engine; the evidence is not written as an outcome until approval.

**Test:** `packages/core/tests/test_sqlite_repository.py` — proposals survive a reload (reopen the SQLite file, re-list, assert same proposals).

**Definition of done:** All three repository implementations persist proposals; SQLite is event-sourced; reload preserves proposals.

---

### Step 5 — MCP tools + contract registration

Add to `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` and register in `packages/core/src/agentic_odi_core/contract.py`:
- `propose_outcomes(evidence_ids: list[str]) -> list[OutcomeProposal]`
- `list_proposals(status: str | None = None) -> list[OutcomeProposal]`
- `approve_proposal(proposal_id: str, statement: str | None = None, importance: float | None = None, satisfaction: float | None = None) -> Outcome`
- `reject_proposal(proposal_id: str) -> OutcomeProposal`

**Test:** `apps/mcp-server/tests/test_proposals.py` — the four tools exist and behave as the service methods.

**Definition of done:** Four MCP tools exist, are in `TOOL_SPECS`, and `get_capabilities` describes them.

---

### Step 6 — Studio API routes

Support both backends per `apps/studio-api/src/agentic_odi_studio_api/studio/router.py:51-52`:
- `GET /api/proposals?status=proposed` — list proposals
- `POST /api/proposals/{id}/approve` — approve (optionally with edits)
- `POST /api/proposals/{id}/reject` — reject

**Test:** `apps/studio-api/tests/test_studio_proposals.py` — the three routes under both backends.

**Definition of done:** Routes work under both the in-memory and SQLite backends.

---

### Step 7 — Studio UI: proposal card + typed actions

- Add a `proposal` card type to `apps/studio/src/ui/catalog.ts` and a component in `apps/studio/src/ui/cards.tsx` showing: proposed statement, suggested importance/satisfaction, confidence, rationale, supporting quote; actions **approve**, **edit**, **reject**; card displays the word **"Proposed"** and the confidence.
- Extend `UiAction` (`apps/studio/src/ui/actions.ts:8-12`) with a typed `kind`:
  ```ts
  kind?: "intent" | "approve" | "reject" | "edit";
  target?: string;  // proposal id
  ```
  `approve`/`reject`/`edit` carry a `target` and are dispatched **directly to the API**, not as chat text. `intent` is existing behavior. Backward compatibility: an action with no `kind` is treated as `kind: "intent"`.
- Update `readActions` (`actions.ts:29-51`) to parse and defensively drop malformed entries; `actionList` (`catalog.ts:15-35`) describes the new kinds.
- The `render_ui` server-side validator (`apps/studio-api/src/agentic_odi_studio_api/studio/ui_spec.py:106-155`) must accept actions with no `kind`.

**Tests:**
- `apps/studio/src/ui/protocol.test.ts` — no `kind` → `intent`; `approve` with `target` valid; unknown `kind` dropped.
- `apps/studio/src/ui/UiRenderer.test.tsx` — proposal card renders confidence and rationale.

**Definition of done:** Proposal card exists; typed actions dispatch to API; no-`kind` actions remain `intent`; validator accepts both.

---

### Step 8 — Connector integration (transport only; connectors must NOT depend on core)

- `packages/connectors/src/agentic_odi_connectors/mapping.py` — keep `EvidenceDraft` as a transport shape; add an optional `discriminator` field (stable key of the source record: Gong call id, Notion page id, Slack message ts). Re-ingesting the same source record must not create a second proposal (stable fingerprint).
- `packages/connectors/src/agentic_odi_connectors/mcp/connector.py:161` — support per-tool argument schemas. Extend `McpConnectorSettings` (`models.py:37`) with `tool_args: dict[str, dict]` defaulting to `{}`. Call `client.call_tool(tool_name, tool_args.get(tool_name, {}))`.
- `apps/cli/src/agentic_odi_cli/connectors.py:311-334` — after ingest, if a `--job-id` was supplied, create **proposals** rather than writing outcomes directly. Add `--propose` (default on) and `--apply` (off by default) so the current destructive behavior is opt-in, not opt-out. Add `--tool-args` (JSON string), validated to parse.
- `packages/connectors/src/agentic_odi_connectors/catalog.py` — update preset `summary` strings to state what each preset actually produces; add a `produces` field: `"evidence" | "proposals" | "raw"` per preset.

**Tests:**
- `packages/connectors/tests/test_mcp_connector.py` — `tool_args` are passed to `call_tool`.
- `apps/cli/tests/test_connectors_cli.py` — `ingest` proposes by default; `--apply` writes; `--tool-args` validation error exits non-zero.

**Definition of done:** `discriminator` fingerprint prevents duplicate proposals on re-ingest; `tool_args` supported; `ingest` proposes by default and only writes with `--apply`.

---

### Step 9 — Docs

Correct `docs/connectors.md:66-69` (currently says records are "not written into the ODI jobs/outcomes store" and mapping is "still on the roadmap"). Ensure catalog `summary` strings match what presets actually produce.

Per AGENTS.md README maintenance guardrail: if any documented command/path changes, update `README.md` and `docs/` in the same task.

---

## 4. Non-negotiable constraints

- No outcome is written without an explicit human approval (CLI, Studio, or background agent).
- Proposals are never presented as measurements; confidence and rationale always visible.
- Default proposal strategy is deterministic, offline, unit-testable.
- `packages/connectors` must **not** gain a dependency on `packages/core`. Mapping lives in core; connectors stay a transport.
- The evidence record is never mutated by the proposal engine.
- Do not change the `Evidence` entity's existing fields; only add `discriminator` to `EvidenceDraft`.

---

## 5. Out of scope

- Writing back to external systems ("delegation").
- A UI for bulk reviewing many proposals — v1 reviews one at a time.
- An LLM-backed proposal strategy (protocol allows it later).

---

## 6. Verification

```bash
uv run --directory packages/core pytest
uv run --directory packages/connectors pytest
uv run --directory apps/mcp-server pytest
uv run --directory apps/studio-api pytest
uv run --directory apps/cli pytest
npm --prefix apps/studio test -- --run
npm --prefix apps/studio run typecheck
uv run ruff check . && uv run ruff format --check .
uv run mypy apps packages
```

Tests to add (listed per step above):
- `packages/core/tests/test_mapping.py`
- `packages/core/tests/test_proposals.py`
- `packages/core/tests/test_sqlite_repository.py`
- `packages/connectors/tests/test_mcp_connector.py`
- `apps/mcp-server/tests/test_proposals.py`
- `apps/studio-api/tests/test_studio_proposals.py`
- `apps/cli/tests/test_connectors_cli.py`
- `apps/studio/src/ui/protocol.test.ts`
- `apps/studio/src/ui/UiRenderer.test.tsx`

## Context an implementing agent must read

- `packages/connectors/src/agentic_odi_connectors/mapping.py:1-68` — current 1:1 copy.
- `packages/connectors/src/agentic_odi_connectors/models.py:1-66` — `EvidenceDraft`, `McpConnectorSettings`.
- `packages/connectors/src/agentic_odi_connectors/mcp/connector.py:115-176` — ingest path and the `{}` tool-call bug.
- `packages/connectors/src/agentic_odi_connectors/sink.py:1-31` — in-process sink (lost on exit).
- `packages/connectors/src/agentic_odi_connectors/catalog.py:51-71, :236` — `ConnectorPreset`, `list_presets()`.
- `apps/cli/src/agentic_odi_cli/connectors.py:311-334` — only current persistence path for ingested records.
- `packages/core/src/agentic_odi_core/services.py:223-320` — `add_evidence` and `promote_evidence`.
- `packages/core/src/agentic_odi_core/models.py:99-116` — `Evidence` entity.
- `packages/core/src/agentic_odi_core/evaluation.py:1-64` — existing statement evaluator (#83 turns it into the shared validator; reuse it).
- `apps/studio/src/ui/actions.ts:1-51` — current one-directional action model.
- `apps/studio/src/ui/catalog.ts:15-35, :54-57` — how actions and card props are declared.
- `apps/studio-api/src/agentic_odi_studio_api/studio/ui_spec.py:61-155` — server-side `render_ui` schema/validator.
- `packages/core/src/agentic_odi_core/contract.py:14-142` — tool contract.
- `apps/studio-api/src/agentic_odi_studio_api/studio/router.py:51-67` — dual-backend pattern.
- `docs/connectors.md:66-69` — stale documentation to correct.

## Open question for the human

None — #83 and #84 are external preconditions; note them as sequencing gates, not blockers on writing the spec.
