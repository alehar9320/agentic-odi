"""A2 — transcript parsing (pure), ahead of persistence."""

from __future__ import annotations

import pytest
from agentic_odi_core.transcript import (
    TranscriptFormatError,
    Turn,
    detect_format,
    parse_transcript,
)

VTT = """WEBVTT

00:00:01.000 --> 00:00:03.000
<v Ana>Setup takes forever.

00:00:03.000 --> 00:00:05.500
<v Bo>And it is worse for new hires.
"""

SRT = """1
00:00:01,000 --> 00:00:03,000
Setup takes forever.

2
00:00:03,000 --> 00:00:05,500
And it is worse for new hires.
"""

MARKDOWN = """**Ana:** Setup takes forever.
It is the worst part of onboarding.

**Bo:** Agreed.
"""

PLAIN = """Setup takes forever for every new engineer.

It is worse for people joining remotely.
"""


def test_vtt_yields_speaker_text_and_timing() -> None:
    turns = parse_transcript(VTT, "vtt")
    assert turns[0] == Turn(speaker="Ana", text="Setup takes forever.", start_ms=1000, end_ms=3000)
    assert turns[1].speaker == "Bo"
    assert turns[1].start_ms == 3000
    assert turns[1].end_ms == 5500


def test_srt_yields_speaker_none_and_timing() -> None:
    turns = parse_transcript(SRT, "srt")
    assert [t.text for t in turns] == ["Setup takes forever.", "And it is worse for new hires."]
    assert all(t.speaker is None for t in turns)
    assert turns[0].start_ms == 1000


def test_markdown_folds_wrapped_lines_into_one_turn() -> None:
    turns = parse_transcript(MARKDOWN, "md")
    assert turns[0].speaker == "Ana"
    assert turns[0].text == "Setup takes forever. It is the worst part of onboarding."
    assert turns[1].speaker == "Bo"


def test_plain_text_is_one_quote_per_paragraph_without_speaker() -> None:
    turns = parse_transcript(PLAIN, "txt")
    assert len(turns) == 2
    assert all(t.speaker is None for t in turns)
    assert turns[0].text == "Setup takes forever for every new engineer."


def test_plain_speaker_colon_form_is_recognised() -> None:
    turns = parse_transcript("Ana: hello\nBo: hi\n", "md")
    assert [(t.speaker, t.text) for t in turns] == [("Ana", "hello"), ("Bo", "hi")]


def test_unknown_speaker_stays_none() -> None:
    turns = parse_transcript("just a note with no colon marker\n", "txt")
    assert turns[0].speaker is None


def test_bom_and_crlf_are_handled() -> None:
    text = "\ufeff**Ana:** hello\r\nworld\r\n"
    turns = parse_transcript(text, "md")
    assert turns[0].text == "hello world"


def test_vtt_header_is_optional() -> None:
    turns = parse_transcript(
        "00:00:01.000 --> 00:00:02.000\nhello\n",
        "vtt",
    )
    assert turns == [Turn(speaker=None, text="hello", start_ms=1000, end_ms=2000)]


def test_malformed_cue_timing_names_the_line() -> None:
    with pytest.raises(TranscriptFormatError) as exc:
        parse_transcript("WEBVTT\n\n00:00:1.0 --> nope\nhello\n", "vtt")
    assert exc.value.line == 3
    assert "cue timing" in str(exc.value)


def test_empty_input_is_refused() -> None:
    with pytest.raises(TranscriptFormatError):
        parse_transcript("   \n\n  \n", "txt")


def test_unknown_format_is_refused_not_guessed() -> None:
    with pytest.raises(TranscriptFormatError) as exc:
        parse_transcript(VTT, "docx")
    assert "unknown transcript format" in str(exc.value)


@pytest.mark.parametrize(
    ("text", "filename", "expected"),
    [
        (MARKDOWN, "a.md", "md"),
        (PLAIN, "a.txt", "txt"),
        (VTT, "a.vtt", "vtt"),
        (SRT, "a.srt", "srt"),
        (SRT, None, "srt"),
        (VTT, None, "vtt"),
        (MARKDOWN, None, "md"),
        (PLAIN, None, "txt"),
        (PLAIN, "no-extension", "txt"),
    ],
)
def test_detect_format_prefers_extension_then_content(
    text: str, filename: str | None, expected: str
) -> None:
    assert detect_format(text, filename) == expected


def test_detect_format_uses_extension_even_when_content_differs() -> None:
    # A ``.md`` file with cue timing still parses as markdown: extension first.
    assert detect_format(VTT, "weird.md") == "md"


def test_detect_format_routes_malformed_cues_to_the_cue_parser() -> None:
    # A bad cue arrow must not be read as prose and accepted.
    assert detect_format("WEBVTT\n\n00:00:1.0 --> nope\nhello\n") == "vtt"


@pytest.mark.parametrize(
    ("case", "text", "fmt", "expected"),
    [
        # All four formats.
        (
            "vtt",
            VTT,
            "vtt",
            [("Ana", "Setup takes forever."), ("Bo", "And it is worse for new hires.")],
        ),
        (
            "srt",
            SRT,
            "srt",
            [(None, "Setup takes forever."), (None, "And it is worse for new hires.")],
        ),
        (
            "markdown",
            MARKDOWN,
            "md",
            [
                ("Ana", "Setup takes forever. It is the worst part of onboarding."),
                ("Bo", "Agreed."),
            ],
        ),
        (
            "prose",
            PLAIN,
            "txt",
            [
                (None, "Setup takes forever for every new engineer."),
                (None, "It is worse for people joining remotely."),
            ],
        ),
        # Blank runs collapse; wrapped lines fold into one turn.
        ("blank_runs", "first\n\n\n\nsecond\n", "txt", [(None, "first"), (None, "second")]),
        (
            "wrapped_lines",
            "one long\nwrapped sentence\n\nnext\n",
            "txt",
            [(None, "one long\nwrapped sentence"), (None, "next")],
        ),
        # BOM and CRLF.
        ("bom", "\ufeff**Ana:** hello\r\nworld\r\n", "md", [("Ana", "hello world")]),
        (
            "crlf_vtt",
            "WEBVTT\r\n\r\n00:00:01.000 --> 00:00:02.000\r\nhi\r\n",
            "vtt",
            [(None, "hi")],
        ),
        # Missing WEBVTT header.
        ("no_header", "00:00:01.000 --> 00:00:02.000\nhello\n", "vtt", [(None, "hello")]),
        # Plain `Ana:` speaker form.
        ("colon_form", "Ana: hello\nBo: hi\n", "md", [("Ana", "hello"), ("Bo", "hi")]),
        # Unknown speaker stays None.
        (
            "no_speaker",
            "just a note with no colon marker\n",
            "txt",
            [(None, "just a note with no colon marker")],
        ),
        # A single-paragraph file is one quote.
        ("single", "only one paragraph here.\n", "txt", [(None, "only one paragraph here.")]),
    ],
)
def test_parser_variants_table(
    case: str, text: str, fmt: str, expected: list[tuple[str | None, str]]
) -> None:
    turns = parse_transcript(text, fmt)
    assert [(t.speaker, t.text) for t in turns] == expected, case
