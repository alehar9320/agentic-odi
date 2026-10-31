"""GitHub issue intake and terminal reporting.

Opt-in by label and by repository. The source never uses the ``gh`` binary at
runtime; it speaks the REST API directly so the daemon has one HTTP stack and
tests can substitute ``httpx.MockTransport``.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from agentic_odi_integrations_openhands.models import (
    AgentRun,
    AgentRunStatus,
    GitHubSettings,
    SourceKind,
    WorkItem,
)

GITHUB_API = "https://api.github.com"
_API_VERSION = "2022-11-28"


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(
        self,
        token: str,
        *,
        base_url: str = GITHUB_API,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
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
        response = self._client.request(method, f"{self.base_url}{path}", headers=headers, **kwargs)
        if response.status_code == 401:
            raise GitHubError("GitHub rejected the token (401)")
        if response.status_code == 403 and "rate limit" in response.text.lower():
            raise GitHubError("GitHub rate limit reached")
        if response.status_code >= 400:
            raise GitHubError(f"GitHub {method} {path} returned {response.status_code}")
        return response

    def list_issues(
        self, repo: str, label: str, etag: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None, bool]:
        headers = {"If-None-Match": etag} if etag else {}
        response = self._client.request(
            "GET",
            f"{self.base_url}/repos/{repo}/issues",
            headers={**self._headers, **headers},
            params={"labels": label, "state": "open", "per_page": 50},
        )
        if response.status_code == 304:
            return [], etag, True
        if response.status_code >= 400:
            raise GitHubError(f"GitHub issue listing returned {response.status_code}")
        payload = response.json()
        issues = (
            [item for item in payload if isinstance(item, dict)]
            if isinstance(payload, list)
            else []
        )
        return issues, response.headers.get("etag"), False

    def add_labels(self, repo: str, number: int, labels: list[str]) -> None:
        self._request("POST", f"/repos/{repo}/issues/{number}/labels", json={"labels": labels})

    def remove_label(self, repo: str, number: int, label: str) -> None:
        self._request("DELETE", f"/repos/{repo}/issues/{number}/labels/{label}")

    def comment(self, repo: str, number: int, body: str) -> None:
        self._request("POST", f"/repos/{repo}/issues/{number}/comments", json={"body": body})


def _token(settings: GitHubSettings) -> str | None:
    return os.environ.get(settings.token_env)


class GitHubSource:
    """Poll labeled issues and enqueue one work item per issue."""

    def __init__(
        self,
        settings: GitHubSettings,
        client_factory: Any | None = None,
    ) -> None:
        self.settings = settings
        self._client_factory = client_factory or (lambda: GitHubClient(_token(settings) or ""))
        self._etags: dict[str, str | None] = {}
        self._polled_at: dict[str, float] = {}

    def poll(self, service: Any, now_epoch: float) -> int:
        if not self.settings.enabled or not self.settings.repos:
            return 0
        token = _token(self.settings)
        if not token:
            raise GitHubError(f"GitHub intake is enabled but {self.settings.token_env} is not set")
        created = 0
        client = self._client_factory()
        try:
            for repo in self.settings.repos:
                last = self._polled_at.get(repo, 0.0)
                if now_epoch - last < self.settings.poll_interval_s:
                    continue
                issues, etag, not_modified = client.list_issues(
                    repo, self.settings.label, self._etags.get(repo)
                )
                self._etags[repo] = etag
                self._polled_at[repo] = now_epoch
                if not_modified:
                    continue
                for issue in issues:
                    if "pull_request" in issue:
                        continue
                    number = issue.get("number")
                    title = str(issue.get("title") or "").strip()
                    if not isinstance(number, int) or not title:
                        continue
                    work_key = f"github:{repo}#{number}"
                    if service.store.get_work_item_by_key(work_key) is not None:
                        continue
                    body = str(issue.get("body") or "").strip()
                    prompt = (
                        f"GitHub issue {repo}#{number}: {title}\n\n{body}\n\n"
                        "Implement the change requested by this issue. Keep the change "
                        "scoped to the repository and follow its existing conventions."
                    ).strip()
                    work, was_created = service.add_work_item(
                        f"{repo}#{number}: {title}",
                        prompt,
                        repository=repo,
                        work_key=work_key,
                        source_kind=SourceKind.GITHUB,
                        source_ref=str(issue.get("html_url") or ""),
                        metadata={
                            "github_repo": repo,
                            "github_number": number,
                            "github_url": issue.get("html_url"),
                            "labels": [
                                label.get("name")
                                for label in issue.get("labels", [])
                                if isinstance(label, dict)
                            ],
                        },
                    )
                    if not was_created:
                        continue
                    created += 1
                    try:
                        client.add_labels(repo, number, [self.settings.running_label])
                    except GitHubError:
                        pass
                    del work
        finally:
            client.close()
        return created


class GitHubNotifier:
    """Mirror a terminal run back to the issue with one comment and labels."""

    def __init__(self, settings: GitHubSettings, client_factory: Any | None = None) -> None:
        self.settings = settings
        self._client_factory = client_factory or (lambda: GitHubClient(_token(settings) or ""))

    def notify_terminal(self, work: WorkItem, run: AgentRun) -> None:
        repo = work.metadata.get("github_repo")
        number = work.metadata.get("github_number")
        if not isinstance(repo, str) or not isinstance(number, int):
            return
        token = _token(self.settings)
        if not token:
            return
        label = {
            AgentRunStatus.COMPLETED: self.settings.done_label,
            AgentRunStatus.FAILED: self.settings.failed_label,
            AgentRunStatus.BLOCKED: self.settings.blocked_label,
            AgentRunStatus.CANCELLED: self.settings.failed_label,
        }.get(run.status, self.settings.failed_label)
        lines = [
            f"**ODI orchestrator:** `{run.status.value}`",
            "",
        ]
        if run.summary:
            lines.append(run.summary.strip())
        if run.pr_urls:
            lines.append("")
            lines.append("Pull request: " + ", ".join(run.pr_urls))
        if run.error:
            lines.append("")
            lines.append(f"Error: {run.error}")
        if run.blocked_reason:
            lines.append("")
            lines.append(f"Blocked: {run.blocked_reason}")
        if run.conversation_url:
            lines.append("")
            lines.append(f"Conversation: {run.conversation_url}")
        body = "\n".join(lines)
        client = self._client_factory()
        try:
            try:
                client.remove_label(repo, number, self.settings.running_label)
            except GitHubError:
                pass
            try:
                client.add_labels(repo, number, [label])
            except GitHubError:
                pass
            try:
                client.comment(repo, number, body)
            except GitHubError:
                pass
        finally:
            client.close()
