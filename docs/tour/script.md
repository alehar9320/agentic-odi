# The 90-second tour, as a terminal session

One truthful walkthrough of the loop: a study goes in, a strategy comes out, and
every number you see is traceable to a record. It needs no model, no API key and
no network, and it never touches a workspace you care about.

**Everything below runs against a disposable store.** Set the two paths first; the
tour writes only inside them.

```bash
export TOUR_WORKSPACE="$(mktemp -d)/tour"
export TOUR_DB="$TOUR_WORKSPACE/tour.db"
export TOUR_OUT="$TOUR_WORKSPACE/out"
mkdir -p "$TOUR_OUT"
```

The data is sample data, generated on purpose: `scripts/gen_corpus.py` builds a
study whose jobs are named *Study job 0* and whose evidence is labelled
`source_kind=corpus`. No customer content and no real research appear here, and
the cast says so on its first line.

`scripts/tour.py` executes each command below in order, in a throwaway workspace,
and writes the recording. Regenerate it after any change to the CLI's output with:

```bash
uv run python scripts/tour.py --write
```

---

## 1. Load the demo study

Deterministic ids (`JOB-0000`, `OUT-00016`), so the walkthrough says the same thing
on every machine. This is the setup step: it is timed separately from the narration.

```bash
uv run python scripts/gen_corpus.py --out "$TOUR_DB" --outcomes 48 --jobs 2
```

## 2. Confirm the store is reachable

The tour refuses to continue if the store cannot be opened, so a missing
workspace is a message rather than a stack trace.

```bash
uv run agentic-odi --no-update --db "$TOUR_DB" health
```

## 3. See what is in it

Two generated jobs. A real workspace would show the job you are studying.

```bash
uv run agentic-odi --no-update --db "$TOUR_DB" jobs list
```

## 4. Read the job the way the method reads it

Coverage of the eight job-map phases, and the outcomes ranked by opportunity score.

```bash
uv run agentic-odi --no-update --db "$TOUR_DB" summary JOB-0000
```

## 5. The map itself, in order

Eight phases, named in the order the job happens.

```bash
uv run agentic-odi --no-update --db "$TOUR_DB" steps list --job-id JOB-0000
```

## 6. The outcomes behind one phase

Importance, satisfaction, and the score that comes out of the gap between them.

```bash
uv run agentic-odi --no-update --db "$TOUR_DB" desired-outcomes list --job-id JOB-0000 --step-id STP-0000-2
```

## 7. Check the arithmetic yourself

The score is `importance + max(importance - satisfaction, 0)`; nothing is a vibe.

```bash
uv run agentic-odi --no-update --db "$TOUR_DB" score 8 3
```

## 8. Follow a claim back to its evidence

Every statement the strategy leans on resolves to a record with a source.

```bash
uv run agentic-odi --no-update --db "$TOUR_DB" evidence list --outcome-id OUT-00016
```

## 9. Group the need, not the demographic

Segments are clustered on the job map. Confidence is the evidence count, not a
gut feel.

```bash
uv run agentic-odi --no-update --db "$TOUR_DB" segments run --job JOB-0000
```

## 10. Ask what the evidence supports

One path wins, and the paths it beat come back with the reason they lost.

```bash
uv run agentic-odi --no-update --db "$TOUR_DB" strategy propose --job JOB-0000
```

## 11. Read the recommendation again later

The strategy is a stored record, not a chat reply that evaporates.

```bash
uv run agentic-odi --no-update --db "$TOUR_DB" strategy show
```

## 12. Take it with you

The whole study as JSON, ready for a spreadsheet or another tool.

```bash
uv run agentic-odi --no-update --db "$TOUR_DB" data-export --output "$TOUR_OUT/study.json"
```

---

## Where the terminal stops

This cast ends at the exported study because that is where the terminal ends. The
decision brief — the two-page document with the ranked opportunities, their
evidence excerpts and the dissent — is rendered in the browser at
`apps/studio/src/lib/brief.ts`, and the annotated screenshots of it belong to
ALH-236. Neither appears in this recording, because neither is a terminal surface.

The same loop as a conversation, with the job map, the landscape and the segments
as lenses: [The Living Studio](../living-studio.md).
