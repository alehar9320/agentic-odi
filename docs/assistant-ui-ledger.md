# The assistant-ui ledger

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

## Runtime, store, and adapters

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
| `groupPartByType` / `GroupedParts` | Partial | `apps/studio/src/components/chat/workGrouping.ts` | — | The fallback fired: the turn's work groups through `GroupedParts` (see the message table), but with our own `workGrouping`. `groupPartByType` keys by part type or tool name alone, so a pending approval — a `tool-call` part — would be folded into the row. |
| `getExternalStoreMessages` / `bindExternalStoreMessage` | Rejected | — | — | One store. These exist to reconcile foreign messages, which we do not accept. |

## Thread

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

## Message and parts

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `MessagePrimitive.Parts` | Adopted | `apps/studio/src/components/chat/Conversation.tsx` | #238 | With the `components` map. |
| `MessagePrimitive.Attachments` | Adopted | `apps/studio/src/components/chat/Conversation.tsx` | #238 | User turns show what was sent. |
| `MessagePrimitive.Root` | Partial | `apps/studio/src/components/chat/Conversation.tsx` | — | The message wrapper is a hand-written article carrying `aria-busy` and the assistant avatar. |
| `MessagePrimitive.Quote` | Adopted | `apps/studio/src/assistant/quote.ts` | #435 | Renders the quoted passage on a sent turn. |
| `MessagePrimitive.Error` / `ErrorPrimitive` | Rejected | — | — | `FailurePanel` already renders the structured error, the retry copy, and the Try again action from `metadata.custom.error`. Swapping adds nothing and loses the ODI failure language. |
| `GenerativeUIRender` / `MessagePrimitive.GenerativeUI` | Decision | — | — | Would let a model emit UI we did not validate. The ODI catalog is schema-validated; revisit only if validation moves server-side. |
| `MessagePrimitive.GroupedParts` | Adopted | `apps/studio/src/components/chat/Conversation.tsx` | #392 | The reasoning and tool calls of one run fold into a single disclosure; `indicator="never"` keeps the activity line and caret where the `components` map put them. |
| `MessagePrimitive.PartByIndex` / `Content` | Rejected | — | — | `Parts` is the one path; aliases would be a second. |
| `MessagePartPrimitive.Text` / `.Image` / `.File` | Partial | `apps/studio/src/assistant/parts.tsx` | — | Rendered through the `components` map (custom `TextPart`, `FilePart`) rather than the bare primitives, which cannot show claim chips or extraction state. |
| `MessagePartPrimitive.InProgress` | Decision | — | — | Our `TypingPart` shows a phase ("checking the sidecar"). The primitive would flatten that to a generic indicator. |
| `MessagePartPrimitive.Messages` | Rejected | — | — | Nested conversations are not a Studio surface. |
| `useMessagePartText/Reasoning/Source/File/Image/Data` | Rejected | — | — | The `components` map already receives exactly these props. |

## Composer

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
| `ComposerPrimitive.AttachmentByIndex` | Rejected | — | — | The composer renders chips through `ComposerPrimitive.Attachments`, which scopes each to its attachment; the bare by-index form stays unused. |
| `composer.quote` / `composer.queue` / `composer.dictation` / `composer.submission` / `composer.inTransit` | Partial | `apps/studio/src/components/chat/ThreadComposer.tsx` | — | `quote` and `dictation` are read today; `queue` arrives with #410, and `submission`/`inTransit` matter to that issue's honesty: a sent message the thread does not show yet must not look lost. |

## Action bar

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `ActionBarPrimitive.Root` / `.Copy` / `.Edit` / `.Reload` | Adopted | `apps/studio/src/components/chat/Conversation.tsx` | #238 | The reply's own controls. |
| `ActionBarPrimitive.Speak` / `.StopSpeaking` | Planned | — | #412 | Read a reply aloud. |
| `ActionBarPrimitive.FeedbackPositive` / `.FeedbackNegative` | Planned | — | #414 | Local-only rating. |
| `ActionBarPrimitive.ExportMarkdown` | Partial | `apps/studio/src/lib/export.ts` | — | Whole-conversation Markdown export exists and also serialises generated surfaces. Adopting the primitive for one reply would produce a second, weaker export format. |
| `ActionBarMorePrimitive` | Decision | — | — | An overflow menu earns its place only when the action row exceeds ~5 buttons; #412 and #414 add two. Revisit after both land. |

## Branch picker

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `BranchPickerPrimitive.Root` / `.Previous` / `.Next` / `.Count` / `.Number` | Adopted | `apps/studio/src/components/chat/Conversation.tsx` | #238 | Exposed only when `branchCount > 1`. Branching, editing, and regenerating round-trip through the sidecar's `head_id`. |

## Attachments

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| Attachment adapter (`AttachmentAdapter`) | Adopted | `apps/studio/src/assistant/attachments.ts` | #238 | Text extraction capped at 20k chars, images capped at 5 MB, refusals explained. |
| Drop and paste | Adopted | `apps/studio/src/components/chat/ThreadComposer.tsx` | #238 | The composer follows the same accept rules as the input. |
| `AttachmentPrimitive.Root` / `.Name` / `.Remove` / `unstable_Thumb` | Partial | `apps/studio/src/components/chat/ThreadComposer.tsx` | — | The composer chip composes the primitive inside `ComposerPrimitive.Attachments`, which scopes each chip to its own attachment; the extraction state, the refusal reason and the size ride inside `Root` as children, so the primitive shows more than a name. The sent-turn chip in `parts.tsx` still writes its own `attachment-chip` markup, so this is a partial slice of #859. |

## Thread list

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

## Queue

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `createMessageQueue(driver)` | Adopted | `apps/studio/src/assistant/queue.ts` | #410 | `driver.run(message, {steer})`, optional `driver.cancel`. |
| `MessageQueueController` | Adopted | `apps/studio/src/assistant/queue.ts` | #410 | `notifyBusy` / `notifyIdle` / `notifyCancelled` / `hold` / `release` / `clear` / `subscribe` — the cancel pause is why we must not hand-roll. |
| `QueueItemPrimitive.Text` / `.Steer` / `.Remove` | Adopted | `apps/studio/src/components/chat/QueueLane.tsx` | #410 | One lane above the composer. |
| `QueueItemState.prompt` | Rejected | — | — | Deprecated in the installed types; derive text from `parts`. |

## Reasoning and work

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `ChainOfThoughtPrimitive.Root` / `.AccordionTrigger` / `.Parts` | Rejected | — | — | Checked against the installed 0.15.31 rather than the docs: `groupMessageParts` starts a run at any adjacent `tool-call` or `reasoning` part, so its one disclosure would gather a write that is still asking. `GroupedParts` with `workGrouping` ends a run at an unanswered approval. |
| Pending approvals inside a group | Rejected | — | — | A pending write is a question, not history. It stays ungrouped and visible, always. |
| `useToolCallElapsed` | Rejected | — | — | It reads `part.timing`, and none of our parts carry one — the sidecar's frames report a call started and settled, never how long it took. `WorkBlock` times only a run the browser watched, and a restored turn says *Worked · N calls* rather than inventing a duration. |
| `useMessageTiming` | Decision | — | — | Tokens/second is engineering telemetry. Useful to us, not to the PM; expose it only behind a diagnostics toggle if at all. |

## Selection and quote

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `SelectionToolbarPrimitive.Root` / `.Quote` | Adopted | `apps/studio/src/components/chat/SelectionToolbar.tsx` | #435 | Quote on select, inside one message. |
| `data-aui-quote-selectable="false"` | Adopted | `apps/studio/src/assistant/parts.tsx` | #435 | Marks tool traces, approval cards, and generated surfaces as non-prose; inline claim chips stay selectable. |
| `QuoteInfo` (`{ text, messageId }`) / `useMessageQuote` | Adopted | `apps/studio/src/assistant/quote.ts` | #435 | The quote persists in `metadata.custom.quote` and renders on the sent turn. |

## Errors and honesty

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| Structured turn failure | Adopted | `apps/studio/src/components/FailurePanel.tsx` | #129 | `metadata.custom.error` / `retryText`, rendered by `FailurePanel`. |
| `unstable_useMessageStallDetection` | Adopted | `apps/studio/src/components/chat/StallNotice.tsx` | #431 | Speaks only when output stops moving. |
| `MessageNotSentError` | Decision | — | — | See the runtime table. |
| `ErrorPrimitive` | Rejected | — | — | See the message table. |

## Assistant modal

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `AssistantModalPrimitive` (`Root`/`Trigger`/`Content`/`Anchor`) | Decision | — | — | A floating assistant on the canvas. The composer already stays on screen while a lens is open; a second surface must justify a second runtime instance and a second place errors can appear. |

## State hooks and utilities

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

## Model context — "the assistant sees the app"

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `useAssistantContext` / `ModelContextRegistry` / `mergeModelContexts` / `useModelContextSnapshot` | Rejected | — | — | Focus reaches the model as a pointer the sidecar re-reads (`apps/studio/src/lib/focus.ts`, `chat.py:_focus_context`), which is what makes the description true. The registry feeds a prompt a client authors, and `useExternalStoreRuntime` has no send path that carries it — a prototype proved `getModelContext()` returns nothing here. #425 delivered the pointer instead. |
| `makeAssistantVisible` | Rejected | — | — | Wrapping canvas cards to make them describable is not needed: the composer already names the focused record from the snapshot it holds, and refuses to name it when the snapshot cannot (`focusedSubjectLabel`). Per-card visibility declarations would be a second description of the same screen. |
| `useAssistantInstructions` | Rejected | — | — | The sidecar assembles the ODI system prompt. A client-side instruction layer would be a second authority and would drift from the methodology guardrails. |
| `AssistantFrameHost` / `AssistantFrameProvider` / `useAssistantFrameHost` / `frame` transport | Decision | — | — | Embeds the assistant in someone else's page. The Studio is the product surface, not an embedded widget. |

## Tools and toolkits

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

## Generative UI and MCP Apps

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| ODI surfaces as `data` parts | Adopted | `apps/studio/src/ui` | #55 | Validated by a catalog manifest and rendered through the same `UiRenderer`. |
| `GenerativeUIRender` / A2UI / `json-generative-ui` | Decision | — | — | Model-authored UI would bypass schema validation. Revisit only with server-side validation and a CSP story. |
| MCP Apps (`McpAppRenderer`, `csp`, `bridge`, `ui://` resources) | Decision | — | — | Connector tools could render their own UI inline. Blocked on the sandbox origin and CSP decision, and there is no front door yet (#90). Never ship a frame before that. |
| Realtime voice (`createVoiceSession`, `OpenAIRealtimeVoiceAdapter`, `useVoiceState`/`useVoiceVolume`/`useVoiceControls`) | Decision | — | — | Needs an audio provider, a cost, and even WebKit support in Tauri. #413 (dictation) covered the realistic need first. |

## Observability

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
| `DevToolsHooks` / `DevToolsProviderApi` | Rejected | — | — | Developer surface, not a PM surface. `docs/` and the sidecar's diagnostics already cover the need. |
| `webmcp` host/registration | Rejected | — | — | Would expose the Studio's actions to an external agent browser. Out of scope for a local-first app with approvals. |

## The count

| Status | Rows |
|---|---|
| Adopted | 45 |
| Partial | 10 |
| Planned | 14 |
| Decision | 26 |
| Rejected | 34 |
| Total | 129 |

Read it as: **52** of the library's 129 relevant capabilities already deliver
something a person can use, **20** more are carried by open issues, **26** rows
wait on a named decision, and **31** are rejected with a reason. Every row is
accounted for — that is the whole point of the page.

