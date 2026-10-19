# Kiro CLI Tool Mapping

Skills speak in actions ("dispatch a subagent", "create a todo", "read a file"). On the Kiro CLI these resolve to the tools below.

| Action skills request | Kiro CLI equivalent |
|---|---|
| Invoke or load a skill | Read the skill's `SKILL.md` with the `read` tool and follow its instructions directly |
| Create a todo / mark one complete | `todo_list` (create, add, complete, remove commands) |
| Read a file | `read` tool (Line or Directory mode) |
| Create or overwrite a file | `write` tool (create command) |
| Edit a file in place | `write` tool (strReplace command) |
| Insert content into a file | `write` tool (insert command) |
| Delete, move, or rename a file | `shell` tool (`rm`, `mv`) |
| Run a shell command | `shell` tool |
| Search file contents | `grep` tool (regex pattern search) |
| Search by symbol / semantic code search | `code` tool (search_symbols, pattern_search, etc.) |
| Find files by name | `glob` tool |
| List a directory | `read` tool (Directory mode) |
| Fetch a URL | `web_fetch` tool |
| Search the web | `web_search` tool |
| Ask your human partner a question | Respond to the user in your message |
| Dispatch a subagent (`Subagent (general-purpose):` template) | `subagent` tool with a `kiro_default` stage (blocking mode) |
| Enter plan mode | `todo_list` to track steps; write designs to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` |
| Persist progress across compaction | `todo_list` state is session-local; write ledger and briefs under `.superpowers/sdd/<plan-basename>/` (see `executing-plans`) |

## Skill discovery

Kiro has no automatic skill-loading tool. Skills live in `.agents/skills/*/SKILL.md`. Read a skill file with the `read` tool before following it.

## Subagents

Kiro exposes a `subagent` tool that runs agent pipelines. Use it for the `Subagent (general-purpose):` dispatch template in skills:

```json
{
  "task": "<overall task description>",
  "stages": [
    {
      "name": "implementer",
      "role": "kiro_default",
      "prompt_template": "<task instructions>"
    }
  ]
}
```

For `subagent-driven-development`, dispatch one implementer stage per task (blocking mode) and review its output before continuing. Parallel stages (no `depends_on`) run concurrently — use them when tasks are independent. When no parallel work is needed, dispatch stages sequentially.

## Task lists / todos

`todo_list` is the primary task-tracking mechanism. Use the `create` command at the start of a multi-step task, `complete` as each step finishes, and `add`/`remove` when the plan changes. `todo_list` is session-local, so also write a durable progress ledger to `.superpowers/sdd/<plan-basename>/progress.md` when running `executing-plans`.

## Plan mode

Kiro has no separate plan mode. Write plans to:

- Designs: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- Plans: `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`

Then execute them step-by-step, tracking progress with `todo_list`.

## Git worktrees

Kiro has no native worktree tool. Follow the `using-git-worktrees` skill Step 1b (git worktree fallback) to create worktrees manually. Check isolation first (Step 0) before creating anything.
