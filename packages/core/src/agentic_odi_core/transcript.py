"""Turn a transcript file into ordered turns.

This module is pure: it reads text and returns :class:`Turn` objects. It never
writes to a store and never invents a speaker or a timestamp. Persisting the
turns as interview quotes is the caller's job, so a parse failure leaves no
partial interview behind.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from agentic_odi_core.errors import ValidationError

SUPPORTED_FORMATS = ("md", "txt", "vtt", "srt")

# ``**Ana:** text`` or ``Ana: text`` on one line, wrapped lines folded in.
_MARKDOWN_SPEAKER = re.compile(r"^\*\*(?P<speaker>[^*]+):?\*\*:?\s*(?P<text>.*)$")
_PLAIN_SPEAKER = re.compile(r"^(?P<speaker>[A-Za-z][\w .'\-]{0,40}):\s*(?P<text>.*)$")

# ``00:01:02.500 --> 00:01:05.000`` (VTT) or ``00:01:02,500 --> 00:01:05,000`` (SRT).
_CUE_TIME = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(?P<end>\d{1,2}:\d{2}:\d{2}[.,]\d{3})"
)
_VTT_SPEAKER = re.compile(r"^<v\s+(?P<speaker>[^>]+)>(?P<text>.*)$")


@dataclass(frozen=True)
class Turn:
    """One speaker's contiguous utterance, with optional cue timing in ms."""

    speaker: str | None
    text: str
    start_ms: int | None = None
    end_ms: int | None = None


class TranscriptFormatError(ValidationError):
    """A transcript could not be parsed; the message names the line and reason."""

    def __init__(self, message: str, *, line: int | None = None) -> None:
        self.line = line
        prefix = f"line {line}: " if line is not None else ""
        super().__init__(f"{prefix}{message}")


def _clean(text: str) -> str:
    return text.strip()


def _clean_speaker(text: str) -> str:
    return text.strip().rstrip(":").strip()


def _time_to_ms(value: str) -> int:
    hours, minutes, rest = value.split(":")
    seconds, millis = re.split(r"[.,]", rest)
    return int(hours) * 3_600_000 + int(minutes) * 60_000 + int(seconds) * 1000 + int(millis)


def parse_markdown_dialogue(text: str) -> list[Turn]:
    """Parse ``**Ana:** text`` or ``Ana: text`` dialogue, folding wrapped lines.

    A line without a speaker marker continues the previous turn. Blank lines
    separate turns but never produce an empty one.
    """
    turns: list[Turn] = []
    buffer: list[str] = []
    speaker: str | None = None

    def flush() -> None:
        nonlocal buffer, speaker
        if buffer:
            joined = _clean(" ".join(buffer))
            if joined:
                turns.append(Turn(speaker=speaker, text=joined))
        buffer = []

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush()
            speaker = None
            continue
        markdown = _MARKDOWN_SPEAKER.match(line.strip())
        plain = None if markdown else _PLAIN_SPEAKER.match(line.strip())
        match = markdown or plain
        if match:
            flush()
            speaker = _clean_speaker(match.group("speaker"))
            buffer = [match.group("text")]
        else:
            buffer.append(line.strip())
    flush()
    return turns


def parse_prose(text: str) -> list[Turn]:
    """Parse plain prose: one quote per paragraph, with no speaker."""
    paragraphs = re.split(r"\n\s*\n", text)
    return [Turn(speaker=None, text=_clean(p)) for p in paragraphs if _clean(p)]


def _parse_cues(text: str, *, strip_header: bool) -> list[Turn]:
    """Shared cue parser for WebVTT and SubRip."""
    lines = text.splitlines()
    if strip_header and lines and lines[0].lstrip("\ufeff").strip().upper().startswith("WEBVTT"):
        lines = lines[1:]

    turns: list[Turn] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line or line.isdigit():
            index += 1
            continue
        cue = _CUE_TIME.search(line)
        if not cue:
            index += 1
            continue
        start = _time_to_ms(cue.group("start"))
        end = _time_to_ms(cue.group("end"))
        index += 1
        body: list[str] = []
        while index < len(lines) and lines[index].strip() and not _CUE_TIME.search(lines[index]):
            body.append(lines[index].strip())
            index += 1
        speaker: str | None = None
        if body:
            voice = _VTT_SPEAKER.match(body[0])
            if voice:
                speaker = _clean_speaker(voice.group("speaker"))
                body[0] = voice.group("text").strip()
                if not body[0]:
                    body.pop(0)
        text_value = _clean(" ".join(body))
        if text_value:
            turns.append(Turn(speaker=speaker, text=text_value, start_ms=start, end_ms=end))
    return turns


def parse_vtt(text: str) -> list[Turn]:
    """Parse a WebVTT transcript; the ``WEBVTT`` header is optional."""
    return _parse_cues(text, strip_header=True)


def parse_srt(text: str) -> list[Turn]:
    """Parse a SubRip transcript."""
    return _parse_cues(text, strip_header=False)


_PARSERS = {
    "md": parse_markdown_dialogue,
    "txt": parse_prose,
    "vtt": parse_vtt,
    "srt": parse_srt,
}


def detect_format(text: str, filename: str | None = None) -> str:
    """Pick a format from the filename extension, then from the content.

    The extension wins when it is one we support. Otherwise the content is
    checked for cue timing; if neither is conclusive the caller must pass an
    explicit ``--format`` rather than have us guess.
    """
    if filename:
        suffix = Path(filename).suffix.lstrip(".").lower()
        if suffix in _PARSERS:
            return suffix
    text = text.lstrip("\ufeff")
    # A cue arrow means a cue transcript. Malformed timing still routes to the
    # cue parser, which rejects it rather than reading the file as prose.
    if "-->" in text:
        return "srt" if re.search(r"\d{1,2}:\d{2}:\d{2},\d{3}\s*-->", text) else "vtt"
    for line in text.splitlines():
        stripped = line.strip()
        if _MARKDOWN_SPEAKER.match(stripped) or _PLAIN_SPEAKER.match(stripped):
            return "md"
    return "txt"


def parse_transcript(text: str, fmt: str) -> list[Turn]:
    """Parse ``text`` in ``fmt``; refuse an unknown format or an empty result.

    Raises :class:`TranscriptFormatError` with the offending line when cue
    timing is malformed, and refuses a transcript that yields no turns so a
    caller never persists an empty interview.
    """
    if fmt not in _PARSERS:
        supported = ", ".join(SUPPORTED_FORMATS)
        raise TranscriptFormatError(f"unknown transcript format '{fmt}' (supported: {supported})")
    text = text.lstrip("\ufeff")
    if fmt in ("vtt", "srt"):
        _check_cue_timing(text)
    turns = _PARSERS[fmt](text)
    if not turns:
        raise TranscriptFormatError("no transcript content found")
    return turns


def _check_cue_timing(text: str) -> None:
    """Reject a cue whose timing is malformed, naming the line."""
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if "-->" in line and not _CUE_TIME.search(line):
            raise TranscriptFormatError("malformed cue timing", line=number)
