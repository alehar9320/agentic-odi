# The Catch-Up Feed

- Intent & outcome notifications live in the Studio's **Catch Up** lens.
- Persistent state is `localStorage` under `studio.notifications`.
- The bell in the top bar shows the unread count; opening the feed marks real
  notifications as read.
- The feed has a summary card ("While you were away"), category filters (All,
  Unread, Outcomes, Signals), and per-item read/dismiss controls.
- **There is no server-side event source yet.** Everything in this feed is
  produced by the local simulator in `StudioContext`; [#79](https://github.com/alehar9320/agentic-odi/issues/79)
  replaces it with real signals. No route, poll, or SSE subscription feeds it.
- **First run is empty.** The studio does not fabricate notifications. The feed
  only contains events the studio actually recorded.
- **Simulated events are labelled.** **+ Simulate update** creates a
  demonstration event with `simulated: true`. It shows a **Simulated** badge,
  is excluded from the unread count and the summary counters, and never
  contributes to the bell badge.
- A simulated event is a demo of the feed, not evidence that background work
  happened.

## Not the same as banners

This document covers the notification feed behind the bell icon — a persistent,
browsable history the user opens on purpose. For the transient and persistent
strips the studio shows *now* (sidecar down, model offline, a write rejected),
see [Studio banners](banners.md). The two systems are independent: the feed
keeps history, banners state current conditions.
