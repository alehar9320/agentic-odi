#!/usr/bin/env bash
#
# score.sh — Native GitHub Action PR risk classifier.
#
# Evaluates a pull request diff across three factors and applies a single,
# mutually exclusive risk label. Runs entirely on ubuntu-latest with git + gh
# (both preinstalled on GitHub-hosted runners). Zero external SaaS, zero API
# keys, zero PR comments.
#
# Factors (0-100 score):
#   1. File & line churn        -> 0-30 points
#   2. Critical path override   -> forces danger zone (>= 51)
#   3. Test delta               -> +20 if source changed without test files
#
# Tiers:
#   <= 20  -> safe to merge     (🟢)
#   21-50  -> needs a look      (🟡)
#   >= 51  -> danger zone       (🔴)
#
# Env required: GITHUB_TOKEN, BASE_SHA, HEAD_SHA, PR_NUMBER, REPO

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
readonly RISK_LABELS=("safe to merge" "needs a look" "danger zone")
readonly CRITICAL_PREFIXES=("auth/" "migrations/" "billing/" "infra/" ".github/workflows/")
readonly PROTECTED_FILES_FILE=".ci/protected-files.txt"

# Score thresholds
readonly CHURN_FILES_MAX=10      # points
readonly CHURN_LINES_MAX=20      # points
readonly CHURN_LINES_CAP=400     # lines at which line-points saturate
readonly TEST_DELTA_POINTS=20
readonly DANGER_FLOOR=51

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Returns 0 (true) if $1 is a test file: *.test.*, *.spec.*, or under tests/
is_test_file() {
  local f="$1"
  [[ "${f}" == *.test.* || "${f}" == *.spec.* ]] && return 0
  [[ "${f}" == tests/* || "${f}" == */tests/* ]] && return 0
  return 1
}

# Returns 0 (true) if $1 is source code worth test coverage (excludes docs,
# configs, static assets, lockfiles, etc.). Test delta only fires on these.
is_source_file() {
  local f="$1"
  local ext="${f##*.}"
  case "${ext}" in
    py|ts|tsx|js|jsx|go|rs|rb|java|c|cpp|h|hpp|cs|php|swift|kt|scala|r|m|mm|sh|bash|zsh|tf|vue|dart|lua|ex|exs|erl|hs|ml|clj|cljs|sql|graphql|proto) return 0 ;;
  esac
  local base="${f##*/}"
  case "${base}" in
    Dockerfile|dockerfile|Makefile|makefile|Gemfile|Rakefile|Vagrantfile|BUILD|BUILD.bazel|WORKSPACE|configure|Configure) return 0 ;;
  esac
  return 1
}

# ---------------------------------------------------------------------------
# Gather diff between base and head
# ---------------------------------------------------------------------------

# All changed files (Added / Copied / Modified / Deleted)
CHANGED_FILES="$(git diff --name-only --diff-filter=ACMD "${BASE_SHA}" "${HEAD_SHA}" || true)"

# Shortstat for churn counts
STAT="$(git diff --shortstat "${BASE_SHA}" "${HEAD_SHA}" || true)"

FILES_CHANGED_COUNT=0
LINES_ADDED=0
LINES_DELETED=0
if [[ -n "${STAT}" ]]; then
  FILES_CHANGED_COUNT="$(printf '%s' "${STAT}" | grep -oE '[0-9]+ file' | grep -oE '[0-9]+' || echo 0)"
  LINES_ADDED="$(printf '%s' "${STAT}" | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+' || echo 0)"
  LINES_DELETED="$(printf '%s' "${STAT}" | grep -oE '[0-9]+ deletion' | grep -oE '[0-9]+' || echo 0)"
fi
[[ -z "${FILES_CHANGED_COUNT}" ]] && FILES_CHANGED_COUNT=0
[[ -z "${LINES_ADDED}" ]] && LINES_ADDED=0
[[ -z "${LINES_DELETED}" ]] && LINES_DELETED=0
readonly TOTAL_LINES=$((LINES_ADDED + LINES_DELETED))

# ---------------------------------------------------------------------------
# Factor 1: File & line churn (0-30)
# ---------------------------------------------------------------------------
score=0

# Files changed: 1 point per file, capped at CHURN_FILES_MAX
if [[ "${FILES_CHANGED_COUNT}" -ge "${CHURN_FILES_MAX}" ]]; then
  churn_files="${CHURN_FILES_MAX}"
else
  churn_files="${FILES_CHANGED_COUNT}"
fi
score=$((score + churn_files))

# Lines changed: linear up to CHURN_LINES_MAX at CHURN_LINES_CAP lines
if [[ "${TOTAL_LINES}" -ge "${CHURN_LINES_CAP}" ]]; then
  churn_lines="${CHURN_LINES_MAX}"
else
  churn_lines=$((TOTAL_LINES * CHURN_LINES_MAX / CHURN_LINES_CAP))
  [[ "${churn_lines}" -gt "${CHURN_LINES_MAX}" ]] && churn_lines="${CHURN_LINES_MAX}"
fi
score=$((score + churn_lines))

# ---------------------------------------------------------------------------
# Factor 2: Critical path override (blast radius)
# ---------------------------------------------------------------------------
critical_touch=0

while IFS= read -r f; do
  [[ -z "${f}" ]] && continue
  for prefix in "${CRITICAL_PREFIXES[@]}"; do
    if [[ "${f}" == "${prefix}"* ]]; then
      critical_touch=1
      break 2
    fi
  done
done <<< "${CHANGED_FILES}"

# Deletions of protected CI/site files also count as critical.
if [[ -f "${PROTECTED_FILES_FILE}" && -n "${CHANGED_FILES}" ]]; then
  while IFS= read -r f; do
    [[ -z "${f}" ]] && continue
    # Only consider deletions: a file in the diff that no longer exists at HEAD
    if ! git cat-file -e "${HEAD_SHA}:${f}" 2>/dev/null; then
      while IFS= read -r p; do
        [[ -z "${p}" || "${p}" == \#* ]] && continue
        if [[ "${f}" == "${p}" ]]; then
          critical_touch=1
          break 2
        fi
      done < "${PROTECTED_FILES_FILE}"
    fi
  done <<< "${CHANGED_FILES}"
fi

# ---------------------------------------------------------------------------
# Factor 3: Test delta (+20 if source changed without test files)
# ---------------------------------------------------------------------------
source_changed=0
test_changed=0

while IFS= read -r f; do
  [[ -z "${f}" ]] && continue
  if is_test_file "${f}"; then
    test_changed=1
  elif is_source_file "${f}"; then
    source_changed=1
  fi
done <<< "${CHANGED_FILES}"

if [[ "${source_changed}" -eq 1 && "${test_changed}" -eq 0 ]]; then
  score=$((score + TEST_DELTA_POINTS))
fi

# Apply critical-path floor
if [[ "${critical_touch}" -eq 1 && "${score}" -lt "${DANGER_FLOOR}" ]]; then
  score="${DANGER_FLOOR}"
fi

# ---------------------------------------------------------------------------
# Determine tier (mutually exclusive)
# ---------------------------------------------------------------------------
if [[ "${score}" -le 20 ]]; then
  tier="safe to merge"
elif [[ "${score}" -le 50 ]]; then
  tier="needs a look"
else
  tier="danger zone"
fi

# ---------------------------------------------------------------------------
# Label hygiene: remove all stale risk labels, then apply the current tier.
# No PR comments are posted (silent execution).
# ---------------------------------------------------------------------------
for label in "${RISK_LABELS[@]}"; do
  gh pr edit "${PR_NUMBER}" --repo "${REPO}" --remove-label "${label}" >/dev/null 2>&1 || true
done
gh pr edit "${PR_NUMBER}" --repo "${REPO}" --add-label "${tier}" >/dev/null 2>&1 || true

echo "PR risk score: ${score}/100 -> ${tier}"
