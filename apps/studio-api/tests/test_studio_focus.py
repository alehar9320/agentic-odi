"""The record a PM is looking at must reach the model — in the store's own words.

A client may say *which* record is focused, but never what it says: the sidecar
re-reads the store, and adds nothing it cannot verify.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from agentic_odi_core import InMemoryRepository, ODIService
from agentic_odi_studio_api.studio import chat
from agentic_odi_studio_api.studio.schemas import ChatMessage, ChatRequest, FocusRef

STATEMENT = "Minimize the time it takes to reconcile a failed payment when closing the ledger"


def _store() -> SimpleNamespace:
    service = ODIService(InMemoryRepository())
    job = service.add_job(name="Reconcile a payment", description="Close the day's ledger")
    outcome = service.add_outcome(
        job_id=job.id, statement=STATEMENT, importance=9.0, satisfaction=2.0
    )
    step = service.add_step(job_id=job.id, name="Match the ledger line", order=1)
    evidence = service.add_evidence(
        source_name="Gong",
        source_kind="mcp",
        name="Call with the ops lead",
        content="Reconciliation eats two hours every morning.",
    )
    return SimpleNamespace(
        service=service, job=job.id, step=step.id, outcome=outcome.id, evidence=evidence.id
    )


def _request(focus: FocusRef | None) -> ChatRequest:
    return ChatRequest(
        base_url="http://llm/v1",
        model="model",
        mcp_url="http://mcp",
        messages=[ChatMessage(role="user", content="what would have to be true?")],
        focus=focus,
    )


def _system(store: SimpleNamespace, focus: FocusRef | None) -> str:
    messages = chat._to_openai_messages(
        _request(focus), focus_context=chat._focus_context(focus, store.service)
    )
    return messages[0]["content"]


def test_focused_outcome_is_named_from_the_store() -> None:
    store = _store()

    system = _system(store, FocusRef(kind="outcome", id=store.outcome))

    assert STATEMENT in system
    assert store.outcome in system


def test_focused_job_is_named_from_the_store() -> None:
    store = _store()

    system = _system(store, FocusRef(kind="job", id=store.job))

    assert "Reconcile a payment" in system


def test_focused_step_is_named_from_the_store() -> None:
    store = _store()

    system = _system(store, FocusRef(kind="step", id=store.step))

    assert "Match the ledger line" in system


def test_focused_evidence_is_named_from_the_store() -> None:
    store = _store()

    system = _system(store, FocusRef(kind="evidence", id=store.evidence))

    assert "Call with the ops lead" in system
    assert "Gong" in system


def test_an_unknown_id_adds_nothing() -> None:
    store = _store()

    system = _system(store, FocusRef(kind="outcome", id="no-such-outcome"))

    assert system == chat.SYSTEM_PROMPT


def test_no_local_store_adds_nothing() -> None:
    store = _store()
    focus = FocusRef(kind="outcome", id=store.outcome)

    assert chat._focus_context(focus, None) == ""


def test_no_focus_leaves_the_prompt_unchanged() -> None:
    store = _store()

    assert _system(store, None) == chat.SYSTEM_PROMPT


def test_a_client_cannot_send_the_words_of_a_record() -> None:
    with pytest.raises(ValueError):
        FocusRef.model_validate(
            {"kind": "outcome", "id": "O-1", "statement": "The customer loves it"}
        )
