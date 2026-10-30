# The decision artifact: brief, decision, bet, measure

A decision is worth nothing until it is written down with its reason and its
test. This guide covers the last four stages of the spine — **brief → decision →
bet → measure** — and shows the empty states each stage reports instead of
inventing a number.

It continues from [Scoring and the landscape](scoring.md). Everything here is
available through the MCP tool surface; where a CLI wrapper exists it is shown
too.

## The whole chain in one snippet

The fastest way to see the loop is to drive it through the MCP tool surface.
This is the exact sequence the end-to-end test walks
(`tests/e2e/test_spine.py`):

```python
import asyncio, json, os, re, tempfile

os.environ["AGENTIC_ODI_DB"] = tempfile.mktemp(suffix=".db")
from agentic_odi_mcp_server import mcp_server
from fastmcp import Client


def _j(text):  # a tool reply may prefix a sentence to its JSON body
    return json.loads(re.search(r"[\{\[].*[\}\]]", text, re.DOTALL).group(0))


async def main():
    async with Client(mcp_server.mcp) as client:
        job = _j((await client.call_tool("add_job", {"name": "Onboard customers"})).content[0].text)

        candidates = _j(
            (
                await client.call_tool(
                    "extract_candidates",
                    {
                        "quote_id": "q-1",
                        "quote": "Minimize the time it takes to onboard when a customer signs up.",
                        "job_id": job["id"],
                    },
                )
            )
            .content[0]
            .text
        )

        outcome = _j(
            (
                await client.call_tool(
                    "accept_candidate",
                    {
                        "candidate_id": candidates[0]["id"],
                        "importance": 9.0,
                        "satisfaction": 4.0,
                    },
                )
            )
            .content[0]
            .text
        )
        print("outcome", outcome["id"], outcome["opportunity_score"])  # 14.0

        brief = _j(
            (await client.call_tool("get_brief", {"subject_id": outcome["id"]})).content[0].text
        )
        print("brief", brief["headline"])

        decision = _j(
            (
                await client.call_tool(
                    "record_decision",
                    {
                        "subject_id": outcome["id"],
                        "choice": "build",
                        "rationale": "underserved and frequent",
                    },
                )
            )
            .content[0]
            .text
        )

        bet = _j(
            (
                await client.call_tool(
                    "track_bet",
                    {
                        "decision_id": decision["id"],
                        "statement": "activation within a day rises",
                        "metric": "time_to_first_value",
                    },
                )
            )
            .content[0]
            .text
        )

        measurement = _j(
            (await client.call_tool("get_measurement", {"bet_id": bet["id"]})).content[0].text
        )
        print("measurement", measurement["value"])  # None — nothing measured yet


asyncio.run(main())
```

## 1. The brief

The CLI renders it with `brief`; the MCP tool `get_brief` returns the same
object. Each figure carries its **basis** — the words that say where the number
came from.

```bash
agentic-odi brief <outcome-id>
```

```
Minimize the time it takes to onboard when a customer signs up.

opportunity_score  14.00
                   importance 9.0 + max(importance - satisfaction, 0) at satisfaction 4.0
decisions          0.00
                   0 decisions recorded
```

```json
{
  "subject_id": "…",
  "headline": "Minimize the time it takes to onboard when a customer signs up.",
  "figures": [
    {"name": "opportunity_score", "value": 14.0,
     "basis": "importance 9.0 + max(importance - satisfaction, 0) at satisfaction 4.0"},
    {"name": "decisions", "value": 0.0, "basis": "0 decisions recorded"}
  ]
}
```

Nothing in the brief is authored prose. Every numeral is interpolated from a
stored object, and a figure with no data is reported with a basis that says so
(`0 decisions recorded`) rather than a placeholder.

## 2. The decision

`record_decision` writes a traceable choice: **what** was chosen and **why**.

```json
{"subject_id": "…", "choice": "build", "rationale": "underserved and frequent"}
```

The reply is the recorded decision with its id and timestamp. A decision without
a rationale is refused — the reason is part of the artifact, not an optional
note.

## 3. The bet

`track_bet` attaches the test to a decision: the statement that should become
true and the metric that would move.

```json
{"decision_id": "…", "statement": "activation within a day rises", "metric": "time_to_first_value"}
```

The reply carries the bet's id and its `baseline`. The baseline is `None` until
a measurement establishes one — the product does not invent a starting number.

## 4. The measurement

`get_measurement` reads the bet's observation:

```json
{"bet_id": "…", "metric": "time_to_first_value", "value": null, "observed_at": null}
```

`value` is `null` until something is actually measured. **A null measurement is
not a zero result.** The stage reports "nothing measured yet"; it never
fabricates a passing value.

## Empty and failure paths

- **No decision yet.** A subject with no decision has no brief figures for
  decisions; the brief says `0 decisions recorded`.
- **No measurement yet.** `get_measurement` returns `value: null`, not `0`.
- **Unknown id.** Each stage raises a typed error naming the id it could not
  resolve (surfaced over MCP as a not-found message), rather than returning an
  empty object that looks like real data.

## Not yet delivered

The CLI has no `decide`, `bet`, or `measure` command yet, and there is no
`compare` or `roadmap` command — those arrive with the M4 publish work. Until
then, drive the brief/decision/bet/measure stages through the MCP tool surface
as shown above. The commands this guide does not show are not claimed as shipped.

## See also

- [CLI reference](cli.md) — the commands that do exist, with every flag.
- [Architecture: the spine seam](architecture/spine.md) — how a stage lands
  without a stub pretending to be real.
- [Scoring and the landscape](scoring.md) — the scores the brief reads.
