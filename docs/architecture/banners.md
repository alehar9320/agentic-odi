# Studio banners

Banners are how the Studio tells the user about the state of the studio: the
sidecar is down, the model is unreachable, a step was added, a write was
rejected. Before this system, three of those surfaces were separate components,
each with its own markup, CSS, and idea of when to appear. Now one system owns
all three, and a new banner is a catalog entry — never a new component and never
a new CSS class.

## The shape

```text
types.ts     BannerKind, BannerSeverity, BannerLife, BannerDock, BannerSpec, Banner
catalog.ts   BANNER_CATALOG: every kind's severity, life, dock, and default copy
store.ts     pure functions: raise, resolve, dismiss, select. No React.
BannerProvider.tsx  useReducer over the store; exposes useBanner()
Banner.tsx          one banner on a Radix toast
BannerStack.tsx     both docks: the top strip and the corner stack
BannerBridge.tsx    reads StudioContext, raises and resolves banners, routes clicks
BannerToasts.tsx    turns every pushToast into a keyed banner
```

## Why it is built this way

**The store is pure.** `store.ts` has no React import. Ordering, dedupe, and
capping are unit-testable without a renderer, which is why the tricky rules below
have direct tests rather than being inferred from a screenshot.

**Identity decides dedupe.** A banner with a stable identity — a persistent
condition, or any banner given a `key` — updates in place. A retry loop that
raises `sidecar-down` ten times paints one strip. A transient banner with no key
is an event ("Added connector X"), so two of them are two facts and both stay.

**A kind is a closed set owned by the client.** The agent never composes a
banner. `BANNER_CATALOG` is the single source of truth for severity, life, dock,
and default copy, so the same condition reads the same way everywhere.

**Radix owns the hard parts.** `@radix-ui/react-toast` supplies the live region,
pause-on-hover, swipe dismissal, focus management, and timers. A persistent
banner passes `duration: Infinity`, which Radix treats as "never expire". We do
not hand-roll any of it.

**Two docks, one model.** `top` is a sticky page strip for conditions that hold
the layout still; `corner` is a fixed stack for events. Each dock is its own
Radix viewport, so they never fight over one list, and the visible cap is applied
per dock — top strips can never hide corner toasts.

**Severity drives urgency and ARIA.** `critical` and `warning` interrupt
(`role="alert"`, `type="foreground"`); `info` and `success` wait
(`role="status"`, `type="background"`). Order is
`critical > warning > info > success`, and the default `maxVisible` is 3 per dock;
anything beyond that collapses into a "+N more notices" affordance.

## The durable notice history

A banner is transient by design: it fades, it is dismissed, and a reload wipes
it. That is right for a statement about the present moment and wrong for the
person who looked away. The **activity centre** (#406) is the other half of the
same system: every banner and toast raised through the studio is also written
down as a `Notice`, and the history outlives the banner that produced it.

```text
notices/types.ts       Notice, NoticeSeverity, NoticeInput
notices/recorder.ts    pure functions: recordNotice, dismissNotice, markAllRead, groupNoticesByDay
notices/fromBanner.ts  a BannerSpec resolves to a NoticeInput through the same catalog
notices/ActivityProvider.tsx  holds the list, reads it once, writes every change
components/activity/ActivityCentre.tsx  the dialog: day groups, severity, dismiss
```

**One description, not two.** `fromBanner.ts` calls `resolveSpec` on the banner
catalog, so a notice's severity, title, and body are the exact words the person
saw on screen. A second, hand-written summary of the same event would be a
description that drifts from the thing it describes.

**The recorder is pure and capped.** `recordNotice` returns a new list, newest
first, dedupes a repeat raised within a minute, and keeps at most
`NOTICE_CAP` rows so the history cannot grow without bound. Dismissal removes a
row permanently; "Mark all read" clears the unread count without removing
anything. These rules are unit-tested without a renderer.

**Persistence is best-effort.** `ActivityProvider` reads the list once on mount
and writes it after every change through `LocalStore.putNotices`. A store that
fails to open leaves the list empty rather than blocking the shell, and a
failure to write is swallowed: losing the history is a smaller failure than
losing the studio.

**Escape closes, only Dismiss removes.** The dialog is a dialog: Escape and the
scrim close it without touching a row, and it is portalled to the document root
so the shell behind it can be made inert without inerting the dialog too.
Severity is carried by a word ("Critical", "Warning", "Info", "Done"), never by
colour alone. With no rows the dialog says so — "Nothing has happened yet in
this workspace" — rather than showing an empty list.

## Adding a banner

1. Add the kind to `BannerKind` in `types.ts`.
2. Add its entry to `BANNER_CATALOG` in `catalog.ts` — severity, life, dock,
   default copy, and any actions (an action is a `BannerActionId`, not free
   text).
3. Raise it: `raise({ kind: "your-kind" })` from a component, or from
   `BannerBridge` if it is derived from studio state.

No new component, no new CSS class, no new toast stack.

## What is deliberately not a banner

Two surfaces look like they belong here and do not, by design:

- **`FailurePanel`** shows a failure *in place of the thing that failed* — the
  canvas, a lens. A banner is a statement about the state of the studio, floating
  over it; a failure panel replaces a region. Different idea, different job.
- **The transcript `.notice`** is a line in the conversation history, with the
  turn it belongs to. A banner is not history.

Keeping them out is the point of a closed catalog: a banner means one specific
thing, and the system stays legible because it does not absorb everything.

## Where the old surfaces went

- `components/Toasts.tsx` — replaced by `BannerToasts.tsx`; `pushToast` keeps its
  signature, so its call sites in `StudioContext.tsx` did not change.
- `components/notices/SidecarNotice.tsx` — replaced by the `sidecar-down` kind,
  raised from `BannerBridge`. Dismissing it records a session-long choice, so the
  next failed probe cannot bring it back.
- `components/chat/OfflineNotice.tsx` — replaced by the `model-offline` kind.
- The `offline` kind (browser connectivity, #546) is raised from `BannerBridge`
  off `navigator.onLine`. While the browser is offline it is the only strip: the
  `sidecar-down` and `model-offline` kinds are held back, because their copy and
  their Recheck action assume a network. Each resumes when the connection does.
- The `app-update-ready` kind (#545) is raised from `BannerBridge` off
  `src/lib/swUpdate.ts` when a new service worker is staged. It is held back while
  a turn is streaming, so the reload it offers can never land under a reply that
  is still arriving, and its one action is an explicit reload — never automatic.

## The offline page and the worker

`src/sw.ts` (built to `dist/sw.js`) is the offline shell. It precaches the files
the app build emitted — `index.html`, the hashed JS and CSS, the icons, the
manifest, and `/offline.html` — under one `studio-shell-<version>` cache, so the
installed app **opens with no network** and renders from cache (#545).

A navigation is answered network-first, and the cached shell answers when the
network cannot, in three seconds. `offline.html` (in `public/`) is the last
resort: it is served only when the shell cache was evicted, so the `offline` kind
above is the in-app half of the same story. `/api/**` is passed straight through
and never cached — a cached canvas response would defeat the BFF's fallback — and
`src/lib/swRouting.ts` holds the routing rules, the cache-name rule, and the
handlers so all of it is unit-testable without a service-worker global.

A new build gets a new cache name, so `activate` retires the old cache, but the
waiting worker is left alone: `src/lib/swUpdate.ts` watches for it and raises the
`app-update-ready` banner, and only a person's click sends `SKIP_WAITING` and
reloads. An update therefore never swaps code under a streamed turn.

## Verification

- Unit tests: `npm test -- banners` (store rules, provider, stack, bridge, toasts).
- Worker tests: `npm test -- swRouting swUpdate` (routing, precache, the update
  handshake).
- Browser tests: `npm run test:e2e -- no-sidecar/offline.spec.ts` (shell from
  cache with no network, `offline.html` only on an evicted cache, the API never
  cached, and one update offer that never reloads on its own).
- Visual snapshots: `npm run test:visual` — one snapshot per severity and dock.
