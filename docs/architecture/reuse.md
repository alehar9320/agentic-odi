# Reuse first: the ladder, the bounds, and the ledger

Agents in this repository mostly do not fail to search. They search, find a
near-duplicate, and write a third copy anyway.

So this is a policy about **what the output must contain**, not about effort. The
behaviour skill is `.agents/skills/reuse-first/SKILL.md`; this file is the reference
it points at. Baseline runs measured the failure directly: a relative-time task
found `formatRelativeTime` in
`apps/studio/src/components/notifications/CatchUpFeed.tsx` and wrote a second
relative-time module anyway; a retry-and-backoff task read
`packages/connectors/src/agentic_odi_connectors/http.py`, found the transport-level
retries there, and hand-wrote its own helper regardless.

## The ladder, in cost order

1. **Reuse what is already in this repo.** Search by verb, by return type, and by
   the test that would cover the behaviour — not by the filename you plan to create.
2. **Use a dependency the workspace already declares.** A package in
   `apps/studio/package.json` or a `pyproject.toml` that nothing imports is a cost
   already paid and never collected.
3. **Copy proven code in, with provenance.** See the ledger below. Judge a new
   third-party package against the adoption gate in
   `.agents/skills/reuse-first/references/foss-adoption.md`.
4. **Write it fresh,** naming which rung failed.

Rung 3 is bounded by `docs/architecture/vendor.md`: behaviour primitives —
streaming, tool approval, stores, markdown parsing — are dependencies, never
copies. Only presentation is vendored.

## Canonical owners

Where a concern already has a home, the home wins. These are the copies agents keep
missing.

| Concern | Owner | Known stray copies |
| --- | --- | --- |
| Markdown rendering | `@assistant-ui/react-markdown` (declared, imported nowhere) | `apps/studio/src/lib/markdown.ts` |
| Dialog, focus trap, dismissal | `radix-ui` (declared; used only under `src/vendor`) | `apps/studio/src/lib/useFocusTrap.ts`, four hand-built `role="dialog"` surfaces |
| Opportunity score wording | `apps/studio/src/lib/odi.ts` (`formatOpportunityScore`, `isUnderserved`, `UNDERSERVED_THRESHOLD`) | `apps/studio/src/lib/records.ts` prints the stored number as-is, on purpose — that table reports what the store returned |
| Number clamping | `apps/studio/src/ui/primitives.tsx` | `apps/studio/src/ui/cards.tsx`, `apps/studio/src/components/canvas/OpportunityLandscape.tsx` |
| Id minting | `apps/studio/src/bff/id.ts` | inline id construction in `apps/studio/src/state/StudioContext.tsx` |
| HTTP with retries | `packages/connectors/src/agentic_odi_connectors/http.py` | `urllib.request.urlopen` in `rest/connector.py` and `marketplace.py` |
| HTTP from the CLI | `httpx` (declared by `apps/cli`) | `urllib.request.urlopen` in `apps/cli/src/agentic_odi_cli/update.py` |
| ISO-8601 timestamps | `datetime.isoformat()` | `strftime("%Y-%m-%dT%H:%M:%SZ")` in `apps/cli/src/agentic_odi_cli/profile.py` and `apps/cli/src/agentic_odi_cli/flags.py` |

These rows are the record of an audit, not a to-do list with a deadline. Fixing them
is ordinary refactoring, one pull request per concern.

## The bounds

Reuse is not a licence to add a dependency anywhere. Three places deliberately
close rung 2:

- **`website/`** makes zero third-party requests, loads no webfonts, and pulls from
  no CDN. Copy the markup in and record it; do not add a package.
- **`scripts/*.py`** is standard library only, because it ships with the repository
  and runs before an environment exists.
- **The packaged CLI binary** carries every transitive import in its size and in
  `uv.lock`; a new Python dependency is a build-artefact decision, not an import
  statement.

A new cross-package Python import also needs the workspace edge declared in the same
task, which is ADR 0002's three edits: the dependency in the consuming
`pyproject.toml`, the arrow in `docs/architecture/README.md`, and `uv lock`.

## The acceptance bar for a new dependency

Adopt only what clears both halves: **secure** (licence-clean, advisory-clean,
healthily maintained, small transitive surface) and **tested** (pinned, scanned in
CI, wrapped in one thin contract test on the seam you actually use). That gate is the
vendored `references/foss-adoption.md`, which is Apache-2.0 material with attribution
in its header.

Read it alongside the two sources that shaped it — link them, do not copy them out:

- OpenSSF Best Practices WG, [Concise Guide for Evaluating Open Source Software](https://best.openssf.org/Concise-Guide-for-Evaluating-Open-Source-Software.html)
  (2025-04-23 revision). Its first rule is this document's whole point: *consider
  necessity — evaluate whether the dependency can be avoided by utilizing existing
  components.*
- *Software Engineering at Google* ch. 21, [Dependency Management](https://abseil.io/resources/swe-book/html/ch21.html),
  section "Considerations When Importing". The digital copy is CC BY-NC-ND 4.0, so it
  is cited here rather than reproduced.

Two consequences worth stating plainly. First, the book has no vendoring chapter in
the published edition, which is why `docs/architecture/vendor.md` is this repository's
own rule and not an import. Second, a licence you have not read is not permissive: an
unlicensed repository is legally unusable, and code copied from one is not a shortcut
but a liability.

## The ledger

Anything copied in is recorded where its licence can be audited and its upstream
commit can be re-fetched:

| What copied | Where recorded | Enforced by |
| --- | --- | --- |
| Studio UI under `apps/studio/src/vendor` | `apps/studio/vendor.lock.json`, plus a `vendored:` header per file | `apps/studio/src/vendor/ledger.test.ts` |
| Reference prose under `.agents/skills/reuse-first/references` | a `vendored:` HTML header naming upstream, commit, SPDX id, retrieval date, and drift | review, and the re-copy rule in `docs/architecture/vendor.md` |
| Skills from an upstream pack | `skills-lock.json` | `npx skills update` — never hand-edit this file, and never add a skill to it that upstream does not publish |

A file with no ledger entry is not vendored; it is unsourced.

`skills-lock.json` lists only what upstream publishes. `.agents/skills/reuse-first/`
is this repository's own, so it stays out of the lock: `npx skills update` rewrites
the tracked entries and leaves an untracked directory alone, and
`npx skills experimental_install` restores only what the lock names. That is the
difference between a skill that survives a dependency refresh and one that is
silently deleted.

## What this does not do

It does not license code this repository has not recorded, and it does not authorise
copying a behaviour primitive out of a package to avoid a version bump. It does not
replace `docs/architecture/testing.md`; a reused helper inherits that file's rules
like any other.
