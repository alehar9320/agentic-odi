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
   hash of the fetched artefact rather than a revision that does not exist. Each
   section of the ledger is sorted by path, so the diff of a refresh shows what
   changed instead of a reordering.
4. **One surface per pull request, 400 changed lines maximum.** A 2,000-line
   drop of a UI kit is unauditable and unmaintainable. Copy the one component
   the current issue needs.
5. **A re-copy diff must be possible.** Local drift is allowed only when the
   header says what drifted, in its `local edits:` note. An unmarked edit means
   the next copy-in either loses the fix or pretends the file never changed.

## The dependencies the alley needs

Rule 1 sends behaviour to `package.json` and keeps only presentation in
`src/vendor`, so the packages a copy imports are part of this audit even though
nobody copied their source. A dependency of a copy carries the same two
obligations as the copy: a licence we may ship, and a declaration in
`apps/studio/package.json`. This table is the ledger for them, and
`tests/scripts/test_vendor_policy.py` fails when the three lists — what the tree
imports, what this table names, and what `package.json` declares — stop
agreeing.

| Package | Licence | Declared in | Why the alley needs it |
|---|---|---|---|
| `class-variance-authority` | MIT | devDependencies | the variant table the copied button is built from |
| `clsx` | MIT | devDependencies | the class merger under `lib/utils.ts`, which every copy calls |
| `radix-ui` | MIT | dependencies | `Slot`, the `asChild` primitive the button renders through |
| `react` | MIT | dependencies | `React.ComponentProps` and the JSX the copies are written in |
| `react-dom` | MIT | dependencies | `createPortal`, which the hover-card copy renders its content through |
| `tailwind-merge` | MIT | devDependencies | resolves the class collisions two copies agree to disagree on |
| `tailwindcss` | MIT | devDependencies | `index.css` imports its theme and utilities layers, scoped to this tree |

The class-merger trio sits in `devDependencies` because that is where
`npx shadcn init` put it: the Studio SPA is bundled by Vite, so nothing is
installed on a target machine from this file and the section does not change the
artefact that ships. The table records the section as it is rather than moving
the packages, because a ledger that describes the tree as it should be is not a
ledger.

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

Rule three has a second gate, outside the tree, in
`tests/scripts/test_vendor_policy.py` (`scripts/vendor_policy.py`). It runs in the
`test` job, which executes the whole `tests/` tree, so no workflow change was needed.
Two things there are invisible to a test that lives inside `src/vendor` and one of
them is invisible to any test in JavaScript:

- a licence id with a valid shape is not necessarily one whose terms we ship, so
  every licence in the lock and in the dependency table is checked against a closed
  SPDX allowlist — `MIT`, `Apache-2.0`, `BSD-2-Clause`, `ISC`, `0BSD`;
- the alley's dependencies are outside the directory that gate reads. Comparing
  what the copies import against the table above and against
  `apps/studio/package.json` is the only way a copy that quietly starts depending on
  something, or a table row for a package no copy uses any more, becomes a failure
  instead of a note in review.

The parity assertions overlap on purpose, for the reason rule two already gives: a
gate that can be disabled by a widened glob or a skipped job is one gate, not two.

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
