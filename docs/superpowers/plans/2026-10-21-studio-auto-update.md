# Plan — Living Studio self-update

Date: 2026-10-21
Spec: `docs/superpowers/specs/2026-10-21-studio-auto-update-design.md`

Work in `apps/studio` unless stated otherwise. Every step ends with a check that
can fail.

## 1. Core model (TDD)

1. `apps/studio/src/updater/types.ts` — phases, snapshot, events, `UpdaterHandle`,
   `UpdateTransport`, `UpdatePreferences`.
2. `apps/studio/src/updater/machine.ts` — `initialSnapshot`, `reduce`,
   `bannerView`, `progressPercent`, `describeStatus`.
3. `apps/studio/src/updater/machine.test.ts` — one test per transition and per
   selector (skip/dismiss silence, progress math, failure retention).

Check: `npm test -- --run src/updater/machine.test.ts`.

## 2. Service (TDD)

1. `apps/studio/src/updater/platform.ts` — `detectPlatform`, `installAfterDownload`.
2. `apps/studio/src/updater/service.ts` — `createUpdateService` with injected
   `transport`, `storage`, `now`, `platform`, timers; `start/stop/check/
   installAndRestart/dismiss/skipCurrent/setAutoCheck`.
3. `apps/studio/src/updater/service.test.ts` — fake transport + fake timers:
   no update, update found and staged, Windows pending install, download failure,
   skipped version, concurrent check dedupe, auto-check off, manual check,
   `installAndRestart` sequence, relaunch error.

Check: `npm test -- --run src/updater/service.test.ts`.

## 3. Transport

1. `apps/studio/src/updater/transport.ts` — wraps `@tauri-apps/plugin-updater`,
   `@tauri-apps/plugin-process`, `@tauri-apps/api/app`; maps download events to
   `(received, total)`.
2. `apps/studio/src/updater/transport.test.ts` — mocks the plugin modules and
   asserts mapping, progress accumulation, version/date/notes, unsupported mode.

Check: same command.

## 4. React surface

1. `UpdateProvider.tsx` — context, `useUpdateService`, `useUpdateSnapshot` via
   `useSyncExternalStore`; starts/stops the service.
2. `UpdateBanner.tsx` + test — downloading, ready (restart), Windows pending,
   error retry, dismiss.
3. `UpdateSettings.tsx` + test — version, status, check now, skip, auto-check.
4. `index.ts` barrel.
5. Wire into `App.tsx` (`<UpdateProvider>`, banner under the header), `Sidebar`
   (version row), `SettingsPanel` (new section, remove old disclosure button).
6. Delete `components/updater/useUpdater.ts`; update `SettingsPanel.test.tsx`.
7. `styles/theme.css` — banner, progress hairline, settings block, sidebar
   version row, reduced-motion fallback.

Check: `npm run lint && npm run typecheck && npm test -- --run && npm run build`.

## 5. Desktop shell

1. `apps/studio/src-tauri/Cargo.toml` — `tauri-plugin-process = "2"`.
2. `apps/studio/src-tauri/src/lib.rs` — register the plugin before `.setup`.
3. `capabilities/default.json` — add `"process:default"`.
4. `cargo check` refreshes `Cargo.lock`.

Check: `cargo fmt --check && cargo clippy -- -D warnings && cargo check`.

## 6. Release plumbing

1. `release-please-config.json` — `extra-files` for package.json, tauri.conf.json,
   Cargo.toml.
2. Sync the current version (`0.11.0`) into those three files + package-lock and
   Cargo.lock so a local build matches the manifest.
3. `.github/workflows/tauri-release.yml` — add `release: published`; add a
   `verify` job that downloads `latest.json` and asserts the platform keys.
4. `.github/workflows/release.yml` — add `release: published`.

Check: parse YAML (`python -c "import yaml..."`), review diff.

## 7. Docs

1. `docs/living-studio.md` — replace the stale updater paragraph with the real
   lifecycle and where the UI lives.
2. `docs/installation.md` — release trigger and manifest verification.
3. `README.md` — one line in the Living Studio section if it mentions updates.

## 8. End-to-end proof

`scripts/verify-desktop-update.sh`:

1. Generate a throwaway minisign key.
2. Build a signed 0.1.0 AppImage with `TAURI_CONFIG` overriding the endpoint to
   `http://127.0.0.1:8787/latest.json` and the test public key.
3. Build a signed 0.2.0 AppImage the same way.
4. Serve `latest.json` pointing at the 0.2.0 AppImage.
5. Run the 0.1.0 AppImage from a writable directory; wait for the update to
   install itself.
6. Assert the AppImage on disk now hashes to the 0.2.0 build.
7. Run it again and assert the server sees a check but no download.

## 9. Ship

1. Commit on `feat/studio-auto-update`.
2. Push, open a PR against `main` with the verification evidence.
3. Watch `CI` to green; fix anything that fails.
