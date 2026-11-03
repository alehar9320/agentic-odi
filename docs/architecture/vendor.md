# Vendor alley: copied UI

`apps/studio/src/vendor/` is where copied UI lives. The directory exists so the
copying has a boundary that cannot rot: markup we took from someone else's
project stays replaceable, and product behaviour stays ours.

The rule in one line: **copied markup, depended-on behaviour.**

## The five rules

1. **Behaviour primitives are dependencies; only presentation is vendored.**
   Streaming, tool approval, stores, and markdown parsing are npm packages, so
   an upgrade is a version bump and a changelog. Copying them turns an upgrade
   into a merge we will not do. A file belongs in `src/vendor` when it renders
   and nothing more.
2. **Vendor takes props and never reads app state.** A copied component may not
   import `state/`, `api/`, `assistant/`, or `bff/`. Product data arrives as
   props from a thin wrapper under `apps/studio/src/components/`, which owns the
   store and the fetch. That wrapper is the only place a product concern enters
   the copied surface.
3. **Every vendored file carries a provenance header and a ledger entry.** The
   first line is `// vendored: <source> — <SPDX> — retrieved <date> — local
   edits: <what>`; `apps/studio/vendor.lock.json` records the same facts per
   path plus an integrity handle, so the licence is auditable and the copy is
   re-fetchable. A registry item has no commit, which is why the handle is a
   hash of the fetched artefact rather than a revision that does not exist.
4. **One surface per pull request, 400 changed lines maximum.** A 2,000-line
   drop of a UI kit is unauditable and unmaintainable. Copy the one component
   the current issue needs.
5. **A re-copy diff must be possible.** Local drift is allowed only when the
   header says what drifted, in its `local edits:` note. An unmarked edit means
   the next copy-in either loses the fix or pretends the file never changed.

## How the rules are enforced

Rule two has two independent gates, because a widened lint glob silently deletes the
second one:

- ESLint restricts the aliased forms — `@/state/*`, `@/api/*`, `@/assistant/*`,
  `@/bff/*` — for files under `src/vendor/**`. See `apps/studio/eslint.config.js`.
- `apps/studio/src/vendor/boundary.test.ts` reads every `.ts` and `.tsx` file in
  the tree and resolves each specifier against the importing file. A string
  pattern cannot tell `../assistant/plan` (inside the tree) from
  `../../state/StudioContext` (outside it); resolution can.

Adding `import { useStudio } from "@/state/StudioContext"` to a file under
`src/vendor` therefore fails `npm run lint` and `npm test` both.

Rule three is enforced by `apps/studio/src/vendor/ledger.test.ts`: every copied or
authored file in the tree must appear exactly once in `apps/studio/vendor.lock.json`,
a copied file's header must split into the parts the lock records, and a first-party
file must carry no header. An undocumented copy-in fails `npm test` rather than
waiting for a reviewer to notice the file has no source.

The wider question — when to copy at all, and what to check before adding a
dependency — is `docs/architecture/reuse.md`.

## Layout

```text
src/vendor/
  boundary.ts                  the rule as data
  boundary.test.ts             lint's second pair of eyes
  ledger.test.ts               the ledger rule as a test
  components/ui/               copied primitives (props in, markup out)
  components/assistant/        copied transcript surfaces
```

The ledger itself lives one directory out, at `apps/studio/vendor.lock.json`, so a
`shadcn add` refreshing this tree cannot overwrite the record of what it copied.

The alias `@/` resolves inside this tree, so copied files keep the import
statements they arrived with and stay inside the boundary.

## What this does not do

It is not a mirror of any upstream package, and it does not license code we did
not record. A file with no ledger entry is not vendored — it is unsourced.
Product components keep living under `apps/studio/src/components/`; nothing in
this issue moves them.
