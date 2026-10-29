# website/tests/test_pages_deploy.py
"""Deployment contract for the GitHub Pages site.

Pages is configured with ``build_type: workflow``, so the only thing that
publishes the site is a workflow that uploads the built artifact and deploys
it. When that workflow was removed, every check kept passing while
https://alehar9320.github.io/agentic-odi/ returned 404. These assertions keep
the publish path from disappearing again.

The site is generated, so CI builds it and uploads the artifact for review;
Pages builds and deploys it. There is no committed copy to drift.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _workflow() -> str:
    assert WORKFLOW.is_file(), (
        "missing .github/workflows/pages.yml: GitHub Pages deploys from a workflow, "
        "so without it https://alehar9320.github.io/agentic-odi/ 404s"
    )
    return WORKFLOW.read_text(encoding="utf-8")


def _ci_workflow() -> str:
    assert CI_WORKFLOW.is_file(), "missing .github/workflows/ci.yml"
    return CI_WORKFLOW.read_text(encoding="utf-8")


def test_runs_on_push_to_main_and_on_demand() -> None:
    text = _workflow()
    assert "push:" in text
    assert "branches: [main]" in text
    assert "workflow_dispatch:" in text


def test_grants_pages_and_oidc_permissions() -> None:
    text = _workflow()
    assert "pages: write" in text
    assert "id-token: write" in text


def test_uploads_and_deploys_the_built_site() -> None:
    text = _workflow()
    assert "actions/upload-pages-artifact@" in text
    assert "actions/deploy-pages@" in text
    assert "build_site.py --out _site" in text


def test_the_published_site_is_built_from_source() -> None:
    # The published site is generated, so it is built from the repository's
    # sources at deploy time rather than copied from a committed folder that
    # could be stale.
    text = _workflow()
    assert "rsync" not in text, "the site is generated; it must be built, not copied"


def test_the_site_is_built_before_it_is_uploaded() -> None:
    text = _workflow()
    build = text.index("build_site.py")
    upload = text.index("upload-pages-artifact")
    assert build < upload, "the site must be built before the artifact is uploaded"


def test_the_workflow_verifies_the_site_before_it_publishes() -> None:
    text = _workflow()
    assert "pytest" in text
    verify = text.index("pytest")
    build = text.index("build_site.py")
    assert verify < build, "a broken site must never be published"


def test_ci_builds_the_site_from_source() -> None:
    text = _ci_workflow()
    assert "build_site.py --out _site" in text


def test_ci_uploads_the_built_site_for_review() -> None:
    text = _ci_workflow()
    assert "actions/upload-artifact@" in text
    assert "path: _site" in text


def test_ci_does_not_gate_on_committed_output() -> None:
    text = _ci_workflow()
    assert "build_site.py --check" not in text


def test_ci_never_publishes_the_site() -> None:
    text = _ci_workflow()
    assert "deploy-pages" not in text, "only the Pages workflow may deploy the site"
