# Living Studio — First-Run, Command, and Offline UX Design

**Date:** 2026-10-20
**Branch:** `feat/studio-first-run-ux` (stacked on `feat/studio-chat-first-shell`, PR #34)
**Status:** Implemented

## Intent

PR #34 made the Studio chat-first, but it still assumes a returning user with a
model running. This pass makes the first minute intentional, gives the keyboard
the same reach as the CLI, and makes the product whole when the model is down.

The guiding question: *what does the Studio know about the person in front of it
before they type anything?* Today the answer is "nothing" — so every reply has to
re-derive the user's product, audience, and job. That is the core fix.

## Goals

1. **First-run context.** A short setup conversation captures product, audience,
   job-to-be-done, and the core problem, creates the Job in the ODI store, and
   grounds every later conversation in that brief — without blocking exploration.
2. **Slash commands.** `/` opens a filterable command palette; commands execute
   locally (navigation, status, help, new conversation) without an LLM.
3. **Home is a place.** The wordmark is a real home control that returns to the
   empty stage and closes the workspace.
4. **Full-screen surfaces.** Workspace surfaces replace the conversation instead
   of squeezing beside it; an explicit "Back to conversation" returns.
5. **Honest offline mode.** When the model is unreachable, the Studio says so,
   offers manual work front and centre, and still performs every data mutation
   by hand against the local repository.

## Non-goals

- Chat transcript persistence across reloads.
- Remote/cloud model provisioning.
- New MCP tools (the existing contract already has full CRUD).

## Decisions (made here, not by the partner)

| Area | Decision | Why |
|---|---|---|
| Onboarding shape | A conversation in the chat stage: four questions, one at a time, quick replies, visible progress, skip anywhere, exit always available. No modal. | Autonomy first: people must be free to explore, and guidance works best when it is optional, paced, and answerable in their own words. It also has to work with no model. |
| Brief storage | `localStorage` plus the Job record in the ODI store | The brief is personal context; the Job is shared domain data |
| Home behaviour | Home = new conversation + close surface | Without transcript persistence, "home" is the empty stage; keeping a stale transcript would contradict the greeting |
| Offline replies | Sidecar still answers with deterministic ODI guidance, tagged as offline | The composer must never dead-end; canned guidance beats a spinner or an error |
| Commands | Local-first; only `/help`, `/status`, navigation, `/new`, `/start` | Anything that needs judgment should still be a message to the model |
| Manual CRUD | Jobs (create/rename/delete), steps (add/edit/delete), outcomes (add/adjust scores/delete) via sidecar endpoints | "Interact with the database by hand" is only true if the common operations exist in the UI |

### Why this shape

- **Autonomy first.** The exit is visible from the first message and the
  composer is always available, so guidance never becomes a gate.
- **One question at a time.** Each turn carries a single ask, which keeps
  working memory free and makes skipping cheap.
- **Reflect, then ask.** The assistant repeats the answer before moving on, so
  people feel heard and can correct the record immediately.
- **Recognition over recall.** Quick replies and examples reduce the cost of
  answering; free text stays available for people with a precise answer, and
  "skip" or "show me the landscape" are understood rather than stored as a
  product name.
- **Progress without pressure.** "2 of 4 · skip anything" is visible but quiet;
  the draft survives leaving and reloading, so returning is not a restart.
- **A clean ending.** The review is the last thing seen before the contextual
  home, so the peak-end memory is the summary, not a form.
- **No dark patterns.** Nothing is pre-checked, nothing is trapped, and skipping
  is a first-class action.

## Behaviour

### First run

`brief == null` (or `/start`, or Settings → "Edit context") opens the setup
**conversation** in the chat stage, not a modal. It asks one thing at a time:

1. What are you building?
2. Who feels the problem most?
3. What job are they trying to get done?
4. Where does it hurt most?

Each answer is reflected back before the next question. The composer accepts
free text; the question chips offer quick replies and a skip. Progress and
**Explore on my own** stay visible, and `Esc` exits.

Nothing is required. Skipping advances without judgement; exploring closes the
conversation and leaves a quiet nudge (a dashed home pill and a dot on the
sidebar's **Your context**). The draft and current step persist locally, so
coming back resumes rather than restarts. With an existing brief the
conversation opens on a review and offers to change one line at a time.

Accepting the review saves the brief, creates or updates the Job, refreshes the
canvas, and lands on a context-aware home. If the repository call fails, the
brief is still saved and the failure is surfaced as a toast — context capture is
never lost to a backend hiccup.

### Slash commands

Typing `/` shows the palette above the composer. Filtering is prefix-first, then
substring, over the command name and description. `↑`/`↓` move, `Enter`/`Tab`
run, `Escape` closes. Running a command never calls the model. Unknown commands
produce a transcript notice pointing at `/help`.

| Command | Effect |
|---|---|
| `/help` | Command list as a transcript notice |
| `/new` | New conversation |
| `/home` | Return to the empty home stage |
| `/jobs` | Job summary notice, then the job map |
| `/landscape` `/jobmap` `/impact` `/evidence` `/capture` `/settings` | Open that surface full screen |
| `/status` | Model, MCP, brief, and canvas status |
| `/start` | Resume the context conversation |

### Offline

`llmHealth.healthy === false` shows a persistent "Working by hand" banner in the
chat stage with buttons for the manual surfaces. The composer placeholder and
status line change, `/` commands keep working, and a non-command message returns
deterministic ODI guidance from the sidecar. That reply is labelled "Local
guidance" in the transcript. Every add/edit/delete path is local-first, so the
repository remains fully usable.

### Brief in the model prompt

`/api/chat` accepts the brief and appends it to the system prompt: product,
audience, job, and problem. The assistant starts from the user's context instead
of asking for it again.

## Verification

- `npm --prefix apps/studio run typecheck` — pass
- `npm --prefix apps/studio run lint` — pass
- `npm --prefix apps/studio test -- --run` — 75 passed
- `npm --prefix apps/studio run build` — pass
- `uv run pytest` — 555 passed
- `uv run ruff check apps/studio-api` / `ruff format --check` — pass
- Manual sidecar run on port 8123: job create/rename/delete, step add/edit/delete,
  outcome add/score-edit/delete, canvas persistence, and the offline SSE stream
  all verified, the conversational setup, and the served production bundle contains the new surfaces.
