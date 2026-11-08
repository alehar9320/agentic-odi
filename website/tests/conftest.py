"""Make the website's build tools importable during collection."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO / "website" / "tools"))
# The artifact structural audit is repository tooling that ships in scripts/,
# and the site's pages are the artifacts it was written for.
sys.path.insert(0, str(REPO / "scripts"))
