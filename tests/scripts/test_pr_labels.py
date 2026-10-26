from __future__ import annotations

import pytest
from pr_labels import (
    MANAGED_LABELS,
    domain_labels,
    is_dependency_change,
    size_label,
)


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
