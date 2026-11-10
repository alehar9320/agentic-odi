# Copied conversation surfaces

Presentation for transcript parts — tool calls, plans, quotes, terminals —
copied from a UI kit or from assistant-ui's own examples.

What may live here:

- Components that receive **props** (a label, an input, a result, a status) and
  render them. They never read the Studio store, never call the sidecar, and
  never import `src/assistant/convert.ts`.
- Files with a provenance header and an entry in
  `apps/studio/vendor.lock.json`.

What may not:

- The conversion from `ChatMessage`/`ChatPart` to assistant-ui parts. That
  mapping stays in `src/assistant/convert.ts`, the single place parts are built.
- Product state or API access of any kind. A wrapper in `src/components/chat`
  owns it and hands the data down as props.

Rules and licence policy: `docs/architecture/vendor.md`.
