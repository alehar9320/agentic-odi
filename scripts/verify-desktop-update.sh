#!/usr/bin/env bash
# Proves the Living Studio updater end to end against a local release feed:
#
#   1. generates a throwaway minisign key
#   2. builds signed 0.1.0 and 0.2.0 AppImages pointed at a local latest.json
#   3. runs 0.1.0 and waits for it to install 0.2.0 over its own file
#   4. runs the result again and asserts it checks, finds nothing, and downloads
#      nothing
#
# This runs weekly in CI: the `updater-e2e` job in .github/workflows/ci.yml
# (schedule + workflow_dispatch only) executes it headless under xvfb with
# APPIMAGE_EXTRACT_AND_RUN=1. Its result gates a desktop release in
# .github/workflows/tauri-release.yml rather than sitting in the pull-request gate:
# a release is the decision this proof belongs to, and a ~40-minute build that nobody
# pushed cannot be the reason an unrelated pull request is red. It needs no
# repository secret — the key is generated per run below and the committed updater
# public key is untouched. It also stays runnable from a workstation:
#
#   bash scripts/verify-desktop-update.sh
#
# A Linux display (or xvfb) and AppImage/FUSE or extract-and-run support are
# required, because the script builds the desktop shell twice.
#
# Sourcing this file defines its helpers and runs nothing, so the half that keeps
# failing can be exercised without a 40-minute build:
#
#   bash scripts/tests/desktop_update_wait_e2e.sh
#
# Why the wait is a poll. The job failed three times (runs 41295510624,
# 41309720053, 41328443477) on one line — `The updated app never checked the feed` —
# while the install half stayed green, and the artifact said the same thing each
# time: `server.log` 0 bytes, `app-2.log` holding only an AT-SPI warning, and the
# served bundle byte-identical to what the feed publishes. That is not a broken app;
# it is a fixed 15-second sleep judging a process that needed longer. The second
# launch pays the updater's own 4-second initial delay
# (apps/studio/src/updater/service.ts:31) plus the extraction of an 83 MB bundle
# before anything is sent, and run 1 — polled for up to 180 seconds — was observed
# for about 38 seconds before it checked. `wait_for_feed_check` waits for the event
# instead of guessing its deadline.
#
# Why the two logs differ, which has misled whoever reads a failure. Run 1 prints
# `could not locate repository root; Python sidecar was not started` and run 2 does
# not. The launches are not the cause: `find_repo_root` walks up from the *current
# working directory* (apps/studio/src-tauri/src/lib.rs:13), both instances start in
# `$WORK/run`, and neither tree contains `apps/mcp-server`, so the lookup fails
# identically for both. Run 2 had simply not reached that line when it was judged at
# 15 seconds. `launch_studio` now writes the directory, executable and AppImage
# variables it used into `$WORK/launch-first.env` and `$WORK/launch-second.env` and
# the flow diffs them, so the two launches are shown to be the same rather than
# asserted to be, and the difference in the logs is evidence rather than a mystery.
set -euo pipefail

# GitHub runners have no FUSE daemon; extracting the AppImage to a temp dir
# still leaves the on-disk .AppImage as current_exe(), which is what the
# updater renames and replaces, so the assertions below hold either way.
export APPIMAGE_EXTRACT_AND_RUN="${APPIMAGE_EXTRACT_AND_RUN:-1}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STUDIO="$REPO_ROOT/apps/studio"
WORK="${WORK:-/tmp/studio-update-e2e}"
PORT="${PORT:-8787}"
OLD_VERSION="0.1.0"
NEW_VERSION="0.2.0"

APP_PID=""
SERVER_PID=""
PUBKEY=""

cleanup() {
  if [ -n "$APP_PID" ] && kill -0 "$APP_PID" 2>/dev/null; then
    kill "$APP_PID" 2>/dev/null || true
    wait "$APP_PID" 2>/dev/null || true
  fi
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

# What the app process is actually doing at the moment of the judgement. A pid that
# still exists is not enough: an app that has exited stays a child of this shell
# until it is reaped, and `kill -0` answers for a zombie.
app_process_state() {
  if [ -z "$APP_PID" ]; then
    printf 'not launched\n'
    return
  fi
  local state
  state="$(ps -o state= -p "$APP_PID" 2>/dev/null | tr -d ' ')"
  if [ -z "$state" ]; then
    printf 'exited (pid %s is gone)\n' "$APP_PID"
  elif [ "${state#Z}" != "$state" ]; then
    printf 'exited (pid %s is a zombie, waiting to be reaped)\n' "$APP_PID"
  else
    printf 'running (pid %s, state %s)\n' "$APP_PID" "$state"
  fi
}

# The feed the app is pointed at, and the log it writes its requests to. Opened for
# append rather than write: `reset_feed_log` empties that file while this server is
# still holding the descriptor, and a descriptor not in append mode keeps its old
# offset, so the next request is written past a hole of NUL bytes that grep reads as
# a binary file — the access log is the only evidence the wait below has.
start_feed_server() {
  (
    cd "$WORK/feed"
    exec python3 -m http.server "$PORT" --bind 127.0.0.1 >> "$WORK/server.log" 2>&1
  ) &
  SERVER_PID=$!
}

# Empty the access log between the two launches, so "downloaded nothing" is judged on
# the second launch alone and not on the download the first launch legitimately made.
reset_feed_log() {
  : > "$WORK/server.log"
}

# Poll until the app's own request shows up in the feed's log. The event, not a
# guessed duration, decides when the second launch has had its say. The feed is
# probed alongside, so a timeout can tell "the app never asked" from "the feed was
# unreachable" — different bugs with different fixes.
wait_for_feed_check() {
  local log="$1"
  local deadline="${2:-120}"
  local waited=0
  local feed_ready=""
  local state
  local asked_before seen

  # Count what has already been asked for: the request below that proves the server is
  # up is written to the same access log, and reading it as the app's own check would
  # make every run pass at two seconds whatever the app did.
  asked_before="$(grep -c 'GET /latest.json' "$WORK/server.log" 2>/dev/null || true)"
  asked_before="${asked_before:-0}"

  while [ "$waited" -le "$deadline" ]; do
    seen="$(grep -c 'GET /latest.json' "$WORK/server.log" 2>/dev/null || true)"
    if [ "${seen:-0}" -gt "$asked_before" ]; then
      state="$(app_process_state)"
      printf 'the second launch checked the feed after %ss (app process: %s)\n' \
        "$waited" "$state"
      return 0
    fi
    if [ -z "$feed_ready" ] && curl -fsS -o /dev/null "http://127.0.0.1:${PORT}/"; then
      feed_ready="$waited"
    fi
    sleep 2
    waited=$((waited + 2))
  done

  state="$(app_process_state)"
  printf 'FAIL: the updated app never checked the feed — waited %ss, app process: %s\n' \
    "$waited" "$state" >&2
  if [ -n "$feed_ready" ]; then
    printf '  the feed server answered a direct request at %ss, so the app never asked rather than could not\n' \
      "$feed_ready" >&2
  else
    printf '  the feed never answered a direct request either: the server is the suspect\n' >&2
  fi
  printf -- '--- %s ---\n' "$log" >&2
  tail -40 "$log" >&2 || true
  printf -- '--- server.log ---\n' >&2
  cat "$WORK/server.log" >&2 || true
  printf -- '--- ls -l run/ ---\n' >&2
  ls -l "$WORK/run" >&2 || true
  return 1
}

# Both instances are launched the same way, from the same directory, with the same
# environment; only the log they write to differs. The captured file is what the
# header's asymmetry note gets checked against on every run.
launch_studio() {
  local log="$1"
  local label="$2"

  (
    cd "$WORK/run"
    {
      printf 'cwd=%s\n' "$(pwd)"
      printf 'exe=%s\n' "$(pwd)/studio.AppImage"
      printf 'APPIMAGE=%s\n' "${APPIMAGE:-unset}"
      printf 'APPDIR=%s\n' "${APPDIR:-unset}"
      printf 'APPIMAGE_EXTRACT_AND_RUN=%s\n' "${APPIMAGE_EXTRACT_AND_RUN:-unset}"
      printf 'AGENTIC_ODI_REPO_ROOT=%s\n' "${AGENTIC_ODI_REPO_ROOT:-unset}"
    } > "$WORK/launch-$label.env" 2>&1
    exec ./studio.AppImage > "$log" 2>&1
  ) &
  APP_PID=$!
}

# Sourced rather than executed: the helpers above are the whole contract, and the
# build must not start just because a test wanted to look at them.
if [ "${BASH_SOURCE[0]}" != "${0}" ]; then
  return 0
fi

rm -rf "$WORK"
mkdir -p "$WORK/feed" "$WORK/run"

say "Generating a throwaway updater key"
(
  cd "$STUDIO"
  npx tauri signer generate -w "$WORK/updater.key" -p "" -f > /dev/null
)
# `tauri signer generate` writes the public key already base64-encoded, which
# is exactly what `plugins.updater.pubkey` expects.
PUBKEY="$(tr -d '\n' < "$WORK/updater.key.pub")"

build_appimage() {
  local version="$1"
  local config_file="$WORK/config-$version.json"

  python3 - "$version" "$PUBKEY" "$PORT" > "$config_file" <<'PY'
import json
import sys

version, pubkey, port = sys.argv[1:4]
print(json.dumps({
    "version": version,
    "plugins": {
        "updater": {
            "pubkey": pubkey,
            "endpoints": [f"http://127.0.0.1:{port}/latest.json"],
            "dangerousInsecureTransportProtocol": True,
        }
    },
}))
PY

  if [ ! -s "$config_file" ]; then
    echo "The Tauri config override for $version was not written." >&2
    exit 1
  fi

  rm -f "$STUDIO"/src-tauri/target/release/bundle/appimage/*_"$version"_amd64.AppImage*

  say "Building signed AppImage $version"
  (
    cd "$STUDIO"
    TAURI_SIGNING_PRIVATE_KEY="$WORK/updater.key" \
      TAURI_SIGNING_PRIVATE_KEY_PASSWORD="" \
      npx tauri build --config "$config_file" --bundles appimage
  )

  local built
  built="$(ls "$STUDIO"/src-tauri/target/release/bundle/appimage/*_"$version"_amd64.AppImage)"
  if [ ! -f "$built.sig" ]; then
    echo "No updater signature was produced for $version." >&2
    exit 1
  fi
  local target="$WORK/feed/studio-$version.AppImage"
  cp "$built" "$target"
  cp "$built.sig" "$target.sig"
  sha256sum "$target" | awk '{print $1}' > "$WORK/feed/studio-$version.sha256"
}

build_appimage "$OLD_VERSION"
build_appimage "$NEW_VERSION"

say "Publishing a local update feed"
python3 - "$WORK" "$PORT" "$NEW_VERSION" "$OLD_VERSION" <<'PY'
import json
import pathlib
import sys

work, port, version, _old = sys.argv[1:5]
feed = pathlib.Path(work) / "feed"
signature = (feed / f"studio-{version}.AppImage.sig").read_text().strip()
(feed / "latest.json").write_text(json.dumps({
    "version": version,
    "notes": "Verifies the in-app updater end to end.",
    "pub_date": "2026-10-21T00:00:00Z",
    "platforms": {
        "linux-x86_64": {
            "signature": signature,
            "url": f"http://127.0.0.1:{port}/studio-{version}.AppImage",
        }
    },
}, indent=2))
PY

start_feed_server
sleep 1

cp "$WORK/feed/studio-$OLD_VERSION.AppImage" "$WORK/run/studio.AppImage"
chmod +x "$WORK/run/studio.AppImage"

say "Running $OLD_VERSION; it should update itself in the background"
launch_studio "$WORK/app.log" first

NEW_SHA="$(cat "$WORK/feed/studio-$NEW_VERSION.sha256")"
APPLIED=0
for _ in $(seq 1 90); do
  CURRENT_SHA="$(sha256sum "$WORK/run/studio.AppImage" | awk '{print $1}')"
  if [ "$CURRENT_SHA" = "$NEW_SHA" ]; then
    APPLIED=1
    break
  fi
  sleep 2
done

if [ "$APPLIED" -ne 1 ]; then
  echo "The app did not install $NEW_VERSION over itself." >&2
  echo "  app process: $(app_process_state)" >&2
  echo "--- app log ---" >&2
  tail -40 "$WORK/app.log" >&2 || true
  echo "--- update server log ---" >&2
  cat "$WORK/server.log" >&2 || true
  exit 1
fi
echo "OK: the running $OLD_VERSION replaced its own AppImage with $NEW_VERSION"

kill "$APP_PID" 2>/dev/null || true
wait "$APP_PID" 2>/dev/null || true
APP_PID=""

say "Running the updated app; it should see $NEW_VERSION and download nothing"
reset_feed_log
launch_studio "$WORK/app-2.log" second

# Checking and downloading are asserted separately, so a red job names which of the
# two promises the app broke instead of leaving it to be inferred from a log.
wait_for_feed_check "$WORK/app-2.log" 120 || exit 1
if grep -q "GET /studio-$NEW_VERSION.AppImage" "$WORK/server.log"; then
  echo "The updated app tried to download the release it is already running." >&2
  echo "  app process: $(app_process_state)" >&2
  cat "$WORK/server.log" >&2
  exit 1
fi
echo "OK: the updated app reports no update and downloads nothing"

say "Comparing the two launches"
if ! diff -u "$WORK/launch-first.env" "$WORK/launch-second.env"; then
  echo "The two instances launched differently; the header says what that has meant." >&2
fi

say "Updater verified end to end"
