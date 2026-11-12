"""Linking an outcome to an objective that does not exist is a backend error.

``link_outcome`` refuses an unknown objective by matching the text against the
stored vision, and the CLI must surface that refusal as one error line naming
the objectives that do exist. Without the translation the caller saw a raw
validation exception traceback instead.
"""

from __future__ import annotations

import pytest
from agentic_odi_cli.backend import BackendError, LocalBackend


def _backend_with_outcome(tmp_path) -> tuple[LocalBackend, str]:
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))
    job_id = backend.call("add_job", {"name": "Publish a plugin"})["id"]
    outcome = backend.call(
        "add_outcome",
        {
            "job_id": job_id,
            "statement": "Minimize the time it takes to publish a plugin when a release is ready",
            "importance": 9.0,
            "satisfaction": 3.0,
        },
    )
    return backend, outcome["id"]


def test_an_unknown_objective_is_one_error_line_naming_the_known_ones(tmp_path) -> None:
    backend, outcome_id = _backend_with_outcome(tmp_path)

    with pytest.raises(BackendError) as raised:
        backend.call(
            "link_outcome",
            {"outcome_id": outcome_id, "field": "method", "text": "No such method"},
        )

    message = str(raised.value)
    assert "No method in the vision matches" in message
    assert "Current methods" in message
