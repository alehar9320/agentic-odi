# Architecture critique — design

Dated record of a review of the repository's architecture: what is sound, what is
at risk, and what the cheapest honest response is to each. It is a review, not a
refactor: the only code it changed is the boundary test in Finding 1.

## Intent

Two questions were asked:

1. Where would a principal engineer spend the next quarter, looking at this from
   the outside?
2. How does a maintainer see the whole system at once, and keep seeing it as it
   changes?

The second question turned out to be a case study for the first. While answering
it I found a dependency edge that existed in the code, in no diagram, in no
declaration, and in no test.

## What was checked, and how

Everything below was read in the tree at this commit, not inferred from the
docs. Four earlier claims from a summary I was handed turned out to be wrong or
overstated, and are corrected here — most visibly Finding 4, where a typed error
taxonomy *does* exist. Line numbers are as of this writing; they are the
investigation's trail, not a stable API.

Read: `docs/architecture/` (all twelve documents), `.agents/rules/agent_instructions.md`,
`packages/core` services, models, `consent.py`, `errors.py`, `remote.py`,
`factory.py`, `contract.py`; `apps/mcp-server` tool layer; `apps/studio-api`
chat loop, approvals, memory, errors, observability; `packages/connectors`
mapping and models; `apps/cli` chat and backends; `scripts/` parity, doc check,
PR guards; the CI workflows and the website build.

## The verdict

The design is coherent and the documentation is better than most production
codebases I would review. Boundaries are drawn correctly — core at the bottom,
three surfaces above it, connectors as the only door in — and the reasoning
behind each is written down.

The systemic risk is not the design. It is that **almost every guarantee in
`docs/architecture/` is a sentence rather than a check.** The MCP tool contract
is the exception, and it is enforced in three places; nothing else gets the same
treatment. Where a promise is only written down, the drift is invisible until
someone relies on it.

The second risk is concentration: several of the strongest claims — consent
before writes, one error shape, observability — are true of the Studio sidecar
and not true of the system. They are properties of one client, documented as
though they were properties of the domain.

For a project that calls itself an experimental feasibility test, the
recommendation is not a rewrite. It is to *promote the decisions that have
already been made into checks*, and to stop describing aspirational guarantees
in the present tense. Roughly 150 lines of tests and four ADRs buy back most of
that.

## Findings

### 1. The package boundary existed only in prose — and one edge had already escaped

**Evidence.** `apps/studio-api` imports `agentic_odi_connectors` at module level
in five files (`studio/router.py:13-16`, `studio/connectors.py:15-23`,
`studio/marketplace.py:11-19`, `studio/schemas.py:12`). It was not in
`apps/studio-api/pyproject.toml`'s `dependencies`, and it appears in no diagram.
The edge resolved only because `uv sync --all-packages` installs every workspace
member into one virtualenv; a per-package build would `ImportError`. Meanwhile
`docs/architecture/README.md` stated that `packages/connectors` "depends on
`core` only where it needs shared models" — `packages/connectors` imports nothing
from core at all. So the one written-down boundary rule was wrong in both
directions at once.

**Why it matters.** This is the failure mode the diagram question was really
about: not that the picture was ugly, but that the picture and the code could
disagree silently. The same drift would have hidden a cycle, an app importing an
app, or core reaching upward.

**Cheapest fix.** Make the diagram a check.

**Call — done in this task.** `tests/test_architecture.py` now asserts that the
mermaid diagram in `docs/architecture/README.md`'s Dependency Direction section,
the `[project] dependencies` each member declares, and the cross-package imports
`grimp` finds in the source are all the *same set*, in both directions. It also
asserts the two rules the docs already claim: core imports no workspace package,
and no app imports another app. Six tests, 0.03s. Verified by injecting an
undeclared import, a declared-but-unused dependency, and an extra arrow — each
failed with the edge and the file named. The missing declaration is now added,
the false sentence in the docs is corrected, and the rule is recorded in
`.agents/rules/agent_instructions.md`.

### 2. Consent is a domain rule that only one client enforces

**Evidence.** Core *does* model this: `packages/core/src/agentic_odi_core/consent.py`
defines `ConsentGate`, `READ_ONLY_TOOLS`/`ACTING_TOOLS`, and raises
`ConsentRequired` (`consent.py:88`, mapped to HTTP 403 at `errors.py:75`). It is
dead code in production: the only reference to it outside its own module is
`packages/core/tests/test_consent_pause.py`. Nothing in `services.py`,
`mcp_server.py`, or `chat.py` imports it.

The enforcement that *does* exist is in the sidecar's chat loop
(`apps/studio-api/.../studio/approvals.py`, opened at `chat.py:779-790`), and it
decides whether a call is a write with a **name-prefix heuristic plus a
hand-maintained set** (`chat.py:65-89`) rather than from `TOOL_SPECS`. The domain
itself writes without asking: `ODIService.add_job` goes straight to the repository
(`services.py:278`), the MCP server calls `service.*` with no consent path
(`mcp_server.py:106`, `:369`, `:453`), and the CLI's own agent loop calls any tool
the model names (`apps/cli/src/agentic_odi_cli/chat.py:373`).

The docs are honest about this — `consent.md:61-65` says the gate exists but the
loop does not use it, `:76-79` says contract-classified writes such as
`schedule_work`, `trigger_scheduled_work`, and `cancel_scheduled_work` slip past
the prefix check, and `:80-83` says CLI writes do not prompt. That honesty is why
this is a finding about *placement*, not about a hidden hole.

**Why it matters.** "The agent asks before it writes" is the product's central
safety claim. Today it is a property of one surface's UX. The heuristic also
drifts from the contract as tools are added — the three named in `consent.md` are
already evidence of that — and the mechanism to classify writes correctly already
exists in core, unused.

**Cheapest fix that is not a refactor.** Derive the mutating set from
`TOOL_SPECS` instead of a prefix list, so a new tool cannot be unclassified by
omission. Then decide, in an ADR, whether consent is a domain invariant (call
`ConsentGate` from `ODIService`, and the CLI and MCP inherit it) or a Studio
courtesy (say so in `consent.md`, and delete or document `ConsentGate` as
unavailable rather than dormant).

**Call — do the derivation now; defer the relocation.** The derivation is
contained and removes a class of silent drift. Moving the gate into the domain
changes behaviour for every surface and needs its own decision: ADR 0003 and an
issue.

### 3. The Studio's citations point into the ODI store with no integrity behind them

**Evidence.** `studio.db` stores turn citations in `turn_citations.evidence_id`
(`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py:194-197`) as a
`TEXT` column holding JSON array ids, resolved on read through
`index.resolve(evidence_id)` in `claims.py:318`. In the same schema,
`conversation_id` and `turn_id` are real foreign keys with
`ON DELETE CASCADE` (`memory.py:184`, `:195`). Nothing constrains the evidence
ids, because they live in a different database.

A summary I was handed claimed the two stores share no key. That is wrong and the
correction matters: they *do* reference each other, which is precisely why the
missing constraint is a finding rather than a design choice.

**Why it matters.** Evidence can be deleted or deduplicated (the promotion path
in `319aa83` rewrites ids) while a stored turn still cites it. The citation then
resolves to nothing, and a claim that was once evidenced degrades quietly into a
claim that merely looks evidenced. The canvas never sees it; only the chat does.

**Cheapest fix.** Decide the semantics and assert them on read: a citation whose
evidence no longer resolves should render as "no longer available", not as an
unresolved provenance. A periodic integrity check over the two files is the
next step if that turns out to be common.

**Call — do the read-side behaviour; defer consolidation.** Merging the stores is
a much larger decision and the separation is deliberate (`README.md:49-51`,
`data-flow.md:65`: memory "never feeds the canvas"). ADR 0004 records which store
owns what and what a dangling citation means.

### 4. The error taxonomy exists, and the MCP boundary throws it away

**Evidence.** There *is* a shared typed model — `packages/core/.../errors.py`
defines `OdiError` with `ValidationError`, `NotFoundError`, `ConflictError`,
`RateLimitError`, `ConsentRequired`, `StoreError`, `SerializationError` and an
`error_status()` mapping (`errors.py:81`), and `remote.py` defines
`StudioError`/`StudioErrorCode` shared by CLI and sidecar, with one HTTP error
body assembled by `register_error_handlers` (`studio/errors.py:169-178`).
`docs/architecture/data-flow.md:169-215` documents the whole path. This finding
was a "no error taxonomy" claim until I read it; the taxonomy is good.

The loss is at one hop. MCP tool handlers return prose: `f"Error: {exc}"`
(`mcp_server.py:108`, `:149`, `:181`, `:487`). The only thing that recovers a
type downstream is `parse_tool_result` (`remote.py:113-145`), which matches
**message substrings** — "not found", "must be between", and so on.

**Why it matters.** Six surfaces agree on the vocabulary of errors except at the
boundary that crosses a wire. Reword a message for a user's benefit and you
silently change a caller's control flow, in code paths that no test connects to
the wording. It is also the reason `ConsentRequired`'s careful 403 mapping is
unreachable from an MCP client.

**Cheapest fix.** Serialise the typed error into the tool result payload —
`{code, message, suggestion, retryable}` — and let `parse_tool_result` key on
`code`. The types already exist; only the wire shape changes. Keep accepting the
old prose form for compatibility while callers update.

**Call — do it.** This is a contained change with a large reduction in
accidental-coupling risk, and it makes the retry/suggestion story real for MCP
clients instead of Studio-only.

### 5. No composition root in the MCP server

**Evidence.** `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py:47-48`
builds the repository and the service at module level:
`_repo = build_repository()` then `service = ODIService(_repo)`. `build_repository`
(`packages/core/.../factory.py:11-19`) reads `AGENTIC_ODI_DB` and creates the
`~/.agentic-odi` directory as a side effect of import. The sidecar already does
this correctly — `create_app(repo=None, ...)` is a factory (`app.py:55-63`) served
with `factory=True` (`main.py:7`).

`data-flow.md:35` documents the import-time build, so this is a known property
rather than a surprise — but it is recorded in a data-flow document instead of an
ADR, and the two servers disagree about it.

**Why it matters.** Importing the module touches the filesystem and binds a
configuration decision to process start. It prevents running two configurations
in one process, makes the server's test surface wider than it needs to be, and
leaves the only "how is this configured" answer in an environment variable read
inside a factory.

**Cheapest fix.** Move construction into `main()`/an app factory, mirroring the
sidecar. Roughly twenty lines.

**Call — do it.** Cheap, and it aligns the two servers on a pattern the repo has
already chosen.

### 6. `packages/core` carries four responsibilities in one namespace

**Evidence.** Domain models, `ODIService`, both repository implementations, the
MCP tool contract (`contract.py`), the methodology stages (scoring, segmentation,
strategy), signals/events, and consent all sit under `agentic_odi_core`.
`contract.py` is the wire protocol for the MCP server and is enforced against the
live registry (`tests/contract/test_mcp_contract.py`), yet it is a domain-package
file.

**Why it matters.** Any change to tool shape edits a domain module. The reverse
also holds, which is worse: a domain refactor can perturb the contract.

**Cheapest fix.** None needed yet. Splitting a distribution here is expensive
churn for an experiment, and the workspace-boundary test now makes the layering
visible. The useful cheap step is vocabulary: name the layers in the diagram and
in `README.md` (domain / persistence / methodology / contract) so that "core is
too big" becomes "these four groups have these rules".

**Call — won't fix now; record the trigger.** Split `contract.py` into its own
distribution when a *second* consumer needs the contract — a client library, a
generated SDK, a second server. Not before.

### 7. Observability stops at the sidecar, and nobody configures logging

**Evidence.** What exists is good and specific: `studio/observability.py:50-63`
writes one JSON line per turn with sensitive keys dropped rather than redacted
(`SENSITIVE_KEYS` at `:20`); `RequestIdMiddleware` (`studio/errors.py:147`,
installed at `app.py:95`) mints, echoes, and propagates `X-Request-ID`;
`chat.py:966-976` records `duration_ms`, `rounds`, `tool_calls`, `tool_errors`.

What does not exist: **token or cost accounting anywhere** — no code reads
`usage`, `completion_tokens`, or a price, and the stream path at `chat.py:693`
never asks the model for it; **any equivalent in the MCP server**, which is a
black box by comparison; and **logging configuration** — `basicConfig`/`dictConfig`
appear nowhere in the repo, so whether any of this is emitted depends on uvicorn's
defaults.

**Why it matters.** The product's premise is agentic tool use. "What did this job
cost, in tokens, per tool, and how long did each tool take" is a first-class
question that currently has no architectural slot, and the surface most likely to
be used by another agent — MCP — is the least observable.

**Cheapest fix.** Add usage to the turn record when the backend returns it
(`stream_options: {"include_usage": true}` for OpenAI-compatible servers);
configure logging explicitly in each entrypoint; time each tool call in the MCP
server the way the sidecar times each turn.

**Call — do the first two.** Small, and without them the existing observability
investments quietly under-deliver.

### 8. The chat loop is well tested; the model's output is not testable at all

**Evidence.** The loop has ~911 lines of tests that assert deterministic
behaviour: tool-call sequencing (`test_studio_chat_branches.py:257`), rounds
exhaustion (`:334-349`), approval approved/declined/expired (`:231`, `:251`,
`:277`), citations and claims (`test_studio_chat_stream.py:390-459`). The LLM is a
hand-written fake installed by monkeypatch (`test_studio_chat_stream.py:109-118`).

There is no recorded-transcript replay, no golden fixture, no scoring harness. So
the mechanics of a turn are covered and the *quality* of a turn is unmeasured.

**Why it matters.** For an ODI product, "did this run produce a well-formed
outcome statement grounded in evidence" is the deliverable. Stage-format rules are
enforced in the domain (`odi-contract.md`), which catches malformed output but
says nothing about grounding — the thing the methodology exists to guarantee.

**Cheapest fix.** A `--replay` mode that reads committed transcripts (recorded
prompts plus tool sequences) so a refactor can be checked against real traffic.
Keep it out of CI: it is non-deterministic and paid.

**Call — do it, as a harness, not a gate.** This is the highest-leverage missing
test type after the boundaries in Finding 1, and the reason it is not first is
that it needs a decision about what "good" means before it can be built.

### 9. `packages/connectors` has never been told what it is

**Evidence.** Zero imports of core, deliberately: `mapping.py:1-5` states it
"deliberately does not import the ODI store". It defines `EvidenceDraft`
(`mapping.py:17-31`); core defines `Evidence` (`models.py:188-207`). The field
sets are identical except for `Evidence.id`. `EvidenceItemType` is defined twice,
independently, in `connectors/models.py` and `core/models.py:185`. Consumption is
`drafts_from_batch` → `add_evidence` → repository (`data-flow.md:84`).

**Why it matters.** Two definitions of "evidence" are kept in step by hand.
A field added to one and not the other is a silent mapping bug at the only door
data enters through.

**Cheapest fix.** Keep the separation — a connector should not need the domain to
fetch a document — and make the equivalence a check, not a hope: assert in
`packages/connectors/tests` that `EvidenceDraft`'s fields match `Evidence`'s minus
`id`. One test, and then the duplication is deliberate rather than accidental.

**Call — do the test.** The identity question itself (transport layer vs domain
adapter) deserves a sentence in an ADR, with the recommended answer: transport,
which is what the code already assumes.

### 10. The deployed edge carries no version

**Evidence.** `scripts/check_version_parity.py:22-33` covers the six `pyproject`
files, the CLI's `_build_info.py`, `apps/studio/package.json`,
`tauri.conf.json`, and `Cargo.toml` — so the desktop bundle *is* covered.
`wrangler.jsonc` and `infra/cloudflare/worker.ts` appear nowhere, and neither
carries a version string at all.

**Why it matters.** A support question about the hosted Studio cannot be answered
from the running site: nothing ties the deployed Worker to a release. The CI
already computes a build identity (`scripts/ci_release.py`, exported into every
job), so the capability exists and simply is not wired to the edge.

**Cheapest fix.** Inject the release identity into the Worker build and expose it
on one health response; add it to the parity list if it becomes a declared field.

**Call — do it.** Small, and it closes the only place where "which build is this"
is unanswerable.

### 11. Two silent failure paths worth one line each

**Evidence.**
- `apps/studio-api/.../studio/chat.py:473`: `_persist_turn` wraps its work in
  `except Exception: return None`. A turn's memory, citations, and thread head
  can fail to persist with no log at all, mid-conversation. (studio-api has 45
  `except Exception` sites; this is the one where the loss is user-visible.)
- `packages/core/.../services.py:241`: `record_signal` linearly scans every
  existing signal for a fingerprint match, then rescans the whole map again at
  `:247` to compute today's budget — two O(n) passes on every write, so the feed
  gets slower as it grows.

**Why it matters.** The first contradicts the documented promise that the turn
log is trustworthy. The second is irrelevant at experiment scale and will not
announce itself when it stops being irrelevant.

**Call — log the first, note the second.** A `logger.warning` carrying the
request id that already exists is the whole fix. The signal scan gets a comment
or an index when a store query can express it; not today.

## What this does not do

- It is not a rewrite proposal. Nothing here argues the layering is wrong; the
  layering is the good part.
- It does not re-report gaps the repo already tracks in the open: the LLM key
  reaching the browser is [#90](https://github.com/alehar9320/agentic-odi/issues/90),
  MCP-side request ids are #82, sidecar authentication is a documented rejection
  in `trust-boundaries.md:66-70`. Where I disagree with a recorded decision I say
  so rather than rediscovering it.
- It does not measure anything. No profiling, no load test, no LLM quality
  scoring — so Findings 7 and 8 say the instruments are missing, not what they
  would show.
- It does not cover `apps/studio`'s internals beyond its boundary with the
  sidecar, nor the Tauri update path, nor the connector presets.
- Severity here is *risk × cheapness*, not user impact. A user notices Finding 2
  far more often than Finding 1, which is why 1 came first.

## Calls made in this critique

In the absence of answers, these are my judgement, and they are the things to
argue with:

1. Enforce the boundary before relocating any code. Done, and it paid for itself
   immediately.
2. Consent's real defect is placement, not absence — and the fix that must not be
   deferred is deriving mutating tools from `TOOL_SPECS` rather than a prefix.
3. Treat the two stores as intentional and make the *reference* honest, instead
   of proposing a merge.
4. Do not split `packages/core` yet; name its layers and pick a trigger.
5. Observability and the replay harness are the two things I would fund after the
   quick wins, in that order.
6. The diagrams stay as source in markdown, checked by a test, rendered by the
   platform — no image generation, no bot. A picture nobody can diff is a picture
   nobody updates.
