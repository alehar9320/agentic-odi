# Opportunity Specs — Design Index

**Date:** 2026-10-22
**Status:** Approved
**Milestone:** `Opportunity Specs — 2026-10` (issues #78–#97)
**Scope:** A review of `alehar9320/agentic-odi` at `origin/main` (`624b6857`, release 0.12.0), including all seven open pull requests.

---

## TL;DR

The Living Studio's whole promise is that you **express intent** and the system **gives you signals back**. Two things stand between the product and that promise.

**The product does not tell the truth.** The Studio shows three hardcoded notifications as if they were real activity, serves a demo job map as if it were your research, lists three integrations in Settings that can never connect, and renders "impact simulations" whose numbers are whatever the model typed. In a system whose job is to tell you what your customers need, the system is inventing things you never told it. Nine of these twenty issues close that gap.

**The delivery system does not tell the truth either.** Six of the seven open pull requests contain a commit that replaces the whole repository with a stale snapshot, silently deleting nine to eleven already-shipped features. They pass CI, because the reverted tree is internally consistent. Their descriptions are materially false — one claims twenty improvements and ships three CSS blocks; another claims to delegate knowledge storage to external systems and adds a URL field. Six more issues close that gap, and one turns on the guardrail that would have caught all of them.

Everything else in the milestone — durable memory, consent, the enforced ODI contract, the real signal loop, evidence that becomes outcomes — is the work that turns a demonstration into a product you would trust at 7am on a Tuesday.

---

## The thesis

This is a product about **human intent expressed conversationally, with the agent doing the work and the human staying in the loop**. Three properties follow, and every issue in this milestone serves at least one of them.

### 1. Nothing fabricates

The single most corrosive failure mode for an AI-native product is that it cannot distinguish between what it knows and what it made up. Because the person cannot tell the difference either, the whole channel decays. A notification that was simulated, a score that was typed, a demo job presented as research — each one teaches the person that the signal is unreliable, and once they learn that, they stop reading the signals. The signal channel is the product.

> Issues #78, #79, #83, #86, #87, #89, #90, #91, #94, #95, #97

### 2. The agent never acts without permission

"You express intent, and you get signals" only works if the agent's actions are legible and reversible. Today every card button is a sentence typed back into the chat, every tool call happens invisibly and immediately, and there is no record of what the agent did to your data. A person who cannot see the boundary cannot trust the agent on the other side of it.

> Issues #80, #81, #82, #89, #93, #95, #96

### 3. The methodology is enforced, not narrated

The repository ships a rigorous methodology and does not enforce it. `add_outcome` accepts any string — "make it faster" is a valid desired outcome. `importance` and `satisfaction` are optional, so an outcome can exist with no score, and the "underserved > 10" analysis then skips it silently. The eight Universal Job Map stages exist in exactly one place in the codebase: a hardcoded array in a React file. The tool the agent is told to call for stage guidance describes a **different** stage order than the project's own rulebook. The agent can produce a fluent, plausible, methodologically wrong answer, and nothing catches it.

> Issues #83, #84, #85, #86, #89, #90, #92

---

## The twenty

### Truth and trust — priority high

| Issue | Title | What it fixes |
|---|---|---|
| [#78](https://github.com/alehar9320/agentic-odi/issues/78) | No surface may lie: label every demo, seed, and simulated signal | Seeded notifications, the demo canvas, un-connectable Settings rows, and impact cards with no computation behind them |
| [#79](https://github.com/alehar9320/agentic-odi/issues/79) | "Catch Up" must mean something: a real signal inbox | The catch-up feed has exactly one producer: a button labelled "+ Simulate update" |
| [#83](https://github.com/alehar9320/agentic-odi/issues/83) | Every write must pass the ODI contract | The outcome format, the mandatory scores, and the eight job-map stages are documented and unenforced |
| [#86](https://github.com/alehar9320/agentic-odi/issues/86) | A pull request must not be able to lie | Diff-shape, body-truth, and fabrication gates — the check that would have blocked all six broken PRs |
| [#87](https://github.com/alehar9320/agentic-odi/issues/87) | Land the real work from the six AI-generated pull requests | Salvaging the first commit of each branch, and the specific defects to fix before it lands |
| [#90](https://github.com/alehar9320/agentic-odi/issues/90) | The Studio has no front door: auth, CSP, and secret handling | No auth on the sidecar or the MCP server, `csp: null` in the webview, the API key in `localStorage` |
| [#91](https://github.com/alehar9320/agentic-odi/issues/91) | Failure must be as considered as success | `{"ok": true}` wrapping an error string, a stream that dies without an event, an error rendered as an empty result |

### Intent, consent, and the work the agent does — priority high

| Issue | Title | What it fixes |
|---|---|---|
| [#80](https://github.com/alehar9320/agentic-odi/issues/80) | Evidence must become outcomes | Every ingested record gets the same job, step, and outcome id; nothing is ever classified or proposed |
| [#81](https://github.com/alehar9320/agentic-odi/issues/81) | The conversation must survive you | The transcript is React state and evaporates on reload; there is no `remember` tool and no memory |
| [#82](https://github.com/alehar9320/agentic-odi/issues/82) | The agent must ask before it acts | Every card button is a sentence typed back into the chat; there is no consent, no mandate, and no audit trail |
| [#89](https://github.com/alehar9320/agentic-odi/issues/89) | A release must be verifiable | The desktop app reports `0.1.0` while the project is at `0.12.0`; the release workflow never fires; no `latest.json` has ever been published |

### Closing the ODI loop — priority medium

| Issue | Title | What it fixes |
|---|---|---|
| [#84](https://github.com/alehar9320/agentic-odi/issues/84) | One truth about what I can do | `get_capabilities` hides 11 of 30 tools; two CLI command groups were written and never registered |
| [#85](https://github.com/alehar9320/agentic-odi/issues/85) | The missing half of ODI | Stages 5 and 6 — outcome-based segmentation and innovation strategy — do not exist |
| [#88](https://github.com/alehar9320/agentic-odi/issues/88) | Hold the line: a coverage floor that fails the build | The 90% floor exists only on Codecov, which is configured not to fail the build |
| [#94](https://github.com/alehar9320/agentic-odi/issues/94) | The local model must be real | An "on-device LLM" that is a four-branch keyword matcher with `is_available() → True` and zero dependencies |
| [#95](https://github.com/alehar9320/agentic-odi/issues/95) | Background agents must actually run | A schedule expression nobody parses and a trigger that writes "Executed mock cloud agent task successfully" |
| [#96](https://github.com/alehar9320/agentic-odi/issues/96) | V2MOM must be a living artifact | A five-field model that is never extracted, never persisted, and four-fifths unreachable in the UI |

### The person using it — priority medium and low

| Issue | Title | What it fixes |
|---|---|---|
| [#92](https://github.com/alehar9320/agentic-odi/issues/92) | Usable without a mouse | The opportunity matrix is a blank rectangle to a screen reader; the table rows and job-map tiles are click-only |
| [#93](https://github.com/alehar9320/agentic-odi/issues/93) | The Studio must fit in a pocket | A desktop-shaped shell, no offline path, and no real device testing |
| [#97](https://github.com/alehar9320/agentic-odi/issues/97) | The docs must be the truth | A roadmap that is 100% ticked, a connectors doc that contradicts the code, and a website advertising a "Causal Lineage" that does not exist |

---

## Dependency graph

```text
                    ┌─────────────────────────────────────┐
                    │  #86 PR truth gates                  │
                    │  #87 salvage the six PRs             │
                    │  #88 coverage floor                  │
                    │  #89 release truth                   │
                    │  #97 docs tell the truth             │
                    │  (the guardrail layer — land first)  │
                    └─────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐
│ #78 no surface lies│   │ #83 ODI contract      │   │ #90 security          │
│ #91 failure design │   │ #84 capability manifest│  │ #92 accessibility     │
│ #79 signal inbox   │   │ #85 segments/strategy │   │ #93 mobile            │
│ #80 evidence→outcome│  └───────────────────────┘   │ #94 model routing     │
│ #81 durable memory │            │                  │ #95 background agents  │
│ #82 consent/audit  │            │                  │ #96 V2MOM              │
└───────────────────┘            │                  └───────────────────────┘
             │                    │
             └────────┬───────────┘
                      ▼
              #79 real signal inbox
              (signals need outcomes to signal about)
              #95 background agents
              (an agent needs a mandate to act)
```

**Load-bearing order:**

1. **#86 first.** Every other delivery in this milestone is protected by it. The gate that fails a pull request which deletes a shipped file would have blocked all six broken PRs on its own.
2. **#87 second**, once #86 is in place. The salvages are the last chance to land real work from those branches before they are closed.
3. **#83, #84, #90 next.** The contract, the manifest, and the front door are prerequisites for most of the product work.
4. **#78, #79, #80, #81, #82 together.** These are the signal loop and it is a closed loop — memory produces observations, observations produce proposals, proposals produce outcomes, outcomes produce signals, signals need somewhere to live. Building half of it produces a system that is more capable and more deceptive than today.

---

## Relationship to the seven open pull requests

| PR | Status | Disposition |
|---|---|---|
| **#76** desktop self-update | Healthy — clean diff, green CI, a spec and a plan, 78 tests | **Merge as-is.** Two separable pieces (the version sync, the `release: published` trigger) are folded into #89 and can land earlier |
| **#70** evidence with external links | Conflicting, no CI on head | Salvage commit `81f99a80` per #87. The real delegation work is #80 |
| **#66** mobile UX | Mergeable, green CI, 9 features reverted | Salvage commit `d28d6a6e` per #87. The real mobile shell is #93 |
| **#65** on-device LLM router | Mergeable, green CI, 9 features reverted | Salvage commit `3ff731b8` per #87, renamed honestly. The real engine is #94 |
| **#64** V2MOM capture | Conflicting, no CI on head | Salvage commit `cf8e9489` per #87. The real artifact is #96 |
| **#63** UX copy and clarity | Mergeable, green CI, 9 features reverted | Salvage commit `3714baee` per #87. It is 4 files and +7/−3 — the body says twenty |
| **#62** cloud agent scheduling | Mergeable, green CI, 11 features reverted | Salvage commit `f849c394` per #87, with the fabricated success removed. The real scheduler is #95 |

Every one of the six carries a tree-replacement commit that deletes shipped features. The first commit on each branch is real, small, and worth keeping. **#87 specifies exactly what to salvage and what to fix before it lands.**

---

## What this milestone deliberately does not do

- **It does not redesign the visual language.** The `ui/` protocol — a closed, client-owned catalog with dual validation, a registry-parity test, and per-node error isolation — is the strongest part of this codebase. It is documented (#97) and left alone.
- **It does not add a sync protocol.** The `sync_state` table and the unused half of the `EventStore` protocol are deferred. #81 makes conversations durable and portable in *format*; synchronizing them is a later decision.
- **It does not build a hosted multi-user system.** The hosted Studio gets a shared access code and says so plainly (#90). Accounts, roles, and per-user identity are out of scope for a local-first tool.
- **It does not invent a model.** The deterministic tier (#94) points at real tools and real data. Where the system has nothing, it says so.
- **It does not pick a root npm workspace.** Two branches want one with different content. The recommendation is not to add one; the decision belongs in its own pull request (#87).
- **It does not close the seven open pull requests by hand.** It specifies the procedure. A person or an agent follows it.

---

## How to work the queue

Each issue is written to be implementable by an agent without re-deriving the archaeology. Every one contains:

- a **TL;DR** at the top, in plain language, for a person who has not read the repository;
- **The problem**, with `file:line` evidence and the exact quoted code where the evidence is a claim;
- **What a person experiences**, written in the intent/signals/human-in-the-loop frame;
- **Specification**, broken into data model, service, API routes, MCP tools, UI surfaces, and CLI;
- **Non-negotiable constraints**, including the anti-fabrication and human-in-the-loop rules;
- **Out of scope**, with a pointer to the issue that owns the excluded work;
- **Acceptance criteria** as a checklist;
- **Verification** — the exact commands to run, and the exact tests to add;
- **Context an implementing agent must read** — the file paths and line ranges that matter, with a note on why each one does.

The issues cross-reference each other by number, so an agent can see the dependency order without this document.

---

## Review basis

Everything in this milestone is grounded in the repository at `origin/main` (`624b6857`) and in the seven open pull requests as of 2026-10-22. The principal sources:

- `packages/core/src/agentic_odi_core/` — `models.py`, `services.py`, `evaluation.py`, `contract.py`, `messages.py`, `repository.py`, `sqlite_repository.py`, `intent_store.py`, `events.py`
- `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` — 30 tools, the error-as-string convention, `get_capabilities`
- `apps/studio-api/src/agentic_odi_studio_api/studio/` — `chat.py`, `router.py`, `schemas.py`, `mcp_data.py`, `seed.py`, `ui_spec.py`, `connectors.py`, `probes.py`
- `apps/studio/src/` — `state/StudioContext.tsx`, `components/chat/*`, `components/canvas/*`, `components/notifications/CatchUpFeed.tsx`, `components/workspace/*`, `components/layout/StudioBar.tsx`, `ui/*`, `onboarding/*`, `features/flags.ts`
- `packages/connectors/src/agentic_odi_connectors/` — `protocol.py`, `catalog.py`, `mapping.py`, `sink.py`, `mcp/connector.py`, `rest/connector.py`
- `apps/cli/src/agentic_odi_cli/` — `cli.py`, `backend.py`, `chat.py`, `connectors.py`, `onboard.py`, `settings.py`, `profile.py`, `flags.py`
- `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/tauri-release.yml`, `release-please-config.json`, `codecov.yml`, `pyproject.toml`
- `.agents/rules/agent_instructions.md` — the project's own methodology, which the code is measured against
