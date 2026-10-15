from cli import version


def test_version_matches_build_info():
    from cli import _build_info

    assert version.__version__ == _build_info.VERSION
    assert version.__version__ == "0.1.0"


def test_build_summary_omits_date_when_empty(monkeypatch):
    monkeypatch.setattr(version, "RELEASE_DATE_UTC", "")
    assert version.build_summary() == "0.1.0"


def test_build_summary_includes_date_when_set(monkeypatch):
    monkeypatch.setattr(version, "RELEASE_DATE_UTC", "2026-10-15T21:13:00Z")
    assert version.build_summary() == "0.1.0 (2026-10-15)"
