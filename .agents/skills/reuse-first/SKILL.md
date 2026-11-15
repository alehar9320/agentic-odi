---
name: reuse-first
description: Use when implementing a feature or bugfix and about to add a new source file, helper, component, or third-party dependency — that is, before writing any code this repository or an already-declared package may already provide
---

# Reuse first

**Core principle:** every new file is maintenance you took ownership of; code you
did not have to write is free. Good artists copy, great artists steal.

The measured failure in this repo is not a missing search. Baseline runs searched,
found the near-duplicate, and wrote a third copy anyway. So this skill constrains
the **output**, not the effort.

## The ladder

Work down in cost order. Stop at the first rung that serves the task.

1. **Call what this repo already has.** Search by verb (`clamp`, `formatRelative`,
   `newId`, `retry`), by the type it returns, and by the test that would cover it —
   not by the filename you had in mind. The canonical copies are listed in
   `docs/architecture/reuse.md`.
2. **Use a dependency the workspace already declares.** Read
   `apps/studio/package.json` and the root `pyproject.toml` plus each workspace's.
   A declared package that nothing imports is a cost already paid and never
   collected; using it is free.
3. **Copy proven code in, with provenance.** Fetch the upstream file, keep the
   licence notice, record it in the ledger. `docs/architecture/vendor.md` is the
   rule; a new dependency's fitness is judged by
   `references/foss-adoption.md` in this directory.
4. **Write it fresh** — and say, in one sentence, which of rungs 1-3 failed and
   why. "I would rather own it" is not a reason.

## The report

Any plan, design, or pull request body that adds a source file carries this block,
with these four lines, in this order:

```text
Reuses: <path or package name, or "nothing available">
Near-duplicates considered: <path — refactor-to-share | not applicable, because X>
New code and why: <rung that failed, or "none">
Provenance: <ledger entry added | n/a — nothing copied>
```

A near-duplicate — same logic, slightly different shape — is a refactor-to-share,
not a second copy. Two callers and one behaviour means one function.

## Where the ladder is bounded

- `website/` makes zero third-party requests and loads no webfonts. Rung 2 is closed
  there; rungs 1 and 3 are not — copy the markup in and record it.
- `scripts/*.py` is standard-library only, so it ships with the repo. Prefer a
  helper already in `scripts/`, then stdlib.
- A new cross-package Python import needs the declared workspace edge and its
  `pyproject.toml` dependency added in the same task, or the build breaks for
  whoever comes next.
- `docs/architecture/vendor.md` rule 1 outranks the ladder: streaming, tool
  approval, stores, and markdown parsing stay npm packages, never copies.

`npm run lint` and the vendor tests enforce the copy half. `scripts/pr_guards.py
body-truth` warns when a pull request adds source with no `Reuses:` block.

---

## UI Component Selection Workflow

**Scope:** Applies when adding or changing Studio interaction surfaces (dialogs,
notifications, composer suggestions, menus, popovers, canvas visualizations, or
any user-facing component).

### Decision ladder for UI work

Work down in cost order. Stop at the first rung that serves the task.

1. **Reuse an existing Studio component.** Search `apps/studio/src/components`,
   `apps/studio/src/lib`, and `apps/studio/src/assistant` for a component that
   already implements the required behavior and accessibility. Prefer the
   canonical copies listed in `docs/architecture/reuse.md`.

2. **Use a behavior/accessibility foundation already declared.** The workspace
   declares `radix-ui` (dialog, tooltip, toast, popover, select, tabs, etc.)
   and `assistant-ui` (transcript, composer, approval, branching). If a Radix
   primitive or assistant-ui primitive covers the interaction, compose with it.
   Do not add another foundation library.

3. **Use a specialist library already declared.** `sonner` (toast), `vaul`
   (drawer), `cmdk` (command palette) are declared for focused interactions.
   Use them when the interaction matches their purpose.

4. **Copy reviewed presentation code from a designed component source.** Sources
   such as shadcn/ui, Base UI, Beautiful UI, Rare UI, Magic UI, Aceternity,
   21st.dev, and NumberFlow are *examples*, not required dependencies. If you
   copy presentation markup/styles:
   - Keep the licence notice.
   - Record provenance and any new dependencies in `docs/architecture/vendor.md`
     (the vendor ledger).
   - Adapt colors, typography, and radii to Studio's design tokens — do not
     ship default shadcn styling.
   - The dependency review step (`docs/architecture/references/foss-adoption.md`)
     still applies for any new package.

5. **Write custom behavior** — and say, in one sentence, which of rungs 1–4
   failed and why. "I would rather own it" is not a reason.

### Library categories (for rung 4 reference)

| Category | Purpose | Example sources (not required deps) |
|---|---|---|
| Foundations | Behavior + accessibility primitives | Radix, Base UI, headless UI |
| Specialists | One focused interaction | cmdk (command palette), Vaul (drawer), Sonner (toast), NumberFlow (animated numbers) |
| Designed component sources | Presentation + styling reference | shadcn/ui, Beautiful UI, Rare UI, Magic UI, Aceternity, 21st.dev |

### Restraint rule

**At most one highly decorative or animated standout moment per page.**
Animations, gradients, glassmorphism, particle effects, and similar "wow"
elements count. Exceeding this requires explicit justification in the PR
description.

### Preserved boundaries

- **assistant-ui** owns the transcript, composer, approval prompts, branches,
  and generative UI parts. Do not replace, wrap, or re-implement these.
- **Behavior dependencies** (Radix, assistant-ui, cmdk, Vaul, Sonner) are
  declared at the workspace level. Do not add another dialog, toast, or
  command-palette foundation.
- **Vendor ledger** (`docs/architecture/vendor.md`) is the single source of
  truth for copied code provenance and dependency fitness.
- **Dependency review** follows `docs/architecture/references/foss-adoption.md`
  for any new package.
