# Conversational Generative UI for The Living Studio — design

**Status:** approved for implementation
**Date:** 2026-10-21
**Scope:** `apps/studio` (React SPA + Tauri) and `apps/studio-api` (FastAPI sidecar)

## Intent

The Studio's agent is its product. Today that agent's intelligence is trapped in
prose: it can reason about an opportunity landscape, but it can only *describe*
the landscape. Everything it knows arrives as a wall of text in a `pre-wrap`
bubble, so the user has to read, translate, and then go click a canvas tab to
see the thing they were just told about.

The conversational experience should let the agent **hand you things**. When it
scores an outcome, you get the outcome card. When it pressure-tests a bet, you
get the before/after simulation. When it cites a customer, you get the quote with
its lineage. Prose introduces the artifact; the artifact carries the evidence.

That is the whole idea. Everything below exists to make it safe, modular, and
quiet enough to feel effortless.

## Goals

1. The agent can compose rich surfaces from a **closed, typed catalog** — no
   HTML, no eval, no arbitrary code, ever.
2. Rich surfaces render **inline in the transcript**, interleaved with prose in
   the order the agent produced them.
3. The catalog is **owned by the client** and published to the sidecar per
   request, so there is exactly one source of truth.
4. Every card can offer **actions**, which dispatch a typed intent back to the
   agent. Cards are views, never actors.
5. Degradation is graceful and total: unknown type → a quiet fallback node;
   unparseable spec → the prose still reads; no catalog → the tool is never
   offered; no LLM → the honest by-hand guidance the studio already ships stays
   the answer. Nothing is fabricated to fill the space.

## Non-goals

- **No third-party/remote catalogs.** The catalog ships with the app. The wire
  format is compatible with a future A2UI-style multi-catalog world, but v1 does
  not accept a catalog from anywhere but the trusted client build.
- **No direct data mutation from cards.** Actions produce prompts. The agent
  keeps the single authority and the single audit trail.
- **No prose-embedded UI extraction.** Guessing at fenced blocks in model output
  reintroduces a second, unvalidated protocol path. One path only.
- **No WYSIWYG layout editor.** The agent composes; the human reacts.

## Architecture

Three layers and one contract.

```
┌──────────────────────────── apps/studio (React) ────────────────────────────┐
│                                                                             │
│  ui/catalog.ts        ui/protocol.ts        ui/UiRenderer.tsx               │
│  ┌────────────┐       ┌─────────────┐       ┌──────────────────┐            │
│  │ 15 nodes   │──────▶│ validate +  │──────▶│ registry lookup  │            │
│  │ + schemas  │       │ normalize   │       │ + ErrorBoundary  │            │
│  │ + prompts  │       │ + limits    │       │ + action context │            │
│  └────────────┘       └─────────────┘       └──────────────────┘            │
│         │                                          │                        │
│         │ catalogManifest()                        ▼                        │
│         ▼                                  ui/primitives.tsx               │
│   ChatStreamRequest.ui_catalog             ui/cards.tsx                     │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ POST /api/chat  (SSE)
                               ▼
┌──────────────────── apps/studio-api (FastAPI) ──────────────────────────────┐
│  studio/ui_spec.py                     studio/chat.py                      │
│  ┌──────────────────────────┐          ┌──────────────────────────────────┐ │
│  │ UiCatalog                │          │ tool loop (max 3 rounds):        │ │
│  │ .tool_schema()           │─────────▶│  render_ui is a local tool, not  │ │
│  │ .validate()              │          │  an MCP tool; prose before a      │ │
│  │ (JSON Schema subset)     │          │  surface is kept, not retracted   │ │
│  └──────────────────────────┘          └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

The sidecar is **catalog-agnostic**. It receives a manifest, derives the
`render_ui` tool schema and a validation surface from it, and never hardcodes a
component name. Swap the client, and the server still works.

### Why the catalog lives on the client

Because presentation is a client concern, and because the alternative — a shared
JSON file consumed by a Vite build and a Python wheel — is a packaging problem
waiting to drift. The sidecar is a local trust boundary; the client already
declares its capabilities in the request body. If no manifest is sent (CLI,
scripts, older clients), the server simply does not offer `render_ui`.

### The contract

A UI payload is a tree:

```json
{
  "type": "outcome-card",
  "props": {
    "id": "O-1",
    "statement": "Minimize the time it takes to propagate secrets across environments",
    "importance": 9,
    "satisfaction": 3
  },
  "children": []
}
```

- `type` names a catalog entry. Unknown types are dropped with a visible,
  non-alarming fallback — never silently rendered as blank space.
- `props` are validated against that entry's JSON Schema subset. Unknown keys are
  stripped, not trusted.
- `children` is only legal on layout nodes; stray children on a leaf card are
  dropped rather than allowed to lose the card.
- Nesting happens **only** through `children`. Props never contain nodes.

The manifest is plain JSON Schema (`draft 2020-12` subset: `type`, `properties`,
`required`, `enum`, `minimum`/`maximum`, `items`, `minItems`/`maxItems`,
`additionalProperties`). The same document is embedded verbatim in the tool
schema and used to validate the result, so the model and the validator can never
disagree about what is legal.

### Catalog v1

Two tiers, deliberately small. Tens of components is a design system; fifteen is
a vocabulary.

**Primitives (9)** — composition: `stack`, `grid`, `heading`, `text`, `list`,
`stat`, `meter`, `callout`, `divider`.

**Cards (6)** — ODI shapes worth naming: `outcome-card`, `opportunity-board`,
`impact-simulation`, `evidence-quote`, `job-map`, `decision-record`.

Cards are leaves as far as the wire format goes, but they render internally using
the same primitives. The agent expresses *intent* (`score this outcome`), not
*layout*. Novel shapes compose from primitives.

**Actions** are a prop, not a node: `actions: [{ label, intent, tone? }]`. Any
component may hold them; the renderer places them in a footer row. One shape,
one renderer, no special cases.

### Protocol limits

Generation is untrusted by construction, so the parser enforces ceilings before
anything touches React: max depth 12, max 200 nodes, max 2000-character strings,
max 40 actions per node, max 32 children per node. Over-limit input is rejected
as a whole — partial rendering of a runaway tree is worse than none.

### Streaming model

A new SSE event:

```
event: ui
data: {"id":"ui_3","spec":{...}}
```

It arrives atomically, after validation. The message model becomes ordered parts:

```ts
type ChatPart =
  | { kind: "text"; text: string }
  | { kind: "ui"; id: string; node: UiNode };

interface ChatMessage {
  role: "user" | "assistant" | "notice";
  content: string;
  /** Assistant turns only; `notice` turns stay prose. */
  parts?: ChatPart[];
}
```

`content` is kept as the concatenation of text parts because it is what gets sent
back as conversation history; `parts` is what gets rendered. History serialization
stays byte-identical to today, so the LLM sees no change in its transcript.

### Server tool loop

The sidecar already fans MCP tools into the completion. It gains one **local**
tool, `render_ui`, bound before the MCP call and intercepted after:

- valid spec → `event: ui`, tool result `"Rendered."`
- invalid spec → no event, tool result names the exact schema violation

The corrective tool result is the whole retry mechanism. No second prompt and
no silent failure — a local model that fumbles a prop gets told which prop, and
the loop (bounded at three rounds) offers `render_ui` again, so the correction
can actually be rendered in the same turn.

Prose that precedes a tool call is **kept**. With ordered parts, the sentence
that introduces a card is part of the answer; retraction is only needed when the
transcript has nowhere to put a surface.

`canvas_dirty` is now emitted only when an actual MCP tool ran.

### No-LLM path

Unchanged, deliberately. `offline_fallback` already answers with the commands
that work by hand, and it refuses to invent customer data or scores. The studio
keeps that position: a missing model is a different mode of work, not an excuse
to fabricate a demo. The no-model surface lives in the sidebar panels, which are
real and local.

### Interaction

`UiActionContext` carries `{ onIntent, busy }` from the chat surface into the
renderer. Clicking an action calls `sendMessage(intent)` — disabled while a
response is streaming. The card never reaches into canvas state, never mutates
data, never knows what an MCP tool is.

### Failure isolation

Every rendered node is wrapped in a boundary. A card that throws degrades to a
`callout` saying so, and the rest of the transcript survives. Rendering is pure:
no node can trigger network I/O on mount.

## The experience

What Jobs would have vetoed, and what replaces it:

| Before | After |
| --- | --- |
| Markdown constructs printed literally | Real headings, lists, and emphasis — the transcript's existing `Markdown` component, reused inside cards |
| Every outcome described in prose, then clicked for elsewhere | The outcome card *is* the answer, with its score, its formula, and its lineage |
| A permanent amber `🛠️` bubble per tool call | A quiet, collapsing activity rail that reads as status, not output |
| Generic indigo buttons everywhere | One primary action per card, secondary actions quiet |

Motion is one honest gesture: a card rises 6px and fades in over ~220ms with a
40ms stagger across siblings, and the whole motion block is removed under
`prefers-reduced-motion`.

Accessibility is not a later pass: the transcript is a `role="log"` live region,
cards are `article`s with `aria-label`s, meters expose `role="meter"` with
`aria-valuenow`/`aria-valuemin`/`aria-valuemax`, actions are real `<button>`s with
visible focus rings, and the fallback node is announced rather than hidden.

## Building on the chat-first shell

The chat-first interface (`ChatStage`, `Conversation`, `Composer`, `Markdown`)
landed while this work was in review. The feature ports onto it rather than
alongside it: `Conversation` renders `parts` in order, cards dispatch through
`UiActionContext` into `sendMessage`, and prose reuses the existing `Markdown`
component instead of a second renderer. No component in this design duplicates
something the shell already owns.

## Constraints

- No new runtime dependencies. The validator and every card are hand-written
  against the existing React 19 / Vite / vitest stack; prose reuses the
  transcript's `Markdown` component.
- Python 3.10+, `pydantic`, no new packages.
- Rules of the house: tests per package with the workspace `uv` layout, README
  and `docs/living-studio.md` updated in the same change.

## What is left to the builder

Exact CSS values, animation curves beyond the described feel, the internal
composition of each card, and the precise wording of the catalog descriptions
the model reads. These are craft decisions, not contract decisions.
