# Agent claim convention (single primitive)

**Primitive:** claim via an agent branch named `<agent>/<YYYY-MM-DD>-<issue>[-<slug>]` with an open pull request that references the issue (`Closes #<issue>`). The PR provenance labeler classifies agent authorship from the branch prefix (see `scripts/pr_provenance.py`).

## Pre-flight check (one command)
Before starting work on an issue:

```bash
gh pr list --repo alehar9320/agentic-odi --state open --search '<issue> in:body,title'
gh issue view <issue> --repo alehar9320/agentic-odi --json number,title,labels,assignees
```

If there is an open PR that references the issue, or the issue has `status/in-progress`, treat it as claimed. Check the PR head branch and issue comments/timestamps to determine who/when. If claimed and recent (< 24h) and no indication of abandonment, pick another issue.

## Expiry
A claim (branch/PR/`status/in-progress`) with no push activity and no open PR progress after **24 hours** is stale. To take over a stale claim: comment on the issue noting you're taking over a stale claim, remove/replace `status/in-progress` as appropriate, create your own branch/PR, or ask the human to release it. Never steal in-flight work without checking activity. Abandoned branches may be deleted by humans; agents must not auto-delete others' branches.

## Legacy labels
The following are historical and must not be created for new claims: `agent-claim/*`, `claimed/*`, `agent-handoff` (treat as workflow state, not a claim primitive), and ad-hoc `agent/opencode-*` date labels. Existing ones on closed issues remain as history.
