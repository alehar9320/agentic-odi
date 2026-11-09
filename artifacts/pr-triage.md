# Open PR triage — 2026-11-09 (main @ 8f8c3e7f)

Scope: every pull request numbered #423–#674 that still has a head ref in this repository.
Each state below is computed from the merged tree (`git merge-tree --write-tree origin/main <pr-head>`),
not from GitHub's cached `mergeable` field. A PR whose squash commit names it in main's history is listed
as superseded, naming that commit.

Counts: pushed-clean 7, needs-human 15, superseded 58, clean-not-touched 6.

| PR | head | state | evidence |
|---|---|---|---|
| #468 | `c95c018f` | pushed-clean | branch `fix/vision-surface-312`, pushed fast-forward, zero conflict markers; pytest 2298 passed; ruff clean; tsc clean; studio lint clean and 141 files passed; website 286 passed; doc_check 0 |
| #480 | `a59c5116` | pushed-clean | branch `qoder/ALH-58-demo-workspace`, pushed fast-forward, zero conflict markers; pytest 2391 passed after extending the branch's parity fixtures for proposals/studies/v2mom; contract snapshot re-pinned with `--inline-snapshot=fix`; ruff clean; tsc clean; studio lint clean and 141 files passed; website 286 passed |
| #605 | `125e2037` | pushed-clean | Merged `origin/main` into `76bff6af`. main's `a74bf71b` already landed the report, so main's files were kept (domain row, objective list, MCP seed split) and the branch's one unique behavior preserved: the `ValidationError` refusal in `_link_outcome`. Dropped the branch's stale `methodology` entry for `traceability.py`, which the merged architecture test caught. Merge `125e2037`. Verified: 718 tests across architecture, MCP traceability, CLI, contract and website, ruff clean, zero markers. |
| #616 | `3b1e26ef` | pushed-clean | branch `alehar9320/hosted-first-run-lands`, pushed fast-forward, zero conflict markers |
| #669 | `6fc49d8a` | pushed-clean | Merged `origin/main` into `196d46a6`; the only conflict was `docs/living-studio.md`. Kept main's newer Composer wording, which separates a refused format from a file that is accepted but unreadable, and kept the branch's **Install** control (main has none, and the manifest is what enables it). Merge `6fc49d8a`. Verified: studio lint 0 errors, `tsc --noEmit` clean, vitest 144 files and 1550 tests, `scripts/doc_check.py` clean, zero markers, and `apps/studio/public/manifest.webmanifest` is linked from `index.html`. |
| #670 | `1fd26ba6` | pushed-clean | branch `qoder/ALH-194-search`, pushed fast-forward, zero conflict markers; pytest 2393 passed; ruff, tsc, studio 141 files, doc_check clean |
| #674 | `245ca5fd` | pushed-clean | branch `openhands/601-starter-cards-light-theme`, pushed fast-forward, zero conflict markers; CI green on GitHub |
| #423 | `c734ae45` | needs-human | Conflicting files: `scripts/vendor_policy.py`, `apps/studio/vendor.lock.json`, `apps/studio/src/vendor/components/ui/button.tsx`, `docs/roadmap.md`. main ships the vendor gate as `fbcae9cb` (licence and dependency policy in Python) and its `vendor_policy.py` differs from this branch's by 346 lines with a different lock shape (60 lines). PR side: `b3dfd772` (a vendor ledger plus the policy test for issue #383). Disagreement: two implementations of the same gate, with different lock formats. Human call: which policy and lock format is canonical, since both would police the same vendored tree. |
| #437 | `696d9753` | needs-human | Conflicting files: `apps/studio/src/components/chat/Conversation.tsx` and its test. main's `d1eb1f8f` rewrote the transcript markup and layout (Micro-touch batch 3, #779). PR side: `7cdb1e59` collapses a turn's tool calls into one run row. Disagreement: the run-row grouping has to be re-expressed on main's new markup, and where it sits in the turn is a design decision. Human call: transcript presentation belongs to the product surface, not to a mechanical merge. |
| #452 | `2fdce0a1` | needs-human | Conflicting files: `apps/studio/src/state/StudioContext.tsx`, `apps/studio/src/state/StudioContext.test.tsx`. main's `d1eb1f8f` rewrote the same boot and navigation block (time, place, history). PR side: `5e59ebc1` reopens the conversation the person left (#447). Disagreement: the PR restores the last conversation on boot while main derives the view from the URL and history. Human call: which boot semantics the Studio keeps when both are asked for. |
| #454 | `3cc7387a` | needs-human | Conflicting files: `apps/studio/src/components/chat/ThreadComposer.tsx`, `apps/studio/src/state/StudioContext.tsx`, `apps/studio/src/state/StudioContext.test.tsx`, `apps/studio/src/test/a11y.test.tsx`. main's `11e06dd7` reworked the composer for pasting text and files together. PR side: `d527245b` names the record the agent is pointed at inside the composer. Disagreement: where the context chip sits and how it composes with main's new composer rows. Human call: composer layout and copy. |
| #470 | `42a624f3` | needs-human | Conflicting files: `website/content/sample-study.json`, `docs/architecture/testing.md`, `docs/development.md`, `docs/roadmap.md`. main's `58a125de` already published a committed sample workspace the landing page reads. PR side: `42a624f3` publishes a different, larger sample (114 more lines of content). Disagreement: two sample workspaces with different fixture content. Human call: which sample the public site ships and therefore what the landing page demonstrates. |
| #481 | `2fca7f0b` | needs-human | Conflicting files: `apps/cli/src/agentic_odi_cli/studies.py`, `backend.py`, `render.py`, `desired_outcomes.py`. main landed the Study entity and its waves in `812699b4` (#640) and has no `studies compare`. PR side: `2fca7f0b` measures a job again and compares what moved (M2-05.2). Disagreement: the PR's compare model predates the Study entity main shipped. Human call: whether compare is built on #640's waves and what a comparison reports, because the study and wave measurement model is the product's core. |
| #482 | `f4da5acc` | needs-human | Conflicting files: `apps/studio-api/src/agentic_odi_studio_api/app.py`, `studio/router.py`. main's `35ab6d11` (#623) pins `/health` to exactly the `{"status":"ok"}` body with no authentication, and `0584dbbb` (#663) puts every `/api` route behind the bearer token. PR side: `faa5454a` makes `/health` equal `/api/health`. Disagreement: the PR's single health answer exposes behind-the-gate detail to an unauthenticated caller, and its test contradicts main's. Human call: whether unauthenticated health may report anything beyond `ok`. |
| #484 | `d7f2f8fe` | needs-human | Conflicting files: `apps/cli/src/agentic_odi_cli/backend.py`, `render.py`, `apps/cli/tests/test_backend.py`, `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py`. The conflict is purely stacking: the branch is built on #480's pre-merge tip and carries its demo commits (`56808431`, `71a1c0ee`), while main has no `tests/contract/test_contract_snapshot.py` yet. Human call: merge order, land #480 and then rebase this branch on it. No behavior is in dispute. |
| #492 | `3fe391fe` | needs-human | Conflicting files: `apps/studio/src/api/studioApi.ts`, `apps/studio/src/App.test.tsx`, `apps/studio/src/bff/capabilities/registry.ts`, `apps/studio/src/components/SettingsPanel.tsx`. main's `f134a708` added the Settings Data section, `d937deb3` queues canvas and evidence writes locally, and `6a803cbc` explains why a local model cannot be reached. PR side: `3fe391fe`, `1c0906a5`, `7bc7c4f4` let the Worker's own no-sidecar answer reach the browser store. Disagreement: whether the Worker's answer or the local queue is the write of record for a browser-only session. Human call: the same write-semantics decision as #616. |
| #496 | `322892fc` | needs-human | Conflicting files: `apps/studio/src/state/StudioContext.tsx`, `apps/studio/src/state/StudioContext.test.tsx`, `docs/roadmap.md`. main's `d1eb1f8f` rewrote the boot and history block. PR side: `2067e4ff` restores the last conversation (#447) and `9ea3298f` adds the conversations list (#446). Disagreement: this branch bundles the restore and list features that main partly replaced and that #452, #490 and #494 each carry separately. Human call: which of the overlapping restore and list PRs is the one to land. |
| #603 | `566a88e4` | needs-human | Conflicting files: `apps/studio/src/lib/sampleLoop.ts`, `apps/studio/src/onboarding/FirstRunWizard.tsx` and their tests, `apps/studio/src/components/SettingsPanel.tsx`. main's `8a8219e3` (#851) shipped scene three's sample loop (see where it lands, then keep or clear). PR side: `1cf284cb` adds a tour that rehearses and resumes where it stopped (#593) on top of that same loop. Disagreement: whether the rehearsal and resume states replace or wrap main's loop. Human call: the first-run tour's flow. |
| #608 | `fbdd19f9` | needs-human | Conflicting files: `apps/studio/src/api/studioApi.ts`, `apps/studio/src/api/studioApi.local.test.ts`, `apps/studio/src/components/SettingsPanel.tsx`, `apps/studio/src/components/chat/Conversation.tsx`, with the branch 24 commits behind main. main's `d1eb1f8f` and `f134a708` reworked the transcript and Settings Data. PR side: `8758faf3` keeps what the browser answered in the browser, alongside an in-browser model ladder. Disagreement: which answer the browser keeps and how the model ladder coexists with main's queued writes. Human call: browser-only model semantics. |
| #609 | `1615d3ab` | needs-human | Conflicting files: `apps/studio/src/api/studioApi.ts`, `apps/studio/src/api/studioApi.local.test.ts`, `apps/studio/src/api/studioApi.test.ts`, `apps/studio/src/banners/catalog.test.ts`. main's `d937deb3` (queued local writes), `38265a0a` (probe schedule) and `f134a708` (Data section) changed the write path. PR side: `1615d3ab` says which write did not happen and `c86b3c3d` lands a browser-only capture in the board. Disagreement: what a failed write reports and which store records it. Human call: the failure and write-of-record semantics of the outbox. |
| #621 | `67ee613d` | needs-human | Conflicting files: `apps/studio/src/state/StudioContext.tsx`, `apps/studio/src/state/StudioContext.test.tsx`, `docs/living-studio.md`. main's `d937deb3` and `d1eb1f8f` rewrote local writes and boot. PR side: `987d80cc` names which store kept a browser-only write and `dc5add6b` names the browser only when the browser kept the board. Disagreement: the wording and the authority of the browser-store claim. Human call: the same outbox provenance decision as #616 and #609. |
| #656 | `a8b1f872` | needs-human | Conflicting files: `packages/core/src/agentic_odi_core/contract.py`, `repository.py`, `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py`, `apps/cli/src/agentic_odi_cli/backend.py`. main's `a74bf71b` added the traceability surface to the contract and tool registry. PR side: `ea9a59f0` adds themes, a named tree over desired outcomes, as new contract tools. Disagreement: themes introduces new tool names and required fields where main re-pinned the contract. Human call: whether themes ships into the published tool surface, which requires an intended contract change. |
| #430 | `7a20f9fc` | superseded | already in main as `d74167c7` feat(studio): recall sent messages with the up arrow (#427) (#430) |
| #431 | `483fc5d6` | superseded | already in main as `53014bc8` feat(studio): say it is still working when output stalls (#431) |
| #432 | `a665bdcc` | superseded | already in main as `f6b67b31` feat(studio): read a reply aloud and stop on Escape (#432) |
| #433 | `46ca4bfc` | superseded | already in main as `4bb4d5f7` feat(studio): dictate a message into the composer (#433) |
| #434 | `98ced67c` | superseded | already in main as `578a5030` feat(core,studio-api,cli): honest model routing tiers with runtime dem |
| #435 | `97dd5b91` | superseded | already in main as `52f24342` feat(studio): quote a passage from a reply into the composer (#435) |
| #436 | `d5cba66e` | superseded | already in main as `81931957` perf(core,studio): measure and fix the cold open on a 1,500-outcome st |
| #438 | `62f443a1` | superseded | already in main as `430f7560` feat(core,mcp-server): evidence-to-outcome proposal engine (#80) (#438 |
| #439 | `112fac37` | superseded | duplicate of #468, whose vision and routes commits it contains (`48482390`, `10078865`); its remaining durability delta against main is 4 insertions and 196 deletions, i.e. main already carries it. Landed by `#468` (pushed `c95c018f`) plus main |
| #449 | `46ca4bfc` | superseded | identical head to #433 (`46ca4bfc`); the shared commit already landed. Landed by `4bb4d5f7` |
| #451 | `8f471c81` | superseded | already in main as `7269ba2d` feat(studio-api,studio): list every conversation with its turn count ( |
| #455 | `5f9e8bda` | superseded | already in main as `e1d93911` feat(architecture): make the package diagram a checked contract (#455) |
| #456 | `a2d36dd2` | superseded | already in main as `753408a0` docs(architecture): CTO critique and ADRs 0002-0004 (#456) |
| #469 | `0caef82c` | superseded | already in main as `58a125de` feat(website): point the landing page at a committed sample workspace |
| #472 | `5982c45a` | superseded | already in main as `83c013d4` docs: document how agents claim work in this repo (#472) |
| #483 | `2f88881d` | superseded | already in main as `5b1e0cf9` fix(studio): prevent unclassified writes from bypassing approvals (#48 |
| #485 | `29071abd` | superseded | already in main as `0b560d37` fix(studio): the first run answers instead of apologising (#309) (#485 |
| #486 | `57d6fb1c` | superseded | already in main as `d7c42531` build(deps-dev): bump ruff from 0.17.1 to 0.17.3 (#486) |
| #487 | `eba597d5` | superseded | already in main as `e2d7e8c4` build(deps-dev): bump mypy from 2.4.0 to 2.4.1 (#487) |
| #488 | `c41c74f9` | superseded | already in main as `3dbc73a8` build(deps-dev): bump pytest from 9.1.1 to 9.2.0 (#488) |
| #489 | `539170bb` | superseded | already in main as `9b992b77` build(deps-dev): bump pytest-asyncio from 1.4.0 to 1.4.1 (#489) |
| #490 | `993491fa` | superseded | main already serves `GET /conversations` and `/conversations/latest` from `list_conversations`. Landed by `7269ba2d` (#451) |
| #494 | `20b24267` | superseded | same conversations-list feature and roadmap line as #490; both already in main. Landed by `7269ba2d` (#451) |
| #497 | `485c6c4d` | superseded | already in main as `4fd4d9d9` Remove roadmap CI gate to prevent merge conflicts (#497) |
| #602 | `e010e7a1` | superseded | already in main as `bb8c46d3` feat(agents): reuse before you write - the ladder, the ledger, and a g |
| #604 | `f9627fd4` | superseded | main shipped the same keep-or-clear sample exit this PR adds in `6ea1756f`. Landed by `8a8219e3` (#851) |
| #606 | `a9ef6698` | superseded | already in main as `8b7532ba` feat(core,mcp-server): a score carries the questions that produced it |
| #607 | `c4278c95` | superseded | already in main as `c793bc95` Records lens: see every stored record in one view (#565) (#607) |
| #610 | `a2d36dd2` | superseded | already in main as `10a72849` docs(architecture): CTO critique and ADRs 0002-0004 (#610) |
| #614 | `80022943` | superseded | already in main as `9e139690` fix(studio): a turn that is not persisted logs a warning instead of va |
| #615 | `1809bd84` | superseded | already in main as `b1d87161` test(connectors): fail when Evidence and EvidenceDraft drift apart (#6 |
| #617 | `14c1a14d` | superseded | already in main as `3637adca` docs(studio): land the assistant-ui ledger with a citations gate (#617 |
| #618 | `4e0fb49a` | superseded | already in main as `c21fe106` fix(core): read the underserved bucket for the opportunity crossing (# |
| #619 | `37e3fdaf` | superseded | already in main as `7086a840` fix(studio): one tab drains the outbox, the other waits (#525) (#619) |
| #620 | `d0c9b1e1` | superseded | already in main as `f8cd044f` feat(studio): save Settings per field and say so (#620) |
| #622 | `7e0fea27` | superseded | already in main as `fe8599c4` fix(studio): boot must not wait on a request that may never answer (#6 |
| #623 | `045db594` | superseded | already in main as `35ab6d11` feat(core,studio-api,studio): gate the database on boot and close it c |
| #624 | `9ca1d443` | superseded | already in main as `cc833ea7` fix(studio): show the saved canvas instead of a skeleton (#624) |
| #626 | `61723630` | superseded | already in main as `99db0a4d` feat(studio): open the records lens from the command palette (#626) |
| #628 | `50445a5c` | superseded | already in main as `4d6e39ed` feat(infra): let the hosted Worker name the release it runs (#628) |
| #629 | `961eb3e2` | superseded | already in main as `d92cd395` fix(studio): read every opportunity score from one threshold and one f |
| #630 | `77fb6527` | superseded | already in main as `12a45460` feat(studio): queue a follow-up while a reply is running (#410) (#630) |
| #631 | `dfef6783` | superseded | already in main as `eff8c51c` test(studio): pin that scores are compared stored and shown rounded (# |
| #632 | `c6da2b7d` | superseded | already in main as `371cf6a7` feat(studio): an offline page that names what still works (#546) (#632 |
| #634 | `9df381a2` | superseded | already in main as `30a57d84` feat(studio): open one record in full and name what the store never he |
| #636 | `13354950` | superseded | already in main as `42258cf6` feat(studio): one storage-facts selector for where the data lives (#63 |
| #640 | `be37d7e7` | superseded | already in main as `812699b4` feat(core,cli,mcp,studio): add the Study entity and its waves (#640) |
| #644 | `6dba7592` | superseded | already in main as `1fab1d27` fix(core): stop inventing a rating an outcome never had (#644) |
| #655 | `babb59cd` | superseded | already in main as `92b23fba` feat(studio): a history list you can switch back to (#655) |
| #661 | `b466efd6` | superseded | already in main as `67c673d5` docs(architecture): name core's four layers and record the split trigg |
| #663 | `a3d36ca8` | superseded | already in main as `0584dbbb` feat(studio-api): require bearer token on /api routes (#663) |
| #664 | `00d69df2` | superseded | already in main as `8f31f298` fix(core): judge a service by the shared scoring fixture (#664) |
| #665 | `770bd834` | superseded | already in main as `9dc796d2` fix(studio): render the evidence lens's loading, failure and saved-cop |
| #667 | `a1dc3d43` | superseded | already in main as `e33f4c6b` fix(studio): keep evidence reordering on the row, not its form control |
| #668 | `c8f650ce` | superseded | already in main as `b645a9b1` Paint the shell and the right theme before JavaScript runs (#668) |
| #671 | `5f8af677` | superseded | already in main as `4f0f9b6d` test(website): pin the CI job that runs the site suite (#570) (#671) |
| #672 | `75756d88` | superseded | already in main as `46a5bda4` fix(studio): keep cited, hypothesis, and uncited claims in Markdown ex |
| #673 | `45bb643b` | superseded | already in main as `b8bfd8d2` Make contrast a build gate (#543) (#673) |
| #450 | `eebf401c` | clean-not-touched | merge-tree is clean against main; already mergeable, outside this pass's merge list |
| #453 | `10041ebc` | clean-not-touched | merge-tree is clean against main; already mergeable, outside this pass's merge list |
| #627 | `39b7e664` | clean-not-touched | merge-tree is clean against main; already mergeable, outside this pass's merge list |
| #633 | `0eb02cfb` | clean-not-touched | merge-tree is clean against main; already mergeable, outside this pass's merge list |
| #641 | `c80789fa` | clean-not-touched | merge-tree is clean against main; already mergeable, outside this pass's merge list |
| #651 | `614337fb` | clean-not-touched | merge-tree is clean against main; already mergeable, outside this pass's merge list |

## Notes

- `pushed-clean` means the branch carries current `main`, was pushed fast-forward (never force-pushed), has zero
  conflict markers, and passed the default tier locally (`uv run pytest`, `ruff check`, `tsc --noEmit`, studio lint
  and vitest, website pytest, `scripts/doc_check.py`). CI was not awaited after any push.
- `needs-human` rows name the conflicted files, the commit on `main` that embodies main's side, the branch commit that
  embodies the PR's side, the behavior the two disagree about, and why only a person can choose between them.
- `superseded` rows name the commit, and pull request where the subject carries one, that already landed the work.
- Re-confirmed at the end of this pass, `main @ 8f8c3e7f`: `qoder/ALH-58-demo-workspace` still points at `a59c5116`
  (#480) and `fix/vision-surface-312` at `c95c018f` (#468); `git merge-tree --write-tree origin/main <head>` is clean
  for both, and `git grep '^<<<<<<<'` over their trees finds zero conflict markers.
- `#482` and `#616` were left untouched by instruction; `#616` is already pushed-clean from an earlier pass.
- `doc_check.py` reports assistant-ui ledger drift in a checkout whose first-parent history is a PR branch; the same
  script is clean at `main` and in CI's merge ref, where the merge commit's first parent is main.
