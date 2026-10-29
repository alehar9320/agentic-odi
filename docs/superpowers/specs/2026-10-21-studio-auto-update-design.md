# Living Studio — self-updating desktop app

Date: 2026-10-21
Status: approved (implemented in `feat/studio-auto-update`)

## Intent

An installed Living Studio must never go stale. When a newer signed release is
published, the app notices on its own, installs it in the background, and applies
it the next time it starts — or immediately, the moment the person asks it to
restart. Nobody should have to re-download an installer, and nobody should be
interrupted by an update they did not ask for.

## What is true today

- `tauri.conf.json` has `createUpdaterArtifacts`, an endpoint, and a public key.
- `tauri-plugin-updater` is registered, and a `useUpdater` hook can check and
  `downloadAndInstall` from a button hidden in a disclosure.
- The Tauri app version is pinned at `0.1.0`. Releases are cut by release-please
  at `0.11.0` and beyond, so the installed version never changes and the updater
  can never see a newer manifest.
- `Tauri Release` has never run: release-please creates the GitHub release
  through the API, which does not emit the `push: tags` event the workflow
  listens for. Releases therefore carry no bundles and no `latest.json`.
- The updater hook installs without consent, never relaunches, has no restart
  affordance, and offers no progress, failure, or "come back later" story.

## Goals

1. A tagged release publishes signed, platform-specific updater artifacts plus a
   merged `latest.json`, with no manual step.
2. An installed desktop build checks quietly, downloads in the background,
   verifies the signature, and installs without a modal.
3. The update is visible in the studio at all times: a quiet bar above the stage,
   a first-class Settings section, and the running version in the sidebar.
4. Applying the update is one deliberate action ("Restart now"), and if the
   person declines, the next ordinary launch runs the new version (macOS/Linux,
   where staging is safe). Windows needs the app to exit before its installer
   runs, so it offers "Update & restart" instead.
5. Background check failures are silent; only the Settings section reports them.
6. Everything is testable without a desktop runtime.

## Non-goals

- Delta/partial downloads. Tauri ships whole bundles; we keep that.
- A custom update server. GitHub Releases remains the source of truth.
- Downgrades, channels, or beta opt-ins.
- Auto-restarting while someone is mid-conversation.

## Architecture

The feature is split into policy, transport, and presentation so each can be
reasoned about alone.

```
apps/studio/src/updater/
  types.ts        Domain vocabulary: phases, snapshot, events.
  machine.ts      Pure reducer + selectors. No I/O, no timers, no React.
  service.ts      Orchestration: schedule, download, install, relaunch, prefs.
  transport.ts    The only module that imports Tauri plugins.
  platform.ts     Install policy per OS (silent staging vs. exit-to-install).
  UpdateProvider.tsx  One service per app, shared through context.
  UpdateBanner.tsx    The quiet bar above the stage.
  UpdateSettings.tsx  The Settings → Software update section.
```

### The state machine

One snapshot, one event stream. Every UI surface derives from the same
snapshot, so the bar, the sidebar, and Settings can never disagree.

```ts
type UpdatePhase =
  | "unsupported" | "idle" | "checking" | "downloading"
  | "installing" | "ready" | "up-to-date" | "error";

interface UpdateSnapshot {
  phase: UpdatePhase;
  currentVersion: string | null;
  available: { version: string; date: string | null; notes: string | null } | null;
  progress: { received: number; total: number | null } | null;
  lastCheckedAt: number | null;
  installed: boolean;      // artifact staged; a relaunch activates it
  pendingInstall: boolean; // downloaded, but installing requires an app exit
  error: string | null;
  autoCheck: boolean;
  skippedVersion: string | null;
  dismissedVersion: string | null;
}
```

`bannerView(snapshot)` is a selector, not component logic: it returns `null` for
background-check failures, for a version the person skipped or dismissed, and
for an up-to-date app. That keeps the shell silent by construction.

### The service

`UpdateService` owns one update at a time and never runs two checks
concurrently. `start()` schedules the first check four seconds after launch
(never competing with first paint), re-checks every six hours, and re-checks on
`visibilitychange` when the app returns to the foreground after an interval.
Manual checks bypass the schedule.

Flow: `check → found → download (progress) → install (macOS/Linux) → ready`.
On Windows the download stops at `ready + pendingInstall`, and the explicit
action performs `install → relaunch`.

Preferences live in `localStorage` under `studio.update.*`:
`autoCheck` (default on) and `skippedVersion`.

### Transport

The transport is the only Tauri-aware layer:

```ts
interface UpdateTransport {
  supported(): boolean;
  currentVersion(): Promise<string>;
  check(): Promise<UpdaterHandle | null>;
  relaunch(): Promise<void>;
}
```

`UpdaterHandle` exposes `download(onProgress)`, `install()`, and `close()`. Tests
drive the service with a fake transport; nothing in `machine.ts` or `service.ts`
imports a Tauri package.

### Platform policy

`installAfterDownload(platform)` is true everywhere except Windows. macOS and
Linux can replace the running bundle safely, so the update is staged the moment
it finishes downloading; the new code runs on the next launch even if the person
never clicks anything. Windows requires the app to exit for NSIS to run, so the
install is bound to the explicit "Update & restart" action.

### Presentation

- **Banner** (`role="status"`, `aria-live="polite"`) sits directly under the top
  bar: a title, one sentence, a hairline progress indicator, one primary action,
  and a dismiss. It never blocks the conversation and never steals focus.
- **Settings → Software update**: running version, a plain-language status, the
  release notes in a disclosure, "Check now", "Skip this version", and an
  auto-check toggle. In a browser it says, honestly, that in-app updates belong
  to the desktop app.
- **Sidebar footer**: the running version, one quiet line, clickable to Settings.
  A dot appears when an update is ready.

Copy is written for a person, not an engineer: "Living Studio 0.12.0 is ready —
Restart to finish." No percentages without context, no error codes, no modal.

## Release pipeline

1. `release-please-config.json` gains `extra-files` so `apps/studio/package.json`,
   `apps/studio/src-tauri/tauri.conf.json`, and `apps/studio/src-tauri/Cargo.toml`
   are bumped with each release. Without this the installed version cannot move.
2. `Tauri Release` and `release` also trigger on `release: published`, because
   release-please creates the release via the API and no `push: tags` event is
   emitted. The `workflow_dispatch` path stays for manual retries.
3. A `verify` job asserts the release carries `latest.json` covering Linux,
   Windows, and both macOS architectures. `tauri-action` merges platform entries
   into an existing `latest.json`, so matrix jobs do not clobber each other.

## Constraints and risks

- The signing public key in `tauri.conf.json` must match the
  `TAURI_SIGNING_PRIVATE_KEY` secret. If it does not, every install fails
  signature verification; the UI surfaces that as an error instead of a crash.
- Linux updates apply to AppImage installs. A `.deb` install cannot self-replace;
  the error path says so and leaves the app untouched.
- The updater is inactive in `tauri dev` and in the browser build. The transport
  reports `unsupported` and the UI explains where updates live.

## Verification

- Reducer, service, transport mapping, banner, settings, and sidebar each have
  unit tests; the service is exercised with fake timers and a fake transport.
- `npm run lint`, `npm run typecheck`, `npm test -- --run`, `npm run build`.
- `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo check`.
- An end-to-end script builds two signed AppImages (0.1.0 and 0.2.0) with a
  throwaway key, serves `latest.json` locally, runs 0.1.0, and asserts its own
  file on disk becomes the 0.2.0 build. That exercises the real plugin, the real
  signature check, and the real installer.
