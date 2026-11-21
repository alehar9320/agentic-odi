# Design: The agent must ask before it acts (#82)

**Source issue:** https://github.com/alehar9320/agentic-odi/issues/82  
**Date:** 2026-10-31  
**Status:** groomed, ready to implement  
**Labels carried over:** `spec`, `opportunity`, `priority/high`, `area/studio`, `area/core`, `anti-fabrication`, `human-in-the-loop`

---

## 1. Value score: 5 / 5

The human-in-the-loop premise. Today the agent can only call MCP tools immediately and invisibly — there is no approval concept, no denial, no receipt, and no audit trail. After this issue, the agent **proposes an action, waits for a yes or no, adjusts it, and leaves a receipt.** You stay in the loop; the loop is designed, not accidental.

**One value increment:** The agent finds candidate outcomes and renders a card saying "I found 3 candidate outcomes — approve all, or open them one at a time." The user approves two, edits one, rejects one; the rejections are recorded and the agent writes nothing the user did not approve. Every tool call produces an `Execution` receipt visible in a Receipts list.

---

## 2. Preconditions / external dependencies

| Dependency | Issue | Notes |
|------------|-------|-------|
| Durable sessions / real memory (audit substrate) | #81 | Open issue, outside this batch. `Proposal`/`Execution` persistence is the substrate #81's conversation storage builds on. |
| Evidence proposals (#80) | #80 | Name collision on `approve_proposal`: **reconcile into one `Proposal` entity with a `kind` discriminator** (preferred). Whoever lands first owns the entity; the other extends it. Document the choice in code. |
| `request_id` propagation / structured logging | #91 | Open issue; `Execution.request_id` must also appear in the server log line and SSE event. |

#81 is not in this batch. Sequence #82 after #81, or treat durable-session storage as a precondition.

---

## 3. Atomic implementation steps

### Step 1 — Core data model: `Proposal`, `Execution`, `Mandate`

Add to `packages/core/src/agentic_odi_core/models.py`:

```python
class ProposalKind(StrEnum):
    TOOL_CALL = "tool_call"
    BATCH = "batch"
    OUTCOME = "outcome"
    MANDATE = "mandate"


class ProposalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EDITED = "edited"
    EXECUTED = "executed"
    FAILED = "failed"
    EXPIRED = "expired"


class Proposal(BaseModel):
    id: str
    kind: ProposalKind
    title: str  # one line, human-readable
    rationale: str  # why the agent wants this
    tool_name: str | None = None
    tool_args: dict = {}
    payload: dict = {}  # structured payload for non-tool proposals
    state: ProposalState = ProposalState.PENDING
    requires_approval: bool = True
    expires_at: datetime | None = None
    created_at: datetime
    decided_at: datetime | None = None
    decided_by: str | None = None  # e.g. "local-user"
    execution_id: str | None = None


class Execution(BaseModel):
    id: str
    proposal_id: str | None
    actor: str  # "agent" | "local-user" | "mandate:<id>"
    request_id: str
    tool_name: str | None
    tool_args: dict
    result_summary: str
    ok: bool
    started_at: datetime
    finished_at: datetime
    error: str | None = None


class Mandate(BaseModel):
    id: str
    name: str
    allowed_tools: list[str]
    allowed_scope: dict  # e.g. {"connector": "github"}
    max_executions: int  # default 50
    executions_used: int = 0
    expires_at: datetime
    created_at: datetime
```

`Execution` is the receipt — the answer to "what did the agent actually do?" Export all five from `packages/core/src/agentic_odi_core/__init__.py`.

**Test:** `packages/core/tests/test_proposals.py::test_proposal_execution_mandate_roundtrip` — construct each, dump/reload via JSON, assert fields equal.

**Definition of done:** All models exist, are exported, round-trip through JSON.

---

### Step 2 — Persistence: proposals and executions in the repository

Extend the `Repository` protocol, `InMemoryRepository`, and `SQLiteRepository` with:
- `add_proposal`, `get_proposal`, `list_proposals`, `update_proposal`
- `add_execution`, `list_executions`

Add event types `PROPOSAL_CREATED`, `PROPOSAL_DECIDED`, `EXECUTION_RECORDED` in `packages/core/src/agentic_odi_core/sqlite_repository.py:51-112`.

**Constraint:** the audit trail is append-only. A decided proposal and a recorded execution are never updated or deleted. `deny` and `approve` append a new event; they never overwrite. Every `Execution` carries a `request_id`.

Add `ODIService.record_execution(...) -> Execution` and `ODIService.list_executions(...)` in `packages/core/src/agentic_odi_core/services.py`.

**Test:** `packages/core/tests/test_proposals.py` — create, approve, deny, edit; append-only audit (a decided proposal cannot be mutated); execution recorded.

**Definition of done:** All three repository implementations persist proposals and executions; append-only audit enforced; reload preserves them.

---

### Step 3 — Reconcile with #80: one `Proposal` entity with `kind` discriminator

#80 defines `OutcomeProposal` with `ProposalStatus` {PROPOSED, APPROVED, REJECTED, EDITED}. #82 defines `Proposal` with `ProposalKind` and `ProposalState` {PENDING, APPROVED, DENIED, EDITED, EXECUTED, FAILED, EXPIRED}.

**Decision:** one entity. `Proposal` absorbs #80's fields:
- `kind: ProposalKind` — `OUTCOME` for #80 evidence proposals, `TOOL_CALL`/`BATCH`/`MANDATE` for #82.
- `state` subsumes `status`: PENDING → APPROVED/DENIED/EDITED/EXECUTED/FAILED/EXPIRED.
- Add #80-specific optional fields to `Proposal`: `evidence_id`, `job_id`, `step_id`, `statement`, `direction`, `unit_of_measure`, `object_of_control`, `contextual_clarifier`, `importance`, `satisfaction`, `confidence`, `rationale`, `quote`, `source_name`.

#80's `approve_proposal(evidence_id …)` and #82's `approve_proposal(proposal_id …)` become one `approve_proposal(proposal_id, edited_args=None)` that branches on `kind`. Document the choice in code with a comment.

**Test:** `packages/core/tests/test_proposals.py` — an `OUTCOME`-kind proposal approves through the same path as #80's `add_outcome`; a `TOOL_CALL`-kind proposal executes a tool; both appear in one `list_proposals`.

**Definition of done:** One `Proposal` entity; `kind` discriminator distinguishes evidence proposals from action proposals; no duplicate `approve_proposal` names.

---

### Step 4 — Consent gate in the agent loop

Restructure `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py:235-373` (`stream_chat` tool dispatch):

1. The model calls a tool.
2. The sidecar decides whether the call needs approval, using a policy (Step 5).
3. If approval is needed, the sidecar does **not** execute. It creates a `Proposal` in `PENDING`, emits a `proposal` SSE event, and tells the model: "This action needs the PM's approval. It is now waiting as proposal <id>." The model continues and the reply explains what is pending.
4. The person approves from the UI. The sidecar executes the tool, records an `Execution`, emits an `execution` SSE event, and the transcript shows the receipt.
5. If the person denies, the sidecar records the denial, and the model is told: "Proposal <id> was declined. Do not retry it."

**Test:** `apps/studio-api/tests/test_studio_consent.py`:
- a mutating tool call creates a proposal and does not execute
- a read-only tool executes immediately
- approval executes and records an `Execution`
- denial does not execute and the model is told not to retry

**Definition of done:** The agent loop creates a pending proposal instead of executing mutating tool calls; approval executes + records; denial records and stops.

---

### Step 5 — Consent policy module

Create `apps/studio-api/src/agentic_odi_studio_api/studio/consent.py`:

```python
DEFAULT_AUTO_APPROVE_TOOLS = frozenset(
    {
        "get_jobs",
        "get_job",
        "get_job_map",
        "get_step",
        "get_outcomes",
        "get_outcome",
        "get_customer_outcome",
        "list_customer_outcomes",
        "list_evidence",
        "get_evidence",
        "compute_opportunity",
        "evaluate_outcome",
        "get_odi_schema",
        "get_odi_framework_guidelines",
        "get_capabilities",
    }
)
```

- Read-only tools are auto-approved. Derive the set from `packages/core/src/agentic_odi_core/contract.py` — any tool whose name starts with `get_`/`list_`/`compute_`/`evaluate_` is read-only. The explicit set pins the decision and makes it testable.
- Every mutating tool (`add_*`, `update_*`, `delete_*`, `promote_*`, `add_connector`) requires approval by default. `render_ui` is auto-approved (it renders, does not mutate).
- The policy is configurable: `AGENTIC_ODI_AUTO_APPROVE` accepts a comma-separated tool list auto-approved **in addition** to the read-only set; default empty.
- A standing mandate overrides the gate for the tools it names, within scope and expiry. Mandates are themselves proposals: creating one requires approval. A mandate may **never** authorize `delete_*` on a Job, Step, Outcome, CustomerOutcome, or the whole store — deletion always asks, every time (hard constraint).

**Test:** `apps/studio-api/tests/test_studio_consent.py` — auto-approve set derived from contract, contains only read-only tools; overridable via env var; `render_ui` auto-approved; `delete_*` never covered by a mandate.

**Definition of done:** Policy module exists; read-only set derived from contract; mutating tools require approval by default; mandates exclude destructive deletion.

---

### Step 6 — MCP tools + contract registration

Add to `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` and register in `packages/core/src/agentic_odi_core/contract.py`:
- `list_proposals(state: str | None = None)`
- `approve_proposal(proposal_id: str, edited_args: dict | None = None) -> Execution`
- `deny_proposal(proposal_id: str)`
- `list_executions(limit: int = 50)`

**Test:** `apps/mcp-server/tests/test_proposals.py` (shared with #80, extended) — the four tools.

**Definition of done:** Tools exist, are in `TOOL_SPECS`, `get_capabilities` describes them.

---

### Step 7 — Studio API routes

Support both backends per `router.py:51-52`:
- `GET /api/proposals?state=pending` — list proposals
- `GET /api/proposals/{id}` — one proposal
- `POST /api/proposals/{id}/approve` — approve → execute → return the `Execution`
- `POST /api/proposals/{id}/deny` — deny
- `POST /api/proposals/{id}/edit` — edit payload, then approve
- `GET /api/executions?limit=50` — receipts list
- `GET /api/executions/{id}` — one receipt

**Test:** `apps/studio-api/tests/test_studio_proposals.py` (shared with #80, extended) — routes under both backends.

**Definition of done:** All seven routes work under both backends.

---

### Step 8 — Studio UI: proposal card + typed actions + receipts panel

- Add a `proposal` card type to `apps/studio/src/ui/catalog.ts` and `cards.tsx` rendering: title, rationale, payload preview, actions `approve` / `deny` / `edit` / `open`.
- Extend `UiAction` (`apps/studio/src/ui/actions.ts:8-12`):
  ```ts
  export interface UiAction {
    label: string;
    intent?: string;
    kind?: "intent" | "approve" | "deny" | "edit";
    target?: string;
    tone?: "primary" | "ghost";
  }
  ```
  `kind` defaults to `"intent"` when absent (backward compatibility). Coordinate with #80: the union is `{intent, approve, reject, deny, edit}`. Prefer a single shared definition; if #80 lands first, extend its `kind` union.
- `approve`/`deny`/`edit` dispatch **directly to the API**, not as chat text. `ActionRow` in `apps/studio/src/ui/primitives.tsx:21-42` branches on `kind`. The action dispatcher is provided by `Conversation.tsx:142`.
- Accessibility: approval buttons keyboard-reachable, accessible name includes what is being approved (`aria-label="Approve: Minimize the time it takes to rotate a production secret"`), pending state announced (`aria-live="polite"` on the proposal region).
- New `ReceiptsPanel` (`apps/studio/src/components/workspace/ReceiptsPanel.test.tsx`) rendering executions, filterable by actor, added to `WorkbenchRail.tsx`.

**Tests:**
- `apps/studio/src/ui/protocol.test.ts` — extended action kinds validate; unknown kind dropped; missing `kind` defaults to `intent`.
- `apps/studio/src/ui/UiRenderer.test.tsx` — proposal card renders; buttons dispatch to API, not `sendMessage`.
- `apps/studio/src/components/workspace/ReceiptsPanel.test.tsx` — receipts list renders executions and filters by actor.

**Definition of done:** Proposal card exists; typed actions dispatch to API; no-`kind` remains `intent`; accessible names + live announcement; receipts panel renders and filters.

---

### Step 9 — Studio system prompt (anti-fabrication)

Update `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py:28-38` (`SYSTEM_PROMPT`) to add:

```
11. You do not have the PM's permission to change their work unless they gave it.
    When a tool call needs approval, it becomes a proposal: explain in one sentence
    what it would do and why, and let the PM decide. Never claim something was
    saved, imported, connected, or deleted unless the tool actually returned success.
```

That last clause is the anti-fabrication rule — the single most important line in the prompt.

**Definition of done:** Prompt contains the consent + anti-fabrication clause.

---

## 4. Non-negotiable constraints

- No mutating tool call executes without either an explicit approval or a valid mandate.
- The audit trail is append-only (decided proposals and executions never mutated).
- A denied proposal is never retried automatically.
- Every mutating MCP tool requires approval by default; the auto-approve list is read-only tools plus an explicit, empty, configurable override.
- Mandates never authorize destructive deletion.
- An `Execution` is recorded for **every** tool call, including auto-approved read-only ones (read-only executions may be sampled for storage but must be countable).
- The consent gate must work when the person is not looking: an unanswered proposal stays `PENDING` and is never auto-approved by a timeout.

---

## 5. Out of scope

- Background agents acting on mandates → #95 builds on this.
- A full "undo" of an executed action → the audit trail is the prerequisite; undo is a later issue.
- Delegated consent (one person approving for another) → single-user local product for now.

---

## 6. Verification

```bash
uv run --directory packages/core pytest
uv run --directory apps/mcp-server pytest
uv run --directory apps/studio-api pytest
npm --prefix apps/studio test -- --run
npm --prefix apps/studio run typecheck && npm --prefix apps/studio run lint
uv run --directory packages/core mypy .
uv run --directory apps/studio-api mypy .
uv run ruff check . && uv run ruff format --check .
```

Tests to add:
- `packages/core/tests/test_proposals.py` — create, approve, deny, edit, append-only audit, execution recording
- `packages/core/tests/test_mandates.py` — scope enforcement, expiry, execution cap, revocation, `delete_*` never covered
- `apps/studio-api/tests/test_studio_consent.py` — mutating tool → proposal, no execute; read-only → immediate; approval executes + records; denial does not execute
- `apps/studio/src/ui/protocol.test.ts` — extended action kinds; unknown kind dropped; missing kind → `intent`
- `apps/studio/src/ui/UiRenderer.test.tsx` — proposal card; buttons dispatch to API
- `apps/studio/src/components/workspace/ReceiptsPanel.test.tsx` — receipts list; filter by actor

## Context an implementing agent must read

- `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py` — whole loop: `:26` `MAX_TOOL_ROUNDS`, `:28-38` `SYSTEM_PROMPT`, `:115-116` `_sse`, `:127-212` tool set + two local tools, `:235-373` `stream_chat`, `:313-367` dispatcher, `:354-358` error swallowing
- `apps/studio/src/ui/actions.ts:1-51` — action model + `readActions`; defensive-parsing pattern
- `apps/studio/src/ui/catalog.ts:15-35, :54-57` — action schema + implicit `actions` prop
- `apps/studio/src/ui/primitives.tsx:21-42` — `ActionRow` (must branch on `kind`)
- `apps/studio/src/components/chat/Conversation.tsx:142` — dispatcher provision
- `apps/studio-api/src/agentic_odi_studio_api/studio/ui_spec.py:61-155` — server-side action schema/validator
- `packages/core/src/agentic_odi_core/contract.py:14-142` — tool contract (auto-approve set derived here)
- `packages/core/src/agentic_odi_core/models.py:12-131` — entity style
- `packages/core/src/agentic_odi_core/services.py:68-320` — service style
- `packages/core/src/agentic_odi_core/sqlite_repository.py:18-112` — event substrate
- `apps/studio-api/src/agentic_odi_studio_api/studio/router.py:51-67` — dual-backend pattern
- `apps/studio/src/state/StudioContext.tsx:717-782` — SSE dispatcher (new events handled here)
- `apps/studio/src/api/sse.ts:10-46` — parser
- `apps/studio/src/components/workspace/WorkbenchRail.tsx` — where Receipts panel is added
- #80 — sibling issue owning evidence proposals; reconcile before coding
- #91 — sibling issue owning `request_id` propagation and structured logging

## Open question for the human

#81 (durable sessions) is a dependency outside this batch. Confirm whether to sequence #82 after #81, or whether the proposal/execution storage can stand alone and #81 layers on top later.
