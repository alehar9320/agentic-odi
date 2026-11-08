"""The scoped share token: one artifact, read-only, expiring, revocable.

The token is a bearer capability for exactly one record. These tests assert the
boundaries that make that true: the raw token is shown once and never stored, a
read returns only the named artifact and its own evidence, every dead token is
the same 404, a stolen hash cannot be replayed, and the route is read-only.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from agentic_odi_core import InMemoryRepository, manual_claim_check
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio.memory import StudioMemory
from agentic_odi_studio_api.studio.sharing import (
    DEFAULT_TTL_DAYS,
    MAX_TTL_DAYS,
    ShareService,
    hash_token,
)
from fastapi.testclient import TestClient

STATEMENT = "Minimize the time it takes to rotate a secret when it leaks"
OTHER_STATEMENT = "Minimize the number of missed values after rotation"


def _seeded() -> tuple[TestClient, dict[str, str]]:
    """A local canvas with one outcome, its evidence, a segment, and a strategy."""
    repo = InMemoryRepository()
    client = TestClient(create_app(repo, backend="local"))
    service = client.app.state.service  # type: ignore[attr-defined]

    job = service.add_job("Rotate a leaked secret")
    gather = service.add_step(
        job.id, "Gather the current values", order=1, allow_empty_job_map=True
    )
    verify = service.add_step(job.id, "Verify the new value", order=2, allow_empty_job_map=True)
    first = service.add_outcome(
        job.id,
        statement=STATEMENT,
        importance=9,
        satisfaction=2,
        step_id=gather.id,
        claim_check=manual_claim_check(),
    )
    service.add_outcome(
        job.id,
        statement=OTHER_STATEMENT,
        importance=8,
        satisfaction=3,
        step_id=gather.id,
        claim_check=manual_claim_check(),
    )
    # A served outcome the bet differentiates from, so a strategy has support.
    service.add_outcome(
        job.id,
        statement="Minimize the time it takes to verify the new value when deploying",
        importance=5,
        satisfaction=5,
        step_id=verify.id,
        claim_check=manual_claim_check(),
    )
    evidence = service.add_evidence(
        source_name="Gong",
        source_kind="mcp",
        name="Acme rotation call",
        content="A junior engineer broke staging because the secret was not copied.",
        raw={"token": "connector-secret", "headers": {"Authorization": "Bearer abc"}},
        outcome_id=first.id,
    )
    segment = service.segment_market()[0]
    strategy = service.propose_strategy()

    return client, {
        "outcome": first.id,
        "segment": segment.id,
        "strategy": strategy.id,
        "evidence": evidence.id,
    }


def _mint(client: TestClient, kind: str, artifact_id: str, ttl_days: int | None = None) -> dict:
    body: dict = {"artifact_kind": kind, "artifact_id": artifact_id}
    if ttl_days is not None:
        body["ttl_days"] = ttl_days
    response = client.post("/api/share", json=body)
    assert response.status_code == 200, response.text
    return response.json()


# -- mint ----------------------------------------------------------------------


def test_minting_returns_a_token_once_and_stores_only_its_hash() -> None:
    client, ids = _seeded()

    minted = _mint(client, "outcome", ids["outcome"])

    assert minted["token"].startswith("odi_sh_")
    assert minted["url"].endswith(minted["token"])
    assert minted["id"].startswith("shr_")

    # The raw token is never in the response again, and only its hash is stored.
    listed = client.get("/api/share").json()
    assert [share["id"] for share in listed] == [minted["id"]]
    assert "token" not in listed[0]

    memory: StudioMemory = client.app.state.memory  # type: ignore[attr-defined]
    share = memory.get_share(minted["id"])
    assert share is not None
    assert share.token_hash == hash_token(minted["token"])
    assert minted["token"] not in share.token_hash


def test_minting_for_an_unknown_artifact_is_a_404() -> None:
    client, _ = _seeded()

    response = client.post(
        "/api/share", json={"artifact_kind": "outcome", "artifact_id": "does-not-exist"}
    )

    assert response.status_code == 404


@pytest.mark.parametrize("ttl_days", [0, 31, 720])
def test_ttl_outside_the_range_is_refused(ttl_days: int) -> None:
    client, ids = _seeded()

    response = client.post(
        "/api/share",
        json={"artifact_kind": "outcome", "artifact_id": ids["outcome"], "ttl_days": ttl_days},
    )

    assert response.status_code == 422


def test_expiry_defaults_to_seven_days_and_never_exceeds_thirty() -> None:
    client, ids = _seeded()

    minted = _mint(client, "outcome", ids["outcome"])
    expires = datetime.fromisoformat(minted["expires_at"])
    assert timedelta(days=DEFAULT_TTL_DAYS - 1) < expires - datetime.now(timezone.utc)
    assert expires - datetime.now(timezone.utc) <= timedelta(days=DEFAULT_TTL_DAYS)

    longest = _mint(client, "outcome", ids["outcome"], ttl_days=MAX_TTL_DAYS)
    span = datetime.fromisoformat(longest["expires_at"]) - datetime.now(timezone.utc)
    assert span <= timedelta(days=MAX_TTL_DAYS)


# -- read with scope only ------------------------------------------------------


def test_reading_returns_exactly_the_named_artifact_and_its_own_evidence() -> None:
    client, ids = _seeded()
    minted = _mint(client, "outcome", ids["outcome"])

    response = client.get(f"/api/share/{minted['token']}")

    assert response.status_code == 200
    body = response.json()
    assert body["artifact_kind"] == "outcome"
    assert body["artifact"]["id"] == ids["outcome"]
    assert [record["id"] for record in body["evidence"]] == [ids["evidence"]]
    # Nothing about the rest of the canvas is reachable through the token.
    assert "canvas" not in body
    assert "memory" not in body
    assert "conversations" not in body


def test_the_shared_evidence_never_carries_the_raw_payload() -> None:
    client, ids = _seeded()
    minted = _mint(client, "outcome", ids["outcome"])

    body = client.get(f"/api/share/{minted['token']}").json()

    assert body["evidence"]
    assert all("raw" not in record for record in body["evidence"])
    assert "connector-secret" not in str(body)


def test_a_segment_share_carries_its_outcomes_evidence_only() -> None:
    client, ids = _seeded()
    minted = _mint(client, "segment", ids["segment"])

    body = client.get(f"/api/share/{minted['token']}").json()

    assert body["artifact_kind"] == "segment"
    assert body["artifact"]["id"] == ids["segment"]
    # The segment's evidence is the evidence of its outcomes, and nothing else.
    assert [record["id"] for record in body["evidence"]] == [ids["evidence"]]


def test_a_strategy_share_resolves_through_its_segment() -> None:
    client, ids = _seeded()
    minted = _mint(client, "strategy", ids["strategy"])

    body = client.get(f"/api/share/{minted['token']}").json()

    assert body["artifact_kind"] == "strategy"
    assert body["artifact"]["id"] == ids["strategy"]
    assert [record["id"] for record in body["evidence"]] == [ids["evidence"]]


def test_the_read_never_lists_records() -> None:
    """There is no list endpoint under the shared path, only the one token read."""
    client, ids = _seeded()
    minted = _mint(client, "outcome", ids["outcome"])

    # A guessed second token is the same 404 as an unknown one: no probing.
    other = client.get("/api/share/odi_sh_0000000000000000000000000000000000000000000")
    assert other.status_code == 404
    # The live token is still the only thing that answers.
    assert client.get(f"/api/share/{minted['token']}").status_code == 200


# -- expiry, revocation, and the one 404 ---------------------------------------


def test_an_unknown_token_is_a_404() -> None:
    client, _ = _seeded()

    response = client.get("/api/share/odi_sh_not-a-real-token")

    assert response.status_code == 404


def test_a_malformed_token_is_a_404_with_no_hint() -> None:
    client, _ = _seeded()

    response = client.get("/api/share/not-even-prefixed")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_every_dead_token_shares_one_404_body() -> None:
    client, ids = _seeded()
    minted = _mint(client, "outcome", ids["outcome"])
    revoked = _mint(client, "outcome", ids["outcome"])
    client.delete(f"/api/share/{revoked['id']}")

    # Pin the request id so the only thing compared is the body the server builds.
    header = {"X-Request-ID": "probe"}
    unknown = client.get("/api/share/odi_sh_unknown", headers=header)
    malformed = client.get("/api/share/nope", headers=header)
    after_revoke = client.get(f"/api/share/{revoked['token']}", headers=header)

    assert unknown.status_code == malformed.status_code == after_revoke.status_code == 404
    assert unknown.text == malformed.text == after_revoke.text
    # The live token is unaffected.
    assert client.get(f"/api/share/{minted['token']}").status_code == 200


def test_an_expired_token_is_a_404_the_moment_the_clock_passes_it() -> None:
    repo = InMemoryRepository()
    memory = StudioMemory(":memory:")
    app = create_app(repo, backend="local", memory=memory)
    service = app.state.service
    job = service.add_job("Rotate a leaked secret")
    outcome = service.add_outcome(
        job.id,
        statement=STATEMENT,
        importance=9,
        satisfaction=2,
        claim_check=manual_claim_check(),
    )

    now = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    current = [now]
    sharing = ShareService(service, memory, clock=lambda: current[0])
    app.state.sharing = sharing
    client = TestClient(app)

    minted = sharing.mint("outcome", outcome.id, ttl_days=1)
    assert client.get(f"/api/share/{minted.token}").status_code == 200

    current[0] = now + timedelta(days=2)
    assert client.get(f"/api/share/{minted.token}").status_code == 404
    memory.close()


def test_revocation_takes_effect_immediately() -> None:
    client, ids = _seeded()
    minted = _mint(client, "outcome", ids["outcome"])
    assert client.get(f"/api/share/{minted['token']}").status_code == 200

    revoked = client.delete(f"/api/share/{minted['id']}")

    assert revoked.status_code == 200
    assert revoked.json() == {"ok": True}
    assert client.get(f"/api/share/{minted['token']}").status_code == 404


def test_revoking_an_unknown_share_is_a_404() -> None:
    client, _ = _seeded()

    assert client.delete("/api/share/shr_does_not_exist").status_code == 404


def test_deleting_the_artifact_empties_the_link_without_a_hint() -> None:
    client, ids = _seeded()
    minted = _mint(client, "outcome", ids["outcome"])

    client.delete(f"/api/outcomes/{ids['outcome']}")

    response = client.get(f"/api/share/{minted['token']}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# -- hash and compare safely ---------------------------------------------------


def test_a_token_stolen_from_the_stored_hash_cannot_be_used() -> None:
    """The database holds a SHA-256 digest, not the token; the digest is not a key."""
    client, ids = _seeded()
    minted = _mint(client, "outcome", ids["outcome"])

    memory: StudioMemory = client.app.state.memory  # type: ignore[attr-defined]
    share = memory.get_share(minted["id"])
    assert share is not None

    stolen = share.token_hash
    assert stolen != minted["token"]
    assert hashlib.sha256(stolen.encode()).hexdigest() != stolen

    # Presenting the stored hash as if it were the token does not open the record.
    assert client.get(f"/api/share/{stolen}").status_code == 404
    assert client.get(f"/api/share/odi_sh_{stolen}").status_code == 404


def test_a_read_records_last_read_at_without_a_reader_identity() -> None:
    client, ids = _seeded()
    minted = _mint(client, "outcome", ids["outcome"])
    memory: StudioMemory = client.app.state.memory  # type: ignore[attr-defined]
    created = memory.get_share(minted["id"])
    assert created is not None
    assert created.last_read_at is None

    client.get(f"/api/share/{minted['token']}")

    share = memory.get_share(minted["id"])
    assert share is not None
    assert share.last_read_at is not None
    # No column and no value names the reader.
    assert set(share.to_dict()) == {
        "id",
        "artifact_kind",
        "artifact_id",
        "created_at",
        "expires_at",
        "revoked_at",
        "last_read_at",
    }


def test_the_store_persists_only_the_hash_across_a_reopen(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    store = StudioMemory(db)
    store.create_share(
        token_hash=hash_token("odi_sh_secret"),
        artifact_kind="outcome",
        artifact_id="o-1",
        expires_at=datetime.now(timezone.utc).isoformat(),
    )
    store.close()

    raw = sqlite3.connect(db)
    try:
        rows = raw.execute("SELECT token_hash, artifact_kind, artifact_id FROM shares").fetchall()
    finally:
        raw.close()

    assert rows == [(hash_token("odi_sh_secret"), "outcome", "o-1")]
    assert "odi_sh_secret" not in str(rows)


# -- keep it read-only ---------------------------------------------------------


def test_a_non_get_on_the_shared_route_is_refused() -> None:
    client, ids = _seeded()
    minted = _mint(client, "outcome", ids["outcome"])

    assert client.post(f"/api/share/{minted['token']}").status_code == 405
    assert client.patch(f"/api/share/{minted['token']}").status_code == 405
    assert client.put(f"/api/share/{minted['token']}").status_code == 405


def test_the_read_still_works_after_a_write_is_refused() -> None:
    client, ids = _seeded()
    minted = _mint(client, "outcome", ids["outcome"])

    client.post(f"/api/share/{minted['token']}")

    assert client.get(f"/api/share/{minted['token']}").status_code == 200
