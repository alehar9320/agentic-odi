# 0008 — Dependency advisories are a gate, not a report

- **Status:** accepted
- **Date:** 2026-11-16

## Context

The `security` job ran Bandit only. Bandit reads first-party Python for unsafe
code patterns; it has no advisory database and cannot say that a pinned version
is vulnerable. `.github/dependabot.yml` watched two ecosystems (`github-actions`
and `pip`), so the Studio's 50 npm packages and the Tauri shell's Cargo tree were
updated by nobody. The release pipeline builds and signs binaries from those
dependencies, so a compromised transitive package reaches a signed artifact a
user installs with a one-line script (#1090).

Running the three audits against `main` found live advisories rather than a clean
bill: `pip-audit` on the runtime export reported `dnspython 2.9.0`
(GHSA-vvf4-9x63-8xvv) and `opentelemetry-api 1.45.1` (GHSA-mf5v-w3w3-f6cg), and
`npm audit --omit=dev` reported `pdfjs-dist` (GHSA-hq66-cqwq-w95j), whose only fix
is a breaking major. A job that blocks immediately would have been red on the day
it landed.

## Decision

1. **Four ecosystems are watched, not two.** `.github/dependabot.yml` adds `npm`
   at `/apps/studio` and `cargo` at `/apps/studio/src-tauri`, both weekly with a
   five-PR limit and a grouped minor+patch update so the queue stays bounded.
2. **A `dependencies` CI job fails on a high-severity advisory.** It audits the
   Python runtime export (`uv export --no-dev`), the Studio's runtime npm
   dependencies, and the Tauri `Cargo.lock`, and it joins `ci-green`'s `needs`
   and enforced-results list. Dev-only advisories are left to Dependabot: a
   linter's transitive advisory is not a reason to fail a build.
3. **Accepting an advisory is a dated entry, not a flag.**
   `security/audit-ignore.toml` records one entry per accepted advisory with the
   package, the reason, and an `expires` date no more than 90 days out.
   `scripts/audit_ignore.py` validates the ledger, turns each id into the ignore
   argument `pip-audit` and `cargo audit` understand, and filters `npm audit
   --json` itself because npm has no per-advisory ignore. An expired entry fails
   the job. The three advisories found on `main` are the initial entries.
4. **The severity threshold is `high` for runtime dependencies.** `moderate` and
   below are reported by the tools but do not fail the build.

## Consequences

- Easier: a vulnerable pinned version fails a pull request before it reaches a
  signed release, and the four ecosystems Dependabot now watches keep the pinned
  versions moving without a human reading a lockfile diff.
- Harder: a dependency bump can now turn CI red for a reason unrelated to the
  change. That is the point — it is the moment the advisory is cheap to fix — and
  the ignore ledger is the escape hatch, with a date attached.
- Maintained: the ledger needs a review every quarter. An entry that reaches its
  expiry fails the build, which is the reminder; nothing else will surface it.
- Maintained: the audit tools are pinned (`pip-audit==2.7.3`,
  `cargo-audit 0.22.2`), so a tool change is a deliberate edit rather than a
  silent behavior change in CI. `cargo-audit` needs 0.22.0 or newer: earlier
  releases cannot parse the CVSS 4.0 vectors the RustSec database began
  carrying, and fail before auditing anything.

## Alternatives considered

- **Make the job blocking immediately.** Rejected: three live advisories would
  have made every pull request red on landing, and the first fix would have been
  to delete the job. The ledger makes the existing risk explicit and expiring
  instead.
- **`cargo audit` without a pinned version.** Rejected: `cargo install
  cargo-audit` resolves latest, so CI's behavior would change without a commit.
  Pinning keeps the gate reproducible.
- **Rely on Dependabot alone.** Rejected: Dependabot opens an update PR; it does
  not fail a pull request that adds a vulnerable dependency, and it cannot know
  which advisories were accepted. The two are complements — Dependabot moves the
  version, the job enforces the threshold.
- **Audit the full export including dev dependencies.** Rejected: the test,
  lint, and build toolchains carry their own advisories that never ship, and
  gating on them would fail the build for a package no user installs.
