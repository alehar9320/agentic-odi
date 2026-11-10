# Running The Living Studio

**The Living Studio** is the conversational GUI for Outcome-Driven Innovation:
an interactive Opportunity Landscape, Universal Job Map, and WYSIWYG Impact
Simulation, paired with an autonomous agent connected to the MCP server.

The Studio runs three ways locally, plus a hosted deployment. All of them serve
the same SPA, which talks only to the sidecar on `http://127.0.0.1:8100` — the
SPA never contacts MCP or the LLM directly.

## Architecture

```text
┌────────────────────────────┐  /api (JSON)  ┌───────────────────────────────┐
│  Living Studio SPA         │ ────────────▶ │  apps/studio-api (sidecar)    │
│  React + TS + Vite         │  /api/chat    │  FastAPI on 127.0.0.1:8100    │
│  (browser or Tauri webview)│ ◀──────────── │  - config / health / canvas   │
└────────────────────────────┘  SSE stream   │  - steps / outcomes (via MCP) │
                                             │  - /api/chat (LLM tool-loop)  │
                                             │  - conversations + PM memory  │
                                             └───────────────┬───────────────┘
                                                             │ MCP (HTTP)
                                                             ▼
                                             ┌───────────────────────────────┐
                                             │  apps/mcp-server :8000/mcp    │
                                             └───────────────────────────────┘
                                                             ▲
                                                             │ OpenAI-compatible
                                             ┌───────────────┴───────────────┐
                                             │  Your local LLM backend       │
                                             └───────────────────────────────┘
```

## Interface

The Studio opens as a conversation, not a dashboard.

| Surface | What it does |
|---|---|
| **First paint** | The window opens already the right colour. `apps/studio/index.html` carries an inline `<style>` with the background and the shell grid (bar, rail, stage) and a short inline script that resolves the theme — the stored `studio.settings` choice, or `prefers-color-scheme` when nothing is stored — and sets the class on `<html>` before the module bundle parses. React replaces the shell on its first commit, so there is no white flash and no dark-then-light flip. The inline colours are copies of `--bg` and `--line` in `src/styles/theme.css`, and `src/styles/bootShell.test.ts` fails if the two drift apart. |
| **First minute** | The studio opens on one question — what do you want to win — with three starters and the composer already focused. Nothing covers the stage: no tour, no form, no required step, and no warning about a server nothing you have done needs yet. After the first exchange, at most one quiet line suggests the next thing (add context, or capture the evidence a score is missing). It sits above the composer, never over the thread, and can be dismissed forever. |
| **Product tour** | An optional four-step tour: what the studio is, which ambition brought you here, the live state of your sidecar/MCP/model (with inline repair when the model is down), and where the outcome lands. The four doors are **I have one in mind**, **My boss handed me a priority**, **Help me find the next one**, and **Pressure-test a bet**; each starts the matching conversation. The last scene plots the scored sample outcome on the landscape beside two comparisons and names the evidence the sample is missing. It ends on one honest choice: **Start your own job** removes every record the tour made (and never a job you made), or **Keep the sample to poke at** leaves the sample marked. It never opens by itself: **Show me around** on the home stage opens it, and **Settings → Replay the tour** starts it over. |
| **Context conversation** | Opened when you ask for it — the **Start with you and your team** starter, the context hint, `/start`, or Settings. A five-turn introduction in the chat, led by the agent: who you are and your team, who feels the problem first, what they are trying to win, where it breaks, and what you already have. One question at a time, examples shown as muted text, with **Skip this question** and **Explore on my own** always available. The five answers come back as an editable card, in your words; skipping stores nothing, and progress is kept as a draft. |
| **Hero** | One headline above the composer. A first run holds a single invitation — *What do you want to win?* — and never changes while you think. With context or canvas data it becomes a quiet rotation: a greeting (time of day, plus your name if you set one in Settings), the product/job you set up, or what is already on the canvas. It stays still under `prefers-reduced-motion`. |
| **Starter cards** | Above the composer, three canvas-aware conversation cards name a situation the person is actually in rather than one of our nouns: **Turn 40 interview notes into one bet**, **Find what the churn spike is telling you**, and **Inherit a roadmap without inheriting its assumptions**. An empty canvas always offers those three, in that order; once the canvas holds outcomes or jobs the second and third swap to **Pressure-test a bet** and **Capture what you heard**. Each card carries a subtitle and the artifact it produces (`artifact` on `StudioSuggestion`), which the card layout (#317) renders. Select one to start that prompt in the thread — the prompt is sent verbatim, and it opens with the material the person brings. **Opportunity landscape** remains a separate, quiet shortcut. |
| **Composer** | Docked at the bottom of the transcript. `Enter` sends, `Shift`+`Enter` adds a line, `Cmd/Ctrl`+`K` focuses it, `/` opens the command palette, and the paperclip attaches a text file or an image. Files can also be dropped anywhere on the composer or pasted from the clipboard (a clipboard carrying both text and a file keeps the text and attaches the file), and each one is shown with a size (and a thumbnail, for images) plus a remove control before it is sent; a file whose format the studio does not accept is refused with the reason instead of becoming a chip that promises content the model will never see, and a file it accepts but cannot turn into content stays on the chip marked *Could not read this file*, with send disabled, until it is removed. The hint row's **Model** control lists the ids the configured backend reports and writes the choice through the same Settings store as the Base URL field. The send button becomes a stop button while a reply streams. Selecting prose in a reply shows **Quote**; one click puts the passage in the composer as a verbatim blockquote attributed to the reply, removable without touching the question you typed, and it is sent as part of the question. On an empty draft `↑` recalls the message you sent last — again for the one before it — and `↓` walks forward and finally restores the draft you were typing; inside a multi-line draft the arrows keep their native caret behavior. |
| **Bar** | The only persistent chrome: home, **New thread**, catch-up, live model status, **Customize**, and settings. **New thread** shows its words above 720px and is named *Start a new thread* at every width; it is switched off with the reason *This thread is already new.* when there is nothing to leave, asks — *A reply is still coming. Stop it and start a new thread?* — only while a reply is in flight, and otherwise gives the thread back for ten seconds through **Undo** on the toast. Starting one creates no conversation until the first message, and moves nothing on the canvas. Home closes what is open and never discards the thread. There is no navigation drawer to compete with the thread. |
| **Customize** | The one place to manage connectors. It replaces the conversation while open (the bar stays, so leaving is one gesture) and shows three bands: what is installed, read from the same `connectors.json` the CLI uses; a handful of curated picks as non-gating examples; and the marketplace, populated from the trusted vendor registry so a listing can be added by id. Capability areas filter the shelf, a listing that needs a token names its environment variable and stores nothing, a listing that cannot be installed says why, and an unreachable marketplace is reported rather than shown as an empty list. A studio with nothing installed suggests a connector when one would help; dismissing the suggestion keeps it dismissed. |
| **Rail** | Above the conversation, and only once the thread has produced something: `Landscape · N`, `Job map · N`, `Evidence · N`, `What I know · N`. Every item is derived from the canvas and the memory, so the strip is a record of the work rather than a fixed menu. |
| **Lens** | A view docks to the right of the thread on wide screens and becomes a full-height sheet on narrow ones. The transcript and the composer stay on screen and stay usable; `Esc`, **Close**, or the rail chip closes it. Closing puts focus back on the chip that opened the lens, so `Esc` never drops the caret into the composer behind it — that only happens when nothing else is open. Every lens ends in one sentence that re-enters the conversation — *Ask which to chase*, *Walk me through the job*, *Weigh the evidence* — so leaving a view is never a return to a menu. Settings and catch-up use the same lens. In the Records lens a row is a button: it opens that one record below the tables with every field the store holds, its id behind **Copy id**, and each parent that exists as a filter that narrows the tables without leaving the lens. Where the store knows nothing it says so — `—` for an absent value, `unscored` for an outcome with no score, and the plain line *This record stores only the fields above — no author and no timestamp.* |

Replies render Markdown (headings, lists, emphasis, inline and fenced code).
While a turn has produced no text yet, an activity line names the phase (*Waking
the model*, *Opening your studio tools*, *Thinking*) with a shimmer and an
elapsed hint; the phase is announced once to assistive technology, and the reply
is marked busy until it settles so a screen reader reads the answer, not every
token. A turn that used your tools folds what it did into one work row —
*Working… · 3 calls* while it runs, *Worked for 12s · 3 calls* once it settles —
open on the way, closed at rest, and reopening it shows the turn's own record
rather than a summary the model wrote: reasoning in a disclosure that opens while
it is being written and collapses to *Thought for Ns*, then each MCP call as a
trace chip. A write still asking permission is never folded in: it stays unfolded
beside the answer until you answer, because a question is not history. Prose,
sources, and generated surfaces sit outside the row, and a turn that only thought
needs no row at all. A conversation reopened from the store counts its calls
without a duration — only the browser that watched the run owns the clock.

### Slash commands

Type `/` to open the palette. `Up`/`Down` move, `Enter` or `Tab` runs the
selected command, `Esc` closes it. While an input method is composing — Japanese,
Chinese, Korean, or any other — its keys are never interpreted: `Enter` and the
arrows choose a candidate, they do not run, move, dismiss, or send. Commands are
handled in the SPA and never call the model, so they work when it is offline.

| Command | Effect |
|---|---|
| `/help` | Every command, as a notice in the transcript |
| `/start` | Resume the context conversation |
| `/new` | New conversation |
| `/home` | Return to the empty stage |
| `/jobs` | Job summary, then the job map |
| `/landscape`, `/jobmap`, `/segments`, `/evidence`, `/records`, `/settings` | Open that lens beside the conversation |
| `/brief` | Open the decision brief — the document a review reads, ready to download or print |
| `/impact`, `/capture` | Start the conversation that produces the card. `/capture` falls back to the offline form when no model answers. |
| `/status` | Model, MCP, context, and canvas status |

Unknown commands produce a transcript notice pointing at `/help`.

### The product tour

The stage is the front door; the tour is an answer to "show me around", not a
gate. It is skippable at every step (`Skip the tour` or `Escape`), resumable
(progress is stored after every transition in `localStorage["studio.onboarding"]`),
and replayable from Settings. Nothing opens it automatically, and a fresh
install writes no record until the person asks for it.

Everything lives in `apps/studio/src/onboarding/`:

| File | Role |
|---|---|
| `content.ts` | Steps and goal copy as typed data — the only place the words live |
| `machine.ts` | Pure state transitions, no React or storage |
| `storage.ts` | Versioned, defensive `localStorage` persistence |
| `OnboardingProvider.tsx` | Explicit opening, persistence, replay |
| `FirstRunWizard.tsx`, `steps.tsx`, `onboarding.css` | The dialog |
| `../features/flags.ts` | The `firstRunWizard` toggle |

`App.tsx` only wires the provider and the wizard around the existing shell;
the chat, canvas, and sidecar code are untouched.

#### Toggling the tour

`firstRunWizard` defaults to on. Resolution order, highest first:

| Source | Example | Use |
|---|---|---|
| Query parameter | `?flags=firstRunWizard:off` | QA a build without rebuilding |
| Local override | `localStorage["studio.flags.firstRunWizard"] = "off"` | Per-browser opt-out |
| Build environment | `VITE_STUDIO_FIRST_RUN_WIZARD=off npm --prefix apps/studio run build` | Ship it dark |
| Default | on | |

Accepted values are `1`/`0`, `true`/`false`, `on`/`off`, `yes`/`no`, and
`enabled`/`disabled`. With the flag off, no dialog renders, no onboarding state
is written, and Settings hides the replay action.

### The first-run introduction

The stage's **Start with you and your team** door opens a five-turn
introduction, in the order a colleague would ask: what you are working on and
your part in it, who feels the problem first, what they are trying to win,
where it breaks, and what you already have. The agent speaks first and asks one
question at a time; the two example answers under the composer are illustrations
and never quick replies, so a click can never store an example as the answer.

Every reply is kept whole as a quote and its turn gets the sentence, capped at
280 characters. Skipping stores nothing; **Explore on my own** and `Escape`
close without saving a partial brief. Progress lives in
`localStorage["studio.intro"]`, so a reload resumes on the same turn. The five
answers become a card of five lines, each editable in place (Enter saves,
Escape cancels), with one primary **Looks like me** and a quiet **Skip the
rest**. Accepting writes `StudioBrief` — now with optional `role`, `team`, and
`evidence_at_hand` — and creates or updates the Job through the same path the
old panel used. No sidecar call and no model are needed.

A `studio.setupDraft` from the five-field panel is migrated once into turns 1–4
and its vision line into a note, then removed. The introduction is behind the
`firstRunIntro` flag, which defaults to on and resolves in the same order as the
tour: `?flags=firstRunIntro:off`,
`localStorage["studio.flags.firstRunIntro"]`, then
`VITE_STUDIO_FIRST_RUN_INTRO`. With it off, the old `SetupConversation` stays
mounted for one release.

| File | Role |
|---|---|
| `apps/studio/src/lib/intro.ts` | Turns, parsing, proposed defaults, draft storage, migration, and brief mapping |
| `apps/studio/src/components/setup/IntroConversation.tsx` | The conversation and the editable summary card |
| `../features/flags.ts` | The `firstRunIntro` toggle |

### Guidance, not gates

Nothing is a prerequisite. The home stage keeps a dashed **Start with you and
your team** pill, and the introduction reopens exactly where you left off.
`/start` and Settings do the same. The conversation also understands a natural
reply: say "skip", "not now", or "show me the landscape" and it reacts instead
of recording it as an answer. When a brief exists, it opens on a review and asks
what changed rather than asking everything again.

After the first exchange, `lib/guidance.ts` picks at most one hint worth showing:
context the studio does not have, or the customer evidence a score is missing.
Context outranks evidence because it makes every later answer better. Dismissals
are permanent (`localStorage["studio.guidance"]`), and with nothing useful to say
the line does not render at all — a hint system that keeps finding things to say
becomes the modal it replaced.

### Without a model

A browser with no model configured is the design working, not a failure. The
Studio says so in one place and keeps going:

- The bar's model chip reads **Local**, and its accessible name and tooltip say
  *Answering from your device. No model connected.* That is read straight from
  your settings — it needs no probe, so it is true on the first paint. A measured
  answer outranks the guess: when the sidecar vouches for a model the chip reads
  **Live**, and when it reports the model is not there, **Local mode**.
  **Connecting** is reserved for an endpoint that is configured and has not
  answered yet — nobody spins for a connection they are not trying to make.
- The light that says which of those it is comes from one primitive,
  `apps/studio/src/components/status/StatusDot.tsx`: one 7 px disc in the tone's
  color, `aria-hidden` when a word already states the state, named by `label`
  when it stands alone. A `.studio-pill` is a label, not an indicator, so it
  carries no dot of its own.
- A reply that no model produced carries one line, on that reply: **Local draft,
  no model connected**. It is a button, and it opens Settings. It never repeats
  on the replies around it, and nothing about it covers the thread.
- The work still happens. `apps/studio/src/bff` is the studio's own BFF running
  in the browser: the conversation, the canvas, and memory are read and written
  in IndexedDB, and the deterministic assistant answers ODI questions, creates
  jobs, records and re-scores outcomes, and renders the board with no server at
  all.
- The outbox is shared by every tab in the origin, so two tabs would otherwise
  drain it and send each record twice. `apps/studio/src/bff/outbox.ts` takes a
  drain guard for the length of a run: `navigator.locks` where the browser has
  it, and a lease row in the store's `meta` store — with an expiry, renewed
  while the drain runs — where it does not. A tab that loses the race leaves the
  records pending and picks them up on the next trigger, so a closed tab's queue
  resumes instead of stalling.
- The browser store can change shape without losing what is in it. The schema
  version and one migration per step live in
  `apps/studio/src/bff/store/migrations.ts`; opening the database runs every
  registered step from the version the person has up to `DB_VERSION`, so a
  release that adds a store upgrades an existing database instead of failing to
  open it. A version bump with no migration is caught by a test before it ships.
- When a second tab opens a newer schema, the first tab would otherwise hold the
  old connection and block the upgrade. `IndexedDbLocalStore` closes its
  connection on `versionchange` and sets `needsReload`, which the app can read
  to show "Reload to continue" rather than hanging.
- Where that work sits, and how much room it takes, is one call away:
  `bff/storageFacts.ts` reports the engine, the database name, the record count,
  the newest write the records carry, and whether the browser agreed to keep the
  store across restarts — plus the settings keys in `localStorage` by name and
  size, never by value, since one of them holds your model key. See
  [Data flow → Storage facts](architecture/data-flow.md).
- A warning strip appears only for something that actually broke: a model or
  sidecar that this session reached and then lost, or a check you asked for by
  pressing **Recheck** or running the tour's live step. Opening Settings measures
  the connections for its own rows and keeps the answer to itself — reading a
  settings panel is not an outage to announce across the window. Background health
  polls may retire a warning, never raise one.
- Settings → Base URL and Model reconnect the assistant whenever you are ready.
  Each field saves when it is left, and the section says **Saved** once an edit
  lands; a value the studio cannot use (a URL that is not an address, an empty
  model name) is refused beside the field with the reason and the last good value
  stays in effect. There is no Save button and no way for one section's edit to
  discard another's. Each section is its own module under
  `apps/studio/src/components/settings/sections/` and reports its own loading and
  failure in place, so a connector fetch that fails shows its error in the
  Connections section and leaves the Model controls beside it working.
  A keyless server on your own network (Ollama, LM Studio, anything on loopback
  or a private address) counts as configured; a public URL without a key does
  not, and `isEndpointConfigured` in `apps/studio/src/lib/modelEndpoint.ts` is
  the single place that decides, for the chip, the capability probe, and the
  chat provider.

  A configured endpoint on your own network is only reachable from a page served
  from that same device. `endpointReachability` in
  `apps/studio/src/lib/modelEndpoint.ts` compares the endpoint's host with the
  page's origin: a loopback or private-address endpoint is **device-only** when
  opened from a hosted page, and the studio says so rather than pretending it can
  connect. The capability probe reports `endpoint-model` as unavailable with the
  reason, and the bar's model chip titles it "local endpoint, not reachable from
  this page" while keeping its light unknown — use the desktop app or open the
  Studio on this device.

The user's context is sent with every chat request, so the assistant starts from
the product, audience, job, and problem rather than asking for them again.

### When the studio is not running

The first minute of a first visit never depends on a local server being up, so
nothing on screen can claim otherwise before the person has asked for something.

- The stage paints from local data: the canvas, the thread you left, and the
  composer. The request for sidecar defaults is a convenience that may fill in
  settings later; a slow or absent sidecar cannot hold the first screen behind
  it, and its failure is silent. A proxy that accepts the connection and never
  answers is bounded at 1,200 ms, so boot carries on with the defaults it already
  has rather than waiting on a reply that may never come.
- Health, connector, and capability probes wait until the browser is idle (or
  two seconds), and are given up entirely if you send a message first. A negative
  they find keeps the studio **unknown** rather than **down**.
- Sending a message is not gated on a server. The request goes to the sidecar,
  and when nothing answers at the transport level the same turn is carried by the
  browser BFF. You get an answer, labelled for what it is. The same is true of a
  model address the browser simply cannot reach — a blocked mixed-content call, a
  laptop off the network its Ollama lives on: the turn is answered on the device
  rather than failing on the first try. An endpoint that *did* answer badly (a
  rejected key) is reported, not hidden behind a local draft that looks like the
  model you asked for.
- The **sidecar isn't running** strip is for the loss of a sidecar this session
  was talking to: the assistant paused and live data froze is only said when both
  are true. It offers **Recheck** and **Start the sidecar**, is dismissible for
  the session, and clears itself the moment the sidecar answers.
- The canvas keeps showing the last thing it drew instead of going blank; a failed
  canvas is a failure panel with Retry, not an empty board. **Settings → About →
  Diagnostics** creates an opt-in, in-memory-only local bundle. It previews the
  exact JSON and byte count before Copy or Save, recursively redacts secrets,
  strips URL credentials and query strings, and contains machine metadata and
  turn counts/timings only — never messages, observations, brief, theses,
  attachments, or canvas entities. It works with the sidecar down. No report is
  uploaded, and no diagnostic capture is retained across reloads.
- **What's New** still opens in front-end-only mode; without the sidecar it
  explains that release notes are unavailable rather than showing invented notes.

On the CLI, the same condition is `BackendError("could not reach MCP server …")`,
rendered as `Error: …` followed by `Hint: Start the MCP server (python -m
agentic_odi_mcp_server)…`. When the Studio is reached through the free
Cloudflare Worker proxy, a missing `SIDECAR_URL` is reported to the browser as
`{"error": {"code": "mcp_unreachable", "suggestion": "Start the studio sidecar
…"}}` with `X-Request-ID` echoed for support.

### When the database failed its check

A store that is *reachable* but *damaged* is a different condition from a sidecar
that is down, and it is shown differently. The sidecar runs a bounded
`PRAGMA quick_check` when it opens the store; when that check fails it refuses
every data route with one `{"error": {"code": "store_corrupt", …}}` body and
leaves the file exactly as it found it. `/health` reports `degraded` with
`reason: store_corrupt`, while `/api/diagnostics` and `/health` stay
reachable so the failure can still be read and copied.

The SPA answers that one code with a full-page failure instead of the shell:
it names the file, shows the last backup it can find under
`AGENTIC_ODI_BACKUP_DIR` (`~/.agentic-odi/backups`), says the damaged file was
left untouched, and offers **Recheck the database** for after the person has
restored a copy. It never offers to delete or overwrite anything — that decision
belongs to the person.

### What the canvas is made of

Every canvas response carries its provenance: `live` when the sidecar read your
store, `empty` when it read your store and found nothing, and `seed` when it is
showing the built-in demonstration because the MCP server could not be reached.
The sidecar says this in the payload (`provenance.kind`, `provenance.reason`,
and record counts); it never dresses the prototype up as your data.

The studio repeats that label where a person can see it: the rail shows a
**DEMO** or **OFFLINE** chip, the Opportunity Landscape shows a sample-data
notice, and an impact simulation must carry `provenance: live | simulated` before
it renders. The catch-up feed starts empty rather than inventing activity, and
no surface can fabricate a signal: the three example signals live only in test
fixtures. Its real content is the store's signal inbox
([The Signal Inbox](architecture/notifications.md)): the bell count comes from
`/api/signals/unread-count`, the feed loads on boot, re-reads after every canvas
refresh, and polls once a minute while the window is visible. Connector rows in Settings come from the real connector
store, grouped by capability area; nothing is pre-listed as though it were
already connected.

### The thread is the room

Capture, scoring, simulation, and decisions are conversations. The storefront
never asks the PM to leave the thread to do work: the agent asks for the
customer's words or the bet in plain language, then renders the surface that
carries it. A lens exists for reading and for people who prefer a click, not for
doing the work.

That is also enforced in the agent's system prompt: it is told to keep every
artifact in the conversation, never to send the PM to a panel, and to end each
reply with the next move as an action on the surface.

### The conversation runtime

The transcript is not a hand-rolled message list. It runs on **assistant-ui**,
a React runtime for streaming assistants, bound to the Studio's own store with
`useExternalStoreRuntime`, so the thread gains real conversation capabilities
without giving up the message model the sidecar already understands.

| Capability | What it means here |
|---|---|
| **Streaming** | `delta` frames append to the open prose part; the send button becomes stop. Before the first token, the last message shows the current phase with a shimmering label and dots. When you scroll away during a reply, a keyboard-accessible **Jump to latest** control names how much arrived (`3 new · Jump to latest`) and returns you to the live end without interrupting assistant-ui's follow behavior; a polite live region announces the count once per arrival, never once per token. Empty-thread starter cards pair each suggested move with its reason, then give way to the conversation after the first turn. |
| **Silence** | A run that stops producing tokens for eight seconds shows *Still working · no new output for Ns* under the reply, while the Stop button keeps its meaning. The signal comes from assistant-ui's stall detection over text, reasoning, tool arguments, and tool results — never from a timer watching the DOM — so a long tool call reads as work, not a freeze. A dropped stream never shows it: that path ends in the failure panel. |
| **Reasoning** | `reasoning` frames render in a disclosure that starts open while the model is thinking, then reads *Thought for Ns* and can be reopened. Never persisted, never counted as the answer. |
| **Work** | What a turn did folds into one row: *Working… · 3 calls* while it runs, then *Worked for 12s · 3 calls*, closed and reopenable. Opening it is the turn's own record, not a paraphrase — the same reasoning disclosure and trace chips, in the order they arrived. A turn the browser did not watch from the start shows its calls with no duration. |
| **Tools** | Each MCP call is a trace chip with its status and a short preview of what came back. |
| **Approval** | A writing tool (`add_`, `create_`, `update_`, `delete_`, `ingest_`, `remove_`) pauses the turn until you answer **Allow** or **Decline**. A decline is a tool result, not an error: the model is told no and may propose something else. The ask is never folded into the work row — a question is not history. |
| **Sources** | Every tool call that returned data emits a `source`, titled with the tool and a preview. Provenance is what the turn actually read; a citation is never invented. |
| **Claims** | Each declarative sentence ends with an evidence marker, and the reply arrives with a validated claim list. A chip names the source and the record (`Gong · Call with Acme`), never the tool; `Hypothesis` tags an ungrounded guess; an unmarked sentence keeps its place with a dotted underline and the accessible name *Uncited claim*. A chip opens that row in the Evidence lens, and Escape returns focus to the chip. Claims are stored with the turn, so they survive a reload; a record deleted later keeps its snapshot label and stops being a link. A seeded demo reply labels its chips **Sample** and does not count as cited. |
| **Attachments** | Attach from the paperclip, by dropping files on the composer, or by pasting a screenshot. The composer describes accepted text-like files (`.md`, `.mdx`, `.json`, `.csv`, `.yaml`, `.yml`, `.log`, `text/*`), Word documents (`.docx`, at most 25 MB), and images (PNG/JPEG/WebP/GIF, at most 5 MB); a drop or paste of anything else is refused with the reason, and a legacy `.doc` is refused with the sentence that says to save it as `.docx` or `.txt`. A turn carries at most five attachments, counting text and images together; a sixth is refused, naming the file and the limit, before the turn is sent. Chips show a name, size, an image preview, and a remove control. A file that is accepted by name but whose bytes never become content — an interrupted read, a `.docx` that will not unpack — is reported before the turn is sent: the chip keeps its name, says "Could not read this file", and send stays disabled until that chip is removed, leaving the draft and every other attachment in place. Text is extracted in the browser — `.docx` through mammoth's raw-text reader, never its HTML converter — and the per-file limit is 20,000 characters: a text-like file longer than that is refused, not silently shortened, with the chip naming the file and the limit (a `.docx` over the cap has its cut announced in the extracted text instead). Nothing is stored server-side. |
| **Model** | The hint row's picker asks the sidecar (`POST /api/models`) which ids the configured backend serves, keeps the configured model selectable even when the backend omits it, and saves the choice through `saveSettings`, so Settings and the composer never disagree. An unreachable or empty backend is explained in the menu rather than shown as an empty list. |
| **Branching** | **Edit** a user turn or **Regenerate** a reply and both versions are kept as siblings. **Alternative 2 of 3** with `‹`/`›` steps between them, and the visible branch is saved as the conversation's `head_id`, so a reload reopens the branch you were reading. |
| **Suggestions** | The empty-stage pills are chosen from the canvas and handed to the runtime as suggestion prompts. |
| **Focus** | Select a job, step, desired outcome, or evidence record and the turn carries *which* one — kind and id, never the words. The sidecar re-reads that record from its own store before the model hears a sentence about it, and adds nothing for an id it does not hold. The composer admits this with a quiet **Looking at: …** chip that opens the record when pressed and can be dismissed; it renders only when the canvas can name the selection, so it cannot claim a record that is not there. |
| **Generative UI** | A validated `UiNode` travels as an assistant-ui **data part** (`data-odi-surface`) and renders through the same `UiRenderer`. The catalog stays ours and server-validated. |
| **Dictation** | Where the shell supports speech recognition, the composer shows a microphone: it turns speech into text, marks the interim transcript as *Listening*, and commits one final sentence to the input. It never sends by itself, no audio leaves the browser, and nothing is stored. In a shell without the API — notably parts of Tauri's WebKit webview — there is no microphone at all. No fallback provider and no realtime voice. |
| **Queue** | A follow-up sent while an answer still streams does not hit a wall: it joins a quiet lane above the composer and runs in the order it was sent once the live turn settles. Each row offers **Run now** — it jumps ahead of the other waiting follow-ups — and a remove that drops only that message. Stop stops the live turn and the lane waits for the next send; it never clears the queue. The lane is in-memory and dies with the page, and the sidecar still sees exactly one SSE turn at a time — the queue sequences, it never parallelises. |
| **Read aloud** | A settled reply with prose offers **Read aloud** beside Copy, and becomes **Stop reading** while it speaks. Starting another reply stops the first; **Stop reading**, Escape inside the thread, and leaving the conversation end it. The runtime is given a `WebSpeechSynthesisAdapter` only where the shell has `speechSynthesis`, so the control is absent rather than broken. A streaming reply is never spoken, and speech is never persisted. |

#### What the runtime gives us, and what we did not take

The full coverage ledger — every assistant-ui capability and its one honest
state — is authored in [The assistant-ui ledger](assistant-ui-ledger.md),
and `scripts/doc_check.py` fails if this projection drifts from it. Whatfollows is everything a person can use today (Adopted) plus what is used
narrower than the library offers (Partial). A row is Adopted only when a test
proves a person can use it, the named file exists, and the Delivered column
cites the issue or PR that landed it.

| Capability | Status | What it means here | Delivered |
|---|---|---|---|
| `useExternalStoreRuntime` | Adopted | The bridge: the sidecar's store, presented as a thread. | #238 |
| `AssistantRuntimeProvider` | Adopted | One provider, whole app. | #238 |
| `convertMessage` (`toThreadMessageLike`) | Adopted | The only mapping between our messages and runtime messages. | #238 |
| `isRunning` | Adopted | Driven by `streaming`. | #238 |
| `setMessages` (branch switch) | Adopted | Branch switch swaps the visible path; the sidecar keeps `head_id`. | #238 |
| `onNew` | Adopted | Sending a message. | #238 |
| `onEdit` | Adopted | Editing a user turn keeps the old path as a branch. | #238 |
| `onReload` (regenerate) | Adopted | Regenerating a reply as a sibling branch. | #238 |
| `onCancel` | Adopted | The stop button. | #238 |
| `onRespondToToolApproval` | Adopted | Allow/Decline on a pending write. | #238 |
| `adapters.attachments` | Adopted | Text capped at 20k chars, images at 5 MB, refusals explained. | #238 |
| runtime `suggestions` | Adopted | Starter suggestions computed from canvas state. | #238 |
| `queue` adapter | Adopted | The follow-up lane: a send while a reply runs joins the queue instead of the wall. | #410 |
| `ExternalThreadBranchAdapter` (`getBranches`, `switchToBranch`) | Partial | Branching works; the dedicated adapter is unused, branches are inferred from parent ids. | — |
| `groupPartByType` / `GroupedParts` | Partial | The work row groups through `GroupedParts` with our own `workGrouping`; the helper, which keys by part type alone, is unused. | — |
| `ThreadPrimitive.Root` | Adopted | The transcript's shell. | #238 |
| `ThreadPrimitive.Viewport` | Adopted | Scrolling; the jump-to-latest affordance reads its `isAtBottom`. | #238 |
| `ThreadPrimitive.Messages` | Adopted | The message map. | #238 |
| `ThreadPrimitive.Suggestion` / `.Suggestions` | Partial | The data is adopted; the pills are hand-rolled because they carry the artifact-preview copy. | — |
| `MessagePrimitive.Parts` | Adopted | Every part of a reply renders through the `components` map. | #238 |
| `MessagePrimitive.GroupedParts` | Adopted | One collapsed row holds what a turn did — its reasoning and tool calls — and never hides a write that is still asking. | #392 |
| `MessagePrimitive.Attachments` | Adopted | User turns show what was sent. | #238 |
| `MessagePrimitive.Root` | Partial | The wrapper is a hand-written article carrying `aria-busy` and the avatar. | — |
| `MessagePrimitive.Quote` | Adopted | The quoted passage renders on the sent turn. | #435 |
| `MessagePartPrimitive.Text` / `.Image` / `.File` | Partial | Custom text/file renderers, because claim chips and extraction state need them. | — |
| `ComposerPrimitive.Root` / `.Input` / `.Send` / `.Cancel` | Adopted | The composer's skeleton. | #238 |
| `ComposerPrimitive.AddAttachment` / `.Attachments` | Adopted | Paperclip and chips, bounded by the attachment adapter. | #238 |
| `ComposerPrimitive.AttachmentDropzone` | Partial | Dropping works through the composer's own handlers with the same accept rules. | — |
| `ComposerPrimitive.Quote` / `.QuoteText` / `.QuoteDismiss` | Adopted | The quote shows above the input and can be cleared before send. | #435 |
| `ComposerPrimitive.Dictate` / `.StopDictation` / `.DictationTranscript` | Adopted | The microphone, hidden where unsupported. | #433 |
| `ComposerPrimitive.Queue` | Adopted | The pending lane rendered above the composer. | #410 |
| `createMessageQueue(driver)` | Adopted | The queue's own driver hook: run with `steer`, optional cancel. | #410 |
| `MessageQueueController` | Adopted | Busy/idle/cancelled signalling and hold/release — the reason the lane is not hand-rolled. | #410 |
| `QueueItemPrimitive.Text` / `.Steer` / `.Remove` | Adopted | One lane row: its text, Run now, and a remove that drops only that message. | #410 |
| `composer.quote` / `composer.queue` / `composer.dictation` / `composer.submission` / `composer.inTransit` | Partial | Quote, dictation, and queue state are read today — the follow-up lane is `composer.queue`; in-transit state arrives later. | — |
| `ActionBarPrimitive.Root` / `.Copy` / `.Edit` / `.Reload` | Adopted | The reply's own controls. | #238 |
| `ActionBarPrimitive.Speak` / `.StopSpeaking` | Adopted | **Read aloud** on a settled reply with prose, **Stop reading** while it speaks. Starting another reply stops the first; Stop reading, Escape inside the thread, and leaving the conversation end it. The runtime is given a `WebSpeechSynthesisAdapter` only where the shell has `speechSynthesis`, so the control is absent rather than broken. A streaming reply is never spoken and speech is never persisted. | #432 |
| `ActionBarPrimitive.ExportMarkdown` | Partial | Whole-conversation export is stronger than the per-reply primitive. | — |
| `BranchPickerPrimitive.Root` / `.Previous` / `.Next` / `.Count` / `.Number` | Adopted | Alternative N of M, shown only when a branch exists. | #238 |
| Attachment adapter (`AttachmentAdapter`) | Adopted | Browser-side extraction; nothing is stored server-side. | #238 |
| Drop and paste | Adopted | The composer accepts exactly what the input accepts. | #238 |
| `SelectionToolbarPrimitive.Root` / `.Quote` | Adopted | Selecting prose in a reply offers Quote. | #435 |
| `data-aui-quote-selectable="false"` | Adopted | Tool traces and generated surfaces are marked non-prose. | #435 |
| `QuoteInfo` (`{ text, messageId }`) / `useMessageQuote` | Adopted | The quote persists in the turn's metadata. | #435 |
| `button` Element | Adopted | The one copy-in: a shadcn button under `src/vendor`, with a provenance header and a `vendor.lock.json` entry. It is not an assistant-ui primitive — it is a vendor decision, recorded here because the ledger audits the library and the alley is part of that audit. | #383 |
| Structured turn failure | Adopted | The failure panel with retry copy. | #129 |
| `unstable_useMessageStallDetection` | Adopted | "Still working · no new output for Ns", only when output stops moving. | #431 |
| `useAuiState` | Adopted | Runtime state read across the transcript and composer. | #238 |
| `useAui` | Adopted | Imperative composer actions. | #238 |
| `AuiIf` | Adopted | The conditional idiom in use. | #238 |
| `unstable_useComposerInputHistory` | Adopted | Up-arrow recalls what you sent last. | #430 |
| `useThreadViewport` (viewport state) | Adopted | `isAtBottom` / `scrollToBottom` drive the jump-to-latest affordance; the arrival count is ours (`arrivalCount.ts`). | #245 |
| Tool approval gate | Adopted | A pending write blocks the turn until you answer. | #238 |
| Tool result rendering | Adopted | Each MCP call is a trace chip, gathered under the turn's work row. | #238 |
| `Tools` / `DataRenderers` / `useAssistantDataUI` | Partial | Only the validated catalog's `components.data.by_name` path is used. | — |
| ODI surfaces as `data` parts | Adopted | A validated `UiNode` rides the transcript and renders through `UiRenderer`. | #55 |

#### Where the bridge lives

| File | Role |
|---|---|
| `apps/studio/src/assistant/convert.ts` | The only mapping between `ChatMessage`/`ChatPart` and assistant-ui parts, in both directions. Pure, and tested without a runtime. |
| `apps/studio/src/assistant/StudioRuntime.tsx` | `useExternalStoreRuntime`: `onNew`, `onEdit`, `onReload`, `onCancel`, `setMessages`, `onRespondToToolApproval`, suggestions, attachments. |
| `apps/studio/src/assistant/attachments.ts` | The attachment adapter and the browser-side text/image extraction. |
| `apps/studio/src/assistant/parts.tsx` | One renderer per part: text, reasoning, tool (with its approval), source, file, generated surface, claims. |
| `apps/studio/src/assistant/claims.ts` | Hides claim markers (including one split across streamed chunks), cuts the reply so every chip lands after its own sentence, and counts citations without a seeded demo. The Markdown export reads a claim-bearing reply through this same parser, so the file cannot say something other than what the transcript showed. |
| `apps/studio/src/components/chat/Conversation.tsx` | `MessagePrimitive.GroupedParts` with the turn's work grouped, the branch picker, the action bar, and the in-place edit composer. |
| `apps/studio/src/components/chat/WorkBlock.tsx` | The work row itself: one line that counts the calls it holds, times only a run this browser watched, and opens on the turn's own record. |
| `apps/studio/src/components/chat/workGrouping.ts` | Which parts of a reply are one run of work — the thinking and the answered calls together, a pending approval never folded in. Pure over the runtime's parts, so it needs no browser to test. |
| `apps/studio/src/components/chat/ThreadComposer.tsx` | `ComposerPrimitive` plus the slash palette, connector chips, attachment drop/paste, and attachment-format/size guidance. |
| `apps/studio/src/components/chat/ModelPicker.tsx` | The composer's model listbox: opens the sidecar's `/api/models`, keeps the configured id selectable, and saves through Settings. |
| `apps/studio/src/components/settings/SavedField.tsx` | A field that saves when it is left, states **Saved** in its section, and refuses an unusable value beside itself with the reason. |
| `apps/studio/src/components/settings/sections/` | One module per Settings section — Context, Data, Model, Studio bridge, Updates, About, Install — each reading its own source and reporting its own loading and error state. |
| `apps/studio/src/components/settings/validation.ts` | What Settings accepts before it writes: a full http(s) URL, and a non-empty model name. |

The sidecar remains the source of truth for what happened. Its additions are
opt-in and additive: `reasoning`, `source`, and `approval` stream events;
`claims` on the terminal `message` frame and on every restored turn;
`attachments` and `approvals` on `/api/chat`; `GET
/api/conversations/{id}/tree`; `PATCH /api/conversations/{id}`; and `POST
/api/models`, which lists the configured backend's ids without raising when it
is offline. A client that sends none of these sees exactly the stream it saw
before, which is what the CLI and older clients do.

When a chat request enables approvals, the sidecar uses the MCP contract to
prompt for writes and unknown tools, while reads run without a prompt. The local
`remember` suggestion and `render_ui` remain ungated. This is not authentication
and does not gate direct CLI or MCP calls. See [Consent and approvals](architecture/consent.md).

The approval gate is per-process and single-user by design. `ApprovalRegistry`
waits on an `asyncio` future, `POST /api/approvals/{id}` answers it, and a
timeout (300 s) or a cancelled turn resolves as a declined write, so a turn can
never hang and a double click can never run a tool twice. That is the right size
for a loopback sidecar with one person at the keyboard; it is not a durable job
queue, and it is not pretending to be one.

#### Extending the conversation

A new kind of part is added in exactly two places — the mapping in `convert.ts`
and the component in `parts.tsx` — and then registered in the `components` map
in `Conversation.tsx`. Do not add a second message list, and never let an unknown
part reach the screen as JSON: the converter drops what it does not understand on
purpose, and `convert.test.ts` holds that line.

### What it remembers

The studio keeps a small, local, editable model of the person it is helping. It
is not a profile and not a transcript index; it is the handful of things that
change the next answer.

| Kind | What it captures |
|---|---|
| `career` | The PM's role, remit, and what success looks like for them |
| `opportunity` | The opportunity or bet currently in play |
| `business` | Goals, metrics, and commercial constraints |
| `stakeholder` | Who else matters and what they care about |
| `constraint` | Time, budget, policy, or technical limits |
| `evidence` | What has actually been heard or measured |
| `preference` | How the PM likes to work and be spoken to |

Each note is `suggested` or `confirmed`. Suggested notes appear first under
**What I know** with **Yes, that's right**, **That's not it**, and **Edit**;
confirmed notes can be edited or forgotten. The PM can also add a note by hand.
Nothing is silently promoted: the agent may propose, but the person decides.

The agent writes notes through a `remember` tool during a normal reply. The
sidecar applies it, emits a `memory` SSE event, and the panel updates without a
refresh. Memory writes are best-effort — a database failure never turns a good
answer into an error. A turn can therefore finish without being remembered; when
that happens the sidecar logs one warning carrying the request id, the role, and
the exception class — never the words of the turn — instead of failing the reply.

Storage is a separate SQLite file from the ODI repository:
`~/.agentic-odi/studio.db`, overridable with `AGENTIC_ODI_STUDIO_DB`
(`:memory:` is supported and is what the tests use). The API is small:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/memory/observations` | Everything the agent believes |
| `POST` | `/api/memory/observations` | Add a note by hand |
| `PATCH` | `/api/memory/observations/{id}` | Edit text, confidence, or status |
| `DELETE` | `/api/memory/observations/{id}` | Forget one note |
| `DELETE` | `/api/memory` | Forget all notes and conversations |
| `GET` | `/api/diagnostics` | App/runtime and database metadata/counts only; never config, database paths, or row contents |

**Forget everything** is a two-step confirmation and also clears the visible
thread, because the server deletes the conversations behind it.

### The thread comes back

Conversations are stored beside the memory. On launch the SPA asks
`GET /api/conversations/latest`, restores that thread's user and assistant
turns, and continues with the same `conversation_id` on the next message. **New
conversation** starts a fresh one without touching the memory; **Forget
everything** removes both. The composer stays usable while the restore is in
flight, and a restore failure simply leaves the room empty.

### Scheduled work says what happened

The canvas can record background work to run on a schedule, and the schedule
panel lists each item with the outcome of its last run. A run that fails is
recorded as failed — never as completed — with the exception's type and message,
a consecutive-attempt count, and the time of the next attempt. The first failure
retries in two minutes, the second in four, and the delay is capped at thirty
minutes. After three consecutive failures the item stops being scheduled and is
marked **needs attention**, so a permanent failure does not retry forever. A run
that succeeds resets the counter and clears the error.

All of the timing arithmetic lives in `packages/core` (`run_scheduled_work`,
`retry_delay_minutes`); the panel only formats the values the record carries. A
turn with no outcome yet shows no run line rather than a plausible-looking
default.

### Printing and export

The bar's overflow menu has **Export → Markdown**. The file labels every
speaker, keeps the prose as Markdown, and writes each agent-composed surface as
a fenced JSON block, so a thread can be pasted into a doc or a ticket without
the reader needing the Studio. A reply that arrived with claims keeps them: each
sentence carries the distinction the transcript drew beside it — *Hypothesis*,
*Uncited*, or `Source · record name, record id` — the claim markers themselves
never print outside code, and the labels state what the turn read when it was
written rather than promising that the record is still there.

**Diagnostics are separate from conversation export.** Settings → About →
Diagnostics builds a local, opt-in bundle, then shows the exact pretty-printed
JSON, byte count, and Included / Never included lists before Copy or Save. Capture
rings live only in memory after the person presses the button and are cleared on
reload. The bundle contains app version/build/platform/theme, sanitized sidecar
configuration and metadata, capabilities, redacted error/console entries, and
turn frame counts/timing; it never includes messages, observations, brief,
theses, attachments, or canvas entities. Secrets, email addresses, bearer tokens,
URL credentials and query strings are redacted, and file paths become basenames.
It still exports while the sidecar is stopped; nothing is uploaded.

Printing (`Cmd`/`Ctrl`+`P`) lays the open conversation out for A4: the bar,
rail, composer, and floating chrome are hidden, the palette switches to paper,
and cards stay whole instead of splitting across sheets. An open lens prints
below the thread instead of being clipped off-screen.

### Sharing one artifact

Sometimes the work has to leave the room without the room going with it. The
sidecar mints a **scoped, expiring, read-only share token** for exactly one
record — an outcome, a segment, or a strategy. `POST /api/share` returns the raw
token once; `DELETE /api/share/{id}` revokes it, effective immediately; and
`GET /api/share/{token}` returns the named artifact and its own evidence and
nothing else. `GET /api/share` lists the owner's links without their tokens.

The token is `odi_sh_` plus 32 random bytes, and only its SHA-256 hash is
stored, so a copy of the database is not a copy of the link. Expiry defaults to
7 days and never exceeds 30. A read never returns the workspace: not the canvas,
not a list, not the memory, not a conversation, and not a connector secret — an
evidence record travels without its raw payload. An unknown, expired, revoked,
or malformed token is the same `404`, so a probe learns nothing, and a read
records only `last_read_at` for the owner, never who read it. Nothing about a
link is writable: a non-`GET` on the shared path is `405`.

The link points at `AGENTIC_ODI_PUBLIC_BASE_URL` when it is set, and at
`http://127.0.0.1:8100` otherwise. It works only while this sidecar is running
and reachable by the reader; the read-only page that renders it is #550. No
accounts, no session, and no public write path exist here — the token is the
whole capability.
### The decision brief

A conversation is hard to hand to a review, so the Studio writes the document
instead: `/brief`, or **Export brief** in the opportunity landscape's header,
docks the brief as a lens beside the thread. It is built in the browser from the
canvas — jobs, steps, outcomes, evidence, theses and the setup context — and not
by the model, so the same offline studio that scores an outcome can produce the
page a colleague reads. **Download .md**, **Print / PDF** and **Copy** all
serialize the one Markdown string the preview is rendering; what a person
approves is what leaves the app.

The document is eight sections in a fixed order: Provenance, Vision, The
decision, Top opportunities, Evidence, Dissent, Next evidence, Method. Every
number in it counts records rather than generating prose, and the Method line
states the score formula (`importance + max(importance - satisfaction, 0)`) so a
reader can check the ranking against the Outcome records. Unscored outcomes are
not opportunities and are not counted. Provenance is the part a reviewer is
entitled to: seeded demo rows are excluded from every count and the sheet carries
*Demo data. Nothing here comes from your research.* rather than quietly mixing
them in, and a canvas served from this device's cached copy says the snapshot may
be stale. Dissent is assembled from what argues against the bet — saved theses,
canvas warnings, evidence that belongs to no outcome — plus one optional field on
the sheet for the objection the studio could not know, which prints labelled
*author-supplied*. Next evidence names the thinnest of the top three and a
connector from the preset catalog that could fill it, or says plainly that no
matching source exists to connect. On an empty canvas the export action is
disabled and says why: nothing to brief yet.

Print is the brief's own contract. While the print dialog is open the body
carries `brief-printing`, and the sheet's controls, the objection field, the
thread and the chrome all disappear — the PDF is the document, not a screenshot
of the app. What the print contract is not allowed to do is hide a paragraph:
`src/styles/print.test.ts` reads the stylesheet's `display: none` list and fails
if any of it reaches inside the document.

The brief is an artifact, so it is held to the same six structural rules as
every page the product emits — one title, no skipped heading level, named
tables with scoped headers, labelled or deliberately hidden images, no id used
twice. `src/test/a11y.test.tsx` runs axe over the rendered sheet, and
`src/components/brief/BriefLens.test.tsx` checks the structure of the document
itself, including that a quote containing `<script>` or `<h1>` prints as the
characters the person said. The rules live in `scripts/artifact_a11y.py`; what
passes them is a well-built document, not a certified one.

### Sharing a read-only artifact

A person can hand a teammate one artifact without handing over the workspace.
The landscape header carries a **Share** control; choosing a duration (7, 14, or
30 days) mints a link through the sidecar and shows it once, with a **Copy
link** button. The link is a capability, not a copy of the database: it opens a
read-only page that renders the landscape — or the vision — and its own
evidence, and nothing else.

The page lives at `/shared/:token`, and it is deliberately *not* the Studio with
its controls hidden. The route is decided before any provider mounts, so no
canvas fetch, rail, composer or sidecar configuration runs; the header names the
artifact and its expiry, and the only action is the browser's own print. An
expired, unknown or revoked token shows one sentence and no data; a guessed
artifact id renders nothing, because only the token is scoped.

The mint and read contract belongs to the sidecar's share store (#549): it mints
a link for one artifact, returns the scoped payload for a token, and revokes by
id. Until that store lands, a click reports the failure rather than promising a
link it did not make, and the sheet says when a link cannot be revoked.

| File | Role |
|---|---|
| `apps/studio/src/lib/share.ts` | The `/shared/:token` route reader and expiry wording. Pure and tested. |
| `apps/studio/src/components/SharedArtifact.tsx` | The read-only page: one artifact, its evidence, the expiry. |
| `apps/studio/src/components/Share{Action,Sheet}.tsx` | The landscape control and the dialog that mints a link, offers it to copy, and states revocability. |

## Rich responses


The copilot does not only talk. When a surface carries the evidence better than a
paragraph, the agent renders one **inline in the conversation**: a scored
outcome, a ranked opportunity board, a before/after simulation of a bet, a
customer quote with its lineage, the eight-stage job map, an opportunity thesis,
a decision record, an outcome-based segment, or the strategy it implies.
Three properties keep this safe and cheap to extend:

- **The catalog is closed and owned by the SPA.**
  `apps/studio/src/ui/catalog.ts` declares nine primitives and nine cards, their
  JSON Schema props, and the description the model reads. There is no HTML, no
  eval, and no third-party component in the path. Prose is rendered by the same
  `Markdown` component the transcript already used.
- **The sidecar is catalog-agnostic.** The SPA sends the catalog with each turn;
  the sidecar derives the `render_ui` tool schema from it, validates what comes
  back, and streams a `ui` SSE event. Invalid props return to the model as a tool
  result naming the exact violation, and the loop offers the tool again, so a
  fumbled prop is corrected in the same reply. A client that sends no catalog
  never sees the tool.
- **Cards are views, never actors.** Every button is an `intent` string that the
  agent receives as the user's next message — one authority, one audit trail.

A surface is one node tree, streamed as one event:

```json
{
  "type": "outcome-card",
  "props": {
    "id": "O-1",
    "statement": "Minimize the time it takes to propagate secrets across environments",
    "importance": 9,
    "satisfaction": 3
  }
}
```

The opportunity thesis is the intent-first card: one opportunity with its
importance, satisfaction, the gap in plain words, the thesis itself, and the
smallest next move. It is the shape the agent reaches for when the PM is deciding
what to chase, rather than when they are inspecting a single score.

The segment card is the answer to "who is this for?": the people, the job they
are doing, the step their outcomes cluster on, and the verdict those outcomes
support. A verdict is never shown apart from the confidence behind it, and
outcomes that joined no cluster are listed under the card rather than folded in.
The board (`SegmentBoard.tsx`) resolves each segment's `outcome_ids` against the
canvas and shows the members themselves — every member's statement and its stored
score — so a segment is inspectable rather than a name to trust. The mean is
taken over scored members only, with an explicit `M not scored` beside it and
`Not scored` when nothing is scored; a missing score is never a zero. An id that
resolves to no outcome is dropped and counted, never invented. One line always
says where the people came from: an inferred group is a **candidate segment**,
grouped by the job it serves, while a supplied group is *people named from your
evidence*. Each member is a button that focuses that outcome in the landscape.
The strategy card carries Stage 6: the one path the evidence supports, the moves
it proposes, and **every path it beat with the reason**. The catalog requires at
least two rejected paths, so a strategy that records none cannot be validated.

The conversation keeps the order the agent produced: a `delta` appends to the
open prose part, a `ui` event opens a card, and the next `delta` opens a new
paragraph after it. The opportunity score is computed from importance and
satisfaction when the agent omits it, so the ODI formula has exactly one home
(`src/lib/odi.ts`). Unknown component types degrade to a quiet fallback; a tree
that fails validation is dropped whole, and the surrounding prose still reads.

### Adding a surface

1. Add an entry to `CATALOG` in `apps/studio/src/ui/catalog.ts` — props as a
   JSON Schema subset, plus the description the model will read.
2. Register the component in `apps/studio/src/ui/registry.ts`.
3. Implement it in `apps/studio/src/ui/cards.tsx` (domain shape) or
   `apps/studio/src/ui/primitives.tsx` (composition).
4. Run `npm --prefix apps/studio test`. The `registry parity` test fails if the
   catalog and the registry drift apart.

No server change is needed, and no new dependency.

## Hosted (experimental)

The built SPA is also served from Cloudflare Workers at
**[https://agentic-odi.alehar.workers.dev/](https://agentic-odi.alehar.workers.dev/)**.
The UI loads without a backend; canvas data, chat, and mutations need the local
sidecar and MCP server. Pull requests get preview URLs from Cloudflare Workers
Builds. See [Deployment](deployment.md) for the Worker setup.

## 1. Web — production build (recommended for a quick look)

```bash
npm --prefix apps/studio run build   # build the SPA into apps/studio/dist
python scripts/dev.py            # starts MCP :8000 + sidecar :8100
```

| Service | URL |
|---|---|
| MCP Server | http://localhost:8000/mcp |
| Living Studio | http://127.0.0.1:8100 |

`python scripts/dev.py` starts both processes concurrently; press **Ctrl+C** to
stop both.

## 2. Web — dev with hot reload

Vite proxies `/api` to the sidecar:

```bash
npm --prefix apps/studio run dev:full   # MCP + sidecar + Vite together
# open http://localhost:5173
```

## 3. Desktop — Tauri 2

The app spawns the MCP server and sidecar itself:

```bash
npm --prefix apps/studio run tauri dev     # dev window
npm --prefix apps/studio run tauri build   # bundles: .deb / .AppImage (Linux), .app / .dmg (macOS), .msi / .exe (Windows)
```

> [!NOTE]
> **Tauri prerequisites.** The desktop build needs the WebKitGTK toolchain and
> Rust 1.90+. On Debian/Ubuntu:
>
> ```bash
> sudo apt-get install -y libwebkit2gtk-4.1-dev build-essential pkg-config curl wget file \
>   libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev patchelf xdg-utils libfuse2t64
> ```
>
> The Tauri CLI ships as the `@tauri-apps/cli` npm dev dependency
> (`npm --prefix apps/studio run tauri`). The sidecar is launched with
> `uv run python -m …` from the repository root; if the app cannot locate the
> repo root, set `AGENTIC_ODI_REPO_ROOT`.

## Desktop signing & updater secrets

Self-updating and code signing are **env-driven**: if a secret is absent, an
unsigned artifact is produced instead of failing. CI reads these from GitHub
Actions secrets.

| Secret | Purpose |
|---|---|
| `TAURI_SIGNING_PRIVATE_KEY` | Signs updater artifacts (`.sig`) and the `latest.json` manifest. A release fails loudly without it. Generate with `npm --prefix apps/studio run tauri signer generate`. |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | Password for the private key (optional when the key has none). |
| `APPLE_CERTIFICATE` / `APPLE_CERTIFICATE_PASSWORD` | macOS Developer ID certificate (base64 `.p12`) and its password. |
| `APPLE_SIGNING_IDENTITY` | macOS signing identity. |
| `APPLE_ID` / `APPLE_PASSWORD` / `APPLE_TEAM_ID` | macOS notarization credentials. |
| `WINDOWS_CERTIFICATE` / `WINDOWS_CERTIFICATE_PASSWORD` | Windows Authenticode PFX (base64) and its password; imported by CI and injected into the bundle config. |

Releases are published by `.github/workflows/tauri-release.yml`. It starts when
a GitHub release is **published**, and on a `v*` tag push for hand-cut tags.
The published release is what matters: release-please creates releases through
the API, which never emits a tag-push event, so a tag-only trigger would leave
every release without binaries. A `verify` job fails the release unless
`latest.json` advertises the release version and carries a signed artifact for
Linux, Windows, and both macOS architectures.

`release-please` bumps the desktop app version from `extra-files`
(`apps/studio/package.json`, `apps/studio/src-tauri/tauri.conf.json`, and
`apps/studio/src-tauri/Cargo.toml`), so the installed version moves with every
release. Without that sync the updater can never see a newer manifest.

The app checks four seconds after launch, every six hours, and when the window
returns to the foreground after that interval. A found update downloads in the
background; the shell shows one quiet bar above the conversation with progress
and a single action. macOS and Linux stage the update as soon as its signature
verifies, so it also applies on the next ordinary launch. **Restart now** in the
bar, **Settings → Software update**, or the version line in the sidebar applies
it immediately. Windows needs the app to exit before its installer runs, so it
offers **Update & restart** instead. Dismissing the bar is safe: a staged update
still applies on the next launch, and check failures are reported in Settings
rather than interrupting the conversation. A failed check never borrows the
last attempt's timestamp: Settings says plainly that the app could not check and
names when it last reached the server successfully, or that it has not yet.
Below that, **Recent update activity** lists the most recent updater actions of
this session — checks, downloads, installs, skips and dismissals — newest first
and capped, so a support conversation starts from what actually happened.

In-app updates are inactive in the browser build and in `tauri dev`; both say so
in **Settings → Software update**.

`scripts/verify-desktop-update.sh` proves the path locally: it builds signed
0.1.0 and 0.2.0 AppImages against a throwaway key and a local `latest.json`,
runs 0.1.0 until it replaces its own file with 0.2.0, then runs the result and
asserts it checks without downloading anything.

The updater key pair itself — generating it, storing it, rotating it — is
covered under **Desktop updater signing keys** in [Deployment](deployment.md).

## Connecting an LLM

The Studio needs an OpenAI-compatible LLM backend with tool-calling support to
drive the agent. For a fully local setup, see
[Local LLM Backend](local-llm.md).

## Reviewing the conversation by hand

Timing, focus rings, drop targets, and menu placement are not things a test can
judge. Start the stack against a local model and a database of its own — a second
checkout sharing `~/.agentic-odi` can otherwise leave this one with a schema it
cannot open:

```bash
AGENTIC_ODI_STUDIO_DB=~/.agentic-odi/studio-review.db \
AGENTIC_ODI_BASE_URL=http://127.0.0.1:11434/v1 \
AGENTIC_ODI_MODEL=qwen2.5-coder:14b \
npm --prefix apps/studio run dev:full          # http://localhost:5173
```

Each row below names a state to reach and what is worth your own eyes.

| State | How to reach it | What to judge |
|---|---|---|
| Activity line | A turn whose first token is slow: a cold model, or a long prompt | The label moves *Waking the model* → *Opening your studio tools* → *Thinking*, the dots animate, an elapsed count appears after 3 s, and the reply does not jump the layout when it arrives |
| Streaming prose | Any turn | The caret trails the last word, the send button is a stop button, and scrolling away offers **Jump to latest** with a count of what arrived, without fighting the follow |
| Reasoning | A backend that streams `reasoning_content` or `reasoning` | The disclosure opens while it is written, settles to *Thought for Ns*, reopens on click, and never repeats the answer |
| Work row | A model that emits real `tool_calls`, then a page reload | The row reads *Working… · N calls* while the turn runs and *Worked for Ns · N calls* at rest; opening it lists the calls in the order they arrived without shifting the answer; the same turn reopened from the store counts its calls and invents no duration |
| Tool trace and sources | A model that emits real `tool_calls` | The dot pulses while the tool runs, the chip previews what came back, and the source names the tool the turn actually read |
| Approval | The same, asking it to write ("add a step to …") | The turn pauses for **Allow**/**Decline**, the ask is never folded into the work row, a decline reads as a tool result and not an error, and a double click runs the tool once |
| Model picker | **Model** in the hint row; open it twice; narrow the window first | The list matches the backend, the configured id stays selectable, arrows/Home/End/Enter/Escape work, an offline backend explains itself and its Settings button is reachable from the keyboard, and it probes once per backend |
| Attachments | Paperclip, drag a file onto the composer, paste a screenshot, then drop a `.exe`; a read failure shows on the chip when the browser hands over a file it will not open (a locked transcript, or one the tab lost the handle to) | Thumbnail, name, size, and remove on the chip; the refused file never becomes a chip; the unreadable one stays as a chip marked *Could not read this file* with send disabled until it is removed, and the draft and any other attachment survive it; the sent turn shows the same; the paperclip has a visible focus ring |
| Branches | Edit your own turn, then regenerate a reply | **Alternative N of M** with `‹`/`›`, and a reload reopens the branch you were reading |
| Reduced motion, narrow window | Turn on OS reduce-motion; then drag the window narrow | Shimmer, dots, cycling, and the landscape's underserved pulse stop; the ring stays drawn and the nodes do not move; the lens becomes a sheet, the composer stays usable, and menus stay on screen |
| Reduced transparency, more contrast | Turn on OS reduce-transparency, then more contrast | Every blurred panel becomes an opaque surface instead of glass; muted and faint text step up, hairlines thicken, and nothing overlaps or clips |
| Theme change | Toggle Appearance in Settings while watching the bar | The window cross-fades in about 120 ms with no white flash; with reduce-motion on it swaps instantly; selected text and the caret carry the accent |

Two things surprise people on a local model:

- **Warm it first.** Loading a 14B model can take minutes, while the sidecar gives
  a completion 15 s; the first turn after the model has been idle that long fails
  as *The model could not be reached*. The error is retryable and the retry works
  once the load finishes. Preload it right before a review with
  `curl -X POST localhost:11434/api/generate -d '{"model":"qwen2.5-coder:14b"}'`,
  or start Ollama with `OLLAMA_KEEP_ALIVE=2h` so an idle pause does not unload it
  (Ollama's own default is five minutes, and every later request re-applies it).
- **A model that prints JSON is not calling a tool.** Some coder models write
  `{"name": "get_jobs", …}` as prose; nothing is traced, so no chip and no
  source appears. Judge those rows on a model that returns `tool_calls`.

Settings come from the browser before they come from the sidecar: if the composer
still points at an old backend, set **Base URL** and **Model** in Settings once —
the picker writes the same place.

## Agent-Driven Testing

Type `/dev` in the AI assistant to trigger the full automated workflow: it starts
both processes, opens the browser, sends a test message, and reports the results.

Type `/test` to have the agent run all tests and report the results
automatically.
