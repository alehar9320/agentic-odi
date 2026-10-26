## Summary

<!-- What changed, and why. One or two sentences is enough. -->

## What changed

<!-- The behavior, files, or commands a reviewer should look at. -->

## Verification

<!-- What you ran and what it proved. Paste the command and its result;
     "tests pass" alone does not tell a reviewer what was covered. -->

- [ ] Tests pass and docs are updated for behavior, command, or link changes.
- [ ] If this changes the Studio or Worker, I checked `/` on the Cloudflare preview.
- [ ] If this changes `/api/*` or Worker behavior, I checked the expected response with and without `SIDECAR_URL`.

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
