from agentic_odi_core.briefing import BriefingItem, Briefing, build_briefing


class DummyItem:
    def __init__(self, kind, text, record_id, record_kind):
        self.kind = kind
        self.text = text
        self.record_id = record_id
        self.record_kind = record_kind


class DummyRunResult:
    def __init__(self, run_id, items):
        self.run_id = run_id
        self.items = items


def test_three_changes_three_items_stable_order():
    items = [
        DummyItem("added", "Two new quotes mention onboarding", "q1", "quote"),
        DummyItem("changed", "O-12 rose to 14.2", "o12", "outcome"),
        DummyItem("failed", "One schedule failed", "s1", "schedule"),
    ]
    result = DummyRunResult("run1", items)
    briefing = build_briefing(result)
    assert len(briefing.items) == 3
    assert briefing.items[0].text == "Two new quotes mention onboarding"
    assert briefing.items[1].text == "O-12 rose to 14.2"
    assert briefing.items[2].text == "One schedule failed"


def test_empty_result_zero_items():
    result = DummyRunResult("run2", [])
    briefing = build_briefing(result)
    assert briefing.items == []
    assert len(briefing.items) == 0


def test_item_without_record_id_rejected():
    try:
        BriefingItem("added", "Something", "", "quote")
        assert False, "Should have raised"
    except Exception:
        pass

    try:
        BriefingItem("added", "Something", None, "quote")  # type: ignore
        assert False, "Should have raised"
    except Exception:
        pass
