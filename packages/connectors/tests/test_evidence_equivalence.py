"""Keep the connector's transport shape equal to the record it becomes.

``agentic_odi_connectors`` must not import the ODI store in production — that is
the boundary ``tests/test_architecture.py`` enforces and the reason
``mapping.py`` builds a draft instead of an ``Evidence``. This module imports
``agentic_odi_core`` **in a test only**, because the only way to prove the two
shapes still agree is to read both of them. Read that as the exception it is,
not as licence to import core from connector source.
"""

from __future__ import annotations

from typing import Any, get_args

from agentic_odi_connectors.mapping import EvidenceDraft
from agentic_odi_connectors.models import EvidenceItemType as ConnectorItemType
from agentic_odi_core.models import Evidence
from agentic_odi_core.models import EvidenceItemType as CoreItemType

DRAFT_FILE = "packages/connectors/src/agentic_odi_connectors/mapping.py"
EVIDENCE_FILE = "packages/core/src/agentic_odi_core/models.py"
CONNECTOR_TYPES_FILE = "packages/connectors/src/agentic_odi_connectors/models.py"

#: ``Evidence`` has an ``id`` the draft cannot pre-decide, and the draft carries
#: ``discriminator`` — the source record's stable key, used to deduplicate ingest
#: and dropped when the draft becomes a stored record. Anything else that appears
#: on only one side is drift and has to be added here on purpose.
DOMAIN_ONLY = {"id"}
DRAFT_ONLY = {"discriminator"}


def _drift_report(
    label: str, left: set[str], right: set[str], left_file: str, right_file: str
) -> str | None:
    """Name the pair of files to edit, and the field or value that moved apart."""
    left_only = left - right
    right_only = right - left
    if not left_only and not right_only:
        return None
    lines = [f"{label} drifted apart between {left_file} and {right_file}:"]
    if right_only:
        lines.append(f"  in {right_file} only: {sorted(right_only)}")
    if left_only:
        lines.append(f"  in {left_file} only: {sorted(left_only)}")
    lines.append(f"Edit {left_file} and {right_file} together, or declare the pair.")
    return "\n".join(lines)


def test_the_draft_and_the_record_describe_the_same_thing() -> None:
    draft_fields = set(EvidenceDraft.model_fields) - DRAFT_ONLY
    evidence_fields = set(Evidence.model_fields) - DOMAIN_ONLY
    report = _drift_report(
        "Evidence field sets", draft_fields, evidence_fields, DRAFT_FILE, EVIDENCE_FILE
    )
    assert report is None, report


def test_both_item_type_vocabularies_list_the_same_kinds() -> None:
    connector_values = {str(value) for value in get_args(ConnectorItemType)}
    core_values = {str(value) for value in get_args(CoreItemType)}
    report = _drift_report(
        "EvidenceItemType", connector_values, core_values, CONNECTOR_TYPES_FILE, EVIDENCE_FILE
    )
    assert report is None, report


def test_the_draft_accepts_every_core_item_type() -> None:
    for value in get_args(CoreItemType):
        draft: dict[str, Any] = {
            "source_name": "Gong",
            "source_kind": "mcp",
            "item_type": value,
            "name": "Call with Acme",
            "content": "The signup flow loses people.",
        }
        assert EvidenceDraft.model_validate(draft).item_type == value


def test_the_drift_report_names_both_files_and_the_offender() -> None:
    report = _drift_report(
        "Evidence field sets",
        {"source_name", "name"},
        {"source_name", "name", "owner"},
        DRAFT_FILE,
        EVIDENCE_FILE,
    )
    assert report is not None
    assert DRAFT_FILE in report
    assert EVIDENCE_FILE in report
    assert "owner" in report
