# Reuse before you write: parked design notes

Date: 2026-11-01
Status: **parked, unapproved, unfinished.** This is a hand-off record, not a design
your partner signed. Nothing in it is built: no skill, no rule change, no ADR, no CI
gate. Read the *Open gaps* section — that is the work.

## Intent and the why

Human partners report that agent turns keep re-deriving things that already exist: a
retry loop, a date formatter, a toast component, a markdown renderer — instead of
adopting a dependency, reusing code already in this repository, or copying a proven
implementation. The goal is speed, in the posture of the line the request quoted:
*good artists copy, great artists steal* — inside reasonable bounds (licence,
maintenance, security, and the deliberate non-dependency decisions this repo has made).

Why agents do it, as far as I got: nothing in the instruction layer tells them to look
first. `.agents/rules/agent_instructions.md` says which libraries to use for a few named
concerns (fastmcp, httpx, pydantic, assistant-ui) and forbids re-implementing the
conversation runtime, but there is no step that says "before writing anything new,
search for an existing implementation and report what you found". A rule that only names
outcomes does not create a search habit.

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

## Prior art found on the web (with verification status)

- `senior-engineering-partner` (bjgreenberg; 137 stars; listed on skillsllm.com) contains
  a **"Reuse before you write"** rule — "search for an existing function/utility that
  already does the job before adding a new one", plus a near-duplicate warning. Seen only
  through the marketplace listing: **the repository itself, its licence, and the full text
  are unverified.**
- Stack Overflow, *Building shared coding guidelines for AI (and people too)*
  (2026-03-26): the search snippet says agent guidelines need to be "more explicit,
  demonstrative of patterns, and obvious". **The fetch returned 404, so the URL and the
  content are unconfirmed.**
- *Software Engineering at Google* ch. 20 (Dependencies) and ch. 21 (Vendoring), and
  OpenSSF's component-evaluation guidance: **not examined at all.** These are the two
  sources most likely to be worth citing for the dependency-acceptance bar.
- Whether `obra/superpowers` upstream already ships a reuse skill: **not checked.** If it
  does, import it rather than write our own.

## Shape under consideration (a proposal, not a decision)

A ladder in ascending cost, entered at the top and stepped down only with a reason:

1. **Reuse what is in the repo** — grep for the helper, component, model, or tool that
   already does this; the vendored tree and existing packages count as found objects.
2. **Adopt a declared dependency** — prefer a maintained library over new code when the
   boundary allows it, declared properly.
3. **Copy with a recorded boundary** — `docs/architecture/vendor.md`'s rules, extended
   past studio markup: header, licence, upstream commit, what drifted.
4. **Write it** — only when 1-3 are named and refused, in the plan or the design.

Where that could live, in increasing weight: a row in the `using-superpowers` red-flag
table in `AGENTS.md`; a `General Philosophy` bullet in
`.agents/rules/agent_instructions.md`; a project skill under `.agents/skills/` that fires
before implementation work (authored per `.agents/skills/writing-skills`); a policy doc
alongside `docs/architecture/vendor.md` generalised to the whole repo; ADR 0005 recording
"adopt before you write" as an architecture decision. Which of those, and how many, is
open — see gaps 5 and 8.

## Open gaps

Numbered so the PR body and this file can share one list. Each names the next action.

1. **Read the candidate upstream skills for real.** `gh api repos/bjgreenberg/senior-engineering-partner`
   and fetch its `SKILL.md` and licence; check `obra/superpowers` for an existing reuse
   skill first. Decide whether a reviewer-persona skill is the right import unit at all.
2. **Confirm the citable sources.** SWE-at-Google ch. 20/21, OpenSSF component guidance,
   the correct Stack Overflow URL. Until then, none of them may be cited as settled.
3. **In-repo duplication audit — never ran.** Both `Explore` dispatches failed with
   `Queuing failed. Try again later or enter /model to switch models`. Needed: hand-rolled
   helpers where a library is already a dependency (`apps/studio/src`, `packages/*`,
   `apps/*`), primitives duplicating `apps/studio/src/vendor/components/ui`, repeated
   retry/poll/date/format logic in Python. Without named instances the rule reads as
   advice, and the examples are the part agents follow.
4. **Where the skill lives, and how it reaches every harness.** `.agents/skills/` is
   lock-managed by `npx skills update`; `.opencode/skills/` holds the PM pack; Pi loads a
   package; `AGENTS.md` is the Freebuff session-start surface. Unresolved: does a
   hand-written local skill survive a `skills update`, and must it be registered in
   `skills-lock.json`?
5. **How it triggers unprompted.** The failure is that agents do not think to look.
   Undecided: skill description keywords, a must-search-before-writing gate, where the
   search results must be reported (plan? PR body?), and how it composes with
   `brainstorming` and `test-driven-development` instead of fighting them.
6. **The vendor policy's own loose ends.** `apps/studio/vendor.lock.json` — the ledger
   `docs/architecture/vendor.md` rule three promises — does not exist, and the one copied
   component uses a header in prose ("Copied from the shadcn registry… MIT licensed")
   rather than the specified `// vendored: <url>@<commit> — <SPDX> — local edits:` form.
   Rules one, three, four and five are prose only; rule two is the sole enforced one.
   Decide whether to close these before generalising the policy, and whether to extend
   `boundary.test.ts`-style enforcement to the header/ledger claim.
7. **Reasonable bounds, written down.** The carve-outs above, plus a dependency-acceptance
   bar: licence (SPDX), maintenance signal, CVE review, `uv.lock` and binary-size cost, and
   the workspace-edge discipline in the package-diagram ADR under review on PR #456.
8. **Then the build,** after a design is actually approved: author per
   `.agents/skills/writing-skills`, land the guardrail line, pick the enforcement level
   (prose, ADR 0005, or a CI gate), and update `README.md` plus `docs/` in the same task per
   the README maintenance guardrail.

## How to resume

Read this file, then run gap 3 and gap 1 — the duplication audit and the upstream-skill
fetch — because those two answers decide gaps 5 and 7 rather than merely informing them.
Then restart the design conversation: this session skipped the brainstorming questions at
the partner's request, so goals, non-goals, and anti-goals (what would make a reuse rule a
failure even if it "works") have never been agreed. The session ended on a tool-model
outage, not on a blocker in the idea.
