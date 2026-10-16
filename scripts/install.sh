#!/usr/bin/env bash
set -euo pipefail

# Default install locations (user-local)
INSTALL_ROOT="${AGENTIC_ODI_INSTALL_DIR:-${XDG_DATA_HOME:-${HOME}/.local/share}/agentic-odi}"
BIN_DIR="${AGENTIC_ODI_BIN_DIR:-${XDG_BIN_HOME:-${HOME}/.local/bin}}"

# Base URL overrides (for local testing)
BASE_URL_DEFAULT="https://github.com/alehar9320/agentic-odi/releases"
API_BASE_DEFAULT="https://api.github.com/repos/alehar9320/agentic-odi"

detect_os() {
  case "$(uname -s)" in
    Linux*)  echo "linux" ;;
    Darwin*) echo "macos" ;;
    *)       echo "linux" ;;
  esac
}

detect_arch() {
  local m
  m="$(uname -m)"
  case "$m" in
    x86_64|amd64|AMD64) echo "x86_64" ;;
    aarch64|arm64)      echo "arm64" ;;
    *)                  echo "$m" ;;
  esac
}

resolve_version() {
  if [[ -n "${AGENTIC_ODI_VERSION:-}" ]]; then
    echo "${AGENTIC_ODI_VERSION}"
    return
  fi
  local api_base
  api_base="${AGENTIC_ODI_BASE_URL:-${API_BASE_DEFAULT}}"
  if [[ "${api_base}" == http*://* ]] && [[ "${api_base}" != *api.github.com* ]]; then
    # Local test base; try to read version from a file if present? fallback to 0.1.0
    echo "0.1.0"
    return
  fi
  curl -fsSL "${API_BASE_DEFAULT}/releases/latest" | grep -o '"tag_name"[[:space:]]*:[[:space:]]*"[^"]*"' | sed -E 's/.*"([^"]+)"/\1/' | sed 's/^v//'
}

sha256_verify() {
  local file="$1"
  local checksums="$2"
  if command -v sha256sum >/dev/null 2>&1; then
    (cd "$(dirname "$checksums")" && sha256sum -c "$(basename "$checksums")" --quiet 2>/dev/null) || true
    if ! sha256sum -c "$checksums" --quiet 2>/dev/null; then
      echo "Checksum verification failed for $file" >&2
      exit 1
    fi
    return
  fi
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 -c "$checksums" >/dev/null 2>&1 || {
      echo "Checksum verification failed for $file" >&2
      exit 1
    }
    return
  fi
  echo "Warning: no sha256 tool found; skipping verification" >&2
}

main() {
  local os arch version target archive_name checksums_name base
  os="$(detect_os)"
  arch="$(detect_arch)"
  version="$(resolve_version)"
  target="${os}_${arch}"

  archive_name="odi_${version}_${target}.tar.gz"
  checksums_name="checksums.txt"

  base="${AGENTIC_ODI_BASE_URL:-${BASE_URL_DEFAULT}}"
  if [[ "${base}" == *api.github.com* ]]; then
    base="${BASE_URL_DEFAULT}"
  fi
  local dl_base
  dl_base="${base}/download/v${version}"

  mkdir -p "$INSTALL_ROOT/versions" "$BIN_DIR"

  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "${tmpdir}"' EXIT

  curl -fsSL "${dl_base}/${archive_name}" -o "${tmpdir}/${archive_name}"
  curl -fsSL "${dl_base}/${checksums_name}" -o "${tmpdir}/${checksums_name}"

  sha256_verify "${tmpdir}/${archive_name}" "${tmpdir}/${checksums_name}"

  local ver_dir tmp_ver
  ver_dir="${INSTALL_ROOT}/versions/${version}"
  tmp_ver="${INSTALL_ROOT}/versions/.${version}.tmp.$$"
  rm -rf "$tmp_ver"
  mkdir -p "$tmp_ver"

  tar -xzf "${tmpdir}/${archive_name}" -C "$tmp_ver"
  rm -rf "$ver_dir"
  mv "$tmp_ver" "$ver_dir"

  local current_tmp
  current_tmp="${INSTALL_ROOT}/current.tmp.$$"
  ln -sfn "$ver_dir" "$current_tmp"
  mv -T "$current_tmp" "${INSTALL_ROOT}/current"

  # Symlink commands
  for cmd in odi odipm odi-cli agentic-odi; do
    ln -sfn "${INSTALL_ROOT}/current/odi" "${BIN_DIR}/${cmd}"
  done

  if [[ ! ":$PATH:" == *":${BIN_DIR}:"* ]]; then
    echo "Add ${BIN_DIR} to your PATH (export PATH=\"${BIN_DIR}:\$PATH\")"
  fi

  echo "Installed odi ${version} to ${ver_dir}"
}

main "$@"
