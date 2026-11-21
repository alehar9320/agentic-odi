---
title: Test map
blurb: Every test file and the one line it says about itself.
nav_group: Build
nav_order: 5
slug: test-map
---

# Test map

Every test file in the workspace, with the description the file carries itself:
the first line of a Python module's docstring, or the first comment in a
TypeScript test. A file with no description still appears, named, so nothing can
hide from the map.

Do not edit the table by hand. Write a docstring on the test you added, then run
`uv run python scripts/docs_index.py --write`. The tier rules stay prose in
[`.agents/workflows/test.md`](../../.agents/workflows/test.md); the layout,
isolation, and coverage rules stay in
[the testing strategy](../architecture/testing.md).

## Every test file

<!-- BEGIN GENERATED: test-map -->
| Path | Covers |
|---|---|
| `apps/cli/tests/conftest.py` | Shared conftest for CLI tests. |
| `apps/cli/tests/test_backend.py` | Backend seam: local SQLite backend and remote MCP backend. |
| `apps/cli/tests/test_backend_edges.py` | Edge-case tests for backend validation, parsing, and MCP failures. |
| `apps/cli/tests/test_backend_selection.py` | — |
| `apps/cli/tests/test_build_info.py` | — |
| `apps/cli/tests/test_chat_cli.py` | Tests for the interactive CLI chat. |
| `apps/cli/tests/test_chat_runtime.py` | Runtime tests for the interactive chat loop and command handlers. |
| `apps/cli/tests/test_chat_wizard.py` | Tests for the /connect wizard. |
| `apps/cli/tests/test_cli.py` | — |
| `apps/cli/tests/test_cli_edges.py` | Edge tests for the root CLI callback and update re-exec. |
| `apps/cli/tests/test_connectors_cli.py` | — |
| `apps/cli/tests/test_connectors_edges.py` | Edge-case tests for the connectors CLI adapter. |
| `apps/cli/tests/test_context.py` | Tests for the CLI's global backend context. |
| `apps/cli/tests/test_customer_outcomes_cli.py` | Customer Outcomes CLI: local backend, aliases, output, and errors. |
| `apps/cli/tests/test_data_export.py` | `data-export` writes a restorable snapshot of the local store. |
| `apps/cli/tests/test_data_path.py` | `odi data path` prints the resolved ODI and Studio database paths. |
| `apps/cli/tests/test_desired_outcomes_cli.py` | Tests for desired Outcomes CLI commands. |
| `apps/cli/tests/test_evidence_cli.py` | Tests for the evidence CLI group. |
| `apps/cli/tests/test_insight_commands.py` | The insight commands work on the local backend, without an MCP server. |
| `apps/cli/tests/test_jobs_cli.py` | Tests for the Jobs CLI command group. |
| `apps/cli/tests/test_mascot.py` | The Odi banner: shape, colour, and when it is allowed to appear. |
| `apps/cli/tests/test_onboard.py` | Tests for first-run onboarding signal extraction and gating. |
| `apps/cli/tests/test_paths.py` | — |
| `apps/cli/tests/test_persistence.py` | Acceptance test: every ODI entity survives a fresh repository. |
| `apps/cli/tests/test_profile.py` | — |
| `apps/cli/tests/test_profile_cli.py` | Tests for profile management and setup wizard CLI commands. |
| `apps/cli/tests/test_render.py` | Rendering: tables, blocks, JSON, truncation, and unicode safety. |
| `apps/cli/tests/test_schedule_cli.py` | — |
| `apps/cli/tests/test_segments_cli.py` | Tests for the segments and strategy CLI groups (Stages 5 and 6). |
| `apps/cli/tests/test_settings_cli.py` | Tests for settings and feature flags CLI commands. |
| `apps/cli/tests/test_signals_cli.py` | Tests for the signals CLI group. |
| `apps/cli/tests/test_startup_perf.py` | Guard against importing heavy dependencies at CLI module load time. |
| `apps/cli/tests/test_stats_cli.py` | `odi stats` — the funnel, printed from the machine that counted it. |
| `apps/cli/tests/test_steps_cli.py` | — |
| `apps/cli/tests/test_studies_cli.py` | Tests for the studies CLI group (ALH-69, M2-05). |
| `apps/cli/tests/test_summary_cli.py` | Tests for the `odi summary` report. |
| `apps/cli/tests/test_update.py` | — |
| `apps/cli/tests/test_update_check.py` | — |
| `apps/cli/tests/test_update_command.py` | — |
| `apps/cli/tests/test_update_edges.py` | Edge-case tests for the self-update engine and background updater. |
| `apps/cli/tests/test_version_flag.py` | — |
| `apps/cli/tests/test_wizard_cli.py` | Tests for the interactive ODI entity creation wizard command. |
| `apps/mcp-server/tests/conftest.py` | — |
| `apps/mcp-server/tests/mcp_failures.py` | How these tests read a failing tool's answer. |
| `apps/mcp-server/tests/test_context_tools.py` | — |
| `apps/mcp-server/tests/test_customer_outcomes.py` | Tests for Customer Outcome entities. |
| `apps/mcp-server/tests/test_graceful_shutdown.py` | Tests for the MCP server's graceful shutdown path. |
| `apps/mcp-server/tests/test_health.py` | The store health tool reports readiness without touching ODI data. |
| `apps/mcp-server/tests/test_odi.py` | — |
| `apps/mcp-server/tests/test_parity.py` | — |
| `apps/mcp-server/tests/test_port_config.py` | The MCP server port must be overridable for dev and multi-instance runs. |
| `apps/mcp-server/tests/test_segments.py` | Stage 5 and Stage 6 round-trip through the live MCP registry. |
| `apps/mcp-server/tests/test_server_tools.py` | — |
| `apps/mcp-server/tests/test_signals.py` | The three signal tools round-trip through the live MCP registry. |
| `apps/mcp-server/tests/test_tool_branches.py` | Branch coverage for MCP tool prompts, errors, and full updates. |
| `apps/mcp-server/tests/test_tool_progress.py` | Long tools report progress so the Studio can stop looking hung. |
| `apps/mcp-server/tests/test_tool_spec_validation.py` | Startup validation refuses a contract that the server cannot serve. |
| `apps/mcp-server/tests/test_tool_timing.py` | Every MCP tool call emits one timing line, so a slow tool is visible. |
| `apps/mcp-server/tests/test_tools.py` | — |
| `apps/mcp-server/tests/test_traceability_tools.py` | The traceability tools round-trip through the live MCP registry. |
| `apps/studio-api/tests/conftest.py` | Isolate each test's Studio memory database from the developer's home. |
| `apps/studio-api/tests/test_api.py` | — |
| `apps/studio-api/tests/test_app_spa.py` | Tests for the static SPA fallback and the local server entrypoint. |
| `apps/studio-api/tests/test_boot_integrity.py` | Boot integrity and clean-shutdown tests for the Studio sidecar (issue #598). |
| `apps/studio-api/tests/test_capability_routes.py` | The MCP health route and the capability probe must agree on one method. |
| `apps/studio-api/tests/test_probe_cache.py` | Tests for the LLM probe TTL cache and the ``/api/health/llm`` response. |
| `apps/studio-api/tests/test_studio_api.py` | Tests for the Living Studio sidecar API (``/api/*``). |
| `apps/studio-api/tests/test_studio_approvals.py` | The write-approval gate: it resolves once, expires, and never leaks. |
| `apps/studio-api/tests/test_studio_auth.py` | Authentication requirements for the Living Studio sidecar API (``/api/*``). |
| `apps/studio-api/tests/test_studio_brief.py` | The user's onboarding context must reach the model and the offline fallback. |
| `apps/studio-api/tests/test_studio_capabilities.py` | Tests for the sidecar capabilities manifest. |
| `apps/studio-api/tests/test_studio_chat_branches.py` | Branch tests for the streaming tool loop in ``studio.chat``. |
| `apps/studio-api/tests/test_studio_chat_prompt.py` | What the Studio's system prompt tells the agent to do before it scores. |
| `apps/studio-api/tests/test_studio_chat_stream.py` | The turn's new parts: thinking, provenance, write approval, and attachments. |
| `apps/studio-api/tests/test_studio_chat_ui.py` | Tests for the ``render_ui`` local tool in the streaming tool loop. |
| `apps/studio-api/tests/test_studio_claims.py` | The claim contract: a sentence carries a record or says it does not. |
| `apps/studio-api/tests/test_studio_connectors.py` | — |
| `apps/studio-api/tests/test_studio_connectors_router.py` | — |
| `apps/studio-api/tests/test_studio_conversations.py` | Conversations keep a branch tree, and old rows still open. |
| `apps/studio-api/tests/test_studio_csp.py` | Content-Security-Policy headers on sidecar responses. |
| `apps/studio-api/tests/test_studio_diagnostics.py` | Tests for the Studio's metadata-only diagnostics endpoint. |
| `apps/studio-api/tests/test_studio_errors.py` | HTTP error shape, status mapping, and request-id correlation. |
| `apps/studio-api/tests/test_studio_evidence.py` | The evidence routes: capture with a link, promote it, delete it. |
| `apps/studio-api/tests/test_studio_focus.py` | The record a PM is looking at must reach the model — in the store's own words. |
| `apps/studio-api/tests/test_studio_funnel.py` | The sidecar is the thing that launches, so the sidecar is the thing that counts. |
| `apps/studio-api/tests/test_studio_llm_proxy.py` | Tests for the sidecar LLM chat proxy. |
| `apps/studio-api/tests/test_studio_manual_crud.py` | Manual CRUD endpoints: the Studio must work without a model. |
| `apps/studio-api/tests/test_studio_marketplace.py` | Marketplace routes and marketplace-backed installs. |
| `apps/studio-api/tests/test_studio_mcp_data.py` | Tests for MCP hydration and passthrough helpers. |
| `apps/studio-api/tests/test_studio_memory.py` | Tests for the Living Studio's local memory store. |
| `apps/studio-api/tests/test_studio_model_router.py` | Tests for the multi-tier model router used by the chat endpoint. |
| `apps/studio-api/tests/test_studio_models.py` | Tests for listing the configured backend's model ids. |
| `apps/studio-api/tests/test_studio_observability.py` | Tests for the per-turn structured log line and its redaction. |
| `apps/studio-api/tests/test_studio_outcome_evidence_crud.py` | Customer-outcome and evidence CRUD through the Studio API. |
| `apps/studio-api/tests/test_studio_paths.py` | Tests for the per-install sidecar token file and its mode. |
| `apps/studio-api/tests/test_studio_probes.py` | Tests for endpoint probing and LLM health classification. |
| `apps/studio-api/tests/test_studio_proposals.py` | The proposal routes: mine evidence, review it, approve or reject it. |
| `apps/studio-api/tests/test_studio_router.py` | Tests for successful passthrough responses from the Studio router. |
| `apps/studio-api/tests/test_studio_segments.py` | Stages 5 and 6 through the sidecar: the same records under both backends. |
| `apps/studio-api/tests/test_studio_sharing.py` | The scoped share token: one artifact, read-only, expiring, revocable. |
| `apps/studio-api/tests/test_studio_signals.py` | The four signal routes answer under both the local and the mcp backend. |
| `apps/studio-api/tests/test_studio_studies.py` | Studies through the sidecar: the same records under both backends. |
| `apps/studio-api/tests/test_studio_traceability.py` | The traceability route and the alignment routes. |
| `apps/studio-api/tests/test_studio_ui_spec.py` | Tests for the catalog-driven UI validator. |
| `apps/studio/src/App.test.tsx` | The probe breaker (#536) asks this to tell a flaky network from a refusal. |
| `apps/studio/src/api/sse.test.ts` | — |
| `apps/studio/src/api/studioApi.local.test.ts` | A static host that answered an `/api` call with the SPA shell, not JSON. */ |
| `apps/studio/src/api/studioApi.test.ts` | A proxy that accepts the connection and never replies. Boot cannot wait on |
| `apps/studio/src/assistant/attachments.test.ts` | Same keys, so a caller cannot tell which extractor ran. |
| `apps/studio/src/assistant/claims.test.ts` | — |
| `apps/studio/src/assistant/consequence.test.ts` | — |
| `apps/studio/src/assistant/convert.test.ts` | — |
| `apps/studio/src/assistant/dictation.test.ts` | — |
| `apps/studio/src/assistant/extract/common.test.ts` | — |
| `apps/studio/src/assistant/extract/docx.test.ts` | Vitest runs with the studio package as its working directory. |
| `apps/studio/src/assistant/extract/pdf.test.ts` | Vitest runs with the studio package as its working directory. |
| `apps/studio/src/assistant/interview/Interview.test.tsx` | The interview host's wiring (issue #397). |
| `apps/studio/src/assistant/interview/conductor.test.ts` | The interview conductor's rules (issue #397). |
| `apps/studio/src/assistant/interview/persistence.test.ts` | The interview draft's rules (issue #402). |
| `apps/studio/src/assistant/parts.approval.test.tsx` | The approval card, exercised directly. |
| `apps/studio/src/assistant/parts.test.tsx` | — |
| `apps/studio/src/assistant/pending.test.ts` | The pending-call selector (issue #390). |
| `apps/studio/src/assistant/plan.test.ts` | — |
| `apps/studio/src/assistant/queue.test.ts` | The follow-up queue sequencing rules (issue #410). |
| `apps/studio/src/assistant/quote.test.ts` | Exactly one copy: the composer strip is gone by the time the turn exists. |
| `apps/studio/src/assistant/speech.test.ts` | — |
| `apps/studio/src/assistant/starterCopy.test.ts` | The copy lint for the first-run starters (#316). |
| `apps/studio/src/banners/BannerBridge.test.tsx` | jsdom reports `onLine: true`; the offline path needs to flip it and dispatch |
| `apps/studio/src/banners/BannerProvider.test.tsx` | — |
| `apps/studio/src/banners/BannerStack.test.tsx` | Scope to the banner itself: Radix also renders its own `role="status"` |
| `apps/studio/src/banners/BannerStack.visual.test.tsx` | The build table would otherwise name this `BannerStack.visual` after the test |
| `apps/studio/src/banners/BannerToasts.test.tsx` | — |
| `apps/studio/src/banners/catalog.test.ts` | A persistent banner with no key would dedupe by kind only; the copy has to |
| `apps/studio/src/banners/store.test.ts` | — |
| `apps/studio/src/bff/capabilities/registry.test.ts` | Configuration is not evidence that a model answers: the honest answer is |
| `apps/studio/src/bff/chat/orchestrator.test.ts` | Ollama and LM Studio answer with no key at all, so the address is a real |
| `apps/studio/src/bff/data/localDataService.test.ts` | — |
| `apps/studio/src/bff/index.test.ts` | The records are the caller's to show now. |
| `apps/studio/src/bff/memory/localMemoryService.test.ts` | A thread with timestamps the wall clock cannot move. */ |
| `apps/studio/src/bff/outbox.test.ts` | A LockManager that grants `ifAvailable` requests and refuses otherwise. */ |
| `apps/studio/src/bff/storageFacts.test.ts` | — |
| `apps/studio/src/bff/store/indexedDbStore.test.ts` | Every store and index the v2 schema declares, read from a live connection. */ |
| `apps/studio/src/bff/store/migrations.test.ts` | The registry is the contract that keeps a version bump honest. These tests |
| `apps/studio/src/bridge/desktopBridge.test.ts` | — |
| `apps/studio/src/bridge/runtime.test.ts` | The four hosts the Studio can run in, as a table. |
| `apps/studio/src/components/BlockedReasonNote.test.tsx` | Setup renders in the chat stage, which Customize replaces while it is |
| `apps/studio/src/components/BootFailurePage.test.tsx` | — |
| `apps/studio/src/components/ChangelogModal.test.tsx` | The primitive dismisses on a keydown it receives from the document, |
| `apps/studio/src/components/FailurePanel.visual.test.tsx` | The build table would otherwise name this `FailurePanel.visual` after the |
| `apps/studio/src/components/OdiMascot.test.tsx` | — |
| `apps/studio/src/components/SettingsPanel.test.tsx` | A browser build has no desktop version to report, so About shows the |
| `apps/studio/src/components/ShareAction.test.tsx` | — |
| `apps/studio/src/components/ShareSheet.test.tsx` | The primitive dismisses on a keydown it receives from the document, |
| `apps/studio/src/components/SharedArtifact.test.tsx` | An ISO timestamp `ms` from now, so the expiry wording is stable in the test. */ |
| `apps/studio/src/components/brief/BriefLens.test.tsx` | The brief sheet is the one place the document is read, so these tests hold it |
| `apps/studio/src/components/canvas/Dashboard.test.tsx` | A signal from a month ago is in "All time" but not in "This week". |
| `apps/studio/src/components/canvas/DirectCapture.test.tsx` | The capture form is where a score is born, and it showed two decimals while |
| `apps/studio/src/components/canvas/EvidenceStream.test.tsx` | A workspace with jobs, and one with nothing but evidence — the second is the |
| `apps/studio/src/components/canvas/JobMap.test.tsx` | A cold load: the cached canvas is on disk, the sidecar has not answered. |
| `apps/studio/src/components/canvas/MemoryPanel.test.tsx` | — |
| `apps/studio/src/components/canvas/OpportunityLandscape.test.tsx` | Mock StudioContext |
| `apps/studio/src/components/canvas/OutcomeCard.test.tsx` | The card lists the records captured against its outcome, so the canvas |
| `apps/studio/src/components/canvas/OutcomeCardSample.test.tsx` | — |
| `apps/studio/src/components/canvas/SchedulePanel.test.tsx` | — |
| `apps/studio/src/components/canvas/ScorePopover.test.tsx` | A consistent record: 8.6 + max(8.6 − 7.2, 0) = 10.0, right on the line. |
| `apps/studio/src/components/canvas/SegmentBoard.test.tsx` | The unscored member still appears, with no invented score. |
| `apps/studio/src/components/canvas/ThesisAction.test.tsx` | The card lists the records captured against its outcome; give it an |
| `apps/studio/src/components/canvas/opportunityLandscape.perf.test.tsx` | The third cold-open segment: the SPA's first interactive render on the |
| `apps/studio/src/components/chat/ChatStage.test.tsx` | The stage is rendered without the shell here, so the tour stays off; the |
| `apps/studio/src/components/chat/ClaimCitation.test.tsx` | — |
| `apps/studio/src/components/chat/CommandPalette.test.tsx` | — |
| `apps/studio/src/components/chat/Composer.test.tsx` | The starter cards are list items too now (#600); count only the attachments. |
| `apps/studio/src/components/chat/Conversation.test.tsx` | The clamp reads real layout, which jsdom does not compute. Each test that |
| `apps/studio/src/components/chat/Dictation.test.tsx` | The refusal must not take the composer with it. |
| `apps/studio/src/components/chat/Markdown.test.tsx` | CommonMark keeps the fenced block's own trailing newline. |
| `apps/studio/src/components/chat/ModelPicker.test.tsx` | The state rides aria-selected; the visible mark is a glyph so the menu |
| `apps/studio/src/components/chat/PendingCalls.test.tsx` | The pending-call strip (issue #390). |
| `apps/studio/src/components/chat/PlanPanel.test.tsx` | — |
| `apps/studio/src/components/chat/QueueLane.test.tsx` | A turn that only settles when the test says so: everything queued behind it |
| `apps/studio/src/components/chat/SelectionToolbar.test.tsx` | jsdom has a Range but no layout; assistant-ui only needs a rectangle to |
| `apps/studio/src/components/chat/Speech.test.tsx` | — |
| `apps/studio/src/components/chat/StallNotice.test.tsx` | The notice's own polite region, beside the transcript's phase status. */ |
| `apps/studio/src/components/chat/StarterCards.visual.test.tsx` | The empty-state starter pills, pinned above the composer input. */ |
| `apps/studio/src/components/chat/SuggestionPills.test.tsx` | Exactly one call, exactly the constant: no prefix, suffix, or wrapper. |
| `apps/studio/src/components/chat/ThreadComposer.test.tsx` | `fireEvent`'s `key` and `isComposing` init both land on the native event, so |
| `apps/studio/src/components/chat/WorkBlock.test.tsx` | The run row (issue #392). |
| `apps/studio/src/components/chat/arrivalCount.test.ts` | The arrival arithmetic behind the scroll control. |
| `apps/studio/src/components/customize/ConnectorSuggestionModal.test.tsx` | — |
| `apps/studio/src/components/customize/CustomizePage.test.tsx` | `com.acme/thing` installs as `thing`, so matching on the raw name would |
| `apps/studio/src/components/interview/InterviewCard.test.tsx` | — |
| `apps/studio/src/components/interview/answered.test.ts` | The answered record's pure mapping (issue #400). |
| `apps/studio/src/components/layout/StudioBar.test.tsx` | #309: an unconfigured browser is a fact about the settings, not a failure |
| `apps/studio/src/components/layout/StudioBar.visual.test.tsx` | The build table would otherwise name this `StudioBar.visual` after the file; |
| `apps/studio/src/components/notifications/CatchUpFeed.test.tsx` | Point the mocked store at a feed; `unread` defaults to what the feed shows. */ |
| `apps/studio/src/components/notifications/noFabricatedSignals.test.ts` | The signal inbox is evidence-first: every card is a change the store |
| `apps/studio/src/components/records/RecordDetail.test.tsx` | The detail as the lens renders it: a real row out of the real builder, so a field the |
| `apps/studio/src/components/records/RecordsTable.test.tsx` | — |
| `apps/studio/src/components/settings/AboutSection.test.tsx` | The transport is supported, so the provider syncs currentVersion from the |
| `apps/studio/src/components/settings/ConnectionsSection.test.tsx` | The failure-isolation contract: both sections are composed from props, |
| `apps/studio/src/components/settings/ContextSection.test.tsx` | — |
| `apps/studio/src/components/settings/DataSection.test.tsx` | — |
| `apps/studio/src/components/settings/InstallSection.test.tsx` | #800: the desktop app is already its own window, so it cannot be installed. |
| `apps/studio/src/components/settings/ModelSection.test.tsx` | — |
| `apps/studio/src/components/settings/SettingsLayout.test.tsx` | The updater's state stays in the Updates row. |
| `apps/studio/src/components/settings/SettingsPanel.perFieldSave.test.tsx` | Typing is not saving: the request waits for the field to be left. |
| `apps/studio/src/components/settings/UpdatesSection.test.tsx` | — |
| `apps/studio/src/components/settings/saves.test.ts` | — |
| `apps/studio/src/components/setup/IntroConversation.test.tsx` | The examples are text, never buttons that could store themselves. |
| `apps/studio/src/components/setup/IntroConversation.visual.test.tsx` | The build table would otherwise name this `IntroConversation.visual` after |
| `apps/studio/src/components/status/StatusDot.test.tsx` | The bug this file exists for: a shared `::before` rule painted a second, |
| `apps/studio/src/components/status/StatusDot.visual.test.tsx` | Chromatic would otherwise name this build `StatusDot.visual` after the file. |
| `apps/studio/src/components/workspace/WorkbenchRail.test.tsx` | The caret is somewhere else — on an empty stage, that is the composer. |
| `apps/studio/src/components/workspace/WorkspacePanel.test.tsx` | The docked lens is the second panel of the stage split, so every test renders |
| `apps/studio/src/components/workspace/panelContext.test.ts` | — |
| `apps/studio/src/components/workspace/panels.test.tsx` | `findPanel` returns SETTINGS_PANEL for an id it does not know, so a lens |
| `apps/studio/src/diagnostics/DiagnosticsModal.test.tsx` | The primitive hides the page behind from assistive technology (and marks |
| `apps/studio/src/diagnostics/bundle.test.ts` | #800: About and diagnostics must report the same runtime facts, and those |
| `apps/studio/src/diagnostics/redact.test.ts` | — |
| `apps/studio/src/features/flags.test.ts` | — |
| `apps/studio/src/install.test.ts` | `isInstalled()` answers one question — is the page running as its own |
| `apps/studio/src/lib/blockedReason.test.ts` | Every id the capability registry models, spelled out so a new one fails here. */ |
| `apps/studio/src/lib/boot.test.ts` | — |
| `apps/studio/src/lib/brandCopy.test.ts` | The name appears once, in the bar. This test is what keeps it that way. |
| `apps/studio/src/lib/brief.test.ts` | The decision brief is the document a review reads, so these tests hold it to |
| `apps/studio/src/lib/canvasProvenance.test.ts` | — |
| `apps/studio/src/lib/changelogRead.test.ts` | — |
| `apps/studio/src/lib/commands.test.ts` | — |
| `apps/studio/src/lib/dashboard.test.ts` | The days really held zero signals, so a flat zero line is honest here — |
| `apps/studio/src/lib/export.test.ts` | The list item lost its terminal punctuation, so the claim cannot be |
| `apps/studio/src/lib/focus.test.ts` | — |
| `apps/studio/src/lib/formula.test.ts` | The opportunity-score ratchet (issue #1087). |
| `apps/studio/src/lib/greeting.test.ts` | — |
| `apps/studio/src/lib/guidance.test.ts` | — |
| `apps/studio/src/lib/intro.test.ts` | — |
| `apps/studio/src/lib/modelEndpoint.test.ts` | Every shape a person may write it in, including the one docs/local-llm.md |
| `apps/studio/src/lib/odi.test.ts` | The fixture is the contract between the Python service and the TypeScript |
| `apps/studio/src/lib/offlinePage.test.ts` | #546: the offline shell is a page, not a React route, so the only way to keep |
| `apps/studio/src/lib/onlineStatus.test.tsx` | jsdom's `navigator.onLine` is a plain property; redefine it per test and put |
| `apps/studio/src/lib/records.test.ts` | — |
| `apps/studio/src/lib/relativeTime.test.ts` | — |
| `apps/studio/src/lib/sampleLoop.test.ts` | Bundled sample data, never the person's live canvas. |
| `apps/studio/src/lib/scoreVocabulary.test.ts` | — |
| `apps/studio/src/lib/session.test.ts` | — |
| `apps/studio/src/lib/setup.test.ts` | — |
| `apps/studio/src/lib/share.test.ts` | A token with a broken percent escape must not crash the boot; it is simply |
| `apps/studio/src/lib/swRouting.test.ts` | A request that never settles: the timeout is the only way out. |
| `apps/studio/src/lib/swUpdate.test.ts` | A worker whose state a test drives. */ |
| `apps/studio/src/lib/theme.test.ts` | — |
| `apps/studio/src/lib/useReducedMotion.test.tsx` | The preference is live, not read once at mount: toggling the OS setting has |
| `apps/studio/src/lib/version.test.ts` | The build version is the single source of truth: it is baked in from |
| `apps/studio/src/lib/windowState.test.ts` | #962: the desktop app opens focused, not sprawling, and remembers the size |
| `apps/studio/src/onboarding/FirstRunWizard.test.tsx` | Render and let the user ask for the tour, the only way it can open. */ |
| `apps/studio/src/onboarding/LandScene.test.tsx` | — |
| `apps/studio/src/onboarding/machine.test.ts` | — |
| `apps/studio/src/onboarding/sampleCleanup.test.ts` | — |
| `apps/studio/src/state/StudioContext.test.tsx` | The browser BFF is the first-run answer path, and it lives in IndexedDB. |
| `apps/studio/src/state/canvas/CanvasContext.test.tsx` | The split (#505) is only real if the two values move independently: a canvas |
| `apps/studio/src/state/deviceStatus.test.ts` | A probed list shaped like the registry's: every id present, all unavailable. */ |
| `apps/studio/src/state/probeBreaker.test.ts` | A controllable clock, so the breaker's window is tested without waiting. */ |
| `apps/studio/src/state/regions.test.ts` | The navigation contract from #735, proved without a renderer: |
| `apps/studio/src/state/scheduleProbe.test.ts` | A document whose visibility the test drives, and which records its listeners. */ |
| `apps/studio/src/styles/bootShell.test.ts` | Guards for the pre-JavaScript shell in `index.html`. |
| `apps/studio/src/styles/brief.test.ts` | Guards for the brief lens stylesheet. |
| `apps/studio/src/styles/colors.test.ts` | The raw-colour gate (issue #543, parent #331). |
| `apps/studio/src/styles/mainstage.test.ts` | Guards for the mainstage stylesheet (#737). |
| `apps/studio/src/styles/motion.test.ts` | The motion budget, asserted against the stylesheet itself. |
| `apps/studio/src/styles/print.test.ts` | The brief sheet marks the body while the print dialog is open, so the page |
| `apps/studio/src/styles/theme.test.ts` | Colour and token guards for the theme. |
| `apps/studio/src/styles/tokens.test.ts` | The typographic and scalar foundation, asserted from the stylesheet source |
| `apps/studio/src/test/a11y.test.tsx` | The accessibility gate for every surface that ships. |
| `apps/studio/src/test/contrast.test.ts` | The walker's own tests (issue #543, parent #331). |
| `apps/studio/src/test/keyboard.test.tsx` | The children keep one control each, so the tab order asserted below is the |
| `apps/studio/src/test/renderCounts.test.tsx` | The case the budget depends on: a surface that re-renders because it reads |
| `apps/studio/src/ui/UiRenderer.test.tsx` | A verdict never appears without the confidence behind it. |
| `apps/studio/src/ui/protocol.test.ts` | A recommendation without its alternatives is a conclusion. The catalog |
| `apps/studio/src/updater/UpdateBanner.test.tsx` | The bar keeps changing; if it lived inside the live region a screen |
| `apps/studio/src/updater/UpdateSettings.test.tsx` | The updater's detail (the running version, the last check, the release |
| `apps/studio/src/updater/machine.test.ts` | — |
| `apps/studio/src/updater/service.test.ts` | — |
| `apps/studio/src/updater/transport.test.ts` | — |
| `apps/studio/src/vendor/boundary.test.ts` | `src/vendor` is copied presentation. It takes props and renders; it does not |
| `apps/studio/src/vendor/components/ui/dialog.test.tsx` | Focus enters the dialog, so Tab and Escape have somewhere to start. |
| `apps/studio/src/vendor/ledger.test.ts` | Rule 3 of `docs/architecture/vendor.md`: every vendored file carries a |
| `apps/studio/src/vendor/vendor.test.tsx` | Tailwind is installed for `src/vendor` alone. |
| `brand/tests/test_brand_assets.py` | The contract for Odi's brand assets. |
| `brand/tests/test_generated_sources.py` | The generated sources must never drift from the generator that made them. |
| `packages/connectors/tests/test_catalog.py` | — |
| `packages/connectors/tests/test_config_path.py` | — |
| `packages/connectors/tests/test_config_validation.py` | — |
| `packages/connectors/tests/test_evidence_equivalence.py` | Keep the connector's transport shape equal to the record it becomes. |
| `packages/connectors/tests/test_factory.py` | — |
| `packages/connectors/tests/test_http_client.py` | — |
| `packages/connectors/tests/test_mapping.py` | — |
| `packages/connectors/tests/test_marketplace.py` | Marketplace normalization, trust matching, caching, and fallback. |
| `packages/connectors/tests/test_mcp_connector.py` | — |
| `packages/connectors/tests/test_rate_limit.py` | — |
| `packages/connectors/tests/test_registry.py` | — |
| `packages/connectors/tests/test_rest_connector.py` | — |
| `packages/connectors/tests/test_sink.py` | — |
| `packages/core/tests/test_capability_manifest.py` | Drift tests for the generated capability manifest. |
| `packages/core/tests/test_claim_check.py` | A score carries the questions that produced it. |
| `packages/core/tests/test_claim_interview.py` | Ask first: an interview transcript is judged before its score is believed. |
| `packages/core/tests/test_connection.py` | MCP connection settings, read and validated in one place (issue #1084). |
| `packages/core/tests/test_consent_pause.py` | The agent must not act on the workspace before the PM agrees. |
| `packages/core/tests/test_errors.py` | Tests for the ODI error hierarchy. |
| `packages/core/tests/test_evaluation.py` | The outcome format guard: what it accepts, and what it refuses to bless. |
| `packages/core/tests/test_evaluation_harness.py` | The evaluation harness: a service is judged by the shared fixture. |
| `packages/core/tests/test_events.py` | Tests for the new event-store schema and migration. |
| `packages/core/tests/test_evidence_not_found.py` | Tests for the actionable ``EvidenceNotFoundError``. |
| `packages/core/tests/test_funnel.py` | Onboarding is measurable on this machine (ALH-147): five local counters. |
| `packages/core/tests/test_funnel_service.py` | The funnel is counted by the paths a person actually walks. |
| `packages/core/tests/test_intent_store.py` | Tests for the append-only Intent Store. |
| `packages/core/tests/test_job_validation.py` | — |
| `packages/core/tests/test_logging.py` | The shared logging configuration is idempotent and level-aware. |
| `packages/core/tests/test_messages.py` | Tests for shared assistant messages and error helpers. |
| `packages/core/tests/test_migrations.py` | The migration ledger: numbered, recorded, and gapless. |
| `packages/core/tests/test_models.py` | Tests for core domain models. |
| `packages/core/tests/test_opportunity_ranking.py` | Pin the opportunity leaderboard and its served/underserved buckets. |
| `packages/core/tests/test_opportunity_score.py` | Regression tests for the ODI opportunity score. |
| `packages/core/tests/test_outcome_mapping.py` | Tests for the evidence-to-outcome proposal engine (issue #80). |
| `packages/core/tests/test_outcome_trace_write.py` | Writing an outcome's V2MOM links at creation and update time (#590). |
| `packages/core/tests/test_outcome_validation.py` | The outcome statement guard is enforced when an outcome is captured. |
| `packages/core/tests/test_pagination.py` | Pagination on the list methods of both repositories and the service layer. |
| `packages/core/tests/test_perf_cold_open.py` | Cold-open budget for a 1,500-outcome study. |
| `packages/core/tests/test_promotion_identity.py` | One customer quote must not become three opportunities. |
| `packages/core/tests/test_proposals.py` | Tests for proposal lifecycle (issue #80). |
| `packages/core/tests/test_remote.py` | Tests for the shared MCP tool-result error parser. |
| `packages/core/tests/test_repository.py` | Tests for the in-memory Repository implementation. |
| `packages/core/tests/test_repository_factory.py` | — |
| `packages/core/tests/test_repository_health.py` | Repository health reflects whether the store can be queried. |
| `packages/core/tests/test_router.py` | — |
| `packages/core/tests/test_schedule.py` | — |
| `packages/core/tests/test_scheduled_work.py` | — |
| `packages/core/tests/test_schema.py` | — |
| `packages/core/tests/test_segmentation.py` | Tests for Stage 5: outcome-based segmentation. |
| `packages/core/tests/test_segments_service.py` | Tests for the Stage 5 and Stage 6 service surface. |
| `packages/core/tests/test_segments_staleness.py` | Tests for the staleness rule on derived artifacts. |
| `packages/core/tests/test_service.py` | Tests for the core ODIService layer. |
| `packages/core/tests/test_signal_inbox.py` | Signals: fingerprint dedupe, emissions from real mutations, the attention budget. |
| `packages/core/tests/test_sqlite_integrity.py` | Tests for the boot integrity gate and clean shutdown (issue #598). |
| `packages/core/tests/test_sqlite_repository.py` | Tests for the SQLite-backed repository and its event-sourced snapshot. |
| `packages/core/tests/test_strategy.py` | Tests for Stage 6: the innovation strategy the segments imply. |
| `packages/core/tests/test_study.py` | A Study is one named pass over a Job, and running it again makes a wave. |
| `packages/core/tests/test_traceability.py` | Traceability: orphans, unfunded objectives, and drift. |
| `tests/conftest.py` | Shared test configuration for cross-package tests. |
| `tests/contract/test_cli_contract.py` | The CLI's local backend must stay aligned with the core contract. |
| `tests/contract/test_mcp_contract.py` | Keep the live MCP surface in lockstep with the core contract. |
| `tests/contract/test_no_unregistered_gitlinks.py` | Index gitlinks must be registered submodules with a url. |
| `tests/contract/test_protected_files.py` | Protected files must never be deleted on main. |
| `tests/scripts/conftest.py` | Make the standalone scripts in scripts/ importable under pytest. |
| `tests/scripts/test_artifact_a11y.py` | The shared structural audit for artifact HTML (issue ALH-238). |
| `tests/scripts/test_artifact_inventory.py` | The renderer inventory and the gate that keeps it true. |
| `tests/scripts/test_assistant_ui_ledger.py` | Tests for the assistant-ui ledger check in scripts/doc_check.py (issue #429). |
| `tests/scripts/test_audit_ignore.py` | The accepted-advisory ledger is the gate's memory (#1090). |
| `tests/scripts/test_bundle_budget.py` | The cold-start bundle budget gate (#529). |
| `tests/scripts/test_ci_label.py` | The CI Label workflow: `ci-pending` while CI runs, and only that label. |
| `tests/scripts/test_ci_release.py` | — |
| `tests/scripts/test_cli_docs.py` | Assert that docs/cli.md stays synchronized with registered Typer CLI commands. |
| `tests/scripts/test_dev.py` | — |
| `tests/scripts/test_dev_main.py` | Tests for the launcher lifecycle: start, poll, and shut down both services. |
| `tests/scripts/test_doc_check.py` | Unit tests for scripts/doc_check.py (issue #97). |
| `tests/scripts/test_doc_churn.py` | ``scripts/doc_churn.py``, the instrument that makes conflicts measurable. |
| `tests/scripts/test_docs_index.py` | Tests for scripts/docs_index.py. |
| `tests/scripts/test_gen_corpus.py` | The committed corpus generator produces the documented study, deterministically. |
| `tests/scripts/test_gen_job_stages.py` | The Studio's eight job stages are generated from the core constant (issue #79). |
| `tests/scripts/test_hosted_first_run_workflow.py` | The hosted probe has a schedule, a commit to compare against, and no vote. |
| `tests/scripts/test_label_merge_conflicts.py` | The merge-conflict labeler, pinned against the failures that silenced it. |
| `tests/scripts/test_migrations_registry.py` | The migration registries are contracts, and these are their guards. |
| `tests/scripts/test_pr_ai_authorize.py` | Test the AI merge authorization and the check-suite gate it reads. |
| `tests/scripts/test_pr_ai_merge.py` | The AI merge trust labeler, pinned so a silent gate failure cannot ship. |
| `tests/scripts/test_pr_ai_merge_act.py` | Test the AI merge act workflow (``.github/workflows/pr-ai-merge-act.yml``). |
| `tests/scripts/test_pr_ai_merge_workflow.py` | The AI merge trust workflow, pinned so the silent failures cannot come back. |
| `tests/scripts/test_pr_body_gate.py` | The pull request template and the CI gate that requires a non-empty body. |
| `tests/scripts/test_pr_guards.py` | Unit tests for scripts/pr_guards.py (issue #86). |
| `tests/scripts/test_pr_labeler_workflow.py` | The labeler workflows, pinned so the silent failures cannot come back. |
| `tests/scripts/test_pr_labels.py` | — |
| `tests/scripts/test_pr_provenance.py` | — |
| `tests/scripts/test_pr_sweep.py` | ``scripts/pr_sweep.py``, the read-only view of the open pull request queue. |
| `tests/scripts/test_pr_sweep_workflow.py` | The PR sweep weekly workflow, pinned so the schedule and permissions cannot regress. |
| `tests/scripts/test_pr_triage.py` | — |
| `tests/scripts/test_release_assets.py` | Unit tests for scripts/release_assets.py. |
| `tests/scripts/test_release_instructions.py` | Unit tests for scripts/release_instructions.py. |
| `tests/scripts/test_release_version_gate.py` | A release tag must match the version the CLI reports. |
| `tests/scripts/test_release_workflow.py` | The release workflows must be wired so assets actually get attached. |
| `tests/scripts/test_settings_registry.py` | Settings drift: declared variables, documented rows, and direct reads. |
| `tests/scripts/test_updater_proof_gate.py` | Where the updater's proof gets read (#613). |
| `tests/scripts/test_vendor_policy.py` | Tests for scripts/vendor_policy.py (issue #383). |
| `tests/scripts/test_verify.py` | — |
| `tests/scripts/test_verify_hosted_first_run.py` | The hosted probe: what it must answer, and what a failure must look like. |
| `tests/scripts/test_version_sync.py` | The released version must be the version the workspace declares. |
| `tests/scripts/test_workflow_triggers.py` | The release workflows must be triggered by the release itself. |
| `tests/test_adr_index.py` | The ADR index is the only map of ``docs/architecture/adr/``, and it is written by hand. |
| `tests/test_architecture.py` | The package diagram is a contract, not an illustration. |
| `tests/test_dev_entrypoint.py` | One canonical way to run the stack locally, everywhere it is documented. |
| `tests/test_docs_code_overview.py` | The README's Code Overview table must match the actual workspace. |
| `tests/test_docs_method.py` | The eight-stage guide must survive being followed, not just being read. |
| `tests/test_timeout_ceiling.py` | — |
| `tests/test_underserved_threshold_parity.py` | The boundary between "served" and "underserved" is one number, not two. |
| `tests/test_worker_build_route.py` | `/api/build` tells a support thread which release the hosted Studio runs. |
| `tests/test_worker_deploy_route.py` | `/api/deploy` tells a probe which commit and which bundle this artifact is. |
| `tests/test_worker_error_origin.py` | Every Worker-generated failure says so with `origin: "proxy"`. |
| `tests/test_worker_error_shape.py` | The Worker returns the one-error-body shape, even when the sidecar is down. |
| `tests/test_worker_security_headers.py` | The Cloudflare Worker puts security headers on every Response. |
| `website/tests/conftest.py` | Make the website's build tools importable during collection. |
| `website/tests/site_support.py` | Shared fixtures and helpers for the website contract tests. |
| `website/tests/test_ci_required.py` | The website's tests run in CI, and the merge cannot ignore them. |
| `website/tests/test_content_sync.py` | The site must agree with the code it documents. |
| `website/tests/test_design_system.py` | The design system: tokens come from the Studio, and nothing hardcodes colour. |
| `website/tests/test_docs_render.py` | The markdown pipeline: the repository's guides must render faithfully. |
| `website/tests/test_generated.py` | The build must be deterministic, and generated output must never be tracked. |
| `website/tests/test_make_og.py` | — |
| `website/tests/test_og_pages.py` | Every page of the site gets its own social card. |
| `website/tests/test_pages_deploy.py` | Deployment contract for the GitHub Pages site. |
| `website/tests/test_site.py` | The site's contract: structure, metadata, honesty, and links. |
| `website/tests/test_theme.py` | The site ships two themes: the reader's choice wins, the OS decides the rest. |
<!-- END GENERATED: test-map -->
