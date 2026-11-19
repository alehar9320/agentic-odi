"""The claim contract: a sentence carries a record or says it does not."""

from __future__ import annotations

import pytest
from agentic_odi_studio_api.studio.claims import (
    MAX_EVIDENCE_PER_CLAIM,
    UNKNOWN_EVIDENCE_ID,
    EvidenceIndex,
    EvidenceSnapshot,
    split_claims,
)

#: Every abbreviation added for corporate suffixes (#1179). Each entry must keep
#: the sentence it appears in whole, so one case per entry is generated below.
CORPORATE_SUFFIXES = [
    "ag",
    "assn",
    "bv",
    "co",
    "corp",
    "dept",
    "esq",
    "gmbh",
    "inc",
    "jr",
    "llc",
    "ltd",
    "plc",
    "pty",
    "sa",
    "sr",
    "univ",
]


def _index(*records: tuple[str, str, str]) -> EvidenceIndex:
    index = EvidenceIndex()
    for identifier, name, source_name in records:
        index.remember(EvidenceSnapshot(identifier, name, source_name))
    return index


def test_a_reply_with_no_markers_is_uncited_not_dropped() -> None:
    claims = split_claims("Customers want faster imports. The export is slow.")

    assert [claim.status for claim in claims] == ["uncited", "uncited"]
    assert [claim.index for claim in claims] == [0, 1]
    assert claims[0].text == "Customers want faster imports."
    assert claims[0].reason is None


def test_a_cited_sentence_carries_its_snapshot_and_hides_the_marker() -> None:
    claims = split_claims(
        "Three accounts stalled. [[ev:E-1]]",
        _index(("E-1", "Call with Acme", "Gong")),
    )

    assert len(claims) == 1
    claim = claims[0]
    assert claim.text == "Three accounts stalled."
    assert claim.status == "cited"
    assert [snapshot.to_dict() for snapshot in claim.evidence] == [
        {"id": "E-1", "name": "Call with Acme", "source_name": "Gong"}
    ]


def test_one_sentence_may_cite_several_records_up_to_the_cap() -> None:
    index = _index(
        ("A", "First call", "Gong"),
        ("B", "Second call", "Gong"),
        ("C", "Third call", "Gong"),
        ("D", "Fourth call", "Gong"),
    )

    claims = split_claims("They agree on the invite step. [[ev:A,B,C,D]]", index)

    assert claims[0].status == "cited"
    assert [snapshot.id for snapshot in claims[0].evidence] == ["A", "B", "C"]
    assert len(claims[0].evidence) == MAX_EVIDENCE_PER_CLAIM


def test_an_id_the_turn_never_received_becomes_uncited_with_a_reason() -> None:
    claims = split_claims("They churned. [[ev:E-9]]", _index(("E-1", "Call", "Gong")))

    assert claims[0].status == "uncited"
    assert claims[0].reason == UNKNOWN_EVIDENCE_ID
    assert claims[0].evidence == ()


def test_a_hypothesis_is_tagged_and_carries_no_record() -> None:
    claims = split_claims(
        "Nobody said the invite step is the problem. [[hypothesis]]",
        _index(("E-1", "Call", "Gong")),
    )

    assert claims[0].status == "hypothesis"
    assert claims[0].evidence == ()
    assert "[[" not in claims[0].text


def test_a_marker_inside_code_is_literal_and_creates_no_claim() -> None:
    claims = split_claims("The syntax is `[[ev:E-1]]` in prose. Use it once.", _index())

    assert [claim.status for claim in claims] == ["uncited"]
    assert "[[ev:E-1]]" in claims[0].text


def test_a_marker_inside_a_fence_is_literal() -> None:
    text = "Example:\n```\n[[ev:E-1]]\n```\nNothing else."

    claims = split_claims(text, _index(("E-1", "Call", "Gong")))

    assert [claim.status for claim in claims] == ["uncited", "uncited"]
    assert all("E-1" not in claim.text for claim in claims)


def test_headings_and_questions_make_no_claim() -> None:
    claims = split_claims("### What customers said\nWhat did they say?\n")

    assert claims == []


def test_an_instruction_makes_no_claim() -> None:
    assert split_claims("Open the Evidence lens.") == []


def test_a_list_item_is_one_claim() -> None:
    claims = split_claims("- Stalled accounts. And more of them.")

    assert [claim.text for claim in claims] == [
        "Stalled accounts.",
        "And more of them.",
    ]
    assert [claim.index for claim in claims] == [0, 1]


def test_a_two_sentence_bullet_is_two_claims() -> None:
    claims = split_claims("- Rotation is slow. It costs two days.")

    assert [claim.text for claim in claims] == [
        "Rotation is slow.",
        "It costs two days.",
    ]
    assert [claim.index for claim in claims] == [0, 1]


def test_each_sentence_in_a_bullet_keeps_its_own_status() -> None:
    index = _index(("E-1", "Call with Acme", "Gong"))
    claims = split_claims(
        "- Rotation is slow. [[ev:E-1]] It costs two days. [[hypothesis]]",
        index,
    )

    assert [claim.status for claim in claims] == ["cited", "hypothesis"]
    assert claims[0].evidence == (index.resolve("E-1"),)
    assert claims[1].evidence == ()


def test_a_bullet_with_no_terminator_is_one_claim() -> None:
    claims = split_claims("- Minimize the time")

    assert len(claims) == 1
    assert claims[0].text == "Minimize the time"


def test_ordered_list_markers_are_stripped() -> None:
    claims = split_claims("1. First. Second.")

    assert [claim.text for claim in claims] == ["First.", "Second."]


def test_a_decimal_is_not_a_sentence_boundary() -> None:
    claims = split_claims("Scores rose 3.5 points.")

    assert len(claims) == 1
    assert claims[0].text == "Scores rose 3.5 points."


def test_one_marker_does_not_spread_to_the_sentence_beside_it() -> None:
    claims = split_claims(
        "Three accounts stalled. [[ev:E-1]] Nobody said why.",
        _index(("E-1", "Call with Acme", "Gong")),
    )

    assert [claim.status for claim in claims] == ["cited", "uncited"]
    assert claims[1].text == "Nobody said why."


def test_an_evidence_tool_result_is_indexed_with_its_label() -> None:
    index = EvidenceIndex()
    index.ingest(
        "list_evidence", {}, '[{"id": "E-7", "name": "Slack thread", "source_name": "Slack"}]'
    )

    claims = split_claims("Three stalled. [[ev:E-7]]", index)

    assert claims[0].status == "cited"
    assert claims[0].evidence[0].source_name == "Slack"


def test_a_get_result_names_the_record_an_argument_only_identified() -> None:
    index = EvidenceIndex()
    index.ingest(
        "get_evidence",
        {"evidence_id": "E-1"},
        '{"id": "E-1", "name": "Call with Acme", "source_name": "Gong"}',
    )

    claims = split_claims("Three stalled. [[ev:E-1]]", index)

    assert claims[0].status == "cited"
    assert claims[0].evidence[0].to_dict() == {
        "id": "E-1",
        "name": "Call with Acme",
        "source_name": "Gong",
    }


def test_a_resolver_accepts_an_id_from_the_local_store() -> None:
    index = EvidenceIndex(
        resolver=lambda identifier: EvidenceSnapshot(identifier, "Local", "Manual")
    )

    claims = split_claims("They stalled. [[ev:L-1]]", index)

    assert claims[0].status == "cited"
    assert claims[0].evidence[0].name == "Local"


def test_an_empty_reply_has_no_claims() -> None:
    assert split_claims("   ") == []


@pytest.mark.parametrize("suffix", CORPORATE_SUFFIXES)
def test_a_corporate_suffix_keeps_its_sentence_together(suffix: str) -> None:
    # The abbreviation is capitalised to match how a company name is written;
    # ``_last_word`` lowercases, so the entry covers every casing.
    text = f"We interviewed Acme {suffix.capitalize()}. Their team has two engineers."

    claims = split_claims(text)

    assert len(claims) == 1
    assert claims[0].text == text


def test_a_corporate_suffix_keeps_the_marker_with_its_sentence() -> None:
    claims = split_claims(
        "We interviewed Acme Inc. Their team has two engineers. [[ev:E-1]]",
        _index(("E-1", "Call with Acme", "Gong")),
    )

    assert [claim.status for claim in claims] == ["cited"]
    assert claims[0].text == "We interviewed Acme Inc. Their team has two engineers."


def test_a_decimal_point_still_splits_where_a_sentence_really_ends() -> None:
    claims = split_claims("The cost is 2.5 million. That is high.")

    assert [claim.text for claim in claims] == ["The cost is 2.5 million.", "That is high."]


def test_a_plain_period_still_splits() -> None:
    claims = split_claims("It ended. Next sentence.")

    assert [claim.text for claim in claims] == ["It ended.", "Next sentence."]


def test_the_existing_abbreviations_still_hold_a_sentence_together() -> None:
    claims = split_claims("We ran it with tools, e.g. a probe. It worked.")

    assert [claim.text for claim in claims] == [
        "We ran it with tools, e.g. a probe.",
        "It worked.",
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Record counts fell 40% last quarter.",
        "Run time doubled after the migration.",
        "Review latency is the bottleneck.",
        "Copy volume is up.",
    ],
)
def test_a_declarative_opening_with_an_imperative_verb_is_a_claim(text: str) -> None:
    claims = split_claims(text)

    assert len(claims) == 1
    assert claims[0].status == "uncited"
    assert claims[0].text == text


@pytest.mark.parametrize(
    "text",
    [
        "Check the invoice step.",
        "Try the newer model.",
        "Open the records lens.",
    ],
)
def test_an_instruction_opening_with_an_imperative_verb_is_exempt(text: str) -> None:
    assert split_claims(text) == []


def test_a_question_still_ends_the_exemption_check_early() -> None:
    assert split_claims("Review the latency, is it the bottleneck?") == []
