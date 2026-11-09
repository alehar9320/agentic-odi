# PR Readiness Plan — ALL alehar9320 open PRs (newest → oldest)

## Objective
Get every open PR authored by alehar9320 ready for human review and merge.
PR Ready = no merge conflicts with main, CI green, spec fulfilled.
Stop when none remain.

## Per-PR checklist (preparing-a-pr-for-merge skill)
1. Read contract (`gh pr view`, spec, files)
2. Make mergeable: rebase onto origin/main, resolve conflicts, push --force-with-lease
3. Prove diff against spec: tests, contract sync, docs, reuse
4. Turn checks green by reproducing locally
5. Fix PR body; push resolved branch
6. Mark complete, move to next newest

## Completed
| # | PR | Head ref | Verdict | Evidence |
|---|----|----------|---------|----------|
| 1 | #875 Stop announcing a supported state as an outage | openhands/507-delete-supported-state-banners | READY | CLEAN merge, CI=SUCCESS, studio tests 160/160 pass; spec met (deletes 2 supported-state outage banners + tests) |
| 2 | #874 Compose the composer attachment chip | openhands/859-attachment-primitive | READY | CLEAN merge; fixed docs ledger drift (Partial row cited "this PR", count table stale, projection missing row); doc_check.py passes, eslint 0 errors, typecheck clean, studio tests 1529/1529, python tests 2293/2293 pass; pushed ec32ec63 |

## Remaining (newest → oldest)
| # | PR | Head ref | Mergeable | CI | Age |
|---|----|----------|-----------|----|-----|
| 3 | #873 Refuse an over-limit text attachment | openhands/652-refuse-oversized-text-attachment | READY | CLEAN merge, CI=SUCCESS, doc_check passes, eslint 0 errors, typecheck clean, studio tests 1539/1539 pass; spec met (refuse oversized text attachment with chip naming file + limit instead of silently slicing) |
| 4 | #872 AI merge-safe PR trust label | qoder/ai-merge-safe-label | READY | CONFLICT resolved (development.md — kept both "AI merge trust" and "Tiered Automated Triage" sections), CI=SUCCESS, doc_check passes; pushed d555fa02 |
| 5 | #867 Run Python suite in parallel | openhands/751-parallel-python-suite | READY | CLEAN merge; CI test jobs all pass (test 3.10/3.11/3.12, docs, lint, studio, typecheck); 2270 tests pass with `-n auto` in 15.87s locally; only `tauri-build` (Rust) fails — unrelated to pytest-xdist/python changes; pushed |
| 6 | #855 Morning briefing | openhands/issue-583 | READY | CLEAN merge; fixed CI failures — added `briefing` to CORE_LAYERS in test_architecture.py (new module unregistered), ruff-formatted 4 briefing test files; ruff check passes, ruff format passes, pytest 2222/2222 pass, eslint 0 errors, typecheck clean; pushed 0074beb1 |
| 7 | #854 Scene two quote → scored outcome | openhands/issue-594 | READY | CONFLICT resolved (12 files: content.ts, onboarding.css, steps.tsx, FirstRunWizard.tsx, FirstRunWizard.test.tsx, App.test.tsx, SettingsPanel.tsx, sampleLoop.ts, sampleLoop.test.ts, test/a11y.test.tsx, development.md); kept both HEAD's scene-based tour and main's step-based wizard where additive; pushed 7842ae74 |
| 8 | #853 Offline capture arrives later | openhands/issue-580 | CONFLICT | FAILURE | Nov 8 13:07 |
| 9 | #852 Tour rehearses and resumes | openhands/issue-593 | CONFLICT | SUCCESS | Nov 8 12:41 |
| 10 | #841 CI label workflow | opencode/ci-label-automation | CLEAN | SUCCESS | Nov 7 22:26 |
| 11 | #838 Fold PR review-comment triage | skill/fixing-failed-pr | CLEAN | SUCCESS | Nov 7 11:45 |
| 12 | #835 Answer and capture no sidecar | freebuff/2026-11-07-347 | CONFLICT | SUCCESS | Nov 7 09:46 |
| 13 | #829 One box searches everything | openhands/issue-539 | CLEAN | SUCCESS | Nov 7 01:26 |
| 14 | #826 Settings five named sections | openhands/issue-530 | CONFLICT | FAILURE | Nov 7 00:58 |
| 15 | #825 Tour/updates/build facts leave main Settings | openhands/issue-533 | CLEAN | SUCCESS | Nov 7 00:57 |
| 16 | #824 Full disk stops writes | openhands/issue-520 | CLEAN | SUCCESS | Nov 7 00:31 |
| 17 | #822 Export/import workspace new schema | openhands/issue-521 | CONFLICT | SUCCESS | Nov 7 00:21 |
| 18 | #821 Scoped expiring read-only share token | openhands/issue-549 | CLEAN | SUCCESS | Nov 7 00:21 |
| 19 | #815 Capability probes tell the truth | freebuff/515-capability-probes | CONFLICT | SUCCESS | Nov 6 21:22 |
| 20 | #814 Words at the edge | freebuff/698-words-at-the-edge | CLEAN | SUCCESS | Nov 6 21:13 |
| 21 | #806 Name each destination plain words | freebuff/637-navigation-names | CONFLICT | FAILURE | Nov 6 20:31 |
| 22 | #805 Context7 MCP connector preset | opencode/2026-11-06-context7-mcp-preset | CLEAN | SUCCESS | Nov 6 20:31 |
| 23 | #803 Consent domain invariant | openhands/issue-458 | CLEAN | SUCCESS | Nov 6 20:25 |
| 24 | #797 Empty state finished ODI loop | openhands/issue-318 | CONFLICT | SUCCESS | Nov 6 20:16 |
| 25 | #796 Approval gates say what call changes | openhands/555-approval-consequence | CLEAN | FAILURE | Nov 6 20:13 |
| 26 | #795 Delete conversation confirmation | freebuff/643-delete-conversation | CONFLICT | FAILURE | Nov 6 19:49 |
| 27 | #794 Fail site build on broken reference | openhands/571-broken-reference-build | CLEAN | SUCCESS | Nov 6 19:43 |
| 28 | #792 Rename conversation | freebuff/642-rename-conversation | CONFLICT | SUCCESS | Nov 6 19:30 |
| 29 | #788 Stop announcing missing model as outage | freebuff/5518dcbfa7d5167025bfce50 | CONFLICT | SUCCESS | Nov 6 18:42 |
| 30 | #786 Remember why you came back ALH-146 | qoder/ALH-146-next-step | CONFLICT | FAILURE | Nov 6 15:57 |

## Conflicts to resolve (13): #872,#854,#853,#852,#835,#826,#822,#815,#821,#819,#806,#797,#795,#786
## CI failures to fix (6 remaining): #867,#855,#853,#826,#796,#786
