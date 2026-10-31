from __future__ import annotations

import os

os.environ["AGENTIC_ODI_DB"] = ":memory:"

from collections.abc import Generator  # noqa: E402
from typing import Any  # noqa: E402

import pytest  # noqa: E402
from agentic_odi_mcp_server import (  # noqa: E402
    customer_outcomes_db,
    evidence_db,
    jobs_db,
    outcomes_db,
    segments_db,
    signals_db,
    steps_db,
    strategies_db,
    studies_db,
)


@pytest.fixture(autouse=True)
def reset_db() -> Generator[None, Any, None]:
    jobs_db.clear()
    steps_db.clear()
    outcomes_db.clear()
    customer_outcomes_db.clear()
    evidence_db.clear()
    signals_db.clear()
    segments_db.clear()
    strategies_db.clear()
    studies_db.clear()
    yield
