Closes #81

**Scope note, updated after folding `main` in.** Most of this branch's original shape — the
durable conversation/message/observation entities, the `remember` tool and `memory` frame, the
`/api/conversations` and `/api/observations` surface, the MCP read tools and the SPA restore —
is already on `main` from the pull requests that landed while this branch was open. What this
branch still carries, and what a reviewer should read here, is the **settings and
provider-key slice**: the key leaves `localStorage` and becomes a `0600` file the sidecar owns,
and the browser only ever sees a mask.

## What this PR still changes

- **`studio/secrets.py`** — a small sidecar-owned secret store: `0600`, atomically written,
  single-writer under a lock, and the key is never returned to the browser in clear.
- **`studio/router.py` + `schemas.py`** — `/api/settings` reports `has_api_key` and a mask such
  as `sk-…4f2a`; the key itself is written, never echoed back.
- **`SettingsContext`** — the SPA caches non-secret settings and keeps a tab copy of the key in
  `sessionStorage` only; an empty tab key means "use the stored one".
- **`ModelKeyField` / `ModelSection`** — the field that sets the key, with per-field save and
  its own failure surface.
- **`storageFacts`** — the BFF's honest answer about what is stored where, so the diagnostics
  modal names the real location instead of guessing.
- **Docs and a11y** — `docs/architecture/trust-boundaries.md` and the settings accessibility
  spec.

## Verification, run on this head

```bash
uv run python scripts/verify.py --changed      # PASSED (1 xfailed)
npm run build                                  # apps/studio, exit 0
npx vitest run                                 # apps/studio, passes; one pre-existing
                                               # wizard timing test flakes under full-suite
                                               # load and passes 21/21 on its own
uv run --directory website pytest tests/ -q    # 304 passed
uv run python scripts/pr_guards.py diff-shape --base-ref origin/main   # OK
uv run python scripts/pr_guards.py fabrication --base-ref origin/main  # 0 warnings
```

## Diff summary

```json
{"changed_files": 19, "tests_added": 28, "net_lines": 800, "simulated": [], "breaking": []}
```

## Reuses

- Reuses: `apps/studio-api/src/agentic_odi_studio_api/studio/memory.py` — `studio/secrets.py`
  is the same shape of small, `0600`, atomically written local file the sidecar already owns,
  so it copies that read/write pattern instead of inventing a second one.
- Reuses: the existing `~/.agentic-odi/` location and the `AGENTIC_ODI_STUDIO_DB`-style env
  override the store already documents, rather than a new config directory.
- Reuses: `STAT`/`os` primitives and `threading.RLock`, as `StudioMemory` already does, for
  permissions and single-writer access.

## Open question for review

CodeQL's `py/clear-text-storage-sensitive-data` flags the provider key landing in the
sidecar's own `0600` settings file. That is the issue's requirement — the key must leave
`localStorage` — so it is a product decision (sidecar-owned file, or move the secret to an OS
keychain) rather than something to paper over in this PR.
