# website/tests/test_pages_deploy.py
"""Deployment contract for the GitHub Pages site.

Pages is configured with ``build_type: workflow``, so the only thing that
publishes ``website/`` is a workflow that uploads the built site and deploys the
artifact. When that workflow was removed, every check kept passing while
https://alehar9320.github.io/agentic-odi/ returned 404. These assertions keep
the publish path from disappearing again.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"


def _workflow() -> str:
    assert WORKFLOW.is_file(), (
        "missing .github/workflows/pages.yml: GitHub Pages deploys from a workflow, "
        "so without it https://alehar9320.github.io/agentic-odi/ 404s"
    )
    return WORKFLOW.read_text(encoding="utf-8")


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
    assert "website/ _site/" in text
