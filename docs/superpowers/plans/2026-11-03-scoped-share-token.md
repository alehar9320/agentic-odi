# A scoped, expiring, read-only share token — Plan

Issue: #549 (parent #349). Design source: the issue body and its atomic steps.

## Storage shape (decided before coding)

A share is one row in `studio.db`, created by the existing `_migrate`
(`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`), so it survives a
sidecar restart.

| Column | Type | Meaning |
|---|---|---|
| `id` | TEXT PK | `shr_<12 hex>`; the revocable handle. Never a secret. |
| `token_hash` | TEXT UNIQUE | SHA-256 hex of the raw token. The raw token is never stored. |
| `artifact_kind` | TEXT | one of `outcome`, `segment`, `strategy`. |
| `artifact_id` | TEXT | the one record the token names. |
| `created_at` | TEXT | ISO-8601 UTC. |
| `expires_at` | TEXT | ISO-8601 UTC; defaults to 7 days, never more than 30. |
| `revoked_at` | TEXT NULL | ISO-8601 UTC when revoked. |
| `last_read_at` | TEXT NULL | ISO-8601 UTC of the last successful read, for the owner. No reader identity. |

The raw token is `odi_sh_` + `secrets.token_urlsafe(32)` (256 bits from the OS
CSPRNG). It is returned exactly once, in the mint response. Only its SHA-256 hash
is persisted, and the read compares hashes with `hmac.compare_digest`.

## Threat model (one paragraph)

The sidecar is loopback and unauthenticated (#90 owns the front door). The token
is therefore a bearer capability: whoever holds it reads exactly the one artifact
it names and that artifact's own evidence, and nothing else. The read resolves
only the named record from the local ODI store; memory, conversations,
connectors, and the rest of the canvas are structurally unreachable. Every
failure — unknown, expired, revoked, malformed — answers the same 404 body, so a
probe learns nothing. There is no passphrase, no account, and no session.

## Steps

1. `studio/memory.py`: `shares` table + `Share` dataclass + CRUD
   (`create_share`, `get_share`, `get_share_by_token_hash`, `list_shares`,
   `revoke_share`, `record_share_read`).
2. `studio/sharing.py` (new): `ShareService` (mint/read/revoke), token minting
   and hashing, TTL bounds, scoped payload builder (artifact + own evidence,
   `Evidence.raw` stripped), URL builder.
3. `studio/schemas.py`: `MintShareRequest`, `ShareMintResponse`,
   `SharedArtifactResponse`.
4. `studio/router.py`: `POST /api/share`, `DELETE /api/share/{id}`,
   `GET /api/share/{token}`; one shared 404 body for every failure.
5. `app.py`: `app.state.sharing` (injectable).
6. `apps/studio-api/tests/test_studio_sharing.py` (new).
7. Docs: `docs/living-studio.md` (sharing paragraph), `docs/architecture/trust-boundaries.md`,
   `README.md` (sidecar row).

## Reuses:

- Reuses `StudioMemory` and its `_migrate` for the share table, rather than a
  second SQLite store.
- Reuses `ODIService` / `Repository` readers (`get_outcome`, `get_segment`,
  `get_strategy`, `list_evidence`) for the scoped read, rather than new queries.
- Reuses the `StudioHTTPError` / `StudioError` shape and the router's `_as_http_error`
  conventions, rather than a second error format.
- Reuses `pydantic` `Field` bounds for the TTL range and `hmac.compare_digest`
  from the standard library for hash comparison.
- Writes fresh: the token-minting/verification service and the scoped payload
  builder — no existing module mints or verifies a capability token (rungs 1–3
  failed: no share module, no declared token dependency, nothing to copy).

## Verification

```bash
uv run pytest apps/studio-api/tests/test_studio_sharing.py -q
```
