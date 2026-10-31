"""The four signal routes answer under both the local and the mcp backend."""

from __future__ import annotations

import json

from agentic_odi_core import InMemoryRepository, SignalKind
from agentic_odi_core.remote import StudioError, StudioErrorCode
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio import router as router_module
from agentic_odi_studio_api.studio.errors import StudioHTTPError
from fastapi.testclient import TestClient


def _client(backend: str = "local") -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend=backend))


def _make_signal(client: TestClient) -> dict:
    client.post("/api/jobs", json={"name": "Ship a service", "description": "Platform"})
    listed = client.get("/api/signals")
    assert listed.status_code == 200
    signals = listed.json()
    assert [signal["kind"] for signal in signals] == ["job_added"]
    return signals[0]


def _record(client: TestClient, kind: str, title: str, **fields: object) -> dict:
    """Record one signal straight into the store, as a real write would."""
    service = client.app.state.service  # type: ignore[attr-defined]
    signal = service.record_signal(
        SignalKind(kind),
        title,
        subject_kind="job",
        subject_id="j-1",
        discriminator=title,
        **fields,
    )
    return signal.model_dump(mode="json")


def test_local_backend_lists_job_added_as_a_real_signal() -> None:
    client = _client()
    signal = _make_signal(client)
    assert signal["subject_kind"] == "job"
    assert signal["severity"] == "info"
    assert signal["fingerprint"]
    assert signal["created_at"]


def test_local_backend_unread_count_tracks_reads_and_dismissals() -> None:
    client = _client()
    signal = _record(client, "bet_due", "Bet is due")
    assert client.get("/api/signals/unread-count").json() == {"count": 1}

    read = client.post(f"/api/signals/{signal['id']}/read", json={})
    assert read.status_code == 200
    assert read.json()["read_at"]
    assert client.get("/api/signals/unread-count").json() == {"count": 0}

    dismissed = client.post(f"/api/signals/{signal['id']}/dismiss", json={})
    assert dismissed.status_code == 200
    assert dismissed.json()["dismissed_at"]
    assert client.get("/api/signals").json() == []


def test_local_backend_bell_applies_the_shared_policy() -> None:
    client = _client()
    # A coverage gap is real and visible in the feed but off by default, so it
    # never rings the bell; a bet coming due does.
    gap = _record(client, "coverage_gap", "A stage has no outcomes")
    _record(client, "bet_due", "Bet is due")
    assert client.get("/api/signals/unread-count").json() == {"count": 1}
    assert {signal["kind"] for signal in client.get("/api/signals").json()} == {
        "coverage_gap",
        "bet_due",
    }

    # A rule edit changes the count immediately, and never marks the signal
    # read or dismisses it.
    assert (
        client.put(
            "/api/notification-rules",
            json={"kind": "coverage_gap", "threshold": 0.0, "enabled": True},
        ).status_code
        == 200
    )
    assert client.get("/api/signals/unread-count").json() == {"count": 2}
    gap_row = next(s for s in client.get("/api/signals").json() if s["id"] == gap["id"])
    assert gap_row["read_at"] is None
    assert gap_row["dismissed_at"] is None


def test_local_backend_repeated_reads_write_nothing() -> None:
    client = _client()
    _record(client, "bet_due", "Bet is due")
    first = client.get("/api/signals").json()
    second = client.get("/api/signals").json()
    # Derivation is read-only: two reads return identical, stable rows and the
    # unread count does not drift, so a feed read never invents state.
    assert first == second
    assert [signal["id"] for signal in first] == [signal["id"] for signal in second]
    assert client.get("/api/signals/unread-count").json() == {"count": 1}


def test_local_backend_returns_404_for_an_unknown_signal_id() -> None:
    client = _client()
    for path in ("/api/signals/nope/read", "/api/signals/nope/dismiss"):
        response = client.post(path, json={})
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


def test_local_backend_excludes_budget_suppressed_signals(monkeypatch) -> None:
    monkeypatch.delenv("AGENTIC_ODI_SIGNAL_BUDGET", raising=False)
    client = _client()
    service = client.app.state.service  # type: ignore[attr-defined]
    for index in range(25):
        service.record_signal(
            SignalKind.BET_DUE,
            f"extra bet {index}",
            subject_kind="bet",
            subject_id=f"b-{index}",
            discriminator=f"b-{index}",
        )
    feed = client.get("/api/signals").json()
    assert len(feed) == 20
    # The budget caps the feed, and the bell only counts what the policy lets
    # interrupt, so both stop at the same 20 eligible signals.
    assert client.get("/api/signals/unread-count").json() == {"count": 20}


def test_local_backend_rule_edit_does_not_resurrect_a_dismissed_signal() -> None:
    client = _client()
    gap = _record(client, "coverage_gap", "A stage has no outcomes")
    assert client.post(f"/api/signals/{gap['id']}/dismiss", json={}).status_code == 200
    assert client.get("/api/signals/unread-count").json() == {"count": 0}

    # Turning the kind on makes the *kind* eligible but must not undo a
    # dismissal: the dismissed signal stays out of the feed and the bell.
    assert (
        client.put(
            "/api/notification-rules",
            json={"kind": "coverage_gap", "threshold": 0.0, "enabled": True},
        ).status_code
        == 200
    )
    assert client.get("/api/signals/unread-count").json() == {"count": 0}
    assert client.get("/api/signals").json() == []


def test_mcp_backend_calls_the_contract_tools(monkeypatch) -> None:
    calls: list[tuple[str, str, dict]] = []

    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        calls.append((mcp_url, tool, arguments))
        if tool == "list_signals":
            return json.dumps([{"id": "sig-1", "kind": "job_added"}])
        return 'Signal marked as read: {"id": "sig-1", "read_at": "now"}'

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)
    client = _client(backend="mcp")

    listed = client.get("/api/signals?unread_only=true&limit=10&mcp_url=http://mcp")
    assert listed.status_code == 200
    assert listed.json() == [{"id": "sig-1", "kind": "job_added"}]

    read = client.post("/api/signals/sig-1/read", json={"mcp_url": "http://mcp"})
    assert read.status_code == 200
    assert read.json()["read_at"] == "now"

    assert calls[0] == ("http://mcp", "list_signals", {"unread_only": True, "limit": 10})
    assert calls[1] == ("http://mcp", "mark_signal_read", {"signal_id": "sig-1"})


def test_mcp_backend_unread_counts_from_the_list_tool(monkeypatch) -> None:
    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        if tool == "list_notification_rules":
            return json.dumps([{"kind": "bet_due", "threshold": 0.0, "enabled": True}])
        assert tool == "list_signals"
        assert arguments == {"unread_only": True, "limit": 1000}
        return json.dumps(
            [
                {"id": "a", "kind": "bet_due", "title": "due", "fingerprint": "fa"},
                {"id": "b", "kind": "coverage_gap", "title": "gap", "fingerprint": "fb"},
            ]
        )

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)
    client = _client(backend="mcp")
    # The bell applies the shared policy, so the coverage gap (off by default)
    # stays in the feed but does not count.
    assert client.get("/api/signals/unread-count?mcp_url=http://mcp").json() == {"count": 1}


def test_mcp_backend_maps_unknown_signal_ids_to_404(monkeypatch) -> None:
    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        raise StudioHTTPError(
            StudioError(code=StudioErrorCode.NOT_FOUND, message="signal not found: nope")
        )

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)
    client = _client(backend="mcp")
    response = client.post("/api/signals/nope/dismiss", json={"mcp_url": "http://mcp"})
    assert response.status_code == 404


def test_mcp_backend_requires_mcp_url_with_the_existing_400_shape() -> None:
    client = _client(backend="mcp")
    response = client.post("/api/signals/sig-1/read", json={})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation"
