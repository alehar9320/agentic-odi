def test_core_exports_service():
    import core
    assert hasattr(core, "ODIService")
