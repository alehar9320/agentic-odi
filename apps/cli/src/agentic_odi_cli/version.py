"""Version information."""

from agentic_odi_cli._build_info import COMMIT, TARGET, VERSION
from agentic_odi_cli._build_info import RELEASE_DATE_UTC as _RELEASE_DATE_UTC

__version__ = VERSION
RELEASE_DATE_UTC = _RELEASE_DATE_UTC
COMMIT = COMMIT
TARGET = TARGET
release_date = RELEASE_DATE_UTC or None


def build_summary() -> str:
    if RELEASE_DATE_UTC:
        return f"{VERSION} ({RELEASE_DATE_UTC[:10]})"
    return VERSION


def verbose_summary() -> str:
    return f"{build_summary()}\ncommit: {COMMIT}\ntarget: {TARGET}"
