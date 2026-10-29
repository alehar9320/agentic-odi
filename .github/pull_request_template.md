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
