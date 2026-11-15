"""Pillar 3 through the sidecar: segments, strategies, bets and outcome history.

These are the write-and-read surfaces the studio calls once a job has scored
outcomes: a segment and its profile, the suggested candidates and their
acceptance, the strategy recorded for a segment with the paths it beat, the bet
that starts from a decision, and an outcome's own history. The refusals matter
as much as the successes — a strategy with no rejected path is not a
recommendation, so the sidecar must refuse it.
"""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


def _client() -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend="local"))


def _service(client: TestClient):
    return client.app.state.service  # type: ignore[attr-defined]


def _seed(client: TestClient) -> tuple[str, str, str, str]:
    service = _service(client)
    job = service.add_job("Rotate a leaked secret")
    step = service.add_step(job.id, "Gather the current values", order=1, allow_empty_job_map=True)
    first = service.add_outcome(
        job.id,
        statement="Minimize the time it takes to rotate the secret when it leaks",
        importance=9,
        satisfaction=2,
        step_id=step.id,
    )
    second = service.add_outcome(
        job.id,
        statement="Minimize the number of missed values after rotation",
        importance=9,
        satisfaction=3,
        step_id=step.id,
    )
    served = service.add_outcome(
        job.id,
        statement="Minimize the time it takes to verify the new value when deploying",
        importance=4,
        satisfaction=9,
        step_id=step.id,
    )
    return job.id, first.id, second.id, served.id


def _segment(client: TestClient, job_id: str, outcome_ids: list[str]) -> dict:
    created = client.post(
        "/api/segments",
        json={
            "job_id": job_id,
            "name": "Platform engineers, secrets rotation",
            "criterion": "Rotate a leaked secret without missing a value",
            "outcome_ids": outcome_ids,
        },
    )
    assert created.status_code in (200, 201), created.text
    return created.json()


def test_a_segment_round_trips_with_its_profile() -> None:
    client = _client()
    job_id, first, second, served = _seed(client)

    segment = _segment(client, job_id, [first, second])
    fetched = client.get(f"/api/segments/{segment['id']}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["outcome_ids"] == [first, second]

    profile = client.get(f"/api/segments/{segment['id']}/profile")
    assert profile.status_code == 200, profile.text
    body = profile.json()
    assert body["total_members"] == 2
    assert body["measured_count"] == 2
    assert body["underserved_count"] == 2
    assert body["overserved_count"] == 0
    assert body["measured_ratio"] == 1.0
    assert [entry["outcome_id"] for entry in body["top_underserved"]] == [first, second]
    assert body["gaps"] == []

    deleted = client.delete(f"/api/segments/{segment['id']}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"deleted": segment["id"]}
    assert client.get(f"/api/segments/{segment['id']}").status_code == 404


def test_a_profile_separates_the_two_bands_and_names_an_unscored_member() -> None:
    client = _client()
    job_id, first, _second, served = _seed(client)
    service = _service(client)
    unscored = service.add_outcome(
        job_id,
        statement="Minimize the time it takes to brief the on-call engineer when a secret leaks",
    )

    segment = _segment(client, job_id, [first, served, unscored.id])
    body = client.get(f"/api/segments/{segment['id']}/profile").json()
    assert body["total_members"] == 3
    assert body["measured_count"] == 2
    assert body["unscored_count"] == 1
    assert body["underserved_count"] == 1
    assert body["overserved_count"] == 1
    assert body["top_overserved"][0]["outcome_id"] == served
    assert any("unscored" in gap for gap in body["gaps"])


def test_a_missing_segment_is_a_404_on_read_and_delete() -> None:
    client = _client()
    assert client.get("/api/segments/not-a-segment").status_code == 404
    assert client.delete("/api/segments/not-a-segment").status_code == 404
    assert client.get("/api/segments/not-a-segment/profile").status_code == 404


def test_suggested_candidates_can_be_listed_and_accepted() -> None:
    client = _client()
    job_id, first, second, _served = _seed(client)
    service = _service(client)
    service.add_outcome(
        job_id,
        statement="Minimize the number of steps it takes to audit a rotated secret when it rotates",
        importance=9,
        satisfaction=2,
        step_id=service.get_outcome(first).step_id,  # type: ignore[union-attr]
    )
    assert client.get("/api/segments").status_code == 200

    listed = client.get(f"/api/jobs/{job_id}/segment-candidates")
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert payload["candidates"], payload
    candidate = payload["candidates"][0]

    accepted = client.post(
        "/api/segment-candidates/accept",
        json={"job_id": job_id, "fingerprint": candidate["fingerprint"]},
    )
    assert accepted.status_code in (200, 201), accepted.text
    assert accepted.json()["outcome_ids"] == candidate["members"]

    refused = client.post(
        "/api/segment-candidates/accept",
        json={"job_id": job_id, "fingerprint": "no-such-fingerprint"},
    )
    assert refused.status_code == 400, refused.text
    assert "stale" in refused.text


def test_a_strategy_records_the_paths_it_beat() -> None:
    client = _client()
    job_id, first, second, _served = _seed(client)
    segment = _segment(client, job_id, [first, second])

    body = {
        "kind": "differentiated",
        "rationale": "The rotation path is underserved and nobody serves it well.",
        "expected_effect": "Cut the time to rotate a leaked secret.",
        "rejected": [
            {"kind": "disruptive", "why": "No non-consumer is priced out of rotation."},
            {"kind": "new_market", "why": "No evidence of non-consumption."},
        ],
    }
    recorded = client.post(f"/api/segments/{segment['id']}/strategy", json=body)
    assert recorded.status_code in (200, 201), recorded.text
    strategy = recorded.json()
    assert strategy["kind"] == "differentiated"
    assert {entry["kind"] for entry in strategy["rejected"]} == {"disruptive", "new_market"}

    listed = client.get("/api/strategies", params={"segment_id": segment["id"]})
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [strategy["id"]]


def test_a_strategy_without_its_rejections_is_refused() -> None:
    client = _client()
    job_id, first, second, _served = _seed(client)
    segment = _segment(client, job_id, [first, second])

    refused = client.post(
        f"/api/segments/{segment['id']}/strategy",
        json={
            "kind": "differentiated",
            "rationale": "Only one path was considered.",
            "expected_effect": "Ship it.",
        },
    )
    assert refused.status_code == 400, refused.text
    assert "rejected" in refused.text


def test_a_bet_starts_from_a_decision_and_advances() -> None:
    client = _client()
    job_id, first, _second, _served = _seed(client)
    service = _service(client)
    decision = service.record_decision(
        job_id=job_id,
        chosen_outcome_ids=[first],
        rationale="Rotation time is the underserved outcome worth a bet.",
        decided_by="alexander",
        decided_at="2026-11-01T09:00:00+00:00",
    )

    recorded = client.post(
        "/api/bets",
        json={
            "decision_id": decision.id,
            "outcome_id": first,
            "hypothesis": "A guided rotation cuts the leaked-secret window.",
            "target": 0.8,
            "measure_by": "2026-12-01",
        },
    )
    assert recorded.status_code in (200, 201), recorded.text
    bet = recorded.json()
    assert bet["status"] == "planned"

    listed = client.get("/api/bets", params={"job_id": job_id})
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [bet["id"]]

    advanced = client.post(f"/api/bets/{bet['id']}/advance", json={"status": "running"})
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["status"] == "running"


def test_an_outcome_history_and_delta_are_readable() -> None:
    client = _client()
    _job_id, first, _second, _served = _seed(client)

    history = client.get(f"/api/outcomes/{first}/history")
    assert history.status_code == 200, history.text
    assert history.json()

    delta = client.get(f"/api/outcomes/{first}/delta")
    assert delta.status_code == 200, delta.text


def test_an_outcome_value_is_set_with_its_unit_and_basis() -> None:
    client = _client()
    _job_id, first, _second, _served = _seed(client)

    valued = client.patch(
        f"/api/outcomes/{first}/value",
        json={"estimate": 120000.0, "unit": "currency", "basis": "estimate"},
    )
    assert valued.status_code == 200, valued.text
    assert valued.json()["value_estimate"] == 120000.0
    assert valued.json()["value_unit"] == "currency"

    refused = client.patch(
        f"/api/outcomes/{first}/value",
        json={"estimate": 120000.0, "unit": "currency", "basis": "market"},
    )
    assert refused.status_code == 400, refused.text
