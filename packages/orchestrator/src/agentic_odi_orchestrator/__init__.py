"""Autopilot orchestrator for OpenHands Agent Canvas.

The orchestrator owns the work queue, the run state machine, the approval
policy, and the daemon loop. It talks to OpenHands through
:mod:`agentic_odi_openhands` and reports terminal outcomes through the ODI
signal inbox.
"""

from agentic_odi_orchestrator.config import (
    config_path,
    db_path,
    default_target,
    load_settings,
    save_settings,
    settings_with_default_target,
)
from agentic_odi_orchestrator.daemon import AlreadyRunning, DaemonLock, OrchestratorDaemon
from agentic_odi_orchestrator.models import (
    ACTIVE_RUN_STATUSES,
    ACTIVE_WORK_STATUSES,
    TERMINAL_RUN_STATUSES,
    TERMINAL_WORK_STATUSES,
    AgentRun,
    AgentRunStatus,
    AgentTarget,
    ApprovalRecord,
    Decision,
    GitHubSettings,
    OrchestratorSettings,
    OrchestratorStatus,
    SourceKind,
    WorkItem,
    WorkItemStatus,
    utcnow,
)
from agentic_odi_orchestrator.service import (
    InvalidTransition,
    OrchestratorError,
    OrchestratorService,
    TargetNotConfigured,
    TickReport,
    WorkItemNotFound,
)
from agentic_odi_orchestrator.store import OrchestratorStore

__all__ = [
    "ACTIVE_RUN_STATUSES",
    "ACTIVE_WORK_STATUSES",
    "TERMINAL_RUN_STATUSES",
    "TERMINAL_WORK_STATUSES",
    "AgentRun",
    "AgentRunStatus",
    "AgentTarget",
    "AlreadyRunning",
    "ApprovalRecord",
    "DaemonLock",
    "Decision",
    "GitHubSettings",
    "InvalidTransition",
    "OrchestratorDaemon",
    "OrchestratorError",
    "OrchestratorService",
    "OrchestratorSettings",
    "OrchestratorStatus",
    "OrchestratorStore",
    "SourceKind",
    "TargetNotConfigured",
    "TickReport",
    "WorkItem",
    "WorkItemNotFound",
    "WorkItemStatus",
    "config_path",
    "db_path",
    "default_target",
    "load_settings",
    "save_settings",
    "settings_with_default_target",
    "utcnow",
]
