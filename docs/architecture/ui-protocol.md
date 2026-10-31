# The generative UI protocol

The model does not write HTML. It composes a tree from a closed catalog that the
Studio owns, the sidecar validates, and the client renders. This document
records the protocol and the reasons it is shaped this way.

## What it is

The protocol has four layers:

1. **The catalog** — `apps/studio/src/ui/catalog.ts:72`. Sixteen entries: nine
   primitives (`stack`, `grid`, `heading`, `text`, `list`, `stat`, `meter`,
   `callout`, `divider`) and seven cards (`outcome-card`, `opportunity-board`,
   `impact-simulation`, `evidence-quote`, `job-map`, `opportunity-thesis`,
   `decision-record`). Each has a typed prop schema and optional `actions`; cards
   describe ODI content rather than generic text.
2. **The manifest** — `catalogManifest()` (`catalog.ts:338`) is sent with a turn
   so the model knows exactly which types and props exist; `catalogPrompt()`
   renders the same information as model-facing prose.
3. **The tool call** — the model calls the local `render_ui` tool. The sidecar
   validates the arguments against the catalog (`ui_spec.py:115-117`), emits an
   SSE frame `event: ui` with `{id, spec}` (`chat.py:762-786`), and does **not**
   forward the call to MCP. An invalid spec produces no frame; the exact
   violation is returned to the model as a tool result, so it can repair the tree
   within its tool rounds (`MAX_TOOL_ROUNDS = 3`).
4. **The client** — every `ui` frame goes through `parseUiSpec` against the same
   manifest (`protocol.ts:281-286`). The renderer maps each type to a React
   component through `NODE_COMPONENTS` (`registry.ts:30-48`).

## Why a closed catalog

A model allowed to emit arbitrary markup turns every prompt injection into an
XSS vector, and every visual decision into an unbranded one. A closed catalog
means:

- the set of rendered things is a known, testable list;
- the data is typed, so a card cannot claim a value the model did not pass;
- the design system owns layout and tone;
- a bad tree fails safely instead of injecting code.

The catalog is owned by the client build, not the server: the sidecar validates
against the manifest the client sent, so a client upgrade and its server stay in
step.

## Limits and fallbacks

Both ends enforce the same ceiling: tree depth 12, 200 nodes, 2000-character
strings, 32 children per node, 40 actions (`protocol.ts:15-21`, mirrored in
`ui_spec.py:17-20`). An over-limit tree is rejected whole rather than truncated.

The two ends differ on the unknown:

- the **server** rejects an unknown type, because the model is expected to use
  the manifest it was given;
- the **client** renders an unknown type as an `unsupported` node showing
  "Unavailable surface" with a copyable spec (`protocol.ts:236-238`,
  `UiRenderer.tsx:38-62`), so a newer server cannot blank a page.

Unknown props are stripped rather than rendered, stray leaf children are
dropped, and a card that throws is isolated so the rest of the tree still shows
(`UiRenderer.tsx:12-36`). `dangerouslySetInnerHTML` is removed anywhere in a
tree.

## The action model

Actions are `{label, intent, tone?: "primary" | "ghost"}`, at most 40. Malformed
entries are dropped (`actions.ts:29-51`). Pressing one calls `onIntent(intent)`,
which sends a chat message (`primitives.tsx:21-41`) and is disabled while a reply
streams. Cards are **views**: an action is a prompt back into the conversation,
never a direct mutation or navigation.

## Registry parity

`apps/studio/src/ui/UiRenderer.test.tsx:207-220` is the parity test: every
catalog type must have a renderer, and every renderer must correspond to a
catalog type. It is bidirectional and runs in both the TS build and CI.

That test does **not** compare the TypeScript catalog to the Python validator.
The server's tests use a hand-built `DEMO_CATALOG`, and the chat test asserts the
tool schema mirrors whatever manifest the client supplied. The thing that keeps
the real catalog and the server aligned is the manifest being sent per turn, not
a cross-language fixture.

## What the alternatives were

- **HTML or Markdown with embedded components.** Rejected: extraction is
  ambiguous, sanitization is a moving target, and the result is not typed.
- **A generic component library.** Rejected: a chart and a paragraph are not ODI
  surfaces. The cards encode the domain (an outcome, a landscape, a decision).
- **Server-owned catalog.** Rejected: the client is the thing that must render
  it; version skew belongs in the manifest, not in a shared schema artifact.
- **Free-form `props` with client-side validation only.** Rejected: the model
  would learn about invalid shapes from a blank screen instead of a same-turn
  error it can fix.

## What this does not do

- It does not accept arbitrary HTML, JavaScript, or `eval`; there is no
  `dangerouslySetInnerHTML` path.
- It does not let a card read from or write to the store. Every action is a chat
  intent.
- It does not enumerate or support third-party catalogs.
- It does not provide a layout editor or persist a tree; a rendered UI is a
  message, not a saved page.
- It does not cross-check the Python validator and the TypeScript catalog against
  one shared fixture.
