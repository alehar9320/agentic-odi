# website/tests/test_sync_readme.py
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "website"
TOOLS = ROOT / "website" / "tools"


def _get_index_html():
    return (SITE / "index.html").read_text(encoding="utf-8")


def test_script_idempotency():
    """Running the sync script twice produces identical output."""
    import subprocess

    result1 = subprocess.run(
        ["uv", "run", "python", "website/tools/sync-readme.py"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result1.returncode == 0, f"First run failed: {result1.stderr}"

    html1 = _get_index_html()

    result2 = subprocess.run(
        ["uv", "run", "python", "website/tools/sync-readme.py"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result2.returncode == 0, f"Second run failed: {result2.stderr}"

    html2 = _get_index_html()

    assert html1 == html2, "Sync script is not idempotent — output differs between runs"


def test_generated_has_social_meta_tags():
    """The generated index.html contains all required social meta tags."""
    text = _get_index_html()

    checks = [
        ('<meta property="og:type" content="website">', "og:type"),
        ('<meta property="og:site_name" content="Agentic ODI">', "og:site_name"),
        ('<meta property="og:title"', "og:title"),
        ('<meta property="og:description"', "og:description"),
        ('<meta property="og:url" content="https://alehar9320.github.io/agentic-odi/">', "og:url"),
        (
            '<meta property="og:image" content="https://alehar9320.github.io/agentic-odi/assets/og.png">',
            "og:image",
        ),
        ('<meta name="twitter:card" content="summary_large_image">', "twitter:card"),
        ('<meta name="twitter:title"', "twitter:title"),
        ('<meta name="twitter:description"', "twitter:description"),
        (
            '<meta name="twitter:image" content="https://alehar9320.github.io/agentic-odi/assets/og.png">',
            "twitter:image",
        ),
    ]

    for pattern, key in checks:
        assert pattern in text, f"Missing {key} meta tag"


def test_generated_has_honesty_contract():
    """The generated index.html contains all honesty contract strings."""
    text = _get_index_html()
    low = text.lower()

    required = [
        "experimental",
        "free prefect account",
        "all rights reserved",
        "strategyn",
        "your roadmap is a guess.",
        "we don't publish dates",
        "open an issue",
        "http://localhost:8000/mcp",
    ]

    for string in required:
        assert string in low, f"Missing honesty contract string: {string!r}"
