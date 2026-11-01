# Edge LLM Ladder — Remaining Work

**Branch:** `alehar9320/flyingfish` **Base:** `main` (`58a125d`)
**Status:** the engine, the ladder, the routing seam, the progression scheduler
and the banners are built and tested, **and a person can now turn the feature
on** — the offer strip asks once, and the answer starts the first download.
What is left is a Settings control for changing that answer later, the
first-run copy, and verification on real hardware.

This file exists because the branch was cut short for review and the working
environment it was built in is temporary. Nothing here may survive only in a
scratch checkout, so the whole gap list lives on the branch.

## Read this first: how a person reaches it today

With no paid endpoint configured and the health probe reporting the model
unreachable, the top dock shows *"This browser can answer, free."* naming the
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

Until this iteration the two ends were missing — nothing granted consent, and
nothing fetched Tier 1 (`noteTurn()` climbed only *from* a hosted tier). Both
now exist, which is the difference between infrastructure and a feature. The
rest of this file is what a reviewer should still expect to be absent.

## What is built (commit map)

| Commit | Iteration | Delivered |
| --- | --- | --- |
| `6796fa2` | 1 | `edge/types.ts`, `edge/ladder.ts`, `edge/storage.ts` + `edgeModel` flag — engine interface, three-tier ladder with device gates, IndexedDB state + engine lock |
| `b91bdc0` | 2 | `browser-model` capability probe reports WebGPU and ladder truth instead of only `window.ai` |
| `76d8bd9` | 3 | `edge/webllmEngine.ts`, `@mlc-ai/web-llm` dependency, Worker CSP for wasm + weight origins |
| `c9fbdf6` | 4 | `edge/turn.ts`, `edge/prompt.ts` — an edge turn emitted as the exact `RawSseEvent` frames the transcript already consumes |
| `dc7988d` | 5 | `edge/manager.ts` + the `runTurn` seam and the relaxed sidecar guard |
| `f39c3fa` | 6 | `edge/scheduler.ts` — ten served answers earn the next tier, consent-locked, idle/visible/SaveData-gated, single-engine-across-tabs |
| `fd0bfe4` | 7 | `edge-downloading` / `edge-unlocked` banner kinds; the bridge subscribes to edge notices and stops claiming "Working by hand" while the edge answers |
| this commit | 9 (first half) | `EdgeScheduler.bootstrap()` (rung zero), `EdgeManager.offerFor / grantAndStart / decline / isBusy`, the `ready` and `consent-changed` notices, and the `edge-offer` / `edge-ready` banners with both buttons wired through the dispatcher. `docs/local-llm.md` now describes a reachable feature. Landed out of plan order, before the Settings section, because nothing else on this branch matters while no person can switch it on. |

Total for the eight feature commits, counting the code and docs they changed
and excluding this document: 28 files, 3,009 lines added, 49 deleted, 83 new
browser test cases plus one amended Python security-header test.

## Remaining iterations

### 8 — Settings `EdgeModelSection` (the control surface)

Pattern to follow: the existing About section in the Settings panel.

- [ ] Enable/disable toggle bound to the `edgeModel` flag.
- [ ] **Consent control** — the place to *change* the answer the offer strip
      recorded: `setConsent("granted" | "denied")`, worded in the size of the
      download ("Answer in this browser — about 1.3 GB, once"). Granting it here
      should fetch Tier 1 through `EdgeManager.grantAndStart()`, exactly as the
      banner button does.
- [ ] Tier cards: label, on-disk size, state (`empty` / `cached` / `active`).
- [ ] **Delete a tier** to free storage (`setTierState(id, {status:"empty"})` plus
      the WebLLM cache eviction), and a storage usage meter from
      `navigator.storage.estimate()`.
- [ ] Tests: a tier card per state; revoke-consent stops edge turns.

### 9 — Light it up: first-run copy, bootstrap download, docs

- [x] **Tier 1 bootstrap.** `EdgeScheduler.bootstrap()` fetches the weakest
      eligible tier as *first*, not only as *next*, and `EdgeManager` reaches it
      from the consent answer. (Delivered in this commit.)
- [x] A no-key visitor is offered the browser model in one sentence, with the
      size, and has an explicit "Not now". (Delivered here as the `edge-offer`
      strip; the intro-flow copy below is still open.)
- [ ] First-run, no-key intro flow offers the browser model too — one consent, no
      jargon, no dead end, in the same words as the strip. Zero-config stays
      intact: rule-based answers keep working until Tier 1 lands, and the edge
      takes over the moment it is cached.
- [ ] `edge-active` marker on an edge reply in the transcript, so a person can
      tell which brain answered.
- [x] `docs/local-llm.md` §"The browser tier" rewritten for what actually
      shipped, including what has never been run on real hardware. (Done here.)
- [ ] Add the capability to the `README.md` capability table; update
      `docs/living-studio.md` and `.agents/rules` if they list capabilities.
- [ ] State the divergence honestly: `router.py:1199` and `worker.ts:57` keep
      `browser-model: false` server-side — a server cannot see a client GPU.

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
- **A yes in one tab is not noticed live in another.** A tab that lost the
  engine lock has no event that re-runs its strip decision; the download the
  other tab finished shows up at the next turn's routing check, not the moment
  it lands. BroadcastChannel or a storage event would close it.
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
npm --prefix apps/studio test -- --run     # 88 files, 835 tests
npm --prefix apps/studio run lint          # 0 errors, 5 pre-existing warnings
npm --prefix apps/studio run build
uv run pytest apps/studio-api tests/test_worker_security_headers.py -q   # 318 passed
```

Then start at iteration 8's consent control if you want the ladder
controllable from Settings, or iteration 10 if you want to prove it on a GPU.
A first real user can already reach the feature; neither of those is required
for that.

Every iteration ends with that block green, one commit, and this file updated.
