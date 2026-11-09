#!/usr/bin/env bash
#
# Prove the second-launch wait of scripts/verify-desktop-update.sh without
# building an AppImage.
#
# The full script takes ~40 minutes because it builds the desktop shell twice, and
# the half that has failed three times is not the build: it is the wait after the
# second launch (the `updater-e2e` job, artifact `updater-e2e-log` — `server.log`
# 0 bytes, `app-2.log` holding only an AT-SPI warning, the install half green).
# A fixed 15-second sleep was judged against an app that needed longer, so this
# exercises exactly that wait against a real HTTP feed and a fake app that checks
# it 18 seconds after launch — longer than the sleep it replaces, short enough to
# keep the job cheap.
#
# Usage: bash scripts/tests/desktop_update_wait_e2e.sh   (PORT=8742 by default)
#
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERIFY="$REPO_ROOT/scripts/verify-desktop-update.sh"
PORT="${PORT:-8742}"
export PORT
# Set before the source: the script keeps a WORK that is already provided, and the
# helpers below launch from it.
WORK="$(mktemp -d)"
export WORK
SERVER_PID=""
APP_PID=""

cleanup() {
  [[ -n "${APP_PID:-}" ]] && kill "$APP_PID" 2>/dev/null
  [[ -n "${SERVER_PID:-}" ]] && kill "$SERVER_PID" 2>/dev/null
  [[ -n "${WORK:-}" ]] && rm -rf "$WORK"
}
trap cleanup EXIT

# `die`/`ok` rather than `fail`/`pass`, and defined after the source, so nothing the
# script itself defines can replace the test's own reporting.

# --- the script must be a library before its wait can be tested -------------
# Sourcing a script that executes its own flow would start a real Tauri build, so the
# flow has to sit behind a source guard. This checks what sourcing does to a scratch
# WORK directory rather than the spelling of the guard: the first thing the flow does
# is `rm -rf "$WORK"`, and any guard that stops it reaching that line is enough.
PROBE="$WORK/sourced-probe"
mkdir -p "$PROBE" && touch "$PROBE/keep"
timeout 20 bash -c 'source "$1" >/dev/null 2>&1' _ "$VERIFY" || true
if [ ! -e "$PROBE/keep" ]; then
  echo "FAIL: $VERIFY runs its build when sourced; its flow must sit behind a source guard" >&2
  exit 1
fi

# shellcheck source=/dev/null
source "$VERIFY"
set +e

# The sourced script installs its own EXIT trap; the test's teardown has to come back
# on top of it, or the temporary directory outlives the run.
teardown() {
  [[ -n "${APP_PID:-}" ]] && kill "$APP_PID" 2>/dev/null
  [[ -n "${SERVER_PID:-}" ]] && kill "$SERVER_PID" 2>/dev/null
  [[ -n "${WORK:-}" ]] && rm -rf "$WORK"
}
trap teardown EXIT

die() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "PASS: $*"; }

declare -F launch_studio >/dev/null || die "verify-desktop-update.sh does not define launch_studio"
declare -F wait_for_feed_check >/dev/null \
  || die "verify-desktop-update.sh does not define wait_for_feed_check"
declare -F start_feed_server >/dev/null \
  || die "verify-desktop-update.sh does not define start_feed_server"
declare -F reset_feed_log >/dev/null \
  || die "verify-desktop-update.sh does not define reset_feed_log"
ok "the script can be sourced and exposes its launch, feed and wait helpers"

mkdir -p "$WORK/feed" "$WORK/run"
printf '{ "version": "0.2.0" }\n' > "$WORK/feed/latest.json"
start_feed_server
for _ in $(seq 1 40); do
  curl -sf -o /dev/null "http://127.0.0.1:${PORT}/latest.json" && break
  sleep 0.25
done
curl -sf -o /dev/null "http://127.0.0.1:${PORT}/latest.json" \
  || die "the local feed server did not come up on port $PORT"
# The readiness probes above are requests this test made, not the app. The wait reads
# the feed's access log, so it starts empty or the first poll reports a check that was
# never launched — which is exactly how this test first passed for the wrong reason.
reset_feed_log

# --- the reset must leave a log the wait can read as text --------------------
# Emptying the log is how the flow tells "downloaded nothing on the second launch"
# from the download it made on the first. A server that holds the file open without
# append mode resumes writing at its old offset, so the gap reads as NUL bytes and
# grep calls the access log a binary file — the wait would then count a check it
# cannot see. This runs before the scenarios: it is the floor they stand on.
curl -sf -o /dev/null "http://127.0.0.1:${PORT}/latest.json" || die "the feed stopped answering after the reset"
raw_bytes="$(wc -c < "$WORK/server.log")"
plain_bytes="$(LC_ALL=C tr -d '\0' < "$WORK/server.log" | wc -c)"
[ "$raw_bytes" -eq "$plain_bytes" ] \
  || die "resetting the feed log left $((raw_bytes - plain_bytes)) NUL bytes for grep to read as binary"
grep_errors="$(grep -c 'GET /latest.json' "$WORK/server.log" 2>&1 >/dev/null)"
[ -z "$grep_errors" ] || die "the feed log is not greppable as text: $grep_errors"
ok "the reset feed log is plain text and holds the request after it"

# The stand-in for the updated AppImage: it starts, prints the warning the real one
# prints from its GTK layer, waits out the updater's initial delay, then checks.
cat > "$WORK/run/studio.AppImage" <<'EOF'
#!/usr/bin/env bash
echo "AT-SPI: Warning: Atspi" 1>&2
sleep 18
curl -fsS "http://127.0.0.1:${PORT}/latest.json" >/dev/null 2>&1 || true
wait
EOF
chmod +x "$WORK/run/studio.AppImage"

# --- scenario 1: the check lands late, and the wait notices -----------------
launch_studio "$WORK/app-2.log" second
[[ -n "${APP_PID:-}" ]] || die "launch_studio did not record a process id"

out="$(wait_for_feed_check "$WORK/app-2.log" 90 2>&1)"
status=$?
echo "$out"

if [[ $status -ne 0 ]]; then
  die "a feed check that lands after the old fixed sleep still fails the wait"
fi
echo "$out" | grep -q 'the second launch checked the feed after [0-9]*s' \
  || die "the wait never printed how long the second launch took to check"
elapsed="$(echo "$out" | sed -n 's/.*checked the feed after \([0-9]*\)s.*/\1/p' | head -1)"
[[ "$elapsed" -ge 16 ]] || die "reported ${elapsed}s for an 18-second check — the poll is not measuring the app"
ok "a check at ${elapsed}s is detected instead of judged at a fixed 15s"

kill "$APP_PID" 2>/dev/null || true
wait "$APP_PID" 2>/dev/null || true
APP_PID=""

# --- scenario 2: nothing checks, and the failure explains itself ------------
# The old branch printed one empty log and an exit code. A failure has to say
# whether the app was even alive, how long it waited, and show both logs.
reset_feed_log
cat > "$WORK/run/studio.AppImage" <<'EOF'
#!/usr/bin/env bash
echo "sidecar died on launch" 1>&2
exit 3
EOF
chmod +x "$WORK/run/studio.AppImage"

launch_studio "$WORK/app-3.log" third
sleep 2
out="$(wait_for_feed_check "$WORK/app-3.log" 4 2>&1)"
status=$?

[[ $status -ne 0 ]] || die "a launch that never checks the feed passed the wait"
echo "$out" | grep -qiE 'exited|not running|dead|stopped' \
  || die "the failure never reported the process state: $out"
grep -q 'sidecar died on launch' "$WORK/app-3.log" \
  || die "the second launch's log was never written: $out"
echo "$out" | grep -q 'app-3.log' || die "the failure did not print the second launch's log: $out"
echo "$out" | grep -q 'server.log' || die "the failure did not print the feed log: $out"
echo "$out" | grep -q 'ls -l run/' || die "the failure did not list the run directory: $out"
echo "$out" | grep -qE 'waited [0-9]+s' || die "the failure did not state the elapsed wait: $out"
ok "a launch that never checks the feed reports process state, elapsed wait and both logs"

printf '\n\033[1m==> %s\033[0m\n' "Second-launch wait verified"
