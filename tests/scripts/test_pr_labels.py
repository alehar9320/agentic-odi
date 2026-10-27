from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from pr_labels import (
    MANAGED_LABELS,
    build_facts,
    compute_labels,
    domain_labels,
    is_dependency_change,
    size_label,
    telemetry_labels,
)
from pr_provenance import classify


@pytest.mark.parametrize(
    "additions,deletions,expected",
    [
        (0, 0, "size/XS"),
        (49, 0, "size/XS"),
        (50, 0, "size/S"),
        (249, 0, "size/S"),
        (250, 0, "size/M"),
        (799, 0, "size/M"),
        (800, 0, "size/L"),
        (1999, 0, "size/L"),
        (2000, 0, "size/XL"),
        (400, 400, "size/L"),
    ],
)
def test_size_label_boundaries(additions, deletions, expected):
    assert size_label(additions, deletions) == expected


@pytest.mark.parametrize(
    "paths,expected",
    [
        (["apps/studio/src/App.tsx"], {"area/studio"}),
        (["apps/studio-api/main.py"], {"area/studio"}),
        (["apps/cli/main.py"], {"area/cli"}),
        (["apps/mcp-server/server.py"], {"area/mcp"}),
        (["packages/core/src/x.py"], {"area/core"}),
        (["packages/connectors/slack.py"], {"area/connectors"}),
        (["website/tools/build_site.py"], {"area/website"}),
        (["brand/src/otter.py"], {"area/brand"}),
        (["packaging/build.sh"], {"area/release"}),
        (["scripts/dev.py"], {"area/release"}),
        (["infra/cloudflare/worker.js"], {"area/infra"}),
        (["wrangler.jsonc"], {"area/infra"}),
        ([".github/workflows/ci.yml"], {"area/ci"}),
        (["README.md"], {"area/docs"}),
        (["docs/development.md"], {"area/docs"}),
        # Additive, not exclusive.
        (["docs/readme.md", "website/index.html"], {"area/docs", "area/website"}),
        # Unknown paths produce nothing rather than a bogus label.
        (["Makefile"], set()),
    ],
)
def test_domain_labels(paths, expected):
    assert domain_labels(paths) == expected


@pytest.mark.parametrize(
    "paths",
    [
        ["package.json"],
        ["package-lock.json"],
        ["pnpm-lock.yaml"],
        ["yarn.lock"],
        ["requirements.txt"],
        ["pyproject.toml"],
        ["uv.lock"],
        ["Cargo.toml"],
        ["go.sum"],
        ["apps/studio/package-lock.json"],
    ],
)
def test_dependency_changes_are_detected(paths):
    assert is_dependency_change(paths) is True


def test_source_only_changes_are_not_dependency_changes():
    assert is_dependency_change(["apps/studio/src/App.tsx", "README.md"]) is False


def test_managed_labels_never_include_labels_another_job_owns():
    """The labels job must not remove the risk tier the risk job just applied."""
    assert not MANAGED_LABELS & {"safe to merge", "needs a look", "danger zone"}
    assert not MANAGED_LABELS & {"ready-for-merge", "merge-conflict"}


def test_managed_labels_cover_every_axis_this_system_owns():
    assert {
        "🤖 agent",
        "👤 human",
        "size/XS",
        "size/S",
        "size/M",
        "size/L",
        "size/XL",
        "dependencies",
        "breaking change",
        "needs deep dive",
        "telemetry invalid",
        "area/studio",
        "area/cli",
        "area/mcp",
        "area/core",
        "area/connectors",
        "area/website",
        "area/brand",
        "area/release",
        "area/infra",
        "area/ci",
        "area/docs",
    } == MANAGED_LABELS


BREAKING = '<!-- AGENT_METADATA {"has_breaking_changes": true} -->'
LOW_CONF = '<!-- AGENT_METADATA {"agent_confidence": "low"} -->'
MULTILINE = '<!-- AGENT_METADATA\n{"has_breaking_changes": true, "agent_confidence": "low"}\n-->'


def test_a_breaking_change_is_flagged():
    assert telemetry_labels(BREAKING) == {"breaking change"}


def test_low_confidence_asks_for_a_deep_dive():
    assert telemetry_labels(LOW_CONF) == {"needs deep dive"}


def test_a_multiline_block_parses():
    assert telemetry_labels(MULTILINE) == {"breaking change", "needs deep dive"}


def test_a_false_breaking_change_is_not_flagged():
    assert telemetry_labels('<!-- AGENT_METADATA {"has_breaking_changes": false} -->') == set()


def test_absent_metadata_is_not_an_error():
    assert telemetry_labels(None) == set()
    assert telemetry_labels("") == set()
    assert telemetry_labels("Just a normal PR body.") == set()


@pytest.mark.parametrize(
    "body",
    [
        "<!-- AGENT_METADATA {not json} -->",
        "<!-- AGENT_METADATA { -->",
        "<!-- AGENT_METADATA true -->",
        '<!-- AGENT_METADATA "a string" -->',
    ],
)
def test_malformed_metadata_is_flagged_and_never_raises(body):
    assert telemetry_labels(body) == {"telemetry invalid"}


@pytest.mark.parametrize(
    "payload",
    [
        '{"agent_confidence": "yes"}',
        '{"has_breaking_changes": 1}',
        '{"has_breaking_changes": null}',
        '{"agent_confidence": null}',
        '{"unrelated": true}',
    ],
)
def test_wrongly_typed_values_are_ignored(payload):
    assert telemetry_labels(f"<!-- AGENT_METADATA {payload} -->") == set()


def test_compute_labels_combines_every_axis():
    facts = {
        "author": {"login": "alehar9320", "type": "User"},
        "branch": "slay/abc-promote-evidence",
        "commits": [],
        "body": BREAKING,
        "files": [{"filename": "package-lock.json", "additions": 20, "deletions": 5}],
    }
    assert compute_labels(facts) == {"🤖 agent", "size/XS", "dependencies", "breaking change"}


def test_compute_labels_survives_an_empty_pr():
    facts = {"author": {"login": "x", "type": "User"}, "branch": "fix/y", "files": []}
    assert compute_labels(facts) == {"👤 human", "size/XS"}


def test_compute_labels_tolerates_missing_keys():
    assert compute_labels({}) == {"👤 human", "size/XS"}


def test_the_cli_runs_as_a_script():
    """The workflow invokes this file directly, so __main__ must call main().

    Without this the workflow would apply zero labels and still exit 0 — the
    same silent failure this work exists to remove.
    """
    script = Path(__file__).resolve().parents[2] / "scripts" / "pr_labels.py"
    managed = subprocess.run(
        [sys.executable, str(script), "--managed"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert managed.returncode == 0, managed.stderr
    assert set(managed.stdout.splitlines()) == MANAGED_LABELS

    computed = subprocess.run(
        [sys.executable, str(script)],
        input='{"author": {"login": "x", "type": "User"}, "branch": "fix/y", "files": []}',
        capture_output=True,
        text=True,
        check=False,
    )
    assert computed.returncode == 0, computed.stderr
    assert set(computed.stdout.splitlines()) == {"👤 human", "size/XS"}


def test_the_cli_fails_loudly_on_unreadable_input():
    script = Path(__file__).resolve().parents[2] / "scripts" / "pr_labels.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        input="not json",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "could not read" in result.stderr


def test_build_facts_flattens_paginated_pages():
    """gh --paginate --slurp returns an array of pages, not one flat array.

    Reading only the first page would silently under-count size on a large PR.
    """
    meta = {"author": {"login": "a", "type": "User"}, "body": "x", "headRefName": "slay/y"}
    commits = [
        [{"commit": {"author": {"name": "A", "email": "a@x"}}}],
        [{"commit": {"author": {"name": "B", "email": "b@x"}}}],
    ]
    files = [
        [{"filename": "a.py", "additions": 1, "deletions": 2}],
        [{"filename": "b.py", "additions": 3, "deletions": 4}],
    ]
    facts = build_facts(meta, commits, files)
    assert facts["branch"] == "slay/y"
    assert facts["commits"] == ["A <a@x>", "B <b@x>"]
    assert [f["filename"] for f in facts["files"]] == ["a.py", "b.py"]
    assert "size/XS" in compute_labels(facts)


def test_build_facts_accepts_unpaginated_single_page_shape():
    """A single page may arrive either flat or wrapped."""
    meta = {"author": {"login": "a", "type": "User"}}
    flat_commits = [{"commit": {"author": {"name": "A", "email": "a@x"}}}]
    flat_files = [{"filename": "a.py", "additions": 10, "deletions": 0}]
    facts = build_facts(meta, flat_commits, flat_files)
    assert facts["commits"] == ["A <a@x>"]
    assert facts["files"] == [{"filename": "a.py", "additions": 10, "deletions": 0}]


def test_build_facts_keeps_every_file_past_one_page():
    meta = {"author": {"login": "a", "type": "User"}}
    page = [{"filename": f"f{i}.py", "additions": 1, "deletions": 0} for i in range(100)]
    facts = build_facts(meta, [], [page, page])
    assert len(facts["files"]) == 200


def test_build_facts_tolerates_missing_and_odd_entries():
    assert build_facts({}, [], []) == {
        "author": {},
        "branch": "",
        "body": "",
        "commits": [],
        "files": [],
    }
    facts = build_facts(
        {"author": None, "headRefName": None, "body": None},
        [{"commit": {"author": {}}}],
        [{"filename": "a.py"}],
    )
    assert facts["author"] == {}
    assert facts["branch"] == ""
    assert facts["body"] == ""
    assert facts["commits"] == [" <>"]
    assert facts["files"] == [{"filename": "a.py", "additions": 0, "deletions": 0}]


def test_build_facts_maps_is_bot_to_the_bot_type():
    """gh pr view --json author returns is_bot, not the REST API's type field.

    Reading only `type` left provenance blind to the PR author entirely.
    """
    facts = build_facts({"author": {"login": "some-app", "is_bot": True}}, [], [])
    assert facts["author"]["type"] == "Bot"
    assert classify(facts["author"]["login"], facts["author"]["type"], "", []) == "🤖 agent"


def test_build_facts_preserves_a_real_type_field():
    facts = build_facts({"author": {"login": "x", "type": "Bot", "is_bot": False}}, [], [])
    assert facts["author"]["type"] == "Bot"
