#!/usr/bin/env bash
# Ask the deployed Worker the questions this repository answers in its README.
#
# Every hosted fix so far has been proven on a Cloudflare preview URL that no
# visitor will ever open, and a merged PR is not proof that the change reached
# the branch that deploys. This probe goes to the production host, waits for a
# deploy to actually answer, and then reports one dated line per promise:
#
#   PASS 2026-11-04T21:00:00Z local data is advertised — available: true
#   FAIL 2026-11-04T21:00:00Z a job write falls back in a code the browser understands — got mcp_unreachable
#
# A FAIL prints the offending response body, because `mcp_unreachable` is not a
# status code problem: it is the body that stops the browser serving the
# capabilities it advertised a second earlier (issue #491).
#
# Only the production host is a pass. `--base-url` exists so the checks can be
# exercised against a stub (see tests/scripts/test_verify_hosted_first_run.py),
# and any target other than production prints a banner saying the run proves
# nothing about the hosted first impression.
set -euo pipefail

PRODUCTION_URL="https://agentic-odi.alehar.workers.dev"

base_url="$PRODUCTION_URL"
expected_commit=""
wait_seconds=180
interval_seconds=15
failures=0

body_file="$(mktemp)"
deploy_file="$(mktemp)"
trap 'rm -f "$body_file" "$deploy_file"' EXIT

usage() {
  cat <<'EOF'
usage: verify-hosted-first-run.sh [--base-url URL] [--commit SHA]
                                 [--wait SECONDS] [--interval SECONDS]

  --base-url   probe another host (a run against it is never a hosted pass)
  --commit     the SHA the deploy is expected to be built from
  --wait       how long to wait for a deploy to answer before judging it
  --interval   polling gap in seconds
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url) base_url="${2:?--base-url needs a URL}"; shift 2 ;;
    --commit) expected_commit="${2:?--commit needs a SHA}"; shift 2 ;;
    --wait) wait_seconds="${2:?--wait needs seconds}"; shift 2 ;;
    --interval) interval_seconds="${2:?--interval needs seconds}"; shift 2 ;;
    -h | --help) usage; exit 0 ;;
    *) echo "verify-hosted-first-run: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if ! command -v jq >/dev/null 2>&1; then
  echo "verify-hosted-first-run: jq is required to read the responses" >&2
  exit 2
fi

stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }

pass() { printf '%s PASS %s — %s\n' "$(stamp)" "$1" "$2"; }

skip() { printf '%s SKIP %s — %s\n' "$(stamp)" "$1" "$2"; }

# A failure names the promise, says what arrived, and prints the body it arrived in.
fail() {
  printf '%s FAIL %s — %s\n' "$(stamp)" "$1" "$2"
  if [[ -s "$body_file" ]]; then
    printf '  body: %s\n' "$(head -c 400 "$body_file" | tr -d '\r')"
  fi
  failures=$((failures + 1))
}

# request METHOD PATH sets STATUS and leaves the body in $body_file.
request() {
  local code
  code="$(curl -sS -m 30 -o "$body_file" -w '%{http_code}' -X "$1" "${base_url}$2" 2>/dev/null)" || code="000"
  STATUS="$code"
}

json_field() { jq -r "$1 // empty" "$body_file" 2>/dev/null || true; }

# A failure prints the most recent response, so a promise about the deploy has to put the
# deploy's own answer back first — otherwise it prints whatever the last check fetched.
claim_body() { cp "$deploy_file" "$body_file"; }

if [[ "$base_url" != "$PRODUCTION_URL" ]]; then
  printf '%s NON-PRODUCTION TARGET %s\n' "$(stamp)" "$base_url"
  printf '%s this run is informational only — it is not a hosted pass\n' "$(stamp)"
fi

# A deploy that has not finished landing is not a broken deploy, so poll before
# judging anything. Only `/api/deploy` proves the Worker landed with its assets.
deadline=$((SECONDS + wait_seconds))
attempt=0
while true; do
  attempt=$((attempt + 1))
  request GET /api/deploy
  if [[ "$STATUS" == "200" ]]; then
    break
  fi
  if ((SECONDS >= deadline)); then
    fail "the deploy identifies itself" \
      "GET /api/deploy answered $STATUS after ${wait_seconds}s of polling (${attempt} attempts)"
    break
  fi
  printf '%s waiting for a deploy to answer (GET /api/deploy -> %s, attempt %d)\n' \
    "$(stamp)" "$STATUS" "$attempt"
  sleep "$interval_seconds"
done

deploy_commit="$(json_field '.commit')"
deploy_entry="$(json_field '.entry')"
cp "$body_file" "$deploy_file"

# 1. The capabilities the README promises for a visitor with no sidecar.
for capability in local-data local-memory deterministic-assistant; do
  case "$capability" in
    local-data) promise="local data is advertised" ;;
    local-memory) promise="local memory is advertised" ;;
    *) promise="the deterministic assistant is advertised" ;;
  esac
  request GET /api/capabilities
  if [[ "$STATUS" != "200" ]]; then
    fail "$promise" "GET /api/capabilities answered $STATUS"
    continue
  fi
  available="$(jq -r --arg id "$capability" \
    '.capabilities[]? | select(.id == $id) | .available' "$body_file" 2>/dev/null)" || available=""
  if [[ "$available" == "true" ]]; then
    pass "$promise" "available: true"
  else
    fail "$promise" "answered ${available:-missing}"
  fi
done

# 2. With no sidecar configured the write path must answer in a code a browser can
#    treat as transport. `mcp_unreachable` is the body that breaks the fallback.
for endpoint in "POST /api/jobs:a job write falls back in a code the browser understands" \
  "GET /api/canvas:the canvas falls back in a code the browser understands"; do
  call="${endpoint%%:*}"
  promise="${endpoint#*:}"
  method="${call%% *}"
  path="${call##* }"
  request "$method" "$path"
  code="$(json_field '.error.code')"
  if [[ "$STATUS" == "502" && "$code" == "sidecar_unavailable" ]]; then
    pass "$promise" "502 sidecar_unavailable"
  else
    fail "$promise" "got $STATUS ${code:-no error code}, wanted 502 sidecar_unavailable"
  fi
done

# 3. A real page, and the bundle it names.
request GET /
served_entry="$(grep -Eo 'assets/index-[A-Za-z0-9_-]+\.js' "$body_file" 2>/dev/null | head -1)" || served_entry=""
if [[ "$STATUS" == "200" && -n "$served_entry" ]]; then
  pass "the entry page names its bundle" "$served_entry"
else
  fail "the entry page names its bundle" "GET / answered $STATUS, asset ${served_entry:-none}"
fi

# 4. The bundle the served page names must be the one the deploy claims, so a
#    Worker that moved while the page stayed cached becomes detectable.
if [[ -z "$deploy_entry" ]]; then
  claim_body
  fail "the served bundle belongs to the deploy that claims it" \
    "the deploy reported no entry asset"
elif [[ "${served_entry##*/}" == "${deploy_entry##*/}" ]]; then
  pass "the served bundle belongs to the deploy that claims it" "$deploy_entry"
else
  claim_body
  fail "the served bundle belongs to the deploy that claims it" \
    "the page serves ${served_entry:-none}, the deploy claims $deploy_entry"
fi

# 5. The commit the deploy believes it was built from, beside the commit on main.
if [[ -z "$expected_commit" ]]; then
  skip "the deploy reports this commit" \
    "no --commit given; the deploy reports ${deploy_commit:-unknown}"
elif [[ "$deploy_commit" == "unknown" || -z "$deploy_commit" ]]; then
  claim_body
  fail "the deploy reports this commit" \
    "the deploy reports ${deploy_commit:-unknown}: the deploy command has to pass it, as in \`npx wrangler deploy --var COMMIT_SHA:\$(git rev-parse HEAD)\` (expected $expected_commit)"
elif [[ "$deploy_commit" == "$expected_commit" ]]; then
  pass "the deploy reports this commit" "$deploy_commit"
else
  claim_body
  fail "the deploy reports this commit" \
    "the deploy reports $deploy_commit, this run expects $expected_commit"
fi

if ((failures > 0)); then
  printf '%s %d hosted promise(s) broken at %s\n' "$(stamp)" "$failures" "$base_url"
  exit 1
fi

printf '%s every hosted promise checked holds at %s\n' "$(stamp)" "$base_url"
