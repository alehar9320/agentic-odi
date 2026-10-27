# Memory Recording for Notification/Alert System in Studio

- Added Intent & Outcome based Notification/Alert System ("Catch Up" experience).
- Persistent state in localStorage (`studio.notifications`).
- Added Bell icon button with pulsing unread count badge in the top bar; the feed opens in the workspace lens.
- Added executive summary card ("While you were away"), category filters (All, Unread, Outcomes, Signals), and background event simulator.

## Not the same as banners

This document covers the notification feed behind the bell icon — a persistent,
browsable history the user opens on purpose. For the transient and persistent
strips the studio shows *now* (sidecar down, model offline, a write rejected),
see [Studio banners](banners.md). The two systems are independent: the feed
keeps history, banners state current conditions.
