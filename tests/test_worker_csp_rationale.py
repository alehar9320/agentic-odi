"""The one relaxed CSP directive carries a recorded reason, and stays the only one.

`style-src` allows `'unsafe-inline'` because React's `style` prop needs it. That
allowance is easy to inherit silently and impossible to remove on a hunch, so the
source must say what depends on it, and no script directive may ever join it.
"""

from __future__ import annotations

import re
from pathlib import Path

WORKER = Path(__file__).resolve().parents[1] / "infra" / "cloudflare" / "worker.ts"


def _source() -> str:
    return WORKER.read_text(encoding="utf-8")


def _csp_block(source: str) -> str:
    """The CSP directive array, from its opening bracket to the `.join`."""
    start = source.index('"Content-Security-Policy": [')
    end = source.index(".join(", start)
    return source[start:end]


def test_the_inline_style_allowance_is_declared() -> None:
    assert "\"style-src 'self' 'unsafe-inline'\"" in _csp_block(_source())


def test_the_inline_style_allowance_names_its_dependency() -> None:
    source = _source()
    start = source.index('"Content-Security-Policy": [')
    # The comment sits immediately above the returned header map, inside
    # `securityHeaders`; read back from the directive array to the function head.
    head = source.rindex("function securityHeaders", 0, start)
    rationale = source[head:start]
    assert "React" in rationale, (
        "the `style-src 'unsafe-inline'` allowance must name the React `style` "
        "prop as its dependency; without that note nobody can decide whether "
        "the relaxation is still needed"
    )


def test_scripts_are_never_relaxed() -> None:
    block = _csp_block(_source())
    script_directives = re.findall(r'"script-src[^"]*"', block)
    assert script_directives == ["\"script-src 'self'\""], (
        "script-src must stay `'self'`; `'unsafe-inline'` on scripts would "
        "undo the CSP for the whole Studio"
    )
    assert "'unsafe-inline'" not in "".join(
        directive
        for directive in re.findall(r'"[^"]*-src[^"]*"', block)
        if "style-src" not in directive
    ), "only style-src may carry 'unsafe-inline'"
