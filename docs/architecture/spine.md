# The ODI spine seam

The product is the spine: **quote → candidate → outcome → score → brief →
decision → bet → measure**. Each hop is its own issue. Until a hop is
implemented, nothing downstream can produce a real number — and inventing one is
worse than reporting the gap, because a plausible-looking placeholder is
indistinguishable from real data once it reaches a brief.

`agentic_odi_core.spine` is the seam that lets the rest of the codebase depend on
a stable shape *now*, while the stages land one at a time. It does three things.

## 1. Names the stages and their owners

`SpineStage` is the ordered pipeline. `SEAM_OWNERS` maps each stage (and the two
off-pipeline seams, `demo` and `template`) to the issue that implements it:

| Seam | Issue | Module |
| --- | --- | --- |
| candidate | ALH-17 (A4) | — |
| outcome | ALH-18 (A5) | — |
| score | ALH-24 (B1) | — |
| brief | ALH-32 (C1) | `brief.py` |
| decision | ALH-37 (C6) | — |
| bet | ALH-46 (E1) | — |
| measure | ALH-47 (E2) | — |
| demo | ALH-58 (M0-13) | — |
| template | ALH-119 (M4-13) | — |

`module` is set only where the owning issue names the file it will add. It is
`None` where the file name is not yet decided, rather than guessed.

## 2. Gives each stage a callable contract and an honest stub

Each stage has a `Protocol` (`CandidateExtractor`, `BriefRenderer`, …). Each has
an `Unavailable*` stub that raises `StageNotImplemented` — a typed `OdiError`
carrying the stage and its owner. A stub never returns a placeholder.

`Spine` holds one object per pipeline stage. `default_spine()` stubs every stage,
so the honest default is "nothing yet". Wiring a real implementation in marks
that stage available.

## 3. Reports the gap so any surface can say "nothing yet"

`seam_inventory()` returns a `SeamStatus` per seam; `missing_stages()` lists the
gaps; `spine_summary()` renders them in words, naming each gap by its owning
issue. The CLI exposes this as `agentic-odi spine` (and `--json`).

## Why the transport shapes are not entities

`CandidateOutcome`, `ScoreSample`, `BriefDocument`, `Decision`, `Bet`,
`Measurement`, and `DemoWorkspace` are the seam's *wire* types. They carry no
`id` factory, no repository, schema, or event wiring, and they deliberately do
not appear in `odi_schema()`. When a stage lands, its real model replaces the
wire shape and takes on the full persistence checklist (models, repository
Protocol + in-memory, SQLite `_apply_event`, remote, schema, service, contract,
CLI, studio-api, studio types) — the checklist is not skipped just because a
shape already exists here.

A test asserts the wire shapes never leak into the persisted schema.

## How this unblocks the rest of Pillar 5

A consumer can depend on `Spine` and a `Protocol` today, wire a real
implementation when it lands, and read `spine_summary()` to render the gap in the
meantime. That is what lets the blocked children be built in parallel: they code
against the seam, not against a stub that pretends to be real.
