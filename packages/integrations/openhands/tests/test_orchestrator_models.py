from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from agentic_odi_integrations_openhands import (
    ACTIVE_WORK_STATUSES,
    TERMINAL_WORK_STATUSES,
    AgentTarget,
    OrchestratorSettings,
    WorkItem,
    WorkItemStatus,
)
from agentic_odi_openhands import AlwaysConfirm, ConfirmRisky, NeverConfirm
from pydantic import ValidationError


def test_work_status_sets_do_not_overlap() -> None:
    assert not ACTIVE_WORK_STATUSES & TERMINAL_WORK_STATUSES
    assert WorkItemStatus.DISPATCHING in ACTIVE_WORK_STATUSES
    assert WorkItemStatus.COMPLETED in TERMINAL_WORK_STATUSES
    assert WorkItemStatus.BLOCKED in TERMINAL_WORK_STATUSES


def test_target_redacts_literal_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ODI_TEST_KEY", raising=False)
    target = AgentTarget(alias="cloud", base_url="https://example.test", api_key="secret")
    view = target.public_view()
    assert view["api_key"] is None
    assert view["has_literal_key"] is True
    assert view["has_env_key"] is True


def test_target_env_key_is_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ODI_TEST_KEY", "from-env")
    target = AgentTarget(alias="cloud", base_url="https://example.test", api_key_env="ODI_TEST_KEY")
    assert target.resolved_api_key == "from-env"
    assert target.public_view()["has_env_key"] is True


def test_confirmation_policies() -> None:
    assert isinstance(AgentTarget(alias="a", base_url="u").confirmation(), ConfirmRisky)
    assert isinstance(
        AgentTarget(alias="a", base_url="u", confirmation_policy="always").confirmation(),
        AlwaysConfirm,
    )
    assert isinstance(
        AgentTarget(alias="a", base_url="u", confirmation_policy="never").confirmation(),
        NeverConfirm,
    )


def test_duplicate_target_aliases_are_rejected() -> None:
    with pytest.raises(ValidationError):
        OrchestratorSettings(
            targets=[
                AgentTarget(alias="cloud", base_url="https://example.test"),
                AgentTarget(alias="cloud", base_url="https://other.test"),
            ]
        )


def test_single_target_is_the_default() -> None:
    target = AgentTarget(alias="cloud", base_url="https://example.test")
    settings = OrchestratorSettings(targets=[target])
    assert settings.target(None) is target


def test_work_item_due() -> None:
    now = datetime.now(timezone.utc)
    overdue = WorkItem(work_key="k", title="t", prompt="p", target_alias="a")
    assert overdue.due(now)
    future = overdue.model_copy(update={"next_attempt_at": now + timedelta(minutes=5)})
    assert not future.due(now)
