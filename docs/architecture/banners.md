# Studio banners

Banners are how the Studio tells the user about the state of the studio: the
sidecar is down, the model is unreachable, a step was added, a write was
rejected. Before this system, five components each owned their own markup, CSS,
and idea of when to appear. Now one system owns all of it, and a new banner is a
catalog entry — never a new component and never a new CSS class.

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

## Adding a banner

1. Add the kind to `BannerKind` in `types.ts`.
2. Add its entry to `BANNER_CATALOG` in `catalog.ts` — severity, life, dock,
   default copy, and any actions (an action is a `BannerActionId`, not free
   text).
3. Raise it: `raise({ kind: "your-kind" })` from a component, or from
   `BannerBridge` if it is derived from studio state.

No new component, no new CSS class, no new toast stack.

## Where the old surfaces went

- `components/Toasts.tsx` — replaced by `BannerToasts.tsx`; `pushToast` keeps its
  signature, so its call sites in `StudioContext.tsx` did not change.
- `components/notices/SidecarNotice.tsx` — replaced by the `sidecar-down` kind,
  raised from `BannerBridge`. Dismissing it records a session-long choice, so the
  next failed probe cannot bring it back.
- `components/chat/OfflineNotice.tsx` — replaced by the `model-offline` kind.

## Verification

- Unit tests: `npm test -- banners` (store rules, provider, stack, bridge, toasts).
- Visual snapshots: `npm run test:visual` — one snapshot per severity and dock.
