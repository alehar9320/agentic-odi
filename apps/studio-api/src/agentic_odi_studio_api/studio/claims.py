"""The claim contract: every declarative sentence carries evidence or says so.

A declarative sentence ends with ``[[ev:<id>]]``, ``[[ev:<id>,<id>]]`` (at most
three records), or ``[[hypothesis]]`` when no record supports it. Questions,
imperatives, headings, and code are exempt, and a marker inside code stays
literal.

This module is the one parser. The sidecar validates a marker against the
evidence the turn actually received, persists the result beside the turn, and
the Studio renders the labels this returns — so a chip always names a record,
never the tool that happened to run.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

ClaimStatus = Literal["cited", "hypothesis", "uncited"]

#: One sentence may rest on a few records, never on a pile of them.
MAX_EVIDENCE_PER_CLAIM = 3

#: Why a cited claim was downgraded. Stable, so the client can explain it.
UNKNOWN_EVIDENCE_ID = "unknown_evidence_id"

#: Tools whose arguments or results name a record the reply may cite.
EVIDENCE_TOOLS: frozenset[str] = frozenset(
    {"list_evidence", "get_evidence", "add_evidence", "promote_evidence"}
)

_MARKER_RE = re.compile(r"\[\[(ev|hypothesis)(?::([^\]]*))?\]\]", re.IGNORECASE)
_LIST_PREFIX = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_HEADING_PREFIX = re.compile(r"^\s*#{1,6}\s+")

#: A period after one of these is punctuation inside the word, not a sentence end.
_ABBREVIATIONS: frozenset[str] = frozenset(
    {
        "e.g",
        "i.e",
        "etc",
        "vs",
        "dr",
        "mr",
        "mrs",
        "ms",
        "prof",
        "st",
        "approx",
        "no",
        "fig",
        "al",
    }
)

#: A sentence that starts with one of these asks for an action, not a fact.
_IMPERATIVE_VERBS: frozenset[str] = frozenset(
    {
        "add",
        "ask",
        "capture",
        "check",
        "choose",
        "click",
        "connect",
        "copy",
        "create",
        "delete",
        "edit",
        "focus",
        "follow",
        "open",
        "pick",
        "press",
        "read",
        "record",
        "review",
        "run",
        "save",
        "search",
        "select",
        "start",
        "stop",
        "tell",
        "try",
        "type",
        "use",
        "write",
    }
)


@dataclass(frozen=True)
class EvidenceSnapshot:
    """The label stored with a claim, so a later delete leaves a name, not a hole."""

    id: str
    name: str
    source_name: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "name": self.name, "source_name": self.source_name}


@dataclass(frozen=True)
class Claim:
    """One declarative sentence, and what stands behind it."""

    index: int
    text: str
    status: ClaimStatus
    evidence: tuple[EvidenceSnapshot, ...] = ()
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "text": self.text,
            "status": self.status,
            "evidence": [snapshot.to_dict() for snapshot in self.evidence],
            "reason": self.reason,
        }


def _mask_code(text: str) -> str:
    """Blank out code spans, keeping every offset and newline in place.

    Markers inside code are literal, and a terminator inside code is not a
    sentence end. Masking keeps indices aligned with the original text.
    """
    chars = list(text)
    index = 0
    length = len(text)
    while index < length:
        if text.startswith("```", index):
            end = text.find("```", index + 3)
            stop = length if end == -1 else end + 3
            for position in range(index, stop):
                if chars[position] != "\n":
                    chars[position] = " "
            index = stop
            continue
        if text[index] == "`":
            line_end = text.find("\n", index)
            limit = length if line_end == -1 else line_end
            end = text.find("`", index + 1, limit)
            stop = limit if end == -1 else end + 1
            for position in range(index, stop):
                if chars[position] != "\n":
                    chars[position] = " "
            index = stop
            continue
        index += 1
    return "".join(chars)


def _last_word(text: str) -> str:
    match = re.search(r"([A-Za-z][A-Za-z.]*)\.$", text.strip())
    return match.group(1).lower() if match else ""


def _sentences(line: str, masked: str) -> list[str]:
    """Split one prose line into sentences, ignoring terminators inside code."""
    sentences: list[str] = []
    start = 0
    index = 0
    length = len(line)
    while index < length:
        if masked[index] not in ".!?":
            index += 1
            continue
        end = index + 1
        while end < length and line[end] in "\"')]}”’":
            end += 1
        # A marker follows the terminator it annotates, so it belongs to this
        # sentence rather than to a marker-only fragment of its own.
        scan = end
        while True:
            probe = scan
            while probe < length and line[probe].isspace():
                probe += 1
            marker = _MARKER_RE.match(line, probe)
            if marker is None:
                break
            scan = marker.end()
            end = scan
        if end < length and not line[end].isspace():
            index += 1
            continue
        candidate = line[start:end].strip()
        if masked[index] == "." and _last_word(line[start : index + 1]) in _ABBREVIATIONS:
            index += 1
            continue
        if candidate:
            sentences.append(candidate)
        start = end
        index = end
    tail = line[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def _strip_markers(text: str) -> tuple[str, list[tuple[str, tuple[str, ...]]]]:
    """Remove markers from the display text and report what they asked for."""
    masked = _mask_code(text)
    markers: list[tuple[str, tuple[str, ...]]] = []
    spans: list[tuple[int, int]] = []
    for match in _MARKER_RE.finditer(masked):
        start, end = match.span()
        found = _MARKER_RE.match(text[start:end])
        if found is None:  # pragma: no cover - masked and original agree
            continue
        kind = found.group(1).lower()
        if kind == "hypothesis":
            markers.append(("hypothesis", ()))
        else:
            ids = tuple(
                value.strip() for value in (found.group(2) or "").split(",") if value.strip()
            )
            markers.append(("ev", ids))
        spans.append((start, end))
    for start, end in reversed(spans):
        text = text[:start] + text[end:]
    return " ".join(text.split()).strip(), markers


def _is_exempt(text: str) -> bool:
    """Questions and instructions make no claim, so they carry no marker."""
    if not text:
        return True
    if text.endswith("?"):
        return True
    first = re.match(r"[A-Za-z']+", text)
    return bool(first and first.group(0).lower() in _IMPERATIVE_VERBS)


def _records(value: Any) -> Iterable[dict[str, Any]]:
    """Yield evidence-shaped records from a tool result, at any nesting."""
    if isinstance(value, list):
        for item in value:
            yield from _records(item)
        return
    if not isinstance(value, dict):
        return
    if "result" in value:
        yield from _records(value["result"])
        return
    if "evidence" in value and isinstance(value["evidence"], (dict, list)):
        yield from _records(value["evidence"])
        return
    if isinstance(value.get("id"), str):
        yield value


def _snapshot_from_record(record: dict[str, Any]) -> EvidenceSnapshot | None:
    identifier = record.get("id")
    if not isinstance(identifier, str) or not identifier:
        return None
    name = record.get("name")
    source_name = record.get("source_name")
    return EvidenceSnapshot(
        id=identifier,
        name=name if isinstance(name, str) and name.strip() else identifier,
        source_name=source_name if isinstance(source_name, str) else "",
    )


@dataclass
class EvidenceIndex:
    """The ids a turn actually received, with the labels that came with them.

    A resolver lets the local backend accept an id from its own store, so a
    citation is validated against a record even when no tool returned it.
    """

    resolver: Callable[[str], EvidenceSnapshot | None] | None = None
    snapshots: dict[str, EvidenceSnapshot] = field(default_factory=dict)

    def remember(self, snapshot: EvidenceSnapshot) -> None:
        self.snapshots.setdefault(snapshot.id, snapshot)

    def ingest(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        result_text: str | None = None,
    ) -> None:
        """Collect the ids one evidence tool call used or returned."""
        if tool_name not in EVIDENCE_TOOLS:
            return
        # The result carries the record's label; the arguments only carry an id.
        # Reading the result first keeps the better snapshot.
        if result_text:
            try:
                payload = json.loads(result_text)
            except (TypeError, ValueError):
                payload = None
            if payload is not None:
                for record in _records(payload):
                    snapshot = _snapshot_from_record(record)
                    if snapshot is not None:
                        self.remember(snapshot)
        if arguments:
            for key in ("evidence_id", "id"):
                value = arguments.get(key)
                if isinstance(value, str) and value.strip():
                    self.remember(EvidenceSnapshot(value.strip(), value.strip(), ""))
            raw_ids = arguments.get("evidence_ids")
            if isinstance(raw_ids, list):
                for value in raw_ids:
                    if isinstance(value, str) and value.strip():
                        self.remember(EvidenceSnapshot(value.strip(), value.strip(), ""))

    def resolve(self, evidence_id: str) -> EvidenceSnapshot | None:
        known = self.snapshots.get(evidence_id)
        if known is not None:
            return known
        if self.resolver is not None:
            try:
                return self.resolver(evidence_id)
            except Exception:  # noqa: BLE001 - a resolver is optional context
                return None
        return None


def split_claims(text: str, index: EvidenceIndex | None = None) -> list[Claim]:
    """Every declarative sentence in a reply, with its status and evidence.

    Without an index the markers are taken at face value; with one every cited id
    must have reached the turn, and an unknown id becomes an uncited claim.
    """
    claims: list[Claim] = []
    if not text.strip():
        return claims

    masked = _mask_code(text)
    offset = 0
    fenced = False
    for line in text.split("\n"):
        line_start = offset
        offset += len(line) + 1
        stripped = line.strip()
        if stripped.startswith("```"):
            fenced = not fenced
            continue
        if fenced or not stripped:
            continue
        if _HEADING_PREFIX.match(line):
            continue

        masked_line = masked[line_start : line_start + len(line)]
        if _LIST_PREFIX.match(line):
            body = _LIST_PREFIX.sub("", line, count=1)
            units = [body]
        else:
            body = line
            masked_body_end = len(masked_line)
            units = _sentences(body, masked_line[masked_body_end - len(body) :])

        for unit in units:
            display, markers = _strip_markers(unit)
            if not display:
                continue
            hypothesis = any(kind == "hypothesis" for kind, _ in markers)
            evidence_ids = [
                evidence_id for kind, ids in markers if kind == "ev" for evidence_id in ids
            ]
            status: ClaimStatus
            evidence: tuple[EvidenceSnapshot, ...] = ()
            reason: str | None = None

            if hypothesis:
                status = "hypothesis"
            elif evidence_ids:
                resolved: list[EvidenceSnapshot] = []
                unknown = False
                for evidence_id in list(dict.fromkeys(evidence_ids))[:MAX_EVIDENCE_PER_CLAIM]:
                    snapshot = index.resolve(evidence_id) if index is not None else None
                    if snapshot is None:
                        if index is None:
                            snapshot = EvidenceSnapshot(evidence_id, evidence_id, "")
                        else:
                            unknown = True
                            break
                    resolved.append(snapshot)
                if unknown:
                    status = "uncited"
                    reason = UNKNOWN_EVIDENCE_ID
                else:
                    status = "cited"
                    evidence = tuple(resolved)
            else:
                if _is_exempt(display):
                    continue
                status = "uncited"

            claims.append(
                Claim(
                    index=len(claims),
                    text=display,
                    status=status,
                    evidence=evidence,
                    reason=reason,
                )
            )
    return claims


__all__ = [
    "EVIDENCE_TOOLS",
    "MAX_EVIDENCE_PER_CLAIM",
    "UNKNOWN_EVIDENCE_ID",
    "Claim",
    "ClaimStatus",
    "EvidenceIndex",
    "EvidenceSnapshot",
    "split_claims",
]
