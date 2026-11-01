# Reuse before you write: the design, its evidence, and what it enforces

Date: 2026-11-01
Status: **built on this branch.** It was first parked as notes in the draft of this pull
request, then resumed: the eight open gaps are closed one by one under *Gap-by-gap*, and
*Evidence* records the baseline runs that decided the shape of the guidance. No design
conversation was ever held — the partner opted out of the brainstorming questions — so
every choice below is mine and is labelled as such, not agreed.

## Intent and the why

Human partners report that agent turns keep re-deriving things that already exist: a
retry loop, a date formatter, a toast component, a markdown renderer — instead of
adopting a dependency, reusing code already in this repository, or copying a proven
implementation. The goal is speed, in the posture of the line the request quoted:
*good artists copy, great artists steal* — inside reasonable bounds (licence,
maintenance, security, and the deliberate non-dependency decisions this repo has made).

The first diagnosis here was wrong, and the baseline runs in *Evidence* corrected it. The
hypothesis was that nothing tells agents to look, so no search habit exists. What actually
happens is a search — a thorough one — followed by a third copy anyway, because a
near-duplicate is easier to walk around than to consolidate. That is why the delivered
guidance constrains the **report** rather than the effort.

## What is already here (verified this session)

The repo is **not** starting from zero. It already has reuse precedent, including one
written policy:

- **`docs/architecture/vendor.md` — "Vendor alley: copied UI".** Five rules for code we
  copy in: behaviour primitives are dependencies and only presentation is vendored;
  copied files take props and never read app state; every vendored file carries a
  provenance header *and* a ledger entry; one surface per pull request, 400 changed
  lines maximum; a re-copy diff must stay possible. Rule two is enforced twice —
  `no-restricted-imports` in `apps/studio/eslint.config.js` and a resolving test in
  `apps/studio/src/vendor/boundary.test.ts`. **This is the closest thing to the requested
  best-practice material, and it is ours.** It is scoped to studio UI markup only.
- **Imported artefacts are normal here.** 69 PM skills vendored from Paweł Huryn's
  pm-skills into `.opencode/skills/`; `apps/studio/src/vendor/components/ui/button.tsx`
  header records it as copied from the shadcn registry (`ui.shadcn.com`, MIT); the
  website vendors its diagram runtime because `script-src 'self'` rules out a CDN
  (`website/dist/assets/diagrams.js`). Superpowers skills are installed and refreshed with
  `npx skills add … --agent universal --copy -y` / `npx skills update -y` and hashed in
  `skills-lock.json` (see `docs/superpowers/freebuff-setup.md`). **A path for importing
  published best-practice material already exists.**
- **Design docs already argue this way when they remember to.**
  `docs/superpowers/specs/2026-10-26-banner-system-design.md` and
  `docs/superpowers/plans/2026-10-26-banner-system.md` route every notice through
  `@radix-ui/react-toast` "so live-region semantics, timers, and dismissal come from the
  library, not hand-rolled code";
  `docs/superpowers/specs/2026-10-26-agent-pr-labeler-design.md` has a "reused, not
  invented" section (reuse the existing `area/*` and `ready-for-merge` labels, drop one
  GitHub action by testing the logic in-repo). Those wins arrived per-spec, by whoever
  wrote that spec — they are not a standing instruction.
- **Deliberate non-dependencies that bound the rule.** The website plan commits to "zero
  third-party requests, zero webfonts, zero CDN, zero analytics"
  (`docs/superpowers/plans/2026-10-22-github-pages-redesign.md`); the labeler plan says
  "no third-party dependencies in `scripts/*.py`. Stdlib only"
  (`docs/superpowers/plans/2026-10-26-agent-pr-labeler.md`); the packaged CLI ships a
  binary, so a new Python dependency costs install size and lock churn. A reuse rule that
  ignores these would trade one failure mode for another.

## Prior art, as verified

- **Imported, not rewritten:** `senior-engineering-partner` (bjgreenberg) at commit
  `dc3e92227aee137ad48da8ccd9b0a44251ff7664`, **Apache-2.0**. Its `SKILL.md` carries the
  rule this design was going to invent — "Search for an existing function/utility that
  already does the job before adding a new one. A near-duplicate (same logic, slightly
  different shape) is a refactor-to-share, not a second copy" — and
  `references/foss-adoption.md`, the dependency-acceptance gate. The second file is
  vendored verbatim under `.agents/skills/reuse-first/references/` with a provenance
  header; the rule is quoted with attribution. The persona skill around it is *not*
  imported: a reviewer persona is the wrong unit for this repo, which already has its
  own review prompts.
- `obra/superpowers` v7.0.1 — the newest tag at the time of writing — ships no
  reuse-first rule: `skills/writing-plans/SKILL.md` at `main` has no reuse slot and a
  code search for a `Reuses:` marker returns nothing. Related issue #2614 ("Reuse-first
  planning") is closed but not reflected upstream. So there was nothing to `skills add`,
  and this skill is written by hand for that reason.
- OpenSSF Best Practices WG, *Concise Guide for Evaluating Open Source Software*
  (2025-04-23 revision), <https://best.openssf.org/Concise-Guide-for-Evaluating-Open-Source-Software.html>.
  Read in full. Its first rule is the whole argument: "evaluate whether the dependency
  can be avoided by utilizing existing components."
- *Software Engineering at Google* ch. 21, *Dependency Management*, section
  "Considerations When Importing", <https://abseil.io/resources/swe-book/html/ch21.html>.
  Read in full. **The chapter numbers in the first draft of these notes were wrong**:
  ch. 20 is Static Analysis, and there is no vendoring chapter in the published edition
  — which is why `docs/architecture/vendor.md` had to be this repository's own rule.
  The digital copy is CC BY-NC-ND 4.0, so it is cited, never copied in.
- **Dropped:** Stack Overflow, *Building shared coding guidelines for AI (and people
  too)*. Every fetch 404'd and the URL could not be reconstructed, so it is not cited
  anywhere in the delivered documentation. A citation you cannot open is not prior art.

## Decisions

A ladder in ascending cost, entered at the top and stepped down only with a reason:

1. **Reuse what is in the repo.**
2. **Use a dependency the workspace already declares.**
3. **Copy with a recorded boundary** — `docs/architecture/vendor.md`, now generalised.
4. **Write it** — only when 1-3 are named and refused.

Where it lives, and why each piece:

- `.agents/skills/reuse-first/SKILL.md` — the behaviour. 470 words, inside the
  500-word budget `.agents/skills/writing-skills` sets, description = triggers only.
- `docs/architecture/reuse.md` — the policy: the ladder, the canonical owners, the
  bounds, the acceptance bar, the ledger table. Separated because the skill is loaded
  by agents under pressure and the policy is read by a reviewer.
- `.agents/rules/agent_instructions.md` §4 — one `General Philosophy` bullet, so the
  ladder is in force for harnesses that never load the skill.
- `AGENTS.md` Project Instructions — one bullet with the red-flag phrasing ("let me
  write a small utility first"), because that file is the session-start surface every
  integration reads.
- `scripts/pr_guards.py body-truth` — the mechanical half, advisory only.
- **No ADR.** ADRs in `docs/architecture/adr/` record architecture decisions; this
  changes no boundary, and the policy doc plus the gate are the durable artefacts. The
  sequence runs to 0004, and 0002 already owns the workspace-edge rule this policy
  defers to. If a later task turns the advisory warning into a blocker, that is 0005.

**Form of the guidance, chosen from the baseline failure.** The failure is not
skipping a rule under pressure — it is producing the wrong shape after a correct
search. `.agents/skills/writing-skills` says prohibitions backfire on that failure
("don't write a third copy" invites negotiation) and a recipe does not: state what the
output *is*. Hence the four-line `Reuses:` block as a required slot, plus one CI warning
that fires when the slot is empty.

## Gap-by-gap, what closed each one

1. **Upstream material** — fetched and read; Apache-2.0; one file vendored with a
   header, one rule quoted. See *Prior art*.
2. **Citable sources** — OpenSSF and SWE ch. 21 verified by fetch; the chapter numbers
   in the earlier notes were wrong and are corrected above; the Stack Overflow article
   is dropped as unrecoverable.
3. **Duplication audit** — ran, and the instances became the canonical-owner table in
   `docs/architecture/reuse.md`. The strongest: `@assistant-ui/react-markdown` is
   declared in `apps/studio/package.json` and imported nowhere, while
   `apps/studio/src/lib/markdown.ts` hand-parses Markdown for the transcript — the
   duplicate that also slipped past §5 of the guardrails, which did not name rendering.
   Others: `radix-ui` Dialog declared but used only under `src/vendor` while four
   surfaces hand-build `role="dialog"` over `lib/useFocusTrap.ts`; `bff/id.ts newId()`
   bypassed by inline id construction in `state/StudioContext.tsx`; `clamp()` in
   `ui/primitives.tsx` re-inlined in `ui/cards.tsx` and
   `components/canvas/OpportunityLandscape.tsx`; `urllib.request.urlopen` in
   `packages/connectors/src/agentic_odi_connectors/rest/connector.py` and
   `marketplace.py` beside the declared `ConnectorHTTPClient`; the same in
   `apps/cli/src/agentic_odi_cli/update.py` while `apps/cli` declares `httpx`; manual
   `strftime("%Y-%m-%dT%H:%M:%SZ")` in `apps/cli/src/agentic_odi_cli/profile.py` and
   `flags.py` where `datetime.isoformat()` is used elsewhere. Honest negatives: the
   banner system does use `@radix-ui/react-toast` rather than a hand-rolled live region,
   `cn` exists once, and the Python `while True` loops are REPL and pagination, not
   retry.
4. **Where a hand-written skill survives** — tested, not assumed. In a scratch project
   with this repo's `skills-lock.json`, `npx skills update brainstorming -y` rewrote the
   tracked skill and left the untracked `reuse-first/` directory untouched. The CLI has
   no prune in `update` (`remove --all` is explicit, `experimental_install` restores
   only what the lock names). Conclusion: **stay out of `skills-lock.json`** — an entry
   with no upstream `source` is how the next `experimental_install` deletes the skill.
5. **How it triggers unprompted** — the report slot is the trigger: it is asked for by
   the skill, the guardrail bullet, and the PR-body gate, and the gate is the only one
   of the three that cannot be skipped by an agent that never loads a skill file.
6. **The vendor policy's loose ends** — `apps/studio/vendor.lock.json` now exists, the
   one copied component was rewritten into the canonical header form, and
   `apps/studio/src/vendor/ledger.test.ts` fails the suite when a file in that tree is
   undeclared or a header stops agreeing with its entry. Registry items have no commit,
   so the checkable handle is the sha256 of the fetched artefact; the upstream JSON was
   re-fetched to compute it, and the copied file diffed against it — one import line and
   the header are the only drift, exactly as recorded.
7. **Reasonable bounds** — written as conditionals in the skill and as *The bounds* in
   the policy: `website/` (no third-party requests), `scripts/*.py` (stdlib only), the
   packaged CLI binary (`uv.lock` and size), and the workspace-edge discipline. Rule one
   of `docs/architecture/vendor.md` outranks the ladder: behaviour primitives stay
   dependencies.
8. **The build** — this PR.

## Evidence

Baseline (RED), before the skill existed, both tasks run in throwaway worktrees:

- A Studio relative-time task searched, found `formatRelativeTime` in
  `apps/studio/src/components/notifications/CatchUpFeed.tsx` and `describeCheckedAt` in
  `apps/studio/src/updater/machine.ts`, then **created a new** `lib/relativeTime.ts`
  beside both and left the duplicates standing.
- A Python retry-and-backoff task found `ConnectorHTTPClient(retries=3)`,
  `retryable_for_code()`, and `RateLimitError.retry_after`, then **created a new**
  `studio/retry.py` plus nine tests, hand-rolling an exponential loop no dependency was
  missing.

With the skill in place, the same two prompts, dispatched fresh:

- The Studio run produced the `Reuses:` block unprompted, named both near-duplicates,
  and **refactored them to share one module**, deleting the private helper and making
  `describeCheckedAt` delegate. Rung 2 was checked and closed on the record (no
  date library declared).
- The Python run **created no file at all.** It read the openai SDK's own retry and
  backoff constants, found that the 2-second `asyncio.wait_for` was cancelling the
  SDK's backoff, and fixed the deadline instead of writing a loop — while still naming
  `ConnectorHTTPClient` and `retryable_for_code` and saying why neither applied.

Both runs disclosed what they reused and what they nearly duplicated. That is the change
the design was for, and it is the difference between this skill and a reminder.

## Left as follow-up work, deliberately

- **Fixing the audit's eight instances.** Each is its own pull request; the policy says
  so in as many words. Landing a rule and a 2,000-line refactor together is how both
  get reverted.
- **Turning the advisory `Reuses:` warning into a blocker,** if warnings prove ignored —
  ADR 0005, per *Decisions*.
- **The `apps/studio/node_modules` friction:** both verification runs had to symlink it
  out of the main workspace to run vitest in a worktree. Unrelated to reuse, worth a
  task of its own.
- **`.opencode/skills/` and the Pi package** carry the PM pack and Superpowers
  respectively; neither was given this skill, since `AGENTS.md` and
  `.agents/rules/agent_instructions.md` already reach those harnesses with the ladder.
  If a harness turns out to miss it, the fix is its instructions file, not a second copy
  of the skill.
- **A second look at §5 of the guardrails.** It now names markdown rendering; the same
  treatment may be owed to dialogs, which are duplicated four times against a declared
  library.

