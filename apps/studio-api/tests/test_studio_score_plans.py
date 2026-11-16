"""The score-plan store: the questions a score must answer before it is written.

These cover the memory half of issue #341 — opening a plan, resolving it with
answers or a skip, refusing a malformed basis, and expiring a stale one.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from agentic_odi_studio_api.studio.memory import (
    MAX_SCORE_PLAN_QUESTIONS,
    ConversationNotFoundError,
    MemoryError,
    ScorePlanNotFoundError,
    StudioMemory,
)

QUESTIONS = [
    "Who feels this problem most sharply today?",
    "What workaround do they use right now?",
    "What does that workaround cost them in time?",
]
STATEMENT = "Minimize the time it takes to file a claim"


@pytest.fixture()
def memory() -> Iterator[StudioMemory]:
    store = StudioMemory(":memory:")
    yield store
    store.close()


def _conversation(memory: StudioMemory) -> str:
    return memory.create_conversation().id


def test_open_score_plan_records_questions_and_proposed_numbers(
    memory: StudioMemory,
) -> None:
    conversation_id = _conversation(memory)
    plan = memory.open_score_plan(
        conversation_id, STATEMENT, QUESTIONS, importance=8.6, satisfaction=4.9
    )

    assert plan.status == "open"
    assert plan.questions == QUESTIONS
    assert plan.importance == 8.6
    assert plan.satisfaction == 4.9
    # The proposed numbers are not a resolved score yet.
    assert memory.resolved_score_plan(conversation_id, STATEMENT) is None


def test_open_score_plan_replaces_the_open_plan_for_the_same_statement(
    memory: StudioMemory,
) -> None:
    conversation_id = _conversation(memory)
    first = memory.open_score_plan(conversation_id, STATEMENT, QUESTIONS)
    second = memory.open_score_plan(conversation_id, STATEMENT, QUESTIONS)

    assert second.id != first.id
    # The replaced plan is gone, so a stale card cannot be answered.
    assert memory.get_score_plan(first.id) is None


def test_opening_a_plan_needs_a_real_conversation(memory: StudioMemory) -> None:
    with pytest.raises(ConversationNotFoundError):
        memory.open_score_plan("nope", STATEMENT, QUESTIONS)


def test_answer_resolves_the_plan_and_hands_back_the_basis(
    memory: StudioMemory,
) -> None:
    conversation_id = _conversation(memory)
    plan = memory.open_score_plan(conversation_id, STATEMENT, QUESTIONS)
    answers = ["Claims reps", "Email threads and a spreadsheet", "About 40 minutes each"]

    resolved = memory.answer_score_plan(plan.id, answers)

    assert resolved.status == "answered"
    assert resolved.answers == answers
    basis = resolved.basis()
    assert basis.asked == QUESTIONS
    assert basis.answers == answers
    assert basis.verified is True
    assert memory.resolved_score_plan(conversation_id, STATEMENT) is not None


def test_answer_must_cover_every_question(memory: StudioMemory) -> None:
    conversation_id = _conversation(memory)
    plan = memory.open_score_plan(conversation_id, STATEMENT, QUESTIONS)

    with pytest.raises(MemoryError):
        memory.answer_score_plan(plan.id, ["only one"])


def test_a_blank_answer_is_refused(memory: StudioMemory) -> None:
    conversation_id = _conversation(memory)
    plan = memory.open_score_plan(conversation_id, STATEMENT, QUESTIONS)

    with pytest.raises(MemoryError):
        memory.answer_score_plan(plan.id, ["Claims reps", "   ", "40 minutes"])


def test_skip_records_a_reason_for_every_question(memory: StudioMemory) -> None:
    conversation_id = _conversation(memory)
    plan = memory.open_score_plan(conversation_id, STATEMENT, QUESTIONS)

    skipped = memory.skip_score_plan(plan.id, "No customer access this week")

    assert skipped.status == "skipped"
    assert skipped.skip_reason == "No customer access this week"
    assert [skip.question for skip in skipped.skips] == QUESTIONS
    assert all(skip.reason == "No customer access this week" for skip in skipped.skips)
    assert skipped.basis().verified is False


def test_a_skip_without_a_reason_is_refused(memory: StudioMemory) -> None:
    conversation_id = _conversation(memory)
    plan = memory.open_score_plan(conversation_id, STATEMENT, QUESTIONS)

    with pytest.raises(MemoryError):
        memory.skip_score_plan(plan.id, "   ")


def test_a_resolved_plan_cannot_be_resolved_twice(memory: StudioMemory) -> None:
    conversation_id = _conversation(memory)
    plan = memory.open_score_plan(conversation_id, STATEMENT, QUESTIONS)
    memory.skip_score_plan(plan.id, "No data")

    with pytest.raises(MemoryError):
        memory.answer_score_plan(plan.id, ["a", "b", "c"])


def test_an_unknown_plan_is_a_not_found(memory: StudioMemory) -> None:
    with pytest.raises(ScorePlanNotFoundError):
        memory.answer_score_plan("missing", ["a", "b", "c"])


def test_two_questions_is_not_enough(memory: StudioMemory) -> None:
    with pytest.raises(MemoryError):
        memory.open_score_plan(_conversation(memory), STATEMENT, QUESTIONS[:2])


def test_more_than_five_questions_is_refused(memory: StudioMemory) -> None:
    with pytest.raises(MemoryError):
        memory.open_score_plan(
            _conversation(memory),
            STATEMENT,
            [*QUESTIONS, "A fourth question here", "A fifth question here", "A sixth question here"],
        )
    assert MAX_SCORE_PLAN_QUESTIONS == 5


def test_questions_must_be_distinct(memory: StudioMemory) -> None:
    with pytest.raises(MemoryError):
        memory.open_score_plan(_conversation(memory), STATEMENT, [QUESTIONS[0], QUESTIONS[0], QUESTIONS[2]])


def test_one_question_must_ask_about_the_workaround_or_its_cost(
    memory: StudioMemory,
) -> None:
    with pytest.raises(MemoryError):
        memory.open_score_plan(
            _conversation(memory),
            STATEMENT,
            [
                "How important is this to them overall?",
                "How satisfied are they with their options?",
                "Which team owns the problem in their view?",
            ],
        )


def test_a_question_that_is_too_short_is_refused(memory: StudioMemory) -> None:
    with pytest.raises(MemoryError):
        memory.open_score_plan(_conversation(memory), STATEMENT, ["Hi?", QUESTIONS[1], QUESTIONS[2]])


def test_a_proposed_score_outside_one_to_ten_is_refused(memory: StudioMemory) -> None:
    with pytest.raises(MemoryError):
        memory.open_score_plan(_conversation(memory), STATEMENT, QUESTIONS, importance=11.0)


def test_an_expired_plan_does_not_resolve_a_score(memory: StudioMemory) -> None:
    conversation_id = _conversation(memory)
    plan = memory.open_score_plan(conversation_id, STATEMENT, QUESTIONS)
    memory.answer_score_plan(plan.id, ["a", "b", "c"])
    # Reach into the row to age it, as the clock would have.
    past = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    with memory._lock, memory._connection:  # noqa: SLF001 - the test ages the row on purpose
        memory._connection.execute(  # noqa: SLF001
            "UPDATE score_plans SET expires_at = ? WHERE id = ?", (past, plan.id)
        )

    assert memory.resolved_score_plan(conversation_id, STATEMENT) is None


def test_resolved_plan_survives_a_reopen(tmp_path) -> None:
    path = tmp_path / "studio.db"
    store = StudioMemory(path)
    try:
        conversation_id = store.create_conversation().id
        plan = store.open_score_plan(conversation_id, STATEMENT, QUESTIONS)
        store.answer_score_plan(plan.id, ["a", "b", "c"])
    finally:
        store.close()

    reopened = StudioMemory(path)
    try:
        resolved = reopened.resolved_score_plan(conversation_id, STATEMENT)
        assert resolved is not None
        assert resolved.status == "answered"
        assert resolved.answers == ["a", "b", "c"]
    finally:
        reopened.close()
