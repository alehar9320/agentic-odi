"""Agentic ODI Core package.

The error hierarchy lives in :mod:`agentic_odi_core.errors`. Every member is
re-exported here except :class:`~agentic_odi_core.errors.ValidationError`,
which is intentionally left off the package root so that
``from agentic_odi_core import ValidationError`` can never be confused with
Pydantic's identically named class. Import it from
``agentic_odi_core.errors`` instead.
"""

from agentic_odi_core.contract import (
    TOOL_NAMES,
    TOOL_SPECS,
    ToolEffect,
    ToolName,
    ToolSpec,
    capability_manifest,
    capability_summary,
)
from agentic_odi_core.errors import (
    ConflictError,
    NotFoundError,
    OdiError,
    RateLimitError,
    SerializationError,
    StoreError,
    error_status,
)
from agentic_odi_core.evaluation import (
    OutcomeStatementError,
    evaluate_outcome_statement,
    statement_to_dict,
)
from agentic_odi_core.factory import build_repository
from agentic_odi_core.messages import (
    CAPABILITIES,
    ODI_ASSISTANT_PROMPT,
    ODI_FRAMEWORK_GUIDELINES,
    customer_outcome_not_found,
    evidence_not_found,
    job_not_found,
    outcome_not_found,
    step_not_found,
)
from agentic_odi_core.models import (
    JOB_STAGE_INDEX,
    JOB_STAGE_ORDER,
    BusinessImpactCategory,
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Direction,
    Evidence,
    EvidenceItemType,
    Job,
    JobStage,
    Outcome,
    Signal,
    SignalKind,
    Step,
    ValueMetric,
    compute_opportunity_score,
    job_stage_catalog,
)
from agentic_odi_core.remote import (
    StudioError,
    StudioErrorCode,
    parse_tool_result,
    tool_result_text,
)
from agentic_odi_core.repository import InMemoryRepository, Repository
from agentic_odi_core.schema import odi_schema
from agentic_odi_core.services import (
    CustomerOutcomeNotFoundError,
    EvidenceNotFoundError,
    InvalidOutcomeStatementError,
    JobNotFoundError,
    ODIService,
    OutcomeNotFoundError,
    SignalBudget,
    SignalNotFoundError,
    StepNotFoundError,
    ValueOutOfRangeError,
)

__all__ = [
    "BusinessImpactCategory",
    "BusinessValue",
    "CAPABILITIES",
    "ConflictError",
    "CustomerOutcome",
    "CustomerOutcomeNotFoundError",
    "CustomerValue",
    "Direction",
    "Evidence",
    "EvidenceItemType",
    "EvidenceNotFoundError",
    "Job",
    "JobNotFoundError",
    "JobStage",
    "JOB_STAGE_INDEX",
    "JOB_STAGE_ORDER",
    "NotFoundError",
    "ODIService",
    "ODI_ASSISTANT_PROMPT",
    "ODI_FRAMEWORK_GUIDELINES",
    "OdiError",
    "Outcome",
    "OutcomeNotFoundError",
    "OutcomeStatementError",
    "RateLimitError",
    "SerializationError",
    "Step",
    "StepNotFoundError",
    "StoreError",
    "Signal",
    "SignalBudget",
    "SignalKind",
    "SignalNotFoundError",
    "StudioError",
    "StudioErrorCode",
    "ValueMetric",
    "ValueOutOfRangeError",
    "InMemoryRepository",
    "InvalidOutcomeStatementError",
    "TOOL_NAMES",
    "TOOL_SPECS",
    "ToolName",
    "ToolSpec",
    "ToolEffect",
    "capability_manifest",
    "capability_summary",
    "Repository",
    "build_repository",
    "compute_opportunity_score",
    "customer_outcome_not_found",
    "error_status",
    "evaluate_outcome_statement",
    "evidence_not_found",
    "job_not_found",
    "job_stage_catalog",
    "odi_schema",
    "outcome_not_found",
    "parse_tool_result",
    "statement_to_dict",
    "step_not_found",
    "tool_result_text",
]
