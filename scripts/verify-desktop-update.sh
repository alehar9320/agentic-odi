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
# (schedule + workflow_dispatch only, outside the `ci-green` gate) executes it
# headless under xvfb with APPIMAGE_EXTRACT_AND_RUN=1. It needs no repository
# secret — the key is generated per run below and the committed updater public
# key is untouched. It also stays runnable from a workstation:
#
#   bash scripts/verify-desktop-update.sh
#
# A Linux display (or xvfb) and AppImage/FUSE or extract-and-run support are
# required, because the script builds the desktop shell twice.
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

python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$WORK/feed" \
  > "$WORK/server.log" 2>&1 &
SERVER_PID=$!
sleep 1

cp "$WORK/feed/studio-$OLD_VERSION.AppImage" "$WORK/run/studio.AppImage"
chmod +x "$WORK/run/studio.AppImage"

say "Running $OLD_VERSION; it should update itself in the background"
(
  cd "$WORK/run"
  ./studio.AppImage > "$WORK/app.log" 2>&1
) &
APP_PID=$!

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
: > "$WORK/server.log"
(
  cd "$WORK/run"
  ./studio.AppImage > "$WORK/app-2.log" 2>&1
) &
APP_PID=$!
sleep 15

if ! grep -q "GET /latest.json" "$WORK/server.log"; then
  echo "The updated app never checked the feed." >&2
  cat "$WORK/server.log" >&2
  exit 1
fi
if grep -q "GET /studio-$NEW_VERSION.AppImage" "$WORK/server.log"; then
  echo "The updated app tried to download the release it is already running." >&2
  cat "$WORK/server.log" >&2
  exit 1
fi
echo "OK: the updated app reports no update and downloads nothing"

say "Updater verified end to end"
