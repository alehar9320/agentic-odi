from __future__ import annotations

import json
from typing import Any

import httpx
from agentic_odi_integrations_openhands.github_source import (
    GitHubClient,
    GitHubNotifier,
    GitHubSource,
)
from agentic_odi_integrations_openhands.models import (
    AgentRun,
    AgentRunStatus,
    AgentTarget,
    GitHubSettings,
    OrchestratorSettings,
    SourceKind,
    WorkItem,
    WorkItemStatus,
)
from agentic_odi_integrations_openhands.service import OrchestratorService
from agentic_odi_integrations_openhands.store import OrchestratorStore

REPO = "acme/repo"

ISSUES: list[dict[str, Any]] = [
    {
        "number": 7,
        "title": "Fix the README typo",
        "body": "The install section says `uv instal`.",
        "html_url": "https://github.test/acme/repo/issues/7",
        "labels": [{"name": "odi:autopilot"}],
    },
    {
        # Pull requests share the issues endpoint and must never be intake.
        "number": 8,
        "title": "A pull request",
        "html_url": "https://github.test/acme/repo/pull/8",
        "pull_request": {"url": "https://api.github.test/repos/acme/repo/pulls/8"},
        "labels": [],
    },
]


class FakeGitHub:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.issues: list[dict[str, Any]] = list(ISSUES)
        self.etag: str | None = '"etag-1"'
        self.release_etag = False
        self.fail_listing = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"null")
        self.calls.append(
            {
                "method": request.method,
                "path": request.url.path,
                "params": dict(request.url.params),
                "if_none_match": request.headers.get("if-none-match"),
                "body": body,
            }
        )
        if request.method == "GET" and request.url.path == f"/repos/{REPO}/issues":
            if self.fail_listing:
                return httpx.Response(500, text="boom")
            if self.etag and request.headers.get("if-none-match") == self.etag:
                return httpx.Response(304, headers={"etag": self.etag})
            headers = {"etag": self.etag} if self.etag else {}
            return httpx.Response(200, json=self.issues, headers=headers)
        return httpx.Response(200, json={})

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def paths(self, method: str) -> list[str]:
        return [call["path"] for call in self.calls if call["method"] == method]


def _service(
    tmp_path, github: FakeGitHub, *, max_concurrency: int = 0
) -> OrchestratorService:
    target = AgentTarget(
        alias="cloud", base_url="https://cloud.test", api_key="test-key", repository=REPO
    )
    settings = OrchestratorSettings(
        targets=[target],
        default_target="cloud",
        github=GitHubSettings(
            enabled=True,
            repos=[REPO],
            token_env="GITHUB_TOKEN",
            poll_interval_s=0,
        ),
        max_concurrency=max_concurrency,
        poll_interval_s=1,
    )
    transport = github.transport()
    source = GitHubSource(
        settings.github,
        client_factory=lambda: GitHubClient(
            "token",
            base_url="https://api.github.test",
            transport=transport,
        ),
    )
    return OrchestratorService(
        store=OrchestratorStore(tmp_path / "orch.db"),
        settings=settings,
        github_source=source,
    )


def test_tick_creates_one_work_item_per_labeled_issue(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    github = FakeGitHub()
    service = _service(tmp_path, github)

    report = service.tick()

    assert report.github_created == 1
    work = service.store.get_work_item_by_key(f"github:{REPO}#7")
    assert work is not None
    assert work.source_kind is SourceKind.GITHUB
    assert work.repository == REPO
    assert work.status is WorkItemStatus.QUEUED
    assert work.metadata["github_repo"] == REPO
    assert work.metadata["github_number"] == 7
    assert work.source_ref == "https://github.test/acme/repo/issues/7"
    assert "Fix the README typo" in work.prompt
    # The pull request was skipped and the running label was applied once.
    assert f"/repos/{REPO}/issues/8/labels" not in github.paths("POST")
    label_calls = [call for call in github.calls if call["path"] == f"/repos/{REPO}/issues/7/labels"]
    assert label_calls[-1]["body"] == {"labels": ["odi:running"]}


def test_second_tick_is_idempotent_even_without_an_etag(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    github = FakeGitHub()
    github.etag = None  # force a full 200 on every poll
    service = _service(tmp_path, github)

    first = service.tick()
    second = service.tick()

    assert first.github_created == 1
    assert second.github_created == 0
    items = [work for work in service.list_work_items() if work.source_kind is SourceKind.GITHUB]
    assert len(items) == 1


def test_etag_304_skips_listing_without_creating_work(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    github = FakeGitHub()
    service = _service(tmp_path, github)

    service.tick()
    report = service.tick()

    assert report.github_created == 0
    listings = [
        call
        for call in github.calls
        if call["method"] == "GET" and call["path"] == f"/repos/{REPO}/issues"
    ]
    assert len(listings) == 2
    assert listings[1]["if_none_match"] == '"etag-1"'


def test_tick_reports_github_failure_without_crashing(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    github = FakeGitHub()
    github.fail_listing = True
    service = _service(tmp_path, github)

    report = service.tick()

    assert report.github_created == 0
    assert any(error.startswith("github:") for error in report.errors)


def test_missing_token_is_a_reported_error_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    github = FakeGitHub()
    service = _service(tmp_path, github)

    report = service.tick()

    assert report.github_created == 0
    assert any("GITHUB_TOKEN" in error for error in report.errors)
    assert github.calls == []


def test_notifier_labels_and_comments_once_with_the_real_result(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    github = FakeGitHub()
    notifier = GitHubNotifier(
        GitHubSettings(enabled=True, repos=[REPO]),
        client_factory=lambda: GitHubClient(
            "token", base_url="https://api.github.test", transport=github.transport()
        ),
    )
    work = WorkItem(
        work_key=f"github:{REPO}#7",
        source_kind=SourceKind.GITHUB,
        title="Fix the README typo",
        prompt="do it",
        target_alias="cloud",
        metadata={"github_repo": REPO, "github_number": 7},
    )
    run = AgentRun(
        work_item_id=work.id,
        attempt=1,
        status=AgentRunStatus.COMPLETED,
        summary="Updated the install command.",
        pr_urls=["https://github.test/acme/repo/pull/9"],
        conversation_url="https://cloud.test/conversations/c-1",
    )

    notifier.notify_terminal(work, run)

    assert f"/repos/{REPO}/issues/7/labels/odi:running" in github.paths("DELETE")
    added = [call for call in github.calls if call["method"] == "POST" and call["path"].endswith("/labels")]
    assert added[-1]["body"] == {"labels": ["odi:done"]}
    comment = [call for call in github.calls if call["path"].endswith("/comments")][-1]
    body = comment["body"]["body"]
    assert "Pull request: https://github.test/acme/repo/pull/9" in body
    assert "https://cloud.test/conversations/c-1" in body
    assert "session" not in body.lower()


def test_notifier_uses_failed_label_for_blocked_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    github = FakeGitHub()
    notifier = GitHubNotifier(
        GitHubSettings(enabled=True, repos=[REPO]),
        client_factory=lambda: GitHubClient(
            "token", base_url="https://api.github.test", transport=github.transport()
        ),
    )
    work = WorkItem(
        work_key=f"github:{REPO}#7",
        source_kind=SourceKind.GITHUB,
        title="t",
        prompt="p",
        target_alias="cloud",
        metadata={"github_repo": REPO, "github_number": 7},
    )
    run = AgentRun(
        work_item_id=work.id,
        attempt=1,
        status=AgentRunStatus.BLOCKED,
        blocked_reason="risky action",
    )

    notifier.notify_terminal(work, run)

    added = [call for call in github.calls if call["method"] == "POST" and call["path"].endswith("/labels")]
    assert added[-1]["body"] == {"labels": ["odi:blocked"]}
