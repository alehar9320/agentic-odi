#!/usr/bin/env bash
#
# Simulate a published GitHub release locally and run scripts/install.sh against
# it, exactly as the release e2e workflow would. Checks:
#   1. install succeeds when checksums.txt lists every platform (only ours exists)
#   2. install fails when our archive is tampered with
#   3. install fails when checksums.txt has no entry for our archive
#
# Usage: bash scripts/tests/install_e2e.sh   (PORT=8731 by default)
#
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTALLER="${INSTALLER:-$REPO_ROOT/scripts/install.sh}"
WORK="$(mktemp -d)"
PORT="${PORT:-8731}"
VERSION="0.3.0"
TARGET="linux_x86_64"
ARCHIVE="odi_${VERSION}_${TARGET}.tar.gz"

cleanup() {
  [[ -n "${SERVER_PID:-}" ]] && kill "$SERVER_PID" 2>/dev/null
  rm -rf "$WORK"
}
trap cleanup EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# --- fake release ------------------------------------------------------------
mkdir -p "$WORK/release/download/v${VERSION}" "$WORK/bundle"
cat > "$WORK/bundle/odi" <<'EOF'
#!/usr/bin/env bash
echo "fake odi 0.3.0"
EOF
chmod +x "$WORK/bundle/odi"
tar -C "$WORK/bundle" -czf "$WORK/release/download/v${VERSION}/${ARCHIVE}" .

(
  cd "$WORK/release/download/v${VERSION}"
  sha256sum "$ARCHIVE" > checksums.txt
  for other in linux_arm64 macos_arm64 macos_x86_64 windows_x86_64; do
    echo "0000000000000000000000000000000000000000000000000000000000000000  odi_${VERSION}_${other}.tar.gz" >> checksums.txt
  done
)
cp "$WORK/release/download/v${VERSION}/checksums.txt" "$WORK/checksums.good"

# --- serve it ----------------------------------------------------------------
( cd "$WORK/release" && exec python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 ) &
SERVER_PID=$!
for _ in $(seq 1 40); do
  curl -sf -o /dev/null "http://127.0.0.1:${PORT}/download/v${VERSION}/checksums.txt" && break
  sleep 0.25
done
curl -sf -o /dev/null "http://127.0.0.1:${PORT}/download/v${VERSION}/checksums.txt" \
  || fail "local release server did not come up"

run_installer() { # $1 = installer path (overridable for regression checks), $2 = home dir
  local installer="${1:-$INSTALLER}" home="$2"
  rm -rf "$home" "${home}-bin"
  env -i PATH="$PATH" HOME="$WORK" \
    AGENTIC_ODI_VERSION="$VERSION" \
    AGENTIC_ODI_BASE_URL="http://127.0.0.1:${PORT}" \
    AGENTIC_ODI_INSTALL_DIR="$home" \
    AGENTIC_ODI_BIN_DIR="${home}-bin" \
    bash "$installer" >"$WORK/installer.log" 2>&1
}

echo "== 1. install with a multi-platform checksums.txt (only our archive present)"
if run_installer "$INSTALLER" "$WORK/home1"; then
  [[ -L "$WORK/home1-bin/odi" ]] || fail "odi was not symlinked into the bin dir"
  out="$("$WORK/home1-bin/odi")"
  [[ "$out" == "fake odi 0.3.0" ]] || fail "installed odi did not run (got: $out)"
  pass "installer succeeded and the binary runs"
else
  cat "$WORK/installer.log" >&2
  fail "installer failed on a well-formed release"
fi

echo "== 2. tampered archive is rejected"
printf 'tampered' >> "$WORK/release/download/v${VERSION}/${ARCHIVE}"
if run_installer "$INSTALLER" "$WORK/home2"; then
  fail "installer accepted a tampered archive"
fi
grep -q "Checksum verification failed" "$WORK/installer.log" || { cat "$WORK/installer.log" >&2; fail "expected checksum failure message"; }
pass "tampered archive rejected"

echo "== 3. missing checksum entry is rejected"
cp "$WORK/checksums.good" "$WORK/release/download/v${VERSION}/checksums.txt"
grep -v "$ARCHIVE\$" "$WORK/checksums.good" > "$WORK/release/download/v${VERSION}/checksums.txt"
if run_installer "$INSTALLER" "$WORK/home3"; then
  fail "installer accepted a checksums.txt without our archive"
fi
grep -q "No checksum entry" "$WORK/installer.log" || { cat "$WORK/installer.log" >&2; fail "expected missing-entry message"; }
pass "missing checksum entry rejected"

echo "ALL CHECKS DONE"
