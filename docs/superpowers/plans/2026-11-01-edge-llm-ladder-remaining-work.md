# Edge LLM Ladder — Remaining Work

**Branch:** `alehar9320/flyingfish` **Base:** `main` (`58a125d`), merged forward
to `main`'s current tip — see "Merged with `main`" below.
**Status:** the engine, the ladder, the routing seam, the progression scheduler
and the banners are built and tested, **a person can turn the feature on** —
the offer strip asks once — **that answer can now be changed from Settings**,
with the tiers on disk listed and freeable, **every reply says which brain
produced it**, and **two open tabs agree without being asked**. What is left is
the first-run intro copy and verification on real hardware.

This file exists because the branch was cut short for review and the working
environment it was built in is temporary. Nothing here may survive only in a
scratch checkout, so the whole gap list lives on the branch.

## Read this first: how a person reaches it today

With nothing answering for the Studio — no model endpoint the client counts as
configured, and the health probe reporting the model unreachable — the top dock
shows *"This browser can answer, free."* naming the
model and its one-time size, with two buttons:

- **Answer in this browser** → `EdgeManager.grantAndStart()`
  (`apps/studio/src/edge/manager.ts`) records consent and calls the new
  `EdgeScheduler.bootstrap()` (`apps/studio/src/edge/scheduler.ts`) — rung zero.
  It fetches the weakest tier this device could host, under the same
  quiet-moment and single-engine-across-tabs rules as any other download. When
  it lands, a `ready` notice replaces the strip with a toast and the next turn
  is answered in the tab.
- **Not now** → durable `setConsent("denied")`. `offerFor()` never returns an
  offer after that, so the studio asks exactly once, and `model-offline` comes
  back because it is again the truth.

The offer appears only where it would change the answer: flag on, no healthy
remote endpoint, consent still `unset`, nothing on disk, and a device the ladder
can actually host. If the yes finds a hidden tab, a Save Data connection, or
another tab holding the engine lock, nothing was fetched and the strip says so
rather than pretending.

**Settings → Answers in this browser** (`apps/studio/src/components/EdgeModelSection.tsx`)
is the second place to give that answer, and the only place to take it back.
It reads one snapshot (`edgeManager.panelState()`) and re-reads it on every
settled edge notice — a tier landing, a tier freed, consent changing — while
ignoring the per-percent download ticks, so it stays a view of the ladder rather
than a second owner of its state. The checkbox is the `edgeModel` flag; the
consent answer moves through the same `grantAndStart()` / `decline()` calls as
the banner, and a yes that starts nothing reports that, in the same words.

Once it is answering, the transcript keeps the person in no doubt about who is
doing the work: a reply the tab produced carries *"Answered in this browser"* on
itself, in the same slot and the same kind of button as *"Local draft, no model
connected"* carries on a reply no model produced. Two brains, one line, never
both on one reply.

Until the previous iteration the two ends were missing — nothing granted
consent, and nothing fetched Tier 1 (`noteTurn()` climbed only *from* a hosted
tier). Both now exist, which is the difference between infrastructure and a
feature. The rest of this file is what a reviewer should still expect to be
absent.

## What is built (commit map)

| Commit | Iteration | Delivered |
| --- | --- | --- |
| `6796fa2` | 1 | `edge/types.ts`, `edge/ladder.ts`, `edge/storage.ts` + `edgeModel` flag — engine interface, three-tier ladder with device gates, IndexedDB state + engine lock |
| `b91bdc0` | 2 | `browser-model` capability probe reports WebGPU and ladder truth instead of only `window.ai` |
| `76d8bd9` | 3 | `edge/webllmEngine.ts`, `@mlc-ai/web-llm` dependency, Worker CSP for wasm + weight origins |
| `c9fbdf6` | 4 | `edge/turn.ts`, `edge/prompt.ts` — an edge turn emitted as the exact `RawSseEvent` frames the transcript already consumes |
| `dc7988d` | 5 | `edge/manager.ts` + the `runTurn` seam and the relaxed sidecar guard — that guard is gone now, deleted by `main`'s "never refuse to send"; the seam is what remains |
| `f39c3fa` | 6 | `edge/scheduler.ts` — ten served answers earn the next tier, consent-locked, idle/visible/SaveData-gated, single-engine-across-tabs |
| `fd0bfe4` | 7 | `edge-downloading` / `edge-unlocked` banner kinds; the bridge subscribes to edge notices and stops claiming "Working by hand" while the edge answers |
| `d34d8e5` | 9 (first half) | `EdgeScheduler.bootstrap()` (rung zero), `EdgeManager.offerFor / grantAndStart / decline / isBusy`, the `ready` and `consent-changed` notices, and the `edge-offer` / `edge-ready` banners with both buttons wired through the dispatcher. `docs/local-llm.md` now describes a reachable feature. Landed out of plan order, before the Settings section, because nothing else on this branch matters while no person can switch it on. |
| `3a1f633` | 8 | `components/EdgeModelSection.tsx` — Settings → *Answers in this browser*: the flag switch, a consent answer that can be changed and withdrawn, per-tier status with device reasons, free-a-tier storage, the progression meter, the quota line. `EdgeManager.panelState()` and `freeTier()` (with `EdgeLLMEngine.evict`, the only Settings path that may pull in the WebLLM chunk), the notice seam turned multi-subscriber so the strip and Settings both react, and the section mounted in `SettingsPanel`. |
| `f475509` | merge | `origin/main` merged forward; see "Merged with `main`" below for the four conflicts and what each one cost this feature. |
| `748e817` | 9 (second half) | The reply names its brain: `edge/turn.ts` opens with `status` `phase: "edge"`, `StudioContext` records `edgeReplyFor` beside the existing `offlineReplyFor`, and `Conversation.tsx` renders one provenance tag per reply — *"Answered in this browser"* — with the edge answer taking precedence over the draft label. Plus the capability prose in `docs/local-llm.md` and `docs/living-studio.md`. |
| `634d927` | 9 (second half) | The other half of the claim, tested: a turn handed to a healthy endpoint earns *neither* provenance label, so the marker provably follows the routing rather than the feature flag. |
| `1fec223` | 9 (cross-tab) | `edge/bus.ts` — the ladder tells its other tabs. `EdgeNotice` gains `{ kind: "changed" }`, `EdgeManager` publishes on settled notices only, `reset()` closes the channel, and `src/test/fakeBroadcastChannel.ts` doubles the browser API for the suites that need two tabs. |
| this commit | merge | `origin/main` merged forward a second time (conversation list, saved canvas, per-field Settings saves, the assistant-ui ledger, the reuse-ladder agents doc). One file conflicted for real: `components/SettingsPanel.tsx`, because `main` moved the connection rows into `settings/sections/*`. Resolved by keeping `main`'s structure and re-mounting `<EdgeModelSection />` after `</ConnectionsSection>` — and pinned with a test, since a silent drop here would have been invisible. |

Everything the branch changes on top of `main` as merged: 43 files, 4,658 lines
added, 50 deleted, and 115 added browser test cases, which now run 965 tests
across 101 files, plus one amended Python security-header test.

## Merged with `main` (twice)

`main` moved under the branch and PR #608 went CONFLICTING. Four files carried
real conflicts. What changed, in the shape a reviewer can check:

- **One endpoint rule.** `apps/studio/src/lib/modelEndpoint.ts` is now the
  studio's single definition of *"a server is answering"*, and it counts a
  keyless model on the person's own network. The browser tier defers to it
  through `hasModelEndpoint()` (`edge/manager.ts`), which delegates instead of
  re-deriving — a fallback that talked over a working Ollama would be a bug, not
  a fallback. `bff/capabilities/registry.ts` reads the same function.
- **A refusal to delete.** `main` removed the guard that blocked a turn when the
  sidecar was known-down ("sending is the only evidence that matters"), so the
  relaxation iteration 5 made at that call site went with it. The seam it opened
  survives, and its job is now exactly one thing: *which brain answers*, not
  *whether to answer at all*.
- **The routing decision reads a snapshot.** A turn no longer awaits a storage
  read to learn who will answer it. `EdgeManager` keeps `{consent, servedTier}`
  in memory, warms it when the provider mounts, refreshes it after every
  non-progress edge notice, and fires a best-effort re-read at each decision —
  so nobody's message is queued behind IndexedDB. The cost, said plainly: a
  change made elsewhere lands on the turn *after* the read that noticed it.
  `sync()` is the awaitable form for surfaces that can wait, and the banner strip
  uses it before deciding. This was not a style preference: awaiting the read
  hung the whole `StudioContext` suite, because fake-indexeddb schedules its
  transactions on the very timers those tests fake.
- **The survey is idle-scheduled.** `main` waits for an idle moment (or 2s)
  before probing anything, and a background probe that finds nothing no longer
  reports the sidecar down. The edge-routing tests were rewritten against those
  rules — they call `recheckConnections()` when they need a fact about the
  server, and wait for the person's own history to paint before typing.
- **The second merge moved Settings under it.** `main`'s per-field save work
  pulled the connection rows and the model controls into
  `settings/sections/ConnectionsSection` and `ModelSection`, so
  `SettingsPanel.tsx` was the only real conflict left. The resolution keeps
  `main`'s layout and re-mounts `<EdgeModelSection />` immediately after
  `</ConnectionsSection>` — the same position it held when the panel was flat:
  below what the studio can reach, above what you can do about it. Nothing else
  on the branch needed re-deriving: the edge section drives its own
  feature-flag override (`features/flags.ts`), not `saveSettings`, so it never
  touched the save path `main` reworked. That reposition was one line and could
  have been dropped without any test noticing, so `SettingsPanel.test.tsx` now
  mocks the section with a visible marker and asserts the panel renders it.

## Remaining iterations

### 8 — Settings `EdgeModelSection` (the control surface) — DONE

Pattern followed: the existing About section in the Settings panel.

- [x] Enable/disable toggle bound to the `edgeModel` flag (`setFeatureOverride`,
      so it writes the same `localStorage` key the URL-parameter and diagnostics
      paths read).
- [x] **Consent control** — the place to *change* the answer the offer strip
      recorded. With nothing on disk it is one button in the size of the
      download ("Download Llama 3.2 1B — about 1.3 GB, once") that goes through
      `EdgeManager.grantAndStart()`, exactly as the banner button does; with a
      tier answering it is "Stop answering here" → `decline()`. A granted consent
      that a paid key currently outranks says so instead of implying the browser
      is answering.
- [x] Tier rows: label, on-disk size, state (`not downloaded` / `on this device`
      / `answering`), and the device reason on any tier that this hardware could
      not host.
- [x] **Delete a tier** to free storage — `EdgeManager.freeTier()` clears our
      IndexedDB state and, for a tier that was actually fetched, calls the new
      `EdgeLLMEngine.evict()` (WebLLM's `deleteModelAllInfoInCache`). Plus a
      storage line from `navigator.storage.estimate()`.
- [x] Tests: 12 in `EdgeModelSection.test.tsx` (a row per state, the flag
      round-trip, revoke-consent, free-a-tier, the meter, the honest
      nothing-started notice, unsubscribe on unmount) and 6 more in
      `manager.test.ts` for the snapshot and the eviction rules — including that
      freeing a tier that was never fetched touches neither the engine nor its
      cache.

What that cost in the existing code, so a reviewer knows where to look: the
notice seam went from one listener to many (`addNoticeListener` returns an
unsubscribe) because the strip and Settings now both react; `panelState()`
reports exactly one tier as `answering` — the strongest on disk — and demotes
stored-but-superseded tiers to `on this device`; `evict` was added to the engine
interface, which is why `turn.test.ts`'s inline fake gained a no-op.

### 9 — Light it up: first-run copy, bootstrap download, docs

- [x] **Tier 1 bootstrap.** `EdgeScheduler.bootstrap()` fetches the weakest
      eligible tier as *first*, not only as *next*, and `EdgeManager` reaches it
      from the consent answer. (Delivered in `d34d8e5`.)
- [x] A no-key visitor is offered the browser model in one sentence, with the
      size, and has an explicit "Not now". (Delivered in `d34d8e5` as the `edge-offer`
      strip; the intro-flow copy below is still open.)
- [ ] First-run, no-key intro flow offers the browser model too — one consent, no
      jargon, no dead end, in the same words as the strip. Zero-config stays
      intact: rule-based answers keep working until Tier 1 lands, and the edge
      takes over the moment it is cached.
- [x] `edge-active` marker on an edge reply in the transcript, so a person can
      tell which brain answered. (Delivered in `748e817`: `edge/turn.ts` now
      opens its stream with `status` `phase: "edge"`, `StudioContext` records that
      as `edgeReplyFor` the same way it already records `offlineReplyFor`, and
      `Conversation` puts *"Answered in this browser"* on the reply — one button,
      opens Settings, never both labels on one reply.)
- [x] Cross-tab ladder sync: a yes, a landed tier, or a freed tier in one tab
      reaches the other tabs immediately. `edge/bus.ts` opens a
      `BroadcastChannel("agentic-odi-edge-ladder")` and `EdgeManager` publishes
      on every settled notice — never on a download tick — while the receive path
      re-reads storage and emits `{ kind: "changed" }` to this page's listeners
      only. Deliberately contentless, and deliberately not a replay: a tab that
      did not fetch a model does not announce one as *"answering in this tab
      now"*. The channel is opened when a page starts caring
      (`addNoticeListener`, or the provider's mount-time `sync()`), so a tab that
      only ever reads still hears; where `BroadcastChannel` is missing or refused
      (private browsing) the bus is silent and the ladder keeps working in one
      tab. `BannerBridge` and Settings needed no changes: both already react to
      any non-progress notice.
- [x] `docs/local-llm.md` §"The browser tier" rewritten for what actually
      shipped, including what has never been run on real hardware. (Done in `d34d8e5`.)
- [x] Add the capability to `README.md` and — per `.agents/rules` line 159,
      which routes a new conversation capability there — to the capability table
      in `docs/living-studio.md`. Both name the conversation-turns-only
      boundary. (Done in `3a1f633`.)
- [x] State the divergence honestly: `apps/studio-api/.../studio/router.py:1220`
      and `infra/cloudflare/worker.ts:57` keep `browser-model` at
      `available: false` — a server cannot see a client GPU — while the client's
      own capability registry reports the truth. Verified against both manifests
      and said in `docs/local-llm.md` §"The browser tier".

### 10 — Verification a reviewer can repeat

- [ ] `e2e/edge.spec.ts` with `FakeEdgeEngine`
      (`apps/studio/src/test/edgeFake.ts`) injected via
      `edgeManager.setEngineFactory` behind the flags mechanism. WebGPU does not
      exist in CI; jsdom covers logic, not the model.
- [ ] **The real gate, by hand, on a WebGPU device:** `npm --prefix apps/studio run
      dev:full` → clear the key in Settings → send a message → the offer strip
      appears → **Answer in this browser** → Tier 1 downloads with a live strip →
      reply streams → ten answers later the next tier prefetches during idle →
      upgrade toast → re-add a key and turns return to the remote path.
- [ ] The **Not now** path by hand: decline, confirm `model-offline` returns and
      that no second ask ever appears.
- [ ] Multi-tab: confirm `navigator.locks` keeps one engine across tabs —
      including two tabs that both show the offer.
- [ ] `scripts/pr_guards.py` and both CI checks (`ci.yml`, `pr-guardrails.yml`).

## Known gaps beyond the iterations

- **Main-thread prefill.** v1 runs WebLLM on the main thread; Tier 3 prefill will
  jank the UI. The worker path (`engine.worker.ts` +
  `SimpleWorkerMLCEngineHandler`) is the scheduled upgrade, and `EdgeLLMEngine`
  exists so the swap touches one file.
- **One-turn staleness is gone; one real-hardware question remains.** Cross-tab
  consent, tier state and the Settings snapshot now travel over the ladder bus
  (iteration 9 above), so a tab never answers a turn from a fact another tab
  invalidated a minute ago. What the bus cannot prove from a test runner is
  `navigator.locks` on a real GPU with two tabs both reaching for the engine: the
  losing tab gets no notice of the lock it never acquired, only the news that
  the ladder moved. That check is on the iteration-10 manual list.
- **The provenance label lives for the session.** *"Answered in this browser"*
  and *"Local draft, no model connected"* both come from a `status` frame in the
  live stream, so a reply re-read from history next visit carries no label. That
  is `main`'s existing mechanism, unchanged and shared; giving a message its own
  stored provenance means a new field on the persisted message and a second
  consumer in `assistant/convert.ts`, which this branch deliberately did not do.
- **Edge turns never reach the server conversation tree** while the sidecar is up.
  A backfill through `POST /api/conversations/{id}/turns` is an explicit non-goal
  for v1 and must stay documented, not discovered.
- **Weighted-cache loss is honest but unmeasured.** Our IndexedDB ladder is the
  source of truth; if WebLLM's own cache is evicted, we re-download rather than
  claim a tier we no longer have.
- **Memory-tight devices (iOS Safari).** The ladder caps tiers by
  `navigator.deviceMemory` and quota headroom, but no real iPhone has been
  tested; treat the caps as designed, not proven.
- **Test coverage floors are Python-only** — `codecov.yml` ignores
  `apps/studio`, so none of this moves the backend coverage gate.
- **The CSP may be moot on the hosted Studio, in its current form.** On the live
  preview and on production `main`, `/` comes back as a Cloudflare edge-cache HIT
  with **no** `Content-Security-Policy` header at all, so nothing in this branch
  blocks WebLLM there — and equally, the app document ships with no CSP. The
  header does apply to Worker-run responses (`/api/*` verified on the preview,
  including `'wasm-unsafe-eval'` and the three weight origins). If the CSP is ever
  made to cover cached documents, re-verify `worker-src`/`child-src` for WebLLM's
  wasm loading, which this branch did not need to touch.

## Resume checklist (for whoever picks this up)

```bash
git fetch origin && git checkout alehar9320/flyingfish
npm --prefix apps/studio install
npm --prefix apps/studio run typecheck
npm --prefix apps/studio test -- --run     # 101 files, 965 tests
npm --prefix apps/studio run lint          # 0 errors, 5 pre-existing warnings
npm --prefix apps/studio run build
uv run pytest apps/studio-api tests/test_worker_security_headers.py -q   # 330 passed
uv run pytest -q                           # 1824 passed (repo-wide)
```

Then start at iteration 9's last open item if you want a first-run visitor to
meet the browser model in the intro flow (the offer strip already does this job
after the studio has opened; the context conversation is what is left), or at
iteration 10 if you want to prove it on a GPU. A first real user can already
reach the feature, control it, see which brain answered, and have two tabs agree
on both; none of those is required for that.

Every iteration ends with that block green, one commit, and this file updated.
