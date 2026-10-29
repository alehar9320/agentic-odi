## Summary

<!-- What changed, and why. One or two sentences is enough. -->

## What a person experiences

<!-- The user-visible change, in user terms. Not a list of files. -->

## What changed

<!-- The behavior, files, or commands a reviewer should look at. -->

## How this was verified

<!-- The exact commands you ran and what they printed. "Tests pass" alone does
     not tell a reviewer what was covered. -->

- [ ] Tests pass and docs are updated for behavior, command, or link changes.
- [ ] If this changes the Studio or Worker, I checked `/` on the Cloudflare preview.
- [ ] If this changes `/api/*` or Worker behavior, I checked the expected response with and without `SIDECAR_URL`.

## What this does NOT do

<!-- The explicit scope boundary. Name the adjacent work this PR leaves out. -->

## Diff summary (for machine-generated work)

<!-- Machine-generated PRs must state the true numbers, not the planned ones. -->

- Files changed:
- Tests added:
- Net line delta:

## Mock/stub disclosure

<!-- List anything simulated, stubbed, or faked. Write "none" when nothing is. -->

## Machine-readable diff summary

<!-- Replace the values with the true numbers. The `PR guardrails` check fails
     when this block disagrees with the cumulative diff by more than 20%
     (`changed_files`, `tests_added`) or by more than 10 lines (`net_lines`).
     Leave the block out only when it cannot be filled in. -->

```json
{"changed_files": 0, "tests_added": 0, "net_lines": 0, "simulated": [], "breaking": []}
```

## Deployment

Cloudflare Workers Builds posts the preview URL on this PR. If it is missing,
paste it here:

- Preview URL:
- [ ] Docs-only or fork PR, so no preview is expected.
- [ ] Merging to `main` will update the hosted Studio at https://agentic-odi.alehar.workers.dev/.

## Related issue

<!-- Closes #123, refs #456, or "none". -->

## Agent metadata

<!-- Coding agents: fill in the block below. It is read by the labeler
     workflow to tag this PR. Humans may leave it as-is; the defaults claim
     nothing. Keep the HTML comment markers exactly as they are, and keep the
     JSON on one line or pretty-printed — both parse. A block that cannot be
     parsed gets the "telemetry invalid" label.

     has_breaking_changes: true only if this changes behavior callers depend on.
     agent_confidence:     high | medium | low. "low" requests a deep dive. -->

<!-- AGENT_METADATA {"has_breaking_changes": false, "agent_confidence": "high"} -->
