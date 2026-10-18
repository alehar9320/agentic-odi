# Freebuff Tool Mapping

Skills speak in actions ("dispatch a subagent", "create a todo", "read a file"). On Freebuff these resolve to the tools below.

| Action skills request | Freebuff equivalent |
| --- | --- |
| Invoke or load a skill | `skill` with the skill directory name (for example `{"name": "brainstorming"}`) |
| Create a todo / mark one complete | `write_todos` (rewrite the whole list each call) |
| Read a file | `read_files` |
| Create or overwrite a file | `write_file` |
| Edit a file in place | `str_replace` |
| Delete, move, or rename a file | `run_terminal_command` (`rm`, `mv`) |
| Run a shell command | `run_terminal_command` |
| Search file contents | `code_search` (ripgrep regex; pass `-F` in `flags` for literal text) |
| Find files by name | `glob` |
| List a directory | `list_directory` |
| Fetch a URL | `read_url` |
| Search the web | `web_search` |
| Ask your human partner a question | `ask_user` |
| Dispatch a subagent (`Subagent (general-purpose):` template) | No subagent tool is exposed. Do not fabricate a dispatch; use `executing-plans` and do the work inline. For a second pair of eyes, use the `requesting-code-review` reviewer prompt as a structured self-review, or ask your human partner to start a fresh session. |
| Enter plan mode | Freebuff has no plan mode. Write designs to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` and plans to `docs/superpowers/plans/YYYY-MM-DD-<topic>.md` with `write_file`. |
| Persist progress across compaction | Write the ledger and briefs under `.superpowers/sdd/<plan-basename>/` (see `executing-plans`); `write_todos` is a live view, not durable storage. |

## Skill discovery

Freebuff discovers project skills in `.agents/skills/*/SKILL.md` and lists each skill's name and description in the system prompt. Load a skill by name with the `skill` tool. Reading a `SKILL.md` with `read_files` is only a fallback if the `skill` tool fails; prefer the tool.

## Subagents

This CLI exposes no subagent or task-dispatch tool. Skills that mention `Subagent (general-purpose):` must use their inline fallback:

- `subagent-driven-development` → use `executing-plans` instead.
- `dispatching-parallel-agents` → do the independent tasks sequentially, or explain that parallel dispatch is unavailable.

Never invent `Task`, `subagent`, or similar tool calls.

## Todos and durable state

`write_todos` is the live progress view; update it after each completed item. Freebuff can compact context, so also keep the durable ledger from `executing-plans` in `.superpowers/sdd/<plan-basename>/progress.md`.
