# Copied primitives

Markup and behaviour copied in from another project's UI kit, verbatim except
where a local edit is recorded.

What may live here:

- Presentational primitives that take **props** and render. No product state,
  no store reads, no API calls.
- Anything whose licence allows it, recorded in `apps/studio/vendor.lock.json`
  with upstream, commit, date, and SPDX id.
- A provenance header on every file: `// vendored: <source> — <SPDX> —
  retrieved <date> — local edits: <what>` (or the `<!-- vendored: … -->` form
  in a copied document), mirrored in `apps/studio/vendor.lock.json`, which
  adds the integrity handle to re-copy against.

What may not:

- Imports of `src/state`, `src/api`, `src/assistant`, or `src/bff`. Copied code
  stays a leaf; the wrapper under `src/components/**` owns the product data and
  passes it down as props.
- Behaviour primitives. Streaming, approvals, and stores are dependencies we
  keep in `package.json`, not files we copy.

Rules and licence policy: `docs/architecture/vendor.md`. The boundary is
enforced by ESLint and re-checked in `src/vendor/boundary.test.ts`.
