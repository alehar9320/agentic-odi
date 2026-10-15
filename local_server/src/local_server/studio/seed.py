"""Seed prototype data, ported verbatim from the Streamlit Living Studio app."""

from __future__ import annotations

from typing import Any

DEMO_JOBS: list[dict[str, Any]] = [
    {
        "id": "JOB-402",
        "name": "Sync Environment Secrets Across Microservices",
        "description": "Backend developers configuring microservice deployment pipelines across staging and production.",
    }
]

DEMO_STEPS: list[dict[str, Any]] = [
    {
        "id": "STP-1",
        "job_id": "JOB-402",
        "name": "1. Define required environment variables",
        "order": 1,
    },
    {
        "id": "STP-2",
        "job_id": "JOB-402",
        "name": "2. Locate credentials in Vault / 1Password",
        "order": 2,
    },
    {
        "id": "STP-3",
        "job_id": "JOB-402",
        "name": "3. Prepare secrets payload for cluster",
        "order": 3,
    },
    {
        "id": "STP-4",
        "job_id": "JOB-402",
        "name": "4. Confirm access permissions & scopes",
        "order": 4,
    },
    {
        "id": "STP-5",
        "job_id": "JOB-402",
        "name": "5. Execute manual copy-paste into CI/CD secrets",
        "order": 5,
    },
    {
        "id": "STP-6",
        "job_id": "JOB-402",
        "name": "6. Monitor pipeline build for config missing errors",
        "order": 6,
    },
    {
        "id": "STP-7",
        "job_id": "JOB-402",
        "name": "7. Modify mismatched keys upon failed deploy",
        "order": 7,
    },
    {"id": "STP-8", "job_id": "JOB-402", "name": "8. Conclude deployment confirmation", "order": 8},
]

DEMO_OUTCOMES: list[dict[str, Any]] = [
    {
        "id": "O-1",
        "job_id": "JOB-402",
        "statement": "Minimize the time taken to propagate secrets across environments",
        "importance": 9.2,
        "satisfaction": 3.1,
        "opportunity_score": 15.3,
        "evidence": "Customer Call #104: 'Lost 2 hours on dev due to manual copy-paste drift breaking staging.'",
        "telemetry": "45 min average manual friction across 400 deployment pipelines.",
    },
    {
        "id": "O-2",
        "job_id": "JOB-402",
        "statement": "Minimize the likelihood of exposing plain-text keys in build logs",
        "importance": 9.8,
        "satisfaction": 4.5,
        "opportunity_score": 15.1,
        "evidence": "Security Audit Q3: '3 accidental developer log leaks detected in git diffs.'",
        "telemetry": "Severity High: Compliance blocker for SOC2.",
    },
    {
        "id": "O-3",
        "job_id": "JOB-402",
        "statement": "Minimize the effort required to rotate expired tokens in running pods",
        "importance": 8.0,
        "satisfaction": 7.2,
        "opportunity_score": 8.8,
        "evidence": "DevOps Slack: 'Token rotation works well enough when using kubesecret operator.'",
        "telemetry": "Appropriately served area — low innovation priority.",
    },
]


def seed_payload() -> dict[str, Any]:
    """Fresh copies of the seed prototype canvas."""
    return {
        "jobs": [dict(job) for job in DEMO_JOBS],
        "steps": [dict(step) for step in DEMO_STEPS],
        "outcomes": [dict(outcome) for outcome in DEMO_OUTCOMES],
    }
