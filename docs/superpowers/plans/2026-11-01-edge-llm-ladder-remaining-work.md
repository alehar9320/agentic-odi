# Edge LLM Ladder — Remaining Work

**Branch:** `alehar9320/flyingfish` **Base:** `main` (`58a125d`)
**Status:** the engine, the ladder, the routing seam, the progression scheduler and
the banners are built and tested. **A person cannot yet turn this on.** Read the
first gap before anything else; it explains why.

This file exists because the branch was cut short for review and the working
environment it was built in is temporary. Nothing here may survive only in a
scratch checkout, so the whole gap list lives on the branch.

## Read this first: the feature is dark

Two links in the chain have no user-facing end yet, and each one alone stops a
real person from ever getting an edge reply:

1. **Nothing grants consent.** `EdgeStateService.setConsent`
   (`apps/studio/src/edge/storage.ts:59`) is called only from tests. `shouldUseEdge`
   requires `consent === "granted"`
   (`apps/studio/src/edge/manager.ts`), so the routing decision is always false.
2. **Nothing fetches Tier 1.** The scheduler climbs *from* a tier that is already
   hosted: `noteTurn()` returns `null` when `strongestHosted(states) === null`
   (`apps/studio/src/edge/scheduler.ts:90`). `EdgeManager.stream()` throws when no
   tier is cached. So the ladder has no rung zero — there is no code path that
   downloads the first model.

Consequence for a user today: **no regression, no new behavior.** With no paid
model, Studio keeps answering through the deterministic BFF assistant and the
`model-offline` banner, exactly as before this branch. Every layer behind that is
wired and green, but it never runs.

The fix is one small surface (Settings section + first-run offer + a bootstrap
prefetch) — iterations 8 and 9 below. Do not merge this branch as a user-facing
feature; merge it, if it merges, as infrastructure.

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

Total across the seven commits, counting only the code diff and excluding this
document: 29 files, 2,465 lines added, 48 deleted, 60 new test cases across
7 test files.

## Remaining iterations

### 8 — Settings `EdgeModelSection` (the control surface)

Pattern to follow: the existing About section in the Settings panel.

- [ ] Enable/disable toggle bound to the `edgeModel` flag.
- [ ] **Consent control** — the affordance that grants or revokes
      `setConsent("granted" | "denied")`, worded in the size of the download:
      "Answer in this browser — about 1.3 GB, once."
- [ ] Tier cards: label, on-disk size, state (`empty` / `cached` / `active`).
- [ ] **Delete a tier** to free storage (`setTierState(id, {status:"empty"})` plus
      the WebLLM cache eviction), and a storage usage meter from
      `navigator.storage.estimate()`.
- [ ] Tests: a tier card per state; revoke-consent stops edge turns.

### 9 — Light it up: first-run copy, bootstrap download, docs

- [ ] **Tier 1 bootstrap.** When consent is granted and no tier is hosted, the
      scheduler must prefetch the strongest tier eligible as *first*, not only as
      *next*. Today that early return at `scheduler.ts:90` is the wall.
- [ ] First-run, no-key intro flow offers the browser model — one consent, no
      jargon, no dead end. Zero-config stays intact: rule-based answers keep
      working until Tier 1 lands, and the edge takes over the moment it is cached.
- [ ] `edge-active` marker on an edge reply in the transcript, so a person can
      tell which brain answered.
- [ ] Rewrite `docs/local-llm.md` §6 for what actually shipped; add the capability
      to the `README.md` capability table; update `docs/living-studio.md` and
      `.agents/rules` if they list capabilities.
- [ ] State the divergence honestly: `router.py:1199` and `worker.ts:57` keep
      `browser-model: false` server-side — a server cannot see a client GPU.

### 10 — Verification a reviewer can repeat

- [ ] `e2e/edge.spec.ts` with `FakeEdgeEngine`
      (`apps/studio/src/test/edgeFake.ts`) injected via
      `edgeManager.setEngineFactory` behind the flags mechanism. WebGPU does not
      exist in CI; jsdom covers logic, not the model.
- [ ] **The real gate, by hand, on a WebGPU device:** `npm --prefix apps/studio run
      dev:full` → clear the key in Settings → send a message → consent → Tier 1
      downloads with a live strip → reply streams → ten answers later the next
      tier prefetches during idle → upgrade toast → re-add a key and turns return
      to the remote path.
- [ ] Multi-tab: confirm `navigator.locks` keeps one engine across tabs.
- [ ] `scripts/pr_guards.py` and both CI checks (`ci.yml`, `pr-guardrails.yml`).

## Known gaps beyond the iterations

- **Main-thread prefill.** v1 runs WebLLM on the main thread; Tier 3 prefill will
  jank the UI. The worker path (`engine.worker.ts` +
  `SimpleWorkerMLCEngineHandler`) is the scheduled upgrade, and `EdgeLLMEngine`
  exists so the swap touches one file.
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

## Resume checklist (for whoever picks this up)

```bash
git fetch origin && git checkout alehar9320/flyingfish
npm --prefix apps/studio install
npm --prefix apps/studio run typecheck
npm --prefix apps/studio test -- --run     # 88 files, 812 tests
npm --prefix apps/studio run lint          # 0 errors, 5 pre-existing warnings
npm --prefix apps/studio run build
uv run pytest apps/studio-api tests/test_worker_security_headers.py -q   # 318 passed
```

Then start at iteration 9's first checkbox (Tier 1 bootstrap) if you want a person
to see this work; iteration 8's consent control if you want the UI first. Either
way, the feature stays dark until both exist.

Every iteration ends with that block green, one commit, and this file updated.
