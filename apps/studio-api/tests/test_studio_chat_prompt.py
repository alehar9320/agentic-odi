"""What the Studio's system prompt tells the agent to do before it scores."""

from __future__ import annotations

from agentic_odi_studio_api.studio import chat


def test_the_system_prompt_puts_three_questions_before_a_score() -> None:
    #: #596 refuses a bare number at the write; the prompt is what makes the agent
    #: ask instead of being refused, and name the person's answer as the source.
    assert "three questions" in chat.SYSTEM_PROMPT
    assert "never answer your own question" in chat.SYSTEM_PROMPT
