# Signals

A "catch up" feed is only worth opening if every item is true. This document is
the design behind the signal inbox; the operational surface is described in
[The signal inbox](notifications.md).

## What it is

A **Signal** is a record that something actually changed in the ODI data. It is
written by `ODIService` at the moment the change happens, stored as an event in
the same append-only log as everything else, and read back by the CLI, MCP
clients, and the Studio bell.

There are exactly six kinds, each tied to one emitter:

| Kind | Emitted when | Severity |
|---|---|---|
| `job_added` | `add_job` | info |
| `outcome_scored` | an outcome's importance or satisfaction changed | info |
| `opportunity_crossed` | an opportunity score crosses 10, up or down | urgent up, notice down |
| `evidence_ingested` | `add_evidence` | info |
| `evidence_promoted` | `promote_evidence` turns evidence into an outcome | notice |
| `job_map_completed` | a job map covers all eight stages | notice |

Deletions emit nothing: removing a record is not news worth interrupting for.

## Why events, not a notifications table

The store is already event-sourced. Writing signals as events means read and
dismissed state survives a reload for free, replays with the rest of the
history, and cannot drift from the data it describes. A separate notifications
table would need its own migration, its own persistence rules, and a join to
explain what each row is about.

A signal is also **never cascade-deleted** with the record it names. The inbox
is a history; history outlives the thing it is about.

## Identity and dedupe

`fingerprint = sha256("kind|subject_kind|subject_id|discriminator")`. Recording a
signal whose fingerprint already exists returns the existing record instead of
creating a second one. This is what makes an ingest re-run safe: the inbox does
not grow by one row per retry.

The discriminator is what distinguishes two real changes to the same subject
(for example, two different score transitions), so dedupe suppresses echoes
without suppressing news.

## Attention budget

`SignalBudget` caps what the feed surfaces: at most
`AGENTIC_ODI_SIGNAL_BUDGET` signals per day (default 20). `urgent` signals bypass
the cap. Suppressed signals stay in the store and stay reachable by id; they are
hidden from the feed and the unread count only. A budget is a statement that
attention is finite — without it, a busy ingest turns the bell into noise.

## The rule a signal must obey

A signal must describe **something that happened**. No reminders, no "you
should", no generated encouragement, no item whose subject cannot be looked up.
The simulated demo signal exists only to exercise the UI; it is marked
`simulated: true`, carries a badge, and is excluded from the unread count and
every counter.

## Surfaces

- **MCP tools:** `list_signals`, `mark_signal_read`, `dismiss_signal`.
- **CLI:** `odi signals list|unread|read|dismiss`.
- **Studio API:** `GET /api/signals`, `GET /api/signals/unread-count`,
  `POST /api/signals/{id}/read`, `POST /api/signals/{id}/dismiss`.
- **Studio:** bell badge, Catch Up lens, keyboard-operable cards, `aria-pressed`
  filter toggles.

There is no browser-side notification store; everything shown comes from the
store.

## What the alternatives were

- **Poll the data and diff it.** Rejected: the store already knows when a write
  happens, and a poller would need its own notion of "changed since" plus a
  cache that can be wrong.
- **Client-side notifications.** Rejected: a browser tab's state is not a
  record, it disappears on reload, and it cannot be read by the CLI.
- **Unbounded feed.** Rejected: an unbounded bell is a log, not a signal.

## What this does not do

- It does not push anything: no email, no OS notification, no webhook. Delivery
  is pull.
- It does not summarize a day or generate a briefing; that is
  [#95](https://github.com/alehar9320/agentic-odi/issues/95).
- It does not emit for deletions, reads, or connector failures — connector and
  agent-work kinds are future work, not part of the six.
- It does not dedupe across kinds or subjects; fingerprints are per transition.
- It does not let the model author a signal directly. Only the service emitters
  write them.
