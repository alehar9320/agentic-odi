"""Ask first: an interview transcript is judged before its score is believed.

#596 made a score carry the questions behind it. These cases judge the harder
thing — whether those questions reached the person. A transcript is read in the
order it happened: three or four questions must be put before any number is
written, and every answer recorded with the score must be words the person said
before that turn. An agent that answers its own question is refused here.
"""

from __future__ import annotations

import pytest
from agentic_odi_core.evaluation import (
    InterviewTurn,
    ScoreBeforeQuestionsError,
    assert_asked_before_scoring,
)
from agentic_odi_core.models import ClaimCheck, ClaimSkip

_QUOTE = "Onboarding takes forever and I hate the spreadsheet we use."
_FREQ = "How often does onboarding come up?"
_TODAY = "What do you do today?"
_COST = "What does it cost when it slips?"

#: The three exchanges a complete interview is made of, so the transcript and the
#: claim check in these cases are always describing the same conversation.
_PAIRS = (
    (_FREQ, "Every week, on every new account."),
    (_TODAY, "A shared spreadsheet, copied from a template."),
    (_COST, "Two days of an engineer's time, usually."),
)


def _interview(*, questions: int = 3) -> list[InterviewTurn]:
    """The interview the tool description asks for, truncated to ``questions``."""
    turns = [InterviewTurn("customer", _QUOTE)]
    for question, answer in _PAIRS[:questions]:
        turns.append(InterviewTurn("agent", question))
        turns.append(InterviewTurn("customer", answer))
    turns.append(InterviewTurn("agent", "That scores 13.0 — underserved.", wrote_score=True))
    return turns


def _check(questions: int = 3) -> ClaimCheck:
    pairs = _PAIRS[:questions]
    return ClaimCheck(asked=[q for q, _ in pairs], answers=[a for _, a in pairs])


def test_an_interview_of_three_questions_before_the_score_passes() -> None:
    assert_asked_before_scoring(_interview(), _check())


def test_a_bare_quote_scored_first_is_refused() -> None:
    #: The case from the spec: the PM's quote arrives and numbers come back, with
    #: nothing asked in between. The claim check looks complete; the transcript is not.
    transcript = [
        InterviewTurn("customer", _QUOTE),
        InterviewTurn("agent", "This scores 13.0.", wrote_score=True),
    ]

    with pytest.raises(ScoreBeforeQuestionsError) as raised:
        assert_asked_before_scoring(transcript, _check())

    assert "0 of the three" in str(raised.value)


def test_scoring_after_two_questions_is_refused_and_says_so() -> None:
    with pytest.raises(ScoreBeforeQuestionsError) as raised:
        assert_asked_before_scoring(_interview(questions=2), _check(questions=2))

    assert "2 of the three" in str(raised.value)


def test_a_score_written_with_no_claim_check_is_refused() -> None:
    with pytest.raises(ScoreBeforeQuestionsError) as raised:
        assert_asked_before_scoring(_interview(), None)

    assert "claim check" in str(raised.value)


def test_an_answer_the_agent_wrote_itself_is_refused() -> None:
    #: Guardrail: never let the agent answer its own question and count it. The
    #: questions were asked, but the person never replied — the agent supplied the
    #: words, so the answer matches a turn that is not the customer's.
    transcript = [InterviewTurn("customer", _QUOTE)]
    for question, answer in [
        (_FREQ, "Every week."),
        (_TODAY, "A spreadsheet."),
        (_COST, "Two days."),
    ]:
        transcript.append(InterviewTurn("agent", question))
        transcript.append(InterviewTurn("agent", answer))
    transcript.append(InterviewTurn("agent", "That scores 13.0.", wrote_score=True))

    check = ClaimCheck(asked=[_FREQ, _TODAY, _COST], answers=["Every week.", "A spreadsheet."])

    with pytest.raises(ScoreBeforeQuestionsError) as raised:
        assert_asked_before_scoring(transcript, check)

    assert "Every week." in str(raised.value)


def test_a_question_the_person_skipped_still_counts_as_asked() -> None:
    #: Skipping is allowed; pretending is not. Two questions were answered and the
    #: third was put to the person and skipped with a reason, so the interview
    #: happened even though only two answers are on the record.
    transcript = [
        InterviewTurn("customer", _QUOTE),
        InterviewTurn("agent", _FREQ),
        InterviewTurn("customer", _PAIRS[0][1]),
        InterviewTurn("agent", _TODAY),
        InterviewTurn("customer", _PAIRS[1][1]),
        InterviewTurn("agent", _COST),
        InterviewTurn("customer", "I've honestly never measured it."),
        InterviewTurn("agent", "That scores 13.0.", wrote_score=True),
    ]
    check = ClaimCheck(
        asked=[_FREQ, _TODAY, _COST],
        answers=[_PAIRS[0][1], _PAIRS[1][1]],
        skips=[ClaimSkip(question=_COST, reason="never measured")],
    )

    assert_asked_before_scoring(transcript, check)


def test_an_unscored_outcome_needs_no_interview() -> None:
    #: A captured statement with no numbers is legal, so a transcript that never
    #: wrote a score has nothing to refuse — even one with no questions in it.
    assert_asked_before_scoring([InterviewTurn("customer", _QUOTE)], None)


def test_the_questions_are_counted_from_the_transcript_not_the_claims() -> None:
    #: A check may list questions in its own field; what matters is that they were
    #: put to the person. One asked, three claimed, still a refusal.
    transcript = [
        InterviewTurn("customer", _QUOTE),
        InterviewTurn("agent", _FREQ),
        InterviewTurn("customer", "Every week, on every new account."),
        InterviewTurn("agent", "That scores 13.0.", wrote_score=True),
    ]

    with pytest.raises(ScoreBeforeQuestionsError) as raised:
        assert_asked_before_scoring(transcript, _check())

    assert "1 of the three" in str(raised.value)
