"""GitHub issue tracker adapter implementing IssueTrackerPort.

Fetches open issues labelled for ODI autopilot intake from configured
repositories. Never uses the ``gh`` binary; speaks the GitHub REST API
directly so tests can substitute ``httpx.MockTransport``.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx

from agentic_odi_integrations_openhands.models import GitHubSettings
from agentic_odi_integrations_openhands.ports import Issue, IssueTrackerPort

GITHUB_API = "https://api.github.com"
_API_VERSION = "2022-11-28"
_ODI_LABEL = "odi:autopilot"


class GitHubIssueTracker(IssueTrackerPort):
    """Poll GitHub issues for ODI autopilot intake."""

    def __init__(
        self,
        settings: GitHubSettings,
        *,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.settings = settings
        token = os.environ.get(settings.token_env) or ""
        self._client = client or httpx.Client(timeout=timeout, transport=transport)
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": _API_VERSION,
        }

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {**self._headers, **kwargs.pop("headers", {})}
        response = self._client.request(
            method, f"{GITHUB_API}{path}", headers=headers, **kwargs
        )
        if response.status_code == 401:
            raise RuntimeError("GitHub rejected the token (401)")
        if response.status_code == 403 and "rate limit" in response.text.lower():
            raise RuntimeError("GitHub rate limit reached")
        if response.status_code >= 400:
            raise RuntimeError(
                f"GitHub {method} {path} returned {response.status_code}"
            )
        return response

    def due_issues(self, since: datetime | None = None) -> list[Issue]:
        """Return open ODI-labelled issues updated since ``since``."""
        issues: list[Issue] = []
        for repo in self.settings.repos:
            params: dict[str, Any] = {
                "state": "open",
                "labels": _ODI_LABEL,
                "sort": "updated",
                "direction": "desc",
                "per_page": 100,
            }
            if since is not None:
                params["since"] = since.astimezone(timezone.utc).isoformat()
            try:
                resp = self._request(
                    "GET", f"/repos/{repo}/issues", params=params
                )
            except RuntimeError:
                continue
            for item in resp.json():
                issues.append(
                    Issue(
                        id=f"{repo}#{item['number']}",
                        number=item["number"],
                        title=item["title"],
                        body=item.get("body") or "",
                        url=item["html_url"],
                        repository=repo,
                        state=item["state"],
                        created_at=datetime.fromisoformat(
                            item["created_at"].replace("Z", "+00:00")
                        ),
                        updated_at=datetime.fromisoformat(
                            item["updated_at"].replace("Z", "+00:00")
                        ),
                        labels=[lab["name"] for lab in item.get("labels", [])],
                    )
                )
        return issues
