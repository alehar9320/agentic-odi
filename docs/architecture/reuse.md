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
| Markdown rendering | `@assistant-ui/react-markdown` (`MarkdownTextPrimitive`, plus the shared `mdComponents` map in `apps/studio/src/components/chat/Markdown.tsx`) | none left — the hand-written parser under `apps/studio/src/lib/` was deleted in #394 |
| Dialog, focus trap, dismissal | `radix-ui` (declared; used only under `src/vendor`), rendered through the shared `apps/studio/src/vendor/components/ui/dialog.tsx` primitive | `apps/studio/src/lib/useFocusTrap.ts` and the remaining hand-built `role="dialog"` surfaces (`ChangelogModal.tsx`, `ShareSheet.tsx`, `FirstRunWizard.tsx`) |
| Opportunity score wording | `apps/studio/src/lib/odi.ts` (`formatOpportunityScore`, `isUnderserved`, `UNDERSERVED_THRESHOLD`) | `apps/studio/src/lib/records.ts` prints the stored number as-is, on purpose — that table reports what the store returned |
| Number clamping | `apps/studio/src/ui/primitives.tsx` | `apps/studio/src/ui/cards.tsx`, `apps/studio/src/components/canvas/OpportunityLandscape.tsx` |
| Which host the app is running in | `apps/studio/src/bridge/runtime.ts` (`detectRuntime`, `runtimeFacts`) | `isTauri()`/`isInstalled()` read directly by a caller that then re-derives host or install state |
| The build version on screen | `apps/studio/src/lib/version.ts` (`STUDIO_VERSION`, `versionLabel`) | any component carrying its own version literal |
| Id minting | `apps/studio/src/bff/id.ts` | inline id construction in `apps/studio/src/state/StudioContext.tsx` |
| HTTP with retries | `packages/connectors/src/agentic_odi_connectors/http.py` | `urllib.request.urlopen` in `rest/connector.py` and `marketplace.py` |
| HTTP from the CLI | `httpx` (declared by `apps/cli`) | `urllib.request.urlopen` in `apps/cli/src/agentic_odi_cli/update.py` |
| ISO-8601 timestamps | `datetime.isoformat()` | `strftime("%Y-%m-%dT%H:%M:%SZ")` in `apps/cli/src/agentic_odi_cli/profile.py` and `apps/cli/src/agentic_odi_cli/flags.py` |
| Handing a file to the browser's save dialog | `downloadFile` in `apps/studio/src/lib/download.ts` | the inline blob-and-anchor `save` in `apps/studio/src/diagnostics/DiagnosticsModal.tsx`, which revokes its object URL in the same turn as the click |
| Structural rules for artifact HTML | `scripts/artifact_a11y.py` (stdlib `html.parser`, six rules) with its inventory in `scripts/artifact_renderers.py` | none left — the four heading, anchor and decorative-svg regexes in `website/tests/test_site.py` were folded in rather than kept as a second opinion |

## Studio interaction surfaces (audit, 2026-11-15)

This is the canonical record of where interaction behavior lives in the Studio,
whether it is reusable library behavior or product-specific presentation/state,
and what to do next. It is not a migration plan; no dependencies or components
change here.

| Surface | Current owner / implementation | Behavior vs presentation & state | Recommendation | Reason |
| --- | --- | --- | --- | --- |
| Conversation transcript, composer shell, thread/list primitives | `@assistant-ui/react` runtime + thread/composer/message primitives in `apps/studio/src/assistant/*`, `components/chat/*` | Reusable conversation behavior (streaming, message model, composer/thread mechanics) owned by the library; Studio owns ODI-specific message parts, copy, and layout | **adopt** | Assistant-ui is the established behavior owner for conversation surfaces; keep extending through its primitives rather than parallel transcript/composer mechanics. |
| Notifications (toasts/banners) | Radix toast stack via `banners/Banner.tsx`, `banners/BannerStack.tsx` (`@radix-ui/react-toast`, `Toast.Provider`/`Viewport`/`Root`/`Action`/`Close`), fed by `BannerToasts` + `state/notices` | Reusable notification behavior and accessibility come from Radix Toast; banner kinds, copy, actions, and when notices are raised are product state/presentation | **adopt** | Existing Radix toast stack is the notification owner; new notification behavior should reuse it, not introduce a second toast mechanism. |
| Standard modal dialogs (release notes, diagnostics export, share link, connector suggestion, first-run wizard) | `diagnostics/DiagnosticsModal.tsx` and `components/customize/ConnectorSuggestionModal.tsx` render through the shared `apps/studio/src/vendor/components/ui/dialog.tsx` primitive; `components/ChangelogModal.tsx`, `components/ShareSheet.tsx` and `onboarding/FirstRunWizard.tsx` still hand-build `role="dialog"` with `useFocusTrap`/Escape/scrim | Dismissal, focus trapping, modality, and `aria` dialog semantics are generic interaction behavior; panel content and product flows are Studio-specific presentation/state | **adopt** (shared Dialog primitive) | The already-declared `radix-ui` Dialog primitive now owns dismissal/focus/modality for diagnostics and connector suggestion; migrating the remaining hand-built surfaces is follow-up work (issues #1001, #1002, #1004), product copy/layout stays local. |
| Inline composer slash-command suggestions | `components/chat/composerParts.tsx` + `lib/commands.ts` (`CommandPalette`, `paletteOpenFor`) as an inline, draft-driven `listbox` over Studio command definitions | Selection/highlighting behavior is small and tightly coupled to the composer draft and ODI command registry; visual treatment matches the composer | **keep** | Inline command suggestions are product-specific composer behavior/state; do not automatically replace with `cmdk` or a generic command menu library. |
| Menus and lightweight popovers | Bespoke anchors/dropdowns in context (e.g. thread/history affordances and canvas-local actions) rather than a shared menu primitive | Interaction is contextual to the owning surface and its state; visuals are product-specific | **keep** (revisit only if a menu becomes a repeated, generic pattern) | Current menus are surface-specific; introducing a generic menu library now would be premature without repeated shared behavior. |
| ODI canvas & visualizations (job map, opportunity landscape, segment/evidence/thesis/capture views) | Canvas components in `components/canvas/*` rendering ODI domain entities and scores | Domain visualization and product meaning are the presentation/state; interactions are specific to ODI artifacts, not generic UI widgets | **keep** | ODI visualizations encode product/domain behavior and should not be marked for automatic replacement with generic charting or UI libraries. |

These rows are the record of an audit, not a to-do list with a deadline. Fixing them
is ordinary refactoring, one pull request per concern.

## Interaction surface audit

A surface-by-surface read of `apps/studio/src`, recording the current owner and an
`adopt`, `keep`, or `revisit` recommendation for each interaction surface. This is
the record of an audit, not a migration plan: no components are moved and no
dependencies are added here. Conventional surfaces point at the libraries already
declared in the workspace; ODI-specific visualizations and composer behavior are
product presentation and state, not generic-library replacements.

| Surface | Files | Owner | Recommendation | Reason |
|---|---|---|---|---|
| Dialogs, focus trap, dismissal | `ChangelogModal.tsx`, `ShareSheet.tsx`, `FirstRunWizard.tsx`, `StudioBar.tsx` (`role="dialog"` ask), `useFocusTrap.ts`; `DiagnosticsModal.tsx` and `ConnectorSuggestionModal.tsx` use the shared `vendor/components/ui/dialog.tsx` | `radix-ui` (declared; used under `src/vendor`) | adopt | `DiagnosticsModal` and `ConnectorSuggestionModal` now render through the shared Radix Dialog primitive (#1004); the remaining hand-built `role="dialog"` surfaces are the consolidation target (issues #1001, #1002). |
| Menus and lightweight popovers | `StudioBar.tsx` history list (`role="menu"`/`menuitem`, Escape close), `More actions` menu (`role="menu"`/`menuitem`, Escape close) | none declared — hand-built anchors/dropdowns | keep | Menus are surface-specific to StudioBar's state and copy; no repeated generic menu pattern exists yet. Revisit only if a second surface needs the same menu mechanics. |
| Notifications | `BannerStack.tsx`, `Banner.tsx`, `useToasts()` in `StudioContext.tsx` | `@radix-ui/react-toast` | keep | The Radix toast stack is already the notification owner; every banner portals into the single registered viewport. |
| Conversation stage (viewport, message list, parts, branch picker) | `ChatStage.tsx`, `Conversation.tsx`, `ThreadComposer.tsx`, `SelectionToolbar.tsx`, `QueueLane.tsx`, `StallNotice.tsx` | `@assistant-ui/react` | keep | assistant-ui owns the conversation runtime; these encode product behavior on top of it and are not replaceable by a generic dialog library. |
| Inline composer suggestions / slash commands | `composerParts.tsx` (`CommandPalette`, `SuggestionPills`), `Composer.tsx`, `ThreadComposer.tsx` | `@assistant-ui/react` | keep | Inline composer suggestions are assistant-ui behavior; not marked for automatic replacement with `cmdk` or a generic library. |
| ODI visualizations | `OpportunityLandscape.tsx`, `JobMap.tsx`, `SegmentBoard.tsx`, `MemoryPanel.tsx`, `DirectCapture.tsx`, `EvidenceStream.tsx` | product-specific (Studio) | keep | ODI-specific visualizations encode domain behavior and are not candidates for generic libraries. |
| Markdown rendering | `lib/markdown.ts` | `@assistant-ui/react-markdown` (declared, imported nowhere) | revisit | Declared but unused; a stray local copy exists. Covered by the canonical owners table. |


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
| Studio UI under `apps/studio/src/vendor` | `apps/studio/vendor.lock.json`, plus a `vendored:` header per file | `apps/studio/src/vendor/ledger.test.ts` and `tests/scripts/test_vendor_policy.py` |
| The npm packages those copies depend on | the dependency table in `docs/architecture/vendor.md` | `tests/scripts/test_vendor_policy.py`, which also holds every recorded licence to its SPDX allowlist |
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
