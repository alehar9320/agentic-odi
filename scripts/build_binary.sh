#!/usr/bin/env bash
#
# Build a self-contained, onedir PyInstaller bundle of the `odi` CLI and
# package it into a distributable archive at the repository root.
#
# Environment:
#   VERSION            required, e.g. 0.1.0
#   RELEASE_DATE_UTC   optional, e.g. 2026-10-15T21:13:00Z (default: "")
#   COMMIT             optional (default: dev)
#   TARGET             optional, e.g. linux_x86_64 (default: dev)
#
# The absolute path of the produced archive is printed on the last line.
set -euo pipefail

export UV_PYTHON="${UV_PYTHON:-3.11}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VERSION="${VERSION:?VERSION is required}"
RELEASE_DATE_UTC="${RELEASE_DATE_UTC:-}"
COMMIT="${COMMIT:-dev}"
TARGET="${TARGET:-dev}"

echo "==> Syncing workspace (uv)"
uv sync --all-packages --locked

echo "==> Writing cli/src/cli/_build_info.py"
cat > cli/src/cli/_build_info.py <<EOF
VERSION = "${VERSION}"
RELEASE_DATE_UTC = "${RELEASE_DATE_UTC}"
COMMIT = "${COMMIT}"
TARGET = "${TARGET}"
EOF

echo "==> Running PyInstaller"
uv run --directory cli pyinstaller --clean --noconfirm \
    --distpath ../dist --workpath ../build/odi \
    ../packaging/pyinstaller/odi.spec

ARCHIVE_NAME="odi_${VERSION}_${TARGET}"
if [[ "$TARGET" == windows* ]]; then
    rm -f "${ARCHIVE_NAME}.zip"
    (cd dist/odi && zip -r -q "../../${ARCHIVE_NAME}.zip" .)
    ARCHIVE_PATH="${REPO_ROOT}/${ARCHIVE_NAME}.zip"
else
    rm -f "${ARCHIVE_NAME}.tar.gz"
    tar -C dist/odi -czf "${ARCHIVE_NAME}.tar.gz" .
    ARCHIVE_PATH="${REPO_ROOT}/${ARCHIVE_NAME}.tar.gz"
fi

echo "$ARCHIVE_PATH"
