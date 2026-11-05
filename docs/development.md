# Development

Everything below mirrors what CI runs. Install the workspace first:

```bash
uv sync --all-packages
```

## Linting, Formatting & Type Checks

Shared tooling lives in the root `pyproject.toml`, so one command covers every
Python project:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy apps packages
uv run --directory website mypy .

# Security scanning
uv run bandit -c pyproject.toml -r apps packages website/
```

## Documentation Checks

`scripts/doc_check.py` keeps the living docs honest against the code:

```bash
uv run python scripts/doc_check.py
```

`docs/roadmap.md` is maintained by hand. No check requires a new capability to
add a roadmap line, because a shared file every change had to edit conflicted
with every other change.

It checks that documented CLI commands exist in the Typer tree, documented paths
exist on disk, documented `/api` routes are served by the Studio router,
documented `AGENTIC_ODI_*` variables are read somewhere, the README's Code
Overview paths exist, and the assistant-ui ledger below is internally honest:
every Adopted row names a file that exists and cites a delivered issue or PR,
the group counts match the tally, and the projection in
[Living Studio](living-studio.md) matches the Adopted and Partial rows here.

## The assistant-ui ledger

The Studio runs on assistant-ui, and "we use assistant-ui" is not a coverage
claim. This is. One hundred and twenty-nine relevant capabilities from
`@assistant-ui/react@0.15.31` and `@assistant-ui/core@0.3.32` (read from the
published type definitions, not from docs prose), each in exactly one state,
each Adopted row citing the issue or PR that put it in a person's hands. The
surface areas `@assistant-ui/vue`, `/ink`, `/native`, `cli`, and `cloud` are
out of scope by platform, not by judgement: this is a React app with a local
sidecar.

**Counting rule.** A row is *Adopted* only when all four hold: a person can use
the capability in the Studio today; the File cell names a file that exists; the
Delivered cell cites an issue that closed or a PR that merged into `main` (the
check in `scripts/doc_check.py` proves the citation is in the repository's own
history); and a test names it. A row missing any of the four is *Partial*, and
the Where / why cell says what is missing. A row is never Adopted because the
dependency is installed. Deciding against something is a result: *Rejected*
rows carry the reason so it is not re-litigated every quarter; *Decision* rows
name the question that must be answered first.

**Keeping this ledger true.** Closing a capability issue means editing its rows
here in the same pull request: *Planned* → *Adopted*, with the file that now
owns it and this PR's number in Delivered. Finding a capability we missed means
adding a row before writing code — with a status; a row with no status is a
wish. The projection in `docs/living-studio.md` (Adopted + Partial rows, in the
person's words) must stay in step, which the check enforces.

Verified against the installed types; source of truth: this table.

### Runtime, store, and adapters

The external store is the whole bridge. Every capability below is switched on
by the presence of one handler.

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `useExternalStoreRuntime` | Adopted | `apps/studio/src/assistant/StudioRuntime.tsx` | #238 | The bridge itself: the sidecar's store, presented as a thread. |
| `AssistantRuntimeProvider` | Adopted | `apps/studio/src/App.tsx` | #238 | One provider, whole app. |
| `convertMessage` (`toThreadMessageLike`) | Adopted | `apps/studio/src/assistant/convert.ts` | #238 | The only mapping between `ChatMessage`/`ChatPart` and runtime messages. |
| `isRunning` | Adopted | `apps/studio/src/assistant/StudioRuntime.tsx` | #238 | Driven by `streaming`. |
| `setMessages` (branch switch) | Adopted | `apps/studio/src/state/StudioContext.tsx` | #238 | `switchBranch` swaps the visible path; the sidecar persists `head_id`. |
| `onNew` | Adopted | `apps/studio/src/assistant/StudioRuntime.tsx` | #238 | `sendMessage`. |
| `onEdit` | Adopted | `apps/studio/src/assistant/StudioRuntime.tsx` | #238 | `editFrom`. |
| `onReload` (regenerate) | Adopted | `apps/studio/src/assistant/StudioRuntime.tsx` | #238 | `regenerateFrom`. |
| `onCancel` | Adopted | `apps/studio/src/assistant/StudioRuntime.tsx` | #238 | `stopStreaming`. |
| `onRespondToToolApproval` | Adopted | `apps/studio/src/assistant/StudioRuntime.tsx` | #238 | `respondToApproval`, the write gate. |
| `adapters.attachments` | Adopted | `apps/studio/src/assistant/attachments.ts` | #238 | Text capped at 20k chars, images at 5 MB, refusals explained. |
| runtime `suggestions` | Adopted | `apps/studio/src/assistant/StudioRuntime.tsx` | #238 | `suggestionsFor`, computed from canvas state. |
| `ExternalThreadBranchAdapter` (`getBranches`, `switchToBranch`) | Partial | `apps/studio/src/state/StudioContext.tsx` | — | Branching works through `setMessages` and `head_id`; the dedicated adapter is unused, so the runtime infers branches from parent ids. |
| `queue` adapter | Adopted | `apps/studio/src/assistant/queue.ts` | #410 | Keeps a follow-up while a reply runs. |
| `onResume` / `thread.canResume` | Planned | — | #424 | Continues a dropped run. |
| `adapters.threadList` switch bridge | Planned | — | #408 | The same row as the Thread list group's `adapters.threadList`, listed here because the runtime side is where the handlers switch on. |
| `onDelete` (message) | Rejected | — | — | The transcript is the audit trail behind every claim. A turn can be edited, regenerated, or branched; deleting it breaks the record the ODI method depends on. |
| `MessageNotSentError` / `isMessageNotSentError` | Decision | — | — | Meaningful only if a send can be dropped. #410 removes the last drop; revisit afterwards, not before. |
| `useLocalRuntime` | Rejected | — | — | A model adapter would be a second message store beside the sidecar's. |
| `useAssistantTransportRuntime` | Rejected | — | — | The sidecar owns the wire (SSE + approvals). This would be a second transport. |
| `ThreadHistoryAdapter` / persistence adapters | Rejected | — | — | The sidecar persists turns and branches; adopting this would double-write. Only the list adapter is adopted (#408). |
| `ExportedMessageRepository` | Rejected | — | — | Same double-store problem. Export is a Markdown file (`apps/studio/src/lib/export.ts`), not a message repository. |
| `useRemoteThreadListRuntime`, `useCloudThreadListAdapter`, `AssistantCloud` | Rejected | — | — | Local-first: no account, no cloud, no outbound thread sync. |
| Prebuilt `ExternalThread`, `SingleThreadList`, `InMemoryThreadList`, `RemoteThreadList` | Rejected | — | — | A prebuilt thread cannot carry the ODI part renderers; adopting it would can the three-file part bridge. |
| `createThreadRowsSelector` / `ThreadRow` | Decision | — | — | Group the conversation list by day once #408 lands. Decide from real list lengths, not now. |
| `groupPartByType` / `GroupedParts` | Planned | — | #392 | Fallback if `ChainOfThoughtPrimitive` cannot exclude a pending approval. |
| `getExternalStoreMessages` / `bindExternalStoreMessage` | Rejected | — | — | One store. These exist to reconcile foreign messages, which we do not accept. |

### Thread

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `ThreadPrimitive.Root` | Adopted | `apps/studio/src/components/chat/ChatStage.tsx` | #238 | The transcript's shell. |
| `ThreadPrimitive.Viewport` | Adopted | `apps/studio/src/components/chat/ChatStage.tsx` | #238 | Scrolling; the jump-to-latest affordance reads its `isAtBottom`. |
| `ThreadPrimitive.Messages` | Adopted | `apps/studio/src/components/chat/ChatStage.tsx` | #238 | The message map. |
| `ThreadPrimitive.Empty` | Rejected | — | — | Deprecated; `AuiIf` on `state.thread.isEmpty` is the replacement, and `ChatStage` should move to it the next time it changes (see #408 task 6). |
| `ThreadPrimitive.If` | Decision | — | — | We use `AuiIf`; do not mix two conditional idioms in one tree. |
| `ThreadPrimitive.ScrollToBottom` | Decision | — | — | `LatestMessageButton` is hand-rolled over `useThreadViewport` because it carries the arrival count. Adopt only if the primitive keeps the reduced-motion behavior and the count. |
| `ThreadPrimitive.LoadEarlier` / `thread.hasEarlier` | Decision | — | — | Needs sidecar paging over a branch tree. Worth it only for very long threads; measure first. |
| `ThreadPrimitive.ViewportFooter` | Decision | — | — | The composer is outside the viewport by design; no problem to solve. |
| `ThreadPrimitive.ViewportProvider` | Rejected | — | — | One viewport; the provider exists for multiple viewports on one thread. |
| `ThreadPrimitive.Row` | Decision | — | — | Only with `createThreadRowsSelector`, together. |
| `ThreadPrimitive.MessageByIndex` / `Unstable_MessageById` | Rejected | — | — | The Messages map covers it; addressing one message by position is fragile under branching. |
| `ThreadPrimitive.Suggestion` / `.Suggestions` | Partial | `apps/studio/src/components/chat/composerParts.tsx` | — | The data (`suggestions`) is adopted; the pills are hand-rolled because they carry the artifact-preview copy. Adopting the primitives would drop that copy; `SuggestionByIndex` is not an option since the list is computed from canvas state. |

### Message and parts

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `MessagePrimitive.Parts` | Adopted | `apps/studio/src/components/chat/Conversation.tsx` | #238 | With the `components` map. |
| `MessagePrimitive.Attachments` | Adopted | `apps/studio/src/components/chat/Conversation.tsx` | #238 | User turns show what was sent. |
| `MessagePrimitive.Root` | Partial | `apps/studio/src/components/chat/Conversation.tsx` | — | The message wrapper is a hand-written article carrying `aria-busy` and the assistant avatar. |
| `MessagePrimitive.Quote` | Adopted | `apps/studio/src/assistant/quote.ts` | #435 | Renders the quoted passage on a sent turn. |
| `MessagePrimitive.Error` / `ErrorPrimitive` | Rejected | — | — | `FailurePanel` already renders the structured error, the retry copy, and the Try again action from `metadata.custom.error`. Swapping adds nothing and loses the ODI failure language. |
| `GenerativeUIRender` / `MessagePrimitive.GenerativeUI` | Decision | — | — | Would let a model emit UI we did not validate. The ODI catalog is schema-validated; revisit only if validation moves server-side. |
| `MessagePrimitive.GroupedParts` | Planned | — | #392 | See the runtime table. |
| `MessagePrimitive.PartByIndex` / `Content` | Rejected | — | — | `Parts` is the one path; aliases would be a second. |
| `MessagePartPrimitive.Text` / `.Image` / `.File` | Partial | `apps/studio/src/assistant/parts.tsx` | — | Rendered through the `components` map (custom `TextPart`, `FilePart`) rather than the bare primitives, which cannot show claim chips or extraction state. |
| `MessagePartPrimitive.InProgress` | Decision | — | — | Our `TypingPart` shows a phase ("checking the sidecar"). The primitive would flatten that to a generic indicator. |
| `MessagePartPrimitive.Messages` | Rejected | — | — | Nested conversations are not a Studio surface. |
| `useMessagePartText/Reasoning/Source/File/Image/Data` | Rejected | — | — | The `components` map already receives exactly these props. |

### Composer

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `ComposerPrimitive.Root` / `.Input` / `.Send` / `.Cancel` | Adopted | `apps/studio/src/components/chat/ThreadComposer.tsx` | #238 | The composer's skeleton. |
| `ComposerPrimitive.AddAttachment` / `.Attachments` | Adopted | `apps/studio/src/components/chat/ThreadComposer.tsx` | #238 | Bounded by `apps/studio/src/assistant/attachments.ts`. |
| `ComposerPrimitive.AttachmentDropzone` | Partial | `apps/studio/src/components/chat/ThreadComposer.tsx` | — | Dropping works: the composer has its own `onDragOver`/`onDrop` with the same accept rules as `attachmentRejection`. Adopting the primitive would only relocate the same logic. |
| `ComposerPrimitive.Queue` | Adopted | `apps/studio/src/components/chat/QueueLane.tsx` | #410 | Renders the pending lane. |
| `ComposerPrimitive.Quote` / `.QuoteText` / `.QuoteDismiss` | Adopted | `apps/studio/src/components/chat/ThreadComposer.tsx` | #435 | Shows and clears the quote before send. |
| `ComposerPrimitive.Dictate` / `.StopDictation` / `.DictationTranscript` | Adopted | `apps/studio/src/assistant/dictation.ts` | #433 | Dictation, hidden where unsupported. |
| `ComposerPrimitive.Resume` | Planned | — | #424 | Appears only with a checkpoint. |
| `ComposerPrimitive.TriggerPopover` (and its `Root`/`Items`/`Item`/`Categories`/`CategoryItem`/`Back`) | Planned | — | #426 | `@` mentions and `/` commands. |
| `ComposerPrimitive.If` | Decision | — | — | `AuiIf` is the idiom already in use. |
| `ComposerPrimitive.AttachmentByIndex` | Rejected | — | — | Attachment chips iterate their own list. |
| `composer.quote` / `composer.queue` / `composer.dictation` / `composer.submission` / `composer.inTransit` | Partial | `apps/studio/src/components/chat/ThreadComposer.tsx` | — | `quote` and `dictation` are read today; `queue` arrives with #410, and `submission`/`inTransit` matter to that issue's honesty: a sent message the thread does not show yet must not look lost. |

### Action bar

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `ActionBarPrimitive.Root` / `.Copy` / `.Edit` / `.Reload` | Adopted | `apps/studio/src/components/chat/Conversation.tsx` | #238 | The reply's own controls. |
| `ActionBarPrimitive.Speak` / `.StopSpeaking` | Planned | — | #412 | Read a reply aloud. |
| `ActionBarPrimitive.FeedbackPositive` / `.FeedbackNegative` | Planned | — | #414 | Local-only rating. |
| `ActionBarPrimitive.ExportMarkdown` | Partial | `apps/studio/src/lib/export.ts` | — | Whole-conversation Markdown export exists and also serialises generated surfaces. Adopting the primitive for one reply would produce a second, weaker export format. |
| `ActionBarMorePrimitive` | Decision | — | — | An overflow menu earns its place only when the action row exceeds ~5 buttons; #412 and #414 add two. Revisit after both land. |

### Branch picker

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `BranchPickerPrimitive.Root` / `.Previous` / `.Next` / `.Count` / `.Number` | Adopted | `apps/studio/src/components/chat/Conversation.tsx` | #238 | Exposed only when `branchCount > 1`. Branching, editing, and regenerating round-trip through the sidecar's `head_id`. |

### Attachments

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| Attachment adapter (`AttachmentAdapter`) | Adopted | `apps/studio/src/assistant/attachments.ts` | #238 | Text extraction capped at 20k chars, images capped at 5 MB, refusals explained. |
| Drop and paste | Adopted | `apps/studio/src/components/chat/ThreadComposer.tsx` | #238 | The composer follows the same accept rules as the input. |
| `AttachmentPrimitive.Root` / `.Name` / `.Remove` / `unstable_Thumb` | Rejected | — | — | The current chip shows extraction state and the reason a file was refused. The primitive would show a name and a thumbnail, which is less than the person needs. |

### Thread list

The whole group exists in the sidecar already (`conversations` with `head_id`);
only the surface is missing.

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `adapters.threadList` | Planned | — | #408 | `threads`, `threadId`, `isLoading`, `onSwitchToThread`, `onSwitchToNewThread`. |
| `ExternalStoreThreadData` fields | Planned | — | #408 | `status`, `id`, `title`, `custom` — there are no timestamp fields. Ordering data must ride in `custom`. |
| `ThreadListPrimitive.Root` / `.New` / `.Items` / `.ItemByIndex` | Planned | — | #408 | The switcher. |
| `ThreadListPrimitive.LoadMore` / `threads.hasMore` | Decision | — | — | The external-store adapter has no paging hook; `hasMore`/`isLoadingMore` are populated by the remote runtimes we rejected. Cap the fetch server-side and offer Show all, or adopt the remote runtime. |
| `ThreadListItemPrimitive.Root` / `.Trigger` / `.Title` | Planned | — | #408 | One row, keyboard reachable. |
| `ThreadListItemPrimitive.Delete` | Planned | — | #409 | Confirmed delete, turns and all. |
| `ThreadListItemPrimitive.Archive` / `.Unarchive` | Decision | — | — | Needs an `archived_at` migration and an `archivedThreads` feed. Build only if real lists pass ~20 threads. |
| `ThreadListItemMorePrimitive` (`Root`/`Trigger`/`Content`/`Item`/`Separator`) | Planned | — | #409 | One keyboard-navigable menu instead of hover buttons. |
| `threads.item().rename()` / `.updateCustom()` | Planned | — | #409 | Inline rename and per-row metadata (`updatedAt` cannot live on `ExternalStoreThreadData`, so it rides in `custom`). |
| `threads.item().generateTitle()` | Rejected | — | — | Needs a model adapter the Studio does not have, and the sidecar already derives a title from the first turn. A client-side title would be a second authority. |

### Queue

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `createMessageQueue(driver)` | Adopted | `apps/studio/src/assistant/queue.ts` | #410 | `driver.run(message, {steer})`, optional `driver.cancel`. |
| `MessageQueueController` | Adopted | `apps/studio/src/assistant/queue.ts` | #410 | `notifyBusy` / `notifyIdle` / `notifyCancelled` / `hold` / `release` / `clear` / `subscribe` — the cancel pause is why we must not hand-roll. |
| `QueueItemPrimitive.Text` / `.Steer` / `.Remove` | Adopted | `apps/studio/src/components/chat/QueueLane.tsx` | #410 | One lane above the composer. |
| `QueueItemState.prompt` | Rejected | — | — | Deprecated in the installed types; derive text from `parts`. |

### Reasoning and work

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `ChainOfThoughtPrimitive.Root` / `.AccordionTrigger` / `.Parts` | Planned | — | #392 | One disclosure per settled turn. |
| Pending approvals inside a group | Rejected | — | — | A pending write is a question, not history. It stays ungrouped and visible, always. |
| `useToolCallElapsed` | Planned | — | #392 | "Worked for Ns · N tools". |
| `useMessageTiming` | Decision | — | — | Tokens/second is engineering telemetry. Useful to us, not to the PM; expose it only behind a diagnostics toggle if at all. |

### Selection and quote

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `SelectionToolbarPrimitive.Root` / `.Quote` | Adopted | `apps/studio/src/components/chat/SelectionToolbar.tsx` | #435 | Quote on select, inside one message. |
| `data-aui-quote-selectable="false"` | Adopted | `apps/studio/src/assistant/parts.tsx` | #435 | Marks tool traces, approval cards, and generated surfaces as non-prose; inline claim chips stay selectable. |
| `QuoteInfo` (`{ text, messageId }`) / `useMessageQuote` | Adopted | `apps/studio/src/assistant/quote.ts` | #435 | The quote persists in `metadata.custom.quote` and renders on the sent turn. |

### Errors and honesty

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| Structured turn failure | Adopted | `apps/studio/src/components/FailurePanel.tsx` | #129 | `metadata.custom.error` / `retryText`, rendered by `FailurePanel`. |
| `unstable_useMessageStallDetection` | Adopted | `apps/studio/src/components/chat/StallNotice.tsx` | #431 | Speaks only when output stops moving. |
| `MessageNotSentError` | Decision | — | — | See the runtime table. |
| `ErrorPrimitive` | Rejected | — | — | See the message table. |

### Assistant modal

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `AssistantModalPrimitive` (`Root`/`Trigger`/`Content`/`Anchor`) | Decision | — | — | A floating assistant on the canvas. The composer already stays on screen while a lens is open; a second surface must justify a second runtime instance and a second place errors can appear. |

### State hooks and utilities

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `useAuiState` | Adopted | `apps/studio/src/components/chat/Conversation.tsx` | #238 | Read across the transcript and composer. |
| `useAui` | Adopted | `apps/studio/src/components/chat/ThreadComposer.tsx` | #238 | Imperative actions. |
| `AuiIf` | Adopted | `apps/studio/src/components/chat/Conversation.tsx` | #238 | The conditional idiom in use. |
| `useAuiEvent` | Decision | — | — | Events are for cross-surface coordination; one surface has nothing to coordinate yet. |
| `unstable_useMentionAdapter` / `unstable_useSlashCommandAdapter` | Planned | — | #426 | Composer triggers. |
| `unstable_useComposerInputHistory` | Adopted | `apps/studio/src/assistant/composerHistory.ts` | #430 | ArrowUp recall. |
| `useSmooth` | Decision | — | — | Smoothes bursty SSE text. Might read as deliberate rather than laggy — needs a comparison, not a guess. |
| `useThreadViewport` (viewport state) | Adopted | `apps/studio/src/components/chat/ChatStage.tsx` | #245 | `isAtBottom` / `scrollToBottom` drive the jump-to-latest affordance; the arrival count lives in `arrivalCount.ts`. |
| `useThreadViewportAutoScroll` / `useScrollLock` | Rejected | — | — | The viewport already owns auto-scroll, and the only overlay that could need a scroll lock is the lens rail, which does not scroll the thread. |
| `unstable_useThreadMessageIds` | Decision | — | — | Only needed if a list needs message identity outside a message scope. |
| `useToolArgsStatus` | Decision | — | — | Belongs to the tool card work, if it needs per-argument state. |
| `createSuggestionAdapter` | Rejected | — | — | Suggestions come from canvas state through the runtime prop; a second adapter is a second source. |
| `useInlineRender` | Rejected | — | — | Belongs to frontend tools, which the MCP server owns. |
| `unstable_useLiveCompletionAdapter` | Rejected | — | — | Inline completion is not a Studio interaction; it would compete with dictation. |

### Model context — "the assistant sees the app"

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `useAssistantContext` / `ModelContextRegistry` / `mergeModelContexts` / `useModelContextSnapshot` | Rejected | — | — | Focus reaches the model as a pointer the sidecar re-reads (`apps/studio/src/lib/focus.ts`, `chat.py:_focus_context`), which is what makes the description true. The registry feeds a prompt a client authors, and `useExternalStoreRuntime` has no send path that carries it — a prototype proved `getModelContext()` returns nothing here. #425 delivered the pointer instead. |
| `makeAssistantVisible` | Rejected | — | — | Wrapping canvas cards to make them describable is not needed: the composer already names the focused record from the snapshot it holds, and refuses to name it when the snapshot cannot (`focusedSubjectLabel`). Per-card visibility declarations would be a second description of the same screen. |
| `useAssistantInstructions` | Rejected | — | — | The sidecar assembles the ODI system prompt. A client-side instruction layer would be a second authority and would drift from the methodology guardrails. |
| `AssistantFrameHost` / `AssistantFrameProvider` / `useAssistantFrameHost` / `frame` transport | Decision | — | — | Embeds the assistant in someone else's page. The Studio is the product surface, not an embedded widget. |

### Tools and toolkits

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| Tool approval gate | Adopted | `apps/studio/src/assistant/convert.ts` | #238 | Plus the sidecar approval registry; a pending write blocks the turn. |
| Tool result rendering | Adopted | `apps/studio/src/assistant/parts.tsx` | #238 | `tools: { Fallback: ToolPart }`. |
| `makeAssistantTool` / `useAssistantTool` / `makeAssistantToolUI` / `useAssistantToolUI` / `useAuiToolOverrides` | Rejected | — | — | The MCP server owns execution and approval. A client-side path could run a tool twice and split the audit trail. |
| `defineToolkit` / `Toolkit` / `stubTool` / `externalTool` / `providerTool` | Rejected | — | — | Same. Two tool registries is the failure mode. |
| `hitl` / `hitlTool` / `humanTool` | Rejected | — | — | Our approval gate is the human-in-the-loop mechanism, and it is already audited server-side. |
| `defineMcpToolkit` | Decision | — | — | It would let tool presentation follow MCP metadata. Only worth it if the MCP server starts publishing per-tool display hints. |
| `Interactables` (`useAssistantInteractable`, `unstable_useInteractable`, `useInteractableState`) | Decision | — | — | The strongest unreleased idea on this list: the agent hands back a live control whose state it can read next turn. Needs a protocol decision — who owns the state, and what happens on reload — before it is an increment. |
| `Tools` / `DataRenderers` / `useAssistantDataUI` | Partial | `apps/studio/src/components/chat/Conversation.tsx` | — | We use the `components.data.by_name` map for the validated ODI catalog and claims. The client-level `DataRenderers` scope would be a second registration path for the same thing. |

### Generative UI and MCP Apps

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| ODI surfaces as `data` parts | Adopted | `apps/studio/src/ui` | #55 | Validated by a catalog manifest and rendered through the same `UiRenderer`. |
| `GenerativeUIRender` / A2UI / `json-generative-ui` | Decision | — | — | Model-authored UI would bypass schema validation. Revisit only with server-side validation and a CSP story. |
| MCP Apps (`McpAppRenderer`, `csp`, `bridge`, `ui://` resources) | Decision | — | — | Connector tools could render their own UI inline. Blocked on the sandbox origin and CSP decision, and there is no front door yet (#90). Never ship a frame before that. |
| Realtime voice (`createVoiceSession`, `OpenAIRealtimeVoiceAdapter`, `useVoiceState`/`useVoiceVolume`/`useVoiceControls`) | Decision | — | — | Needs an audio provider, a cost, and even WebKit support in Tauri. #413 (dictation) covered the realistic need first. |

### Observability

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `DevToolsHooks` / `DevToolsProviderApi` | Rejected | — | — | Developer surface, not a PM surface. `docs/` and the sidecar's diagnostics already cover the need. |
| `webmcp` host/registration | Rejected | — | — | Would expose the Studio's actions to an external agent browser. Out of scope for a local-first app with approvals. |

### The count

| Status | Rows |
|---|---|
| Adopted | 44 |
| Partial | 8 |
| Planned | 18 |
| Decision | 26 |
| Rejected | 33 |
| Total | 129 |

Read it as: **52** of the library's 129 relevant capabilities already deliver
something a person can use, **20** more are carried by open issues, **26** rows
wait on a named decision, and **31** are rejected with a reason. Every row is
accounted for — that is the whole point of the page.

## Frontend & Desktop Checks (studio)

The SPA and Tauri shell mirror their CI jobs locally:

```bash
npm --prefix apps/studio run lint        # ESLint
npm --prefix apps/studio run typecheck   # tsc --noEmit
npm --prefix apps/studio test -- --run   # Vitest on jsdom (run once)
npm --prefix apps/studio run test:visual # Vitest Browser Mode → Chromatic archives
npm --prefix apps/studio run build       # production build → apps/studio/dist
cd apps/studio/src-tauri && cargo fmt --check && cargo clippy -- -D warnings && cargo check
```

### Visual tests

`npm test` runs the jsdom suite and deliberately ignores `*.visual.test.tsx`.
Those files render one component state in Chromium under
`vitest.visual.config.ts`, and the `Chromatic` workflow publishes them on every
branch push so a reviewer can compare pixels component by component. Each test costs one billed snapshot per
build on the free 5,000/month allowance, which is why the two suites are split by
filename instead of running every test in a browser. Browser mode needs Chromium
locally: `npx playwright install chromium`. See
[Deployment](deployment.md) for the project setup and budget rules.

### Copied components (`src/vendor`)

Tailwind v4 styles `src/vendor/**` and nothing else (issue #385). The stylesheet
imports the theme and utility layers with `source(none)` and then rescans that
directory alone, so no product class is ever generated and Tailwind's
document-wide reset stays out of the bundle. The product keeps rendering from
`src/styles/theme.css`, which `src/main.tsx` imports first; vendor utilities land
in `@layer utilities`, and an unlayered product rule always outranks a layered
utility, so the two can never fight over the same element.

`components.json` points the shadcn CLI at that stylesheet and at the `@/` alias,
which resolves to `src/vendor/` in the Vite config and in both tsconfigs. A copied
file therefore keeps the import paths it shipped with:

```bash
npx --yes shadcn@latest add button   # → apps/studio/src/vendor/components/ui/button.tsx
```

Every copied file carries a header naming the registry and any edit made after the
copy; refresh with the CLI instead of editing the markup by hand. Today that is one
line: the registry items import their class merger from the `cn` package, and the
vendor tree standardises on `src/vendor/lib/utils.ts`, so `npm rm cn` and point the
import back at `@/lib/utils` after each add.
`npm --prefix apps/studio test -- --run src/vendor` proves the scope by reading the
compiled stylesheet.

### Conversational UI coverage

The agent-composed surfaces, first-minute guidance, and the product tour are
covered at these levels. `ChatStage.test.tsx` covers the jump-to-latest control
while following a streamed turn — the arrival count, the polite announcement, the
return to the live end, and the keyboard path — and `arrivalCount.test.ts` holds
the pure count arithmetic:

| File | What it covers |
|---|---|
| `apps/studio/src/ui/protocol.test.ts` | Spec parsing: prop types, enums, ranges, required props, depth/node/size ceilings, unknown types |
| `apps/studio/src/vendor/vendor.test.tsx` | Tailwind scope: a vendor utility is compiled, a product-only utility is not, no preflight reset, the copied button renders |
| `apps/studio/src/ui/UiRenderer.test.tsx` | Card rendering, computed opportunity scores, action dispatch, per-node failure isolation, catalog/registry parity |
| `apps/studio/src/components/canvas/SegmentBoard.test.tsx` | The segment board's members and basis (#559): each segment lists its member outcomes with their stored scores, the mean is over scored members only with "Not scored" for none, an inferred group is called a candidate, a missing member is dropped and counted, a member opens in the landscape by mouse and keyboard, and the empty state names the next step |
| `apps/studio/src/assistant/convert.test.ts` | Every part mapping in both directions, unknown parts dropped, `content` preserved for history |
| `apps/studio/src/api/studioApi.test.ts` | Chat request serialization: visible-path messages and attachment fields match the sidecar schema |
| `apps/studio/src/diagnostics/` | Recursive secret/URL/path redaction, 256 KiB cap, opt-in memory-only capture, local-only metadata fetch, and accessible diagnostics preview/export |
| `apps/studio-api/tests/test_studio_diagnostics.py` | Metadata-only diagnostics response, safe database basename/counts, integrity state, and absence of row contents/config |
| `apps/studio-api/tests/test_boot_integrity.py` | A damaged store answers every data route with one `store_corrupt` body, health reports degraded, diagnostics and health stay reachable, the idle timer checkpoints and honors `AGENTIC_ODI_CHECKPOINT_SECONDS`, and a clean shutdown checkpoints and closes both stores |
| `apps/studio-api/tests/test_studio_chat_stream.py` | Streaming chat, opt-in approval decisions for contract writes and unknown tools, and read-only/local-tool classification |
| `apps/studio/src/components/chat/Conversation.test.tsx` | Prose and surfaces interleaved in the agent's order through the real runtime; card actions become messages; named alternative N of M and its switch; reasoning disclosure opens on request; the phase is announced and the reply is busy while streaming; failure retry |
| `apps/studio/src/assistant/quote.test.ts`, `src/components/chat/SelectionToolbar.test.tsx` | Quoting a passage verbatim with its attribution, one copy only, and no toolbar until text is selected |
| `apps/studio/src/components/chat/Composer.test.tsx` | Send, stop, the slash palette, keyboard focus, dropped and pasted attachments, refusal of unreadable files, and accessible attachment format/size limits in the runtime-bound composer |
| `apps/studio/src/components/chat/StallNotice.test.tsx` | The eight-second silence line: appears only while a run is stalled, disappears when it settles, and announces once rather than on every tick |
| `apps/studio/src/assistant/dictation.test.ts`, `src/components/chat/Dictation.test.tsx` | The speech-recognition support gate, the microphone starting a session, and the absence of the control where the API is missing |
| `apps/studio/src/components/chat/ThreadComposer.test.tsx` | Recall of previously sent messages with `ArrowUp`/`ArrowDown`, draft restoration, and the editing and sending keys it must not break |
| `apps/studio/src/assistant/queue.test.ts`, `src/components/chat/QueueLane.test.tsx` | The follow-up lane (#410): enqueue preserves order, steer interrupts once, a cancel pauses instead of draining, a failed dispatch restores rather than drops; the lane rows read their text from parts and their Run-now and remove controls act on one item only |
| `apps/studio/src/components/chat/ModelPicker.test.tsx` | Listing and marking the configured model, selection writes through `saveSettings`, arrow/Enter/Escape operation, an unreachable backend explained with a Settings path, one probe per backend |
| `apps/studio/src/assistant/attachments.test.ts` | Acceptance by extension and type, the 5 MB image ceiling, and human-readable sizes |
| `apps/studio/src/assistant/starterCopy.test.ts` | The first-run starter lint: situation-first titles, material-first prompts, a promised artifact, no quality adjectives, no claim literal, and the untouched returning-user swaps |
| `apps/studio/src/components/chat/SuggestionPills.test.tsx` | A starter click sends its exported prompt verbatim, and a starter clicked while a reply streams enqueues instead of being dropped (#410) |
| `apps/studio-api/tests/test_studio_models.py` | Model listing sorted and deduplicated, offline without connecting, failed probe returned as a message, `/api/models` response shape |
| `apps/studio/src/state/StudioContext.test.tsx` | New, regenerate, and edit turns against a stubbed stream, the follow-up queue against a gated stream (#410), branch switching, approval answers |
| `apps/studio-api/tests/test_studio_ui_spec.py` | Catalog validation and `render_ui` tool-schema generation |
| `apps/studio-api/tests/test_studio_chat_ui.py` | `render_ui` interception, `ui` SSE events, and the correction fed back to the model |
| `apps/studio-api/tests/test_studio_chat_stream.py` | Reasoning and source events, attachment prompt assembly, terminal-event invariants |
| `apps/studio-api/tests/test_studio_chat_branches.py` | Turn ids and sibling branches: edit and regenerate produce a tree, not a rewrite |
| `apps/studio-api/tests/test_studio_conversations.py` | Branch tree endpoint, `head_id` patch, legacy linear fallback, conversation list ordering and turn counts, citation round-trip, idempotent retry, count-mismatch drop |
| `apps/studio-api/tests/test_studio_claims.py` | Claim parser: markers outside code, hypothesis tags, unknown ids downgraded, headings/questions/instructions exempt, list items, decimals, the three-record cap |
| `apps/studio/src/assistant/claims.test.ts` | Marker hiding while a reply streams (including a split marker and literal code), block splitting, claim-to-sentence mapping, seeded counts |
| `apps/studio/src/assistant/parts.test.tsx` | Claim chips open the record, hypothesis tag, uncited underline, missing record, sample chips, the no-citation banner, Escape |
| `apps/studio-api/tests/test_studio_approvals.py` | Gate lifecycle: resolve, timeout, double resolve, unknown id |
| `apps/studio/src/features/flags.test.ts` | Flag precedence (query → storage → env → default), value parsing, local overrides |
| `apps/studio/src/onboarding/machine.test.ts` | Tour transitions, no forward motion without a goal, versioned storage, malformed records |
| `apps/studio/src/onboarding/FirstRunWizard.test.tsx` | Never auto-opens, explicit open, full flow to a destination, skip/Escape, focus trap, resume, replay, inline model repair, flag off |
| `apps/studio/src/test/a11y.test.tsx` | axe-core WCAG 2.1 A/AA sweep over every shipping surface with zero violations; contrast is scoped to the token audit and documented there |
| `apps/studio/src/test/keyboard.test.tsx` | Shell landmarks and skip link, the tab path order (skip link → top bar → rail → transcript), and a project-wide AST scan for click handlers on non-controls |
| `apps/studio/src/styles/theme.test.ts` | Palette contrast in both themes (4.5:1 text, 3:1 focus ring) and no custom property referenced without a definition |
| `apps/studio/src/styles/bootShell.test.ts` | The inline shell in `index.html`: it sits inside `#root`, draws the bar/rail/stage, requests no font or image, stays under budget, keeps its literal colours in step with `theme.css`, and its inline script resolves a stored theme (or the media query) before React |
| `apps/studio/src/lib/theme.test.ts` | `resolveTheme`: the stored choice wins, the media query answers when nothing is stored, and dark is the last resort |
| `apps/studio/src/lib/boot.test.ts` | `removeBootShell` clears the shell on mount and is a no-op without one |
| `apps/studio/e2e/first-paint.spec.ts` | Playwright: the shell paints the token colour with JavaScript off and the bundle blocked, a stored theme wins over the system, and the handover to React keeps the colour |
| `apps/studio/src/lib/guidance.test.ts` | One hint at a time, context before evidence, silence before the first exchange, permanent dismissal, defensive storage |
| `apps/studio/src/components/BootFailurePage.test.tsx` | The boot failure page names the file and the last backup, offers recheck, and never offers to delete or overwrite the store |
| `apps/studio/src/App.test.tsx` | First-minute ordering: no tour or interview over the stage, tour on request, context hint after the first reply, job handoff, chosen surface opens, flag off in shell tests, and a complete introduction that saves the brief; a damaged store renders the boot failure page instead of the shell |
| `apps/studio/src/lib/intro.test.ts` | Introduction turns, parsing under empty, very long, and multi-fact replies, the proposed defaults, draft storage, and one-shot migration |
| `apps/studio/src/components/setup/IntroConversation.test.tsx` | Five turns, skip, Escape, in-place summary edits, and the accepted brief with role, team, and evidence |
| `apps/studio/src/components/setup/IntroConversation.visual.test.tsx` | The summary card as one Chromatic snapshot |

## Website Checks (GitHub Pages)

The `website/` static site is part of the main CI workflow. Its tests assert the
committed OG art is reproducible and that the publish pipeline
(`website/tests/test_pages_deploy.py`) still exists:

```bash
uv run --directory website pytest tests/
```

The site is generated at CI time and never committed. CI runs `build_site.py` to
produce `_site` and uploads it as the `website-site` artifact for review.

The landing page's primary call to action points at the **sample workspace**,
`website/sample/index.html`. Unlike the rest of the site it *is* committed, so
it survives an API outage and can be linked from the README. It is generated
from `website/content/sample-study.json` by `website/tools/build_sample.py`;
regenerate it after editing the fixture or `website/templates/sample.html`:

```bash
uv run python website/tools/build_sample.py          # write the committed page
uv run python website/tools/build_sample.py --check  # fail when it is stale
```

`website/tests/test_content_sync.py` runs the same comparison, so the page
cannot drift from the fixture, and it greps the committed file for an external
reference so the no-network rule is enforced rather than promised.

Publishing happens in `.github/workflows/pages.yml`: it runs those tests,
builds `_site` from `website/`, and deploys the artifact with
`actions/deploy-pages` on every push to `main`. There is no `gh-pages` branch,
so that workflow is the only thing that keeps
<https://alehar9320.github.io/agentic-odi/> online.

## Formatting workflow

- **When editing Python files**, either rely on the **pre-commit hooks** below
  (recommended) or run Ruff formatting directly before pushing:

  ```bash
  uv run ruff format .
  ```

- **CI behavior**:
  - CI runs `uv run ruff check .` to lint without modifying files.
  - CI runs `uv run ruff format --check .` to *verify* formatting only.
  - If CI fails on formatting, run `uv run ruff format .` locally, commit the
    changes, and push again.

## Pre-commit hooks

To run the checks automatically before each commit:

```bash
uv tool install pre-commit
pre-commit install
```

After this, `ruff` and `ruff-format` run on staged files whenever you commit.
You can also trigger them manually:

```bash
pre-commit run --all-files
```

## PR Risk Classification

Every pull request is automatically classified by the
[PR Risk Classification](../.github/workflows/pr-risk.yml) workflow, which runs
on `ubuntu-latest` at $0 cost with zero external dependencies. It scores the diff
(0–100) across three factors and applies a single, mutually exclusive label:

| Label | Meaning | Score |
|---|---|---|
| `safe to merge` | Low risk — small diff, docs-only, or tested source code | ≤ 20 |
| `needs a look` | Medium risk — standard feature work or missing test updates | 21–50 |
| `danger zone` | High risk — critical path (auth, migrations, billing, infra, workflows) or protected-file deletion | ≥ 51 |

Scoring factors:

- **File & line churn** — files changed and lines added/deleted (0–30 points).
- **Critical path override** — touching `auth/`, `migrations/`, `billing/`,
  `infra/`, `.github/workflows/`, or deleting a file in
  `.ci/protected-files.txt` forces the danger zone.
- **Test delta** — source code changed without a corresponding
  `*.test.*`/`*.spec.*`/`tests/**` file adds 20 points.

### PR labels

The same workflow also labels every pull request so a reviewer can read its
shape at a glance, without opening the diff. Labelling is deterministic — no
LLM calls, no network beyond the GitHub API — so it cannot invent a label.

| Axis | Labels | What it tells a reviewer |
|---|---|---|
| Provenance | `🤖 agent`, `👤 human` | Whether a coding agent or a human wrote it. Detected from the PR author, the branch prefix, and the commit identities, because agents in this repository push on the owner's account. |
| Size | `size/XS` … `size/XL` | How much there is to read: <50, 50–249, 250–799, 800–1999, 2000+ lines changed. |
| Domain | `area/studio`, `area/cli`, `area/core`, `area/infra`, `area/docs`, … | Which components the diff touches. A PR can carry several. |
| Supply chain | `dependencies` | A manifest or lockfile changed (`package-lock.json`, `pyproject.toml`, `Cargo.lock`, `go.sum`, …). Worth a careful read even when the diff is one line. |
| Agent telemetry | `breaking change`, `needs deep dive`, `telemetry invalid` | What the agent declared about its own work. |

#### Agent telemetry

Coding agents declare what they know in the pull request body. Add this block to
the description; the [pull request
template](../.github/pull_request_template.md) already includes it:

```html
<!-- AGENT_METADATA {"has_breaking_changes": true, "agent_confidence": "low"} -->
```

- `has_breaking_changes: true` applies `breaking change`.
- `agent_confidence: "low"` applies `needs deep dive`.
- A block that cannot be parsed applies `telemetry invalid`. The workflow keeps
  going either way and never fails the check suite on a malformed block.

Human authors can leave the block alone: the shipped defaults claim nothing.

Labels are managed idempotently. Each run adds the labels it computed and
removes the ones it previously added that no longer apply, so re-pushing a
branch corrects the size label instead of stacking a second one. The set of
labels this system owns is defined once, in `scripts/pr_labels.py`:

```bash
python3 scripts/pr_labels.py --managed          # list every managed label
echo '{"author":{"login":"x","type":"User"},"files":[]}' | python3 scripts/pr_labels.py
```

The risk tier labels (`safe to merge`, `needs a look`, `danger zone`) and the
merge-state labels (`ready-for-merge`, `merge-conflict`) are owned by other
workflows and are deliberately left alone. The workflow is silent: it updates
labels only and never posts PR comments.

## Testing

Tests use **pytest** with **pytest-asyncio** (strict mode) and run entirely
in-memory — no running server required. Tests live next to the package they
cover, and every test runs from the repository root:

```bash
uv run pytest                        # everything
uv run pytest apps/cli               # one app
uv run pytest packages/core          # one package
uv run pytest tests/contract         # cross-package contracts
uv run pytest tests/scripts          # dev launcher
```

The MCP server contract test compares the live FastMCP registry with
`packages/core/src/agentic_odi_core/contract.py`, so add or change a tool in
both places. The CLI local-backend contract test keeps `_LOCAL_HANDLERS` aligned
with the same tool names.

### End-to-end testing

The browser-level suite lives in `apps/studio/e2e/` and runs with
[Playwright](https://playwright.dev). It drives the real Studio against the
real sidecar and MCP server, with no mocked network calls, so it covers the
seams the other tiers cannot: the SPA's assumptions about the sidecar's
response shapes, the sidecar's hydration of the canvas, and the first-run
wizard's ordering relative to the rest of the app.

```bash
npm --prefix apps/studio run build      # the sidecar serves apps/studio/dist
npm --prefix apps/studio run test:e2e
npm --prefix apps/studio run test:e2e:ui   # the Playwright UI
```

The first run needs the browser once:

```bash
npx --prefix apps/studio playwright install chromium
```

Playwright's `webServer` array starts the MCP server, the Studio sidecar, and
a second sidecar on the MCP passthrough backend. Two projects run against
them: `chromium` for the local backend (the product default) and
`mcp-backend` for the passthrough.

Locators bind to what a user perceives — a role, a label, or visible text —
never to a `data-testid`, of which the application has none. When a test
needs data behind it, it seeds through the API rather than through the UI, so
the test stays about the view it is actually checking.

CI runs the suite in the `e2e` job. It is deliberately non-blocking: set the
repository variable `AGENTIC_ODI_E2E` to `false` to skip it, and the
`continue-on-error` on the job keeps a failure from turning CI red.

## Cold-open budget

A study at scale must reach an interactive screen in under a second, or a PM
batches their work instead of checking something. The reference study is 1,500
outcomes over 30 jobs, each with a complete eight-step job map and one customer
quote per outcome (3,270 events). It is generated deterministically by
`agentic_odi_core.corpus.build_corpus`, so the number is comparable between runs
and machines:

```bash
uv run python scripts/gen_corpus.py --out /tmp/corpus.db
```

The number is measured per segment, because the fix differs per segment, and the
regression tests live with the segment they cover:

```bash
uv run pytest packages/core -k perf --no-header -q
npm --prefix apps/studio test -- --run src/components/canvas/opportunityLandscape.perf.test.tsx
```

**Reference environment:** AMD EPYC 9B14, 4 vCPU, 15 GiB RAM, Linux, Python
3.13.15, `uv` 0.13.5, median of seven cold-open runs.

| Segment | Before | After | Fix |
|---|---|---|---|
| Store open (`_load_snapshot` replay) | 32 ms | 27 ms | Unchanged; replay itself was never the bottleneck. |
| Canvas assembly (`fetch_local_canvas`) | 1,146 ms | 23 ms | `_sync` now reads only events appended since the last apply (`get_stream(after_id=…)`) instead of re-parsing the whole log on every read. One assembly read 206,010 rows; it now reads 3,270. |
| First interactive render (SPA matrix) | 590 ms | 162 ms | The landscape plots the 200 highest-opportunity outcomes above the fold and offers "Plot all"; 8,957 DOM nodes became 1,709. |

Cold open, end to end, is store open plus assembly plus first render: **32 + 1,146
+ 590 ≈ 1,768 ms before, 27 + 23 + 162 ≈ 212 ms after.**

The Python bounds in `packages/core/tests/test_perf_cold_open.py` are deliberately
loose (2 s per segment — roughly an order of magnitude over the reference number).
A tight wall-clock bound on a shared runner fails on a busy box and gets deleted
within a month. The deterministic guard is
`test_perf_canvas_assembly_does_not_rescan_the_whole_log`: it counts rows read
rather than seconds, and a return to the full rescan (206,010 rows) fails it on
any machine.

## Test Coverage

The `test` job is the authoritative Python gate. Pytest runs on Python
**3.10, 3.11, and 3.12** with `--cov-fail-under=89`, so it fails the job on its
own — no token, and therefore no fork PR that skips the check. The current
measurement is **89.75%** (7,720 statements, 791 missed).

The floor is a ratchet. On every pull request, `scripts/coverage_floor.py`
compares `[tool.coverage.report] fail_under` in `pyproject.toml` with the base
branch and fails when the head value is lower. Raise `fail_under` as coverage
improves; never lower it to unblock a change.

The 3.12 job also writes a per-distribution table to the job summary. At the
time of writing:

| Distribution | Coverage |
|---|---|
| `agentic_odi_cli` | 90.57% |
| `agentic_odi_connectors` | 91.05% |
| `agentic_odi_core` | 92.11% |
| `agentic_odi_mcp_server` | 81.92% |
| `agentic_odi_studio_api` | 88.13% |

[Codecov](https://codecov.io/gh/alehar9320/agentic-odi) stays a reporting
layer, not the gate. The 3.12 job uploads `coverage.xml` with the
`CODECOV_TOKEN` secret and `fail_ci_if_error: false`, so an outage or a fork
without secrets cannot turn the job red. `codecov.yml` keeps a **90%** project
target with a 1% dip — the same **89%** minimum pytest enforces — and patch
status is informational while new code lands. The upload carries the `python`
flag, and the README badge tracks that flag on `main`; the project status is
scoped to it so the Studio's lower number cannot turn it red.

The Studio is gated separately. `npm run test:coverage` runs Vitest with the V8
provider, writes `apps/studio/coverage/lcov.info`, and fails the studio job
below statements **74%**, branches **65%**, functions **75%**, and lines
**74%**. The measured values are 74.18%, 65.38%, 75.49%, and 74.33%, so the
thresholds have little slack; raise them as the suite grows. The lcov file is
uploaded to Codecov under the `studio` flag, also non-blocking — the Vitest
thresholds are what gate the merge.

Reproduce both reports locally:

```bash
# Python
uv run pytest \
  --cov=agentic_odi_cli \
  --cov=agentic_odi_connectors \
  --cov=agentic_odi_core \
  --cov=agentic_odi_mcp_server \
  --cov=agentic_odi_studio_api \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml

# Studio
npm --prefix apps/studio run test:coverage
```

The known gaps behind these numbers — recorded from issue #88 rather than fixed
by it — are listed in
[`docs/architecture/testing.md`](architecture/testing.md#known-coverage-gaps).

### Conventions

- Test files live under each project's `tests/` directory and are named
  `test_*.py`.
- Root `tests/` is reserved for cross-package checks (`contract/` and
  `scripts/`).
- Every async test is decorated with `@pytest.mark.asyncio`.
- Use `Client(mcp)` directly (no HTTP server needed) for fast, isolated tests.
- The MCP server's `reset_db` autouse fixture clears in-memory state before
  each test.

### Test Coverage Map

Generated from the test tree by `scripts/coverage_map.py`: every test file and
the source files it imports or shares a name with. CI fails when this table and
the code disagree, so do not edit it by hand — run
`uv run python scripts/coverage_map.py --write`.

<!-- coverage-map:start -->
| Test file | Exercises |
|---|---|
| `apps/cli/tests/test_backend.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`packages/core/src/agentic_odi_core/remote.py` |
| `apps/cli/tests/test_backend_edges.py` | `apps/cli/src/agentic_odi_cli/backend.py` |
| `apps/cli/tests/test_backend_selection.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `apps/cli/tests/test_build_info.py` | `apps/cli/src/agentic_odi_cli/_build_info.py`<br>`apps/cli/src/agentic_odi_cli/version.py` |
| `apps/cli/tests/test_chat_cli.py` | `apps/cli/src/agentic_odi_cli/chat.py`<br>`apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_chat_runtime.py` | `apps/cli/src/agentic_odi_cli/chat.py` |
| `apps/cli/tests/test_chat_wizard.py` | `apps/cli/src/agentic_odi_cli/chat.py`<br>`apps/cli/src/agentic_odi_cli/wizard.py` |
| `apps/cli/tests/test_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`apps/cli/src/agentic_odi_cli/version.py` |
| `apps/cli/tests/test_cli_edges.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_connectors_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/rest/connector.py` |
| `apps/cli/tests/test_connectors_edges.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`apps/cli/src/agentic_odi_cli/connectors.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/paths.py` |
| `apps/cli/tests/test_context.py` | `apps/cli/src/agentic_odi_cli/context.py` |
| `apps/cli/tests/test_customer_outcomes_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `apps/cli/tests/test_data_export.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `apps/cli/tests/test_desired_outcomes_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`apps/cli/src/agentic_odi_cli/desired_outcomes.py` |
| `apps/cli/tests/test_evidence_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_insight_commands.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_jobs_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_mascot.py` | `apps/cli/src/agentic_odi_cli/mascot.py` |
| `apps/cli/tests/test_onboard.py` | `apps/cli/src/agentic_odi_cli/onboard.py`<br>`apps/cli/src/agentic_odi_cli/profile.py` |
| `apps/cli/tests/test_paths.py` | `apps/cli/src/agentic_odi_cli/paths.py` |
| `apps/cli/tests/test_persistence.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `apps/cli/tests/test_profile.py` | `apps/cli/src/agentic_odi_cli/chat.py`<br>`apps/cli/src/agentic_odi_cli/profile.py` |
| `apps/cli/tests/test_profile_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_render.py` | `apps/cli/src/agentic_odi_cli/render.py` |
| `apps/cli/tests/test_schedule_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_segments_cli.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_settings_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_signals_cli.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_startup_perf.py` | — no direct source pair |
| `apps/cli/tests/test_stats_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`packages/core/src/agentic_odi_core/funnel.py`<br>`packages/core/src/agentic_odi_core/intent_store.py` |
| `apps/cli/tests/test_steps_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_studies_cli.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_summary_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_update.py` | `apps/cli/src/agentic_odi_cli/update.py` |
| `apps/cli/tests/test_update_check.py` | `apps/cli/src/agentic_odi_cli/update.py` |
| `apps/cli/tests/test_update_command.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`apps/cli/src/agentic_odi_cli/update.py`<br>`apps/cli/src/agentic_odi_cli/version.py` |
| `apps/cli/tests/test_update_edges.py` | `apps/cli/src/agentic_odi_cli/update.py` |
| `apps/cli/tests/test_version_flag.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`apps/cli/src/agentic_odi_cli/version.py` |
| `apps/cli/tests/test_wizard_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/mcp-server/tests/mcp_failures.py` | `packages/core/src/agentic_odi_core/remote.py` |
| `apps/mcp-server/tests/test_context_tools.py` | — no direct source pair |
| `apps/mcp-server/tests/test_customer_outcomes.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` |
| `apps/mcp-server/tests/test_graceful_shutdown.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `apps/mcp-server/tests/test_health.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` |
| `apps/mcp-server/tests/test_odi.py` | — no direct source pair |
| `apps/mcp-server/tests/test_parity.py` | — no direct source pair |
| `apps/mcp-server/tests/test_port_config.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` |
| `apps/mcp-server/tests/test_segments.py` | — no direct source pair |
| `apps/mcp-server/tests/test_server_tools.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` |
| `apps/mcp-server/tests/test_signals.py` | — no direct source pair |
| `apps/mcp-server/tests/test_tool_branches.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` |
| `apps/mcp-server/tests/test_tool_progress.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` |
| `apps/mcp-server/tests/test_tool_spec_validation.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py`<br>`packages/core/src/agentic_odi_core/contract.py` |
| `apps/mcp-server/tests/test_tools.py` | — no direct source pair |
| `apps/studio/e2e/a11y.spec.ts` | `apps/studio/e2e/a11y/knownPairs.ts`<br>`apps/studio/e2e/helpers.ts`<br>`apps/studio/src/test/contrast.ts` |
| `apps/studio/e2e/brief.spec.ts` | `apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/capture.spec.ts` | `apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/chat.spec.ts` | `apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/first-paint.spec.ts` | — no direct source pair |
| `apps/studio/e2e/first-run.spec.ts` | — no direct source pair |
| `apps/studio/e2e/landscape.spec.ts` | `apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/mcp-backend.spec.ts` | `apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/no-sidecar/offline.spec.ts` | — no direct source pair |
| `apps/studio/e2e/starters.spec.ts` | `apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/workspace.spec.ts` | `apps/studio/e2e/helpers.ts` |
| `apps/studio/src/App.test.tsx` | `apps/studio/src/App.tsx`<br>`apps/studio/src/api/studioApi.ts` |
| `apps/studio/src/api/sse.test.ts` | `apps/studio/src/api/sse.ts` |
| `apps/studio/src/api/studioApi.local.test.ts` | `apps/studio/src/api/studioApi.ts` |
| `apps/studio/src/api/studioApi.test.ts` | `apps/studio/src/api/studioApi.ts` |
| `apps/studio/src/assistant/attachments.test.ts` | `apps/studio/src/assistant/attachments.ts` |
| `apps/studio/src/assistant/claims.test.ts` | `apps/studio/src/assistant/claims.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/assistant/convert.test.ts` | `apps/studio/src/assistant/convert.ts`<br>`apps/studio/src/types.ts`<br>`apps/studio/src/ui/catalog.ts`<br>`apps/studio/src/ui/protocol.ts` |
| `apps/studio/src/assistant/dictation.test.ts` | `apps/studio/src/assistant/dictation.ts` |
| `apps/studio/src/assistant/extract/common.test.ts` | `apps/studio/src/assistant/extract/common.ts` |
| `apps/studio/src/assistant/extract/docx.test.ts` | `apps/studio/src/assistant/extract/common.ts`<br>`apps/studio/src/assistant/extract/docx.ts` |
| `apps/studio/src/assistant/parts.test.tsx` | `apps/studio/src/assistant/parts.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/assistant/queue.test.ts` | `apps/studio/src/assistant/queue.ts` |
| `apps/studio/src/assistant/quote.test.ts` | `apps/studio/src/assistant/quote.ts` |
| `apps/studio/src/assistant/starterCopy.test.ts` | `apps/studio/src/assistant/StudioRuntime.tsx` |
| `apps/studio/src/banners/BannerBridge.test.tsx` | `apps/studio/src/banners/BannerBridge.tsx`<br>`apps/studio/src/banners/BannerProvider.tsx`<br>`apps/studio/src/banners/BannerStack.tsx` |
| `apps/studio/src/banners/BannerProvider.test.tsx` | `apps/studio/src/banners/BannerProvider.tsx` |
| `apps/studio/src/banners/BannerStack.test.tsx` | `apps/studio/src/banners/BannerProvider.tsx`<br>`apps/studio/src/banners/BannerStack.tsx`<br>`apps/studio/src/banners/types.ts` |
| `apps/studio/src/banners/BannerStack.visual.test.tsx` | `apps/studio/src/banners/BannerStack.tsx`<br>`apps/studio/src/banners/catalog.ts`<br>`apps/studio/src/banners/types.ts` |
| `apps/studio/src/banners/BannerToasts.test.tsx` | `apps/studio/src/banners/BannerProvider.tsx`<br>`apps/studio/src/banners/BannerStack.tsx`<br>`apps/studio/src/banners/BannerToasts.tsx` |
| `apps/studio/src/banners/catalog.test.ts` | `apps/studio/src/banners/catalog.ts`<br>`apps/studio/src/banners/types.ts` |
| `apps/studio/src/banners/store.test.ts` | `apps/studio/src/banners/store.ts` |
| `apps/studio/src/bff/capabilities/registry.test.ts` | `apps/studio/src/bff/capabilities/registry.ts` |
| `apps/studio/src/bff/chat/orchestrator.test.ts` | `apps/studio/src/api/sse.ts`<br>`apps/studio/src/bff/chat/orchestrator.ts`<br>`apps/studio/src/bff/data/localDataService.ts`<br>`apps/studio/src/bff/memory/localMemoryService.ts`<br>`apps/studio/src/bff/store/memoryStore.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/bff/data/localDataService.test.ts` | `apps/studio/src/bff/data/localDataService.ts`<br>`apps/studio/src/bff/store/memoryStore.ts` |
| `apps/studio/src/bff/index.test.ts` | `apps/studio/src/bff/index.ts`<br>`apps/studio/src/bff/store/memoryStore.ts` |
| `apps/studio/src/bff/memory/localMemoryService.test.ts` | `apps/studio/src/bff/memory/localMemoryService.ts`<br>`apps/studio/src/bff/store/memoryStore.ts` |
| `apps/studio/src/bff/outbox.test.ts` | `apps/studio/src/bff/outbox.ts`<br>`apps/studio/src/bff/store/memoryStore.ts`<br>`apps/studio/src/bff/store/types.ts` |
| `apps/studio/src/bff/storageFacts.test.ts` | `apps/studio/src/bff/storageFacts.ts`<br>`apps/studio/src/bff/store/indexedDbStore.ts`<br>`apps/studio/src/bff/store/memoryStore.ts` |
| `apps/studio/src/bff/store/indexedDbStore.test.ts` | `apps/studio/src/bff/store/indexedDbStore.ts`<br>`apps/studio/src/bff/store/memoryStore.ts`<br>`apps/studio/src/bff/store/migrations.ts`<br>`apps/studio/src/bff/store/types.ts` |
| `apps/studio/src/bff/store/migrations.test.ts` | `apps/studio/src/bff/store/migrations.ts` |
| `apps/studio/src/bridge/desktopBridge.test.ts` | `apps/studio/src/bridge/desktopBridge.ts` |
| `apps/studio/src/components/BootFailurePage.test.tsx` | `apps/studio/src/components/BootFailurePage.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/ChangelogModal.test.tsx` | `apps/studio/src/api/studioApi.ts`<br>`apps/studio/src/components/ChangelogModal.tsx`<br>`apps/studio/src/lib/changelogRead.ts` |
| `apps/studio/src/components/FailurePanel.visual.test.tsx` | `apps/studio/src/components/FailurePanel.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/OdiMascot.test.tsx` | `apps/studio/src/components/OdiMascot.tsx` |
| `apps/studio/src/components/SettingsPanel.test.tsx` | `apps/studio/src/components/SettingsPanel.tsx`<br>`apps/studio/src/onboarding/OnboardingProvider.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/components/brief/BriefLens.test.tsx` | `apps/studio/src/components/brief/BriefLens.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/canvas/DirectCapture.test.tsx` | `apps/studio/src/api/studioApi.ts`<br>`apps/studio/src/components/canvas/DirectCapture.tsx` |
| `apps/studio/src/components/canvas/EvidenceStream.test.tsx` | `apps/studio/src/components/canvas/EvidenceStream.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/canvas/JobMap.test.tsx` | `apps/studio/src/components/canvas/JobMap.tsx`<br>`apps/studio/src/domain/jobStages.ts` |
| `apps/studio/src/components/canvas/MemoryPanel.test.tsx` | `apps/studio/src/components/canvas/MemoryPanel.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/canvas/OpportunityLandscape.test.tsx` | `apps/studio/src/components/canvas/OpportunityLandscape.tsx`<br>`apps/studio/src/lib/odi.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/canvas/OutcomeCard.test.tsx` | `apps/studio/src/components/canvas/OutcomeCard.tsx` |
| `apps/studio/src/components/canvas/OutcomeCardSample.test.tsx` | `apps/studio/src/components/canvas/OutcomeCard.tsx` |
| `apps/studio/src/components/canvas/SchedulePanel.test.tsx` | `apps/studio/src/components/canvas/SchedulePanel.tsx` |
| `apps/studio/src/components/canvas/SegmentBoard.test.tsx` | `apps/studio/src/components/canvas/SegmentBoard.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/canvas/ThesisAction.test.tsx` | `apps/studio/src/components/canvas/OutcomeCard.tsx` |
| `apps/studio/src/components/canvas/opportunityLandscape.perf.test.tsx` | `apps/studio/src/components/canvas/OpportunityLandscape.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/chat/ChatStage.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/ChatStage.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/chat/CommandPalette.test.tsx` | `apps/studio/src/components/chat/Composer.tsx`<br>`apps/studio/src/state/StudioContext.tsx` |
| `apps/studio/src/components/chat/Composer.test.tsx` | `apps/studio/src/components/chat/Composer.tsx`<br>`apps/studio/src/state/StudioContext.tsx` |
| `apps/studio/src/components/chat/Conversation.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/Conversation.tsx`<br>`apps/studio/src/types.ts`<br>`apps/studio/src/ui/catalog.ts`<br>`apps/studio/src/ui/protocol.ts` |
| `apps/studio/src/components/chat/Dictation.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/ThreadComposer.tsx`<br>`apps/studio/src/state/StudioContext.tsx` |
| `apps/studio/src/components/chat/ModelPicker.test.tsx` | `apps/studio/src/components/chat/ModelPicker.tsx` |
| `apps/studio/src/components/chat/QueueLane.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/assistant/queue.ts`<br>`apps/studio/src/components/chat/QueueLane.tsx`<br>`apps/studio/src/state/StudioContext.tsx` |
| `apps/studio/src/components/chat/SelectionToolbar.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/SelectionToolbar.tsx` |
| `apps/studio/src/components/chat/StallNotice.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/Conversation.tsx`<br>`apps/studio/src/components/chat/StallNotice.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/chat/SuggestionPills.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/composerParts.tsx`<br>`apps/studio/src/state/StudioContext.tsx` |
| `apps/studio/src/components/chat/ThreadComposer.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/ThreadComposer.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/chat/arrivalCount.test.ts` | `apps/studio/src/components/chat/arrivalCount.ts` |
| `apps/studio/src/components/customize/ConnectorSuggestionModal.test.tsx` | `apps/studio/src/components/customize/ConnectorSuggestionModal.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/customize/CustomizePage.test.tsx` | `apps/studio/src/components/customize/CustomizePage.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/layout/StudioBar.test.tsx` | `apps/studio/src/components/layout/StudioBar.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/components/layout/StudioBar.visual.test.tsx` | `apps/studio/src/components/layout/StudioBar.tsx` |
| `apps/studio/src/components/notifications/CatchUpFeed.test.tsx` | `apps/studio/src/App.tsx`<br>`apps/studio/src/api/studioApi.ts`<br>`apps/studio/src/components/notifications/CatchUpFeed.tsx`<br>`apps/studio/src/components/notifications/__fixtures__/signals.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/notifications/noFabricatedSignals.test.ts` | — no direct source pair |
| `apps/studio/src/components/records/RecordDetail.test.tsx` | `apps/studio/src/components/records/RecordDetail.tsx`<br>`apps/studio/src/components/records/RecordsPanel.tsx`<br>`apps/studio/src/lib/records.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/records/RecordsTable.test.tsx` | `apps/studio/src/components/records/RecordsTable.tsx`<br>`apps/studio/src/lib/records.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/settings/SettingsPanel.perFieldSave.test.tsx` | `apps/studio/src/components/SettingsPanel.tsx`<br>`apps/studio/src/onboarding/OnboardingProvider.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/components/settings/saves.test.ts` | `apps/studio/src/components/settings/saves.ts`<br>`apps/studio/src/components/settings/validation.ts` |
| `apps/studio/src/components/setup/IntroConversation.test.tsx` | `apps/studio/src/components/setup/IntroConversation.tsx`<br>`apps/studio/src/lib/intro.ts` |
| `apps/studio/src/components/setup/IntroConversation.visual.test.tsx` | `apps/studio/src/components/setup/IntroConversation.tsx` |
| `apps/studio/src/components/status/StatusDot.test.tsx` | `apps/studio/src/components/status/StatusDot.tsx` |
| `apps/studio/src/components/status/StatusDot.visual.test.tsx` | `apps/studio/src/components/icons.tsx`<br>`apps/studio/src/components/status/StatusDot.tsx` |
| `apps/studio/src/components/workspace/WorkbenchRail.test.tsx` | `apps/studio/src/components/workspace/WorkbenchRail.tsx` |
| `apps/studio/src/components/workspace/WorkspacePanel.test.tsx` | `apps/studio/src/components/workspace/WorkspacePanel.tsx` |
| `apps/studio/src/components/workspace/panels.test.tsx` | `apps/studio/src/components/workspace/panels.tsx` |
| `apps/studio/src/diagnostics/DiagnosticsModal.test.tsx` | `apps/studio/src/components/SettingsPanel.tsx`<br>`apps/studio/src/diagnostics/DiagnosticsModal.tsx`<br>`apps/studio/src/onboarding/OnboardingProvider.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/diagnostics/bundle.test.ts` | `apps/studio/src/diagnostics/bundle.ts` |
| `apps/studio/src/diagnostics/redact.test.ts` | `apps/studio/src/diagnostics/redact.ts` |
| `apps/studio/src/features/flags.test.ts` | `apps/studio/src/features/flags.ts` |
| `apps/studio/src/lib/boot.test.ts` | `apps/studio/src/lib/boot.ts` |
| `apps/studio/src/lib/brandCopy.test.ts` | `apps/studio/src/lib/brand.ts` |
| `apps/studio/src/lib/brief.test.ts` | `apps/studio/src/lib/brief.ts`<br>`apps/studio/src/lib/export.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/lib/canvasProvenance.test.ts` | `apps/studio/src/lib/canvasProvenance.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/lib/changelogRead.test.ts` | `apps/studio/src/lib/changelogRead.ts` |
| `apps/studio/src/lib/commands.test.ts` | `apps/studio/src/lib/commands.ts` |
| `apps/studio/src/lib/export.test.ts` | `apps/studio/src/lib/export.ts`<br>`apps/studio/src/types.ts`<br>`apps/studio/src/ui/catalog.ts`<br>`apps/studio/src/ui/protocol.ts` |
| `apps/studio/src/lib/focus.test.ts` | `apps/studio/src/lib/focus.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/lib/greeting.test.ts` | `apps/studio/src/lib/greeting.ts` |
| `apps/studio/src/lib/guidance.test.ts` | `apps/studio/src/lib/guidance.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/lib/intro.test.ts` | `apps/studio/src/lib/intro.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/lib/markdown.test.ts` | `apps/studio/src/lib/markdown.ts` |
| `apps/studio/src/lib/modelEndpoint.test.ts` | `apps/studio/src/lib/modelEndpoint.ts` |
| `apps/studio/src/lib/odi.test.ts` | `apps/studio/src/lib/odi.ts` |
| `apps/studio/src/lib/offlinePage.test.ts` | — no direct source pair |
| `apps/studio/src/lib/onlineStatus.test.tsx` | `apps/studio/src/lib/onlineStatus.ts` |
| `apps/studio/src/lib/records.test.ts` | `apps/studio/src/lib/records.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/lib/relativeTime.test.ts` | `apps/studio/src/lib/relativeTime.ts` |
| `apps/studio/src/lib/session.test.ts` | `apps/studio/src/lib/session.ts` |
| `apps/studio/src/lib/setup.test.ts` | `apps/studio/src/lib/setup.ts` |
| `apps/studio/src/lib/swRouting.test.ts` | `apps/studio/src/lib/swRouting.ts` |
| `apps/studio/src/lib/theme.test.ts` | `apps/studio/src/lib/theme.ts` |
| `apps/studio/src/onboarding/FirstRunWizard.test.tsx` | `apps/studio/src/onboarding/FirstRunWizard.tsx`<br>`apps/studio/src/onboarding/OnboardingProvider.tsx`<br>`apps/studio/src/onboarding/context.ts`<br>`apps/studio/src/onboarding/storage.ts` |
| `apps/studio/src/onboarding/machine.test.ts` | `apps/studio/src/onboarding/machine.ts`<br>`apps/studio/src/onboarding/storage.ts` |
| `apps/studio/src/state/StudioContext.test.tsx` | `apps/studio/src/assistant/queue.ts`<br>`apps/studio/src/lib/session.ts`<br>`apps/studio/src/state/StudioContext.tsx` |
| `apps/studio/src/styles/bootShell.test.ts` | — no direct source pair |
| `apps/studio/src/styles/brief.test.ts` | — no direct source pair |
| `apps/studio/src/styles/colors.test.ts` | — no direct source pair |
| `apps/studio/src/styles/print.test.ts` | — no direct source pair |
| `apps/studio/src/styles/theme.test.ts` | — no direct source pair |
| `apps/studio/src/test/a11y.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/ChangelogModal.tsx`<br>`apps/studio/src/components/SettingsPanel.tsx`<br>`apps/studio/src/components/canvas/JobMap.tsx`<br>`apps/studio/src/components/canvas/OpportunityLandscape.tsx`<br>`apps/studio/src/components/chat/ChatStage.tsx`<br>`apps/studio/src/components/chat/Composer.tsx`<br>`apps/studio/src/components/notifications/CatchUpFeed.tsx`<br>`apps/studio/src/onboarding/FirstRunWizard.tsx`<br>`apps/studio/src/onboarding/OnboardingProvider.tsx`<br>`apps/studio/src/onboarding/context.ts`<br>`apps/studio/src/test/axe.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/test/contrast.test.ts` | `apps/studio/src/test/contrast.ts` |
| `apps/studio/src/test/keyboard.test.tsx` | `apps/studio/src/App.tsx`<br>`apps/studio/src/lib/useFocusTrap.ts` |
| `apps/studio/src/ui/UiRenderer.test.tsx` | `apps/studio/src/ui/UiRenderer.tsx`<br>`apps/studio/src/ui/actions.ts`<br>`apps/studio/src/ui/catalog.ts`<br>`apps/studio/src/ui/protocol.ts`<br>`apps/studio/src/ui/registry.ts` |
| `apps/studio/src/ui/protocol.test.ts` | `apps/studio/src/ui/catalog.ts`<br>`apps/studio/src/ui/protocol.ts` |
| `apps/studio/src/updater/UpdateBanner.test.tsx` | `apps/studio/src/updater/UpdateBanner.tsx`<br>`apps/studio/src/updater/UpdateProvider.tsx`<br>`apps/studio/src/updater/service.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/updater/UpdateSettings.test.tsx` | `apps/studio/src/updater/UpdateProvider.tsx`<br>`apps/studio/src/updater/UpdateSettings.tsx`<br>`apps/studio/src/updater/service.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/updater/machine.test.ts` | `apps/studio/src/updater/machine.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/updater/service.test.ts` | `apps/studio/src/updater/service.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/updater/transport.test.ts` | `apps/studio/src/updater/transport.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/vendor/boundary.test.ts` | `apps/studio/src/vendor/boundary.ts`<br>`apps/studio/src/vendor/lib/utils.ts` |
| `apps/studio/src/vendor/ledger.test.ts` | — no direct source pair |
| `apps/studio/src/vendor/vendor.test.tsx` | — no direct source pair |
| `apps/studio-api/tests/test_api.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `apps/studio-api/tests/test_app_spa.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/main.py`<br>`packages/core/src/agentic_odi_core/messages.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `apps/studio-api/tests/test_boot_integrity.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/intent_store.py` |
| `apps/studio-api/tests/test_studio_api.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/chat.py` |
| `apps/studio-api/tests/test_studio_approvals.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/approvals.py` |
| `apps/studio-api/tests/test_studio_brief.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py` |
| `apps/studio-api/tests/test_studio_capabilities.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_chat_branches.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/connectors.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py` |
| `apps/studio-api/tests/test_studio_chat_prompt.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py` |
| `apps/studio-api/tests/test_studio_chat_stream.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/approvals.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py`<br>`packages/core/src/agentic_odi_core/contract.py` |
| `apps/studio-api/tests/test_studio_chat_ui.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py` |
| `apps/studio-api/tests/test_studio_claims.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/claims.py` |
| `apps/studio-api/tests/test_studio_connectors.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/connectors.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/registry.py` |
| `apps/studio-api/tests/test_studio_connectors_router.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/connectors.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py` |
| `apps/studio-api/tests/test_studio_conversations.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/claims.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py` |
| `apps/studio-api/tests/test_studio_diagnostics.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `apps/studio-api/tests/test_studio_errors.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/errors.py`<br>`packages/core/src/agentic_odi_core/remote.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `apps/studio-api/tests/test_studio_evidence.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_focus.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py` |
| `apps/studio-api/tests/test_studio_funnel.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`<br>`packages/core/src/agentic_odi_core/events.py`<br>`packages/core/src/agentic_odi_core/funnel.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `apps/studio-api/tests/test_studio_llm_proxy.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_manual_crud.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_marketplace.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/connectors.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/marketplace.py`<br>`packages/connectors/src/agentic_odi_connectors/marketplace.py` |
| `apps/studio-api/tests/test_studio_mcp_data.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/errors.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/mcp_data.py` |
| `apps/studio-api/tests/test_studio_memory.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/memory.py` |
| `apps/studio-api/tests/test_studio_model_router.py` | — no direct source pair |
| `apps/studio-api/tests/test_studio_models.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/probes.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/router.py` |
| `apps/studio-api/tests/test_studio_observability.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/observability.py` |
| `apps/studio-api/tests/test_studio_outcome_evidence_crud.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_probes.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/probes.py` |
| `apps/studio-api/tests/test_studio_proposals.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_router.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/errors.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/router.py`<br>`packages/core/src/agentic_odi_core/remote.py` |
| `apps/studio-api/tests/test_studio_segments.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/errors.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/router.py`<br>`packages/core/src/agentic_odi_core/remote.py` |
| `apps/studio-api/tests/test_studio_signals.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/errors.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/router.py`<br>`packages/core/src/agentic_odi_core/remote.py` |
| `apps/studio-api/tests/test_studio_studies.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/router.py` |
| `apps/studio-api/tests/test_studio_ui_spec.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/ui_spec.py` |
| `brand/tests/test_brand_assets.py` | — no direct source pair |
| `brand/tests/test_generated_sources.py` | — no direct source pair |
| `packages/connectors/tests/test_catalog.py` | `packages/connectors/src/agentic_odi_connectors/catalog.py`<br>`packages/connectors/src/agentic_odi_connectors/registry.py` |
| `packages/connectors/tests/test_config_path.py` | `packages/connectors/src/agentic_odi_connectors/paths.py` |
| `packages/connectors/tests/test_config_validation.py` | — no direct source pair |
| `packages/connectors/tests/test_evidence_equivalence.py` | `packages/connectors/src/agentic_odi_connectors/mapping.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/core/src/agentic_odi_core/models.py` |
| `packages/connectors/tests/test_factory.py` | `packages/connectors/src/agentic_odi_connectors/factory.py`<br>`packages/connectors/src/agentic_odi_connectors/mcp/connector.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/protocol.py`<br>`packages/connectors/src/agentic_odi_connectors/registry.py`<br>`packages/connectors/src/agentic_odi_connectors/rest/connector.py` |
| `packages/connectors/tests/test_http_client.py` | — no direct source pair |
| `packages/connectors/tests/test_mapping.py` | `packages/connectors/src/agentic_odi_connectors/mapping.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py` |
| `packages/connectors/tests/test_marketplace.py` | `packages/connectors/src/agentic_odi_connectors/catalog.py`<br>`packages/connectors/src/agentic_odi_connectors/marketplace.py` |
| `packages/connectors/tests/test_mcp_connector.py` | `packages/connectors/src/agentic_odi_connectors/mcp/connector.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py` |
| `packages/connectors/tests/test_rate_limit.py` | `packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/rate_limit.py` |
| `packages/connectors/tests/test_registry.py` | `packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/registry.py` |
| `packages/connectors/tests/test_rest_connector.py` | `packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/rest/connector.py` |
| `packages/connectors/tests/test_sink.py` | `packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/rate_limit.py`<br>`packages/connectors/src/agentic_odi_connectors/sink.py` |
| `packages/core/tests/test_capability_manifest.py` | `packages/core/src/agentic_odi_core/contract.py` |
| `packages/core/tests/test_claim_check.py` | `packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_claim_interview.py` | `packages/core/src/agentic_odi_core/evaluation.py`<br>`packages/core/src/agentic_odi_core/models.py` |
| `packages/core/tests/test_connection.py` | `packages/core/src/agentic_odi_core/connection.py` |
| `packages/core/tests/test_consent_pause.py` | `packages/core/src/agentic_odi_core/consent.py`<br>`packages/core/src/agentic_odi_core/contract.py`<br>`packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `packages/core/tests/test_errors.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_evaluation.py` | `packages/core/src/agentic_odi_core/evaluation.py` |
| `packages/core/tests/test_evaluation_harness.py` | `packages/core/src/agentic_odi_core/evaluation.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_events.py` | `packages/core/src/agentic_odi_core/intent_store.py` |
| `packages/core/tests/test_evidence_not_found.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_funnel.py` | `packages/core/src/agentic_odi_core/events.py`<br>`packages/core/src/agentic_odi_core/funnel.py`<br>`packages/core/src/agentic_odi_core/intent_store.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_funnel_service.py` | `packages/core/src/agentic_odi_core/funnel.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_intent_store.py` | `packages/core/src/agentic_odi_core/intent_store.py` |
| `packages/core/tests/test_job_validation.py` | `packages/core/src/agentic_odi_core/models.py` |
| `packages/core/tests/test_messages.py` | `packages/core/src/agentic_odi_core/contract.py`<br>`packages/core/src/agentic_odi_core/messages.py` |
| `packages/core/tests/test_models.py` | `packages/core/src/agentic_odi_core/models.py` |
| `packages/core/tests/test_opportunity_ranking.py` | `packages/core/src/agentic_odi_core/evaluation.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_opportunity_score.py` | `packages/core/src/agentic_odi_core/models.py` |
| `packages/core/tests/test_outcome_mapping.py` | `packages/core/src/agentic_odi_core/evaluation.py`<br>`packages/core/src/agentic_odi_core/mapping.py`<br>`packages/core/src/agentic_odi_core/models.py` |
| `packages/core/tests/test_outcome_validation.py` | `packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_pagination.py` | `packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_perf_cold_open.py` | `packages/core/src/agentic_odi_core/corpus.py`<br>`packages/core/src/agentic_odi_core/intent_store.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_proposals.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/factory.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_remote.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/remote.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_repository.py` | `packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `packages/core/tests/test_repository_factory.py` | `packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_repository_health.py` | `packages/core/src/agentic_odi_core/factory.py` |
| `packages/core/tests/test_router.py` | `packages/core/src/agentic_odi_core/router.py`<br>`packages/core/src/agentic_odi_core/steve_jobs.py` |
| `packages/core/tests/test_scheduled_work.py` | — no direct source pair |
| `packages/core/tests/test_schema.py` | `packages/core/src/agentic_odi_core/schema.py` |
| `packages/core/tests/test_segmentation.py` | `packages/core/src/agentic_odi_core/segmentation.py` |
| `packages/core/tests/test_segments_service.py` | `packages/core/src/agentic_odi_core/errors.py` |
| `packages/core/tests/test_service.py` | `packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_signal_inbox.py` | `packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_sqlite_integrity.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/integrity.py`<br>`packages/core/src/agentic_odi_core/intent_store.py`<br>`packages/core/src/agentic_odi_core/recovery.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_sqlite_repository.py` | `packages/core/src/agentic_odi_core/intent_store.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_strategy.py` | `packages/core/src/agentic_odi_core/strategy.py` |
| `packages/core/tests/test_study.py` | `packages/core/src/agentic_odi_core/contract.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/schema.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `tests/contract/test_cli_contract.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`packages/core/src/agentic_odi_core/contract.py` |
| `tests/contract/test_mcp_contract.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py`<br>`packages/core/src/agentic_odi_core/contract.py`<br>`packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/remote.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `tests/contract/test_protected_files.py` | — no direct source pair |
| `tests/scripts/test_assistant_ui_ledger.py` | `scripts/doc_check.py` |
| `tests/scripts/test_ci_release.py` | `scripts/ci_release.py` |
| `tests/scripts/test_cli_docs.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `tests/scripts/test_coverage_floor.py` | `scripts/coverage_floor.py` |
| `tests/scripts/test_coverage_map.py` | `scripts/coverage_map.py` |
| `tests/scripts/test_dev.py` | `scripts/dev.py` |
| `tests/scripts/test_dev_main.py` | — no direct source pair |
| `tests/scripts/test_doc_check.py` | `scripts/doc_check.py` |
| `tests/scripts/test_gen_corpus.py` | `packages/core/src/agentic_odi_core/corpus.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py`<br>`scripts/gen_corpus.py` |
| `tests/scripts/test_gen_job_stages.py` | `scripts/gen_job_stages.py` |
| `tests/scripts/test_label_merge_conflicts.py` | `scripts/pr_labels.py` |
| `tests/scripts/test_pr_body_gate.py` | — no direct source pair |
| `tests/scripts/test_pr_guards.py` | `scripts/pr_guards.py` |
| `tests/scripts/test_pr_labeler_workflow.py` | — no direct source pair |
| `tests/scripts/test_pr_labels.py` | `scripts/pr_labels.py`<br>`scripts/pr_provenance.py` |
| `tests/scripts/test_pr_provenance.py` | `scripts/pr_provenance.py` |
| `tests/scripts/test_release_assets.py` | `scripts/release_assets.py` |
| `tests/scripts/test_release_instructions.py` | `scripts/release_instructions.py` |
| `tests/scripts/test_release_version_gate.py` | — no direct source pair |
| `tests/scripts/test_release_workflow.py` | — no direct source pair |
| `tests/scripts/test_vendor_policy.py` | `scripts/vendor_policy.py` |
| `tests/scripts/test_version_sync.py` | `apps/cli/src/agentic_odi_cli/_build_info.py`<br>`scripts/check_version_parity.py` |
| `tests/scripts/test_workflow_triggers.py` | — no direct source pair |
| `tests/test_architecture.py` | — no direct source pair |
| `tests/test_dev_entrypoint.py` | — no direct source pair |
| `tests/test_docs_code_overview.py` | — no direct source pair |
| `tests/test_docs_method.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `tests/test_underserved_threshold_parity.py` | `packages/core/src/agentic_odi_core/evaluation.py` |
| `tests/test_worker_build_route.py` | — no direct source pair |
| `tests/test_worker_error_shape.py` | — no direct source pair |
| `tests/test_worker_security_headers.py` | — no direct source pair |
| `website/tests/site_support.py` | `website/tools/build_site.py` |
| `website/tests/test_ci_required.py` | — no direct source pair |
| `website/tests/test_content_sync.py` | `website/tools/build_sample.py`<br>`website/tools/extract.py` |
| `website/tests/test_design_system.py` | `website/tools/extract.py` |
| `website/tests/test_docs_render.py` | `website/tools/markdown_render.py` |
| `website/tests/test_generated.py` | `website/tools/build_site.py`<br>`website/tools/extract.py` |
| `website/tests/test_make_og.py` | `website/tools/make_og.py` |
| `website/tests/test_pages_deploy.py` | — no direct source pair |
| `website/tests/test_site.py` | `website/tools/extract.py` |
| `website/tests/test_theme.py` | — no direct source pair |
<!-- coverage-map:end -->

> [!TIP]
> Type `/test` in the AI assistant to have the agent run all tests and report the
> results automatically.

## Agent Session Tracking

Agent sessions are captured with the [Entire](https://docs.entire.io/overview)
CLI. The repository integration lives in `.entire/settings.json`,
`.cursor/hooks.json`, and `.opencode/plugins/entire.ts`. Run `entire status` to
confirm it is enabled and `entire checkpoint list` to inspect captured
checkpoints.
