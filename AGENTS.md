# Agent Instructions

<!-- superpowers:freebuff:start -->
<EXTREMELY_IMPORTANT>
> **Harness scope:** This section is the Freebuff integration. If you are running under OpenCode, Pi, Claude Code, or another harness that already injects Superpowers, keep following that integration and ignore the Freebuff-specific tool mapping below.

You have superpowers.

**IMPORTANT: The using-superpowers skill content is included below. It is ALREADY LOADED — you are currently following it. Do NOT use the `skill` tool to load "using-superpowers" again — that would be redundant.**

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, ignore this skill.
</SUBAGENT-STOP>

<EXTREMELY-IMPORTANT>
If you think there is even a 1% chance a skill might apply to what you are doing, you ABSOLUTELY MUST invoke the skill.

IF A SKILL APPLIES TO YOUR TASK, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT.

This is not negotiable. You cannot rationalize your way out of this.
</EXTREMELY-IMPORTANT>

## The Rule

**Invoke relevant or requested skills BEFORE any response or action** — including clarifying questions, exploring the codebase, or checking files. If it turns out wrong for the situation, you don't have to use it.

**Before entering plan mode:** if you haven't already brainstormed, invoke the brainstorming skill first.

Then announce "Using [skill] to [purpose]" and follow the skill exactly. If it has a checklist, create a todo per item.

## Skill Priority

When multiple skills apply, process skills come first — they set the approach, then implementation skills (frontend-design, etc.) carry it out. Brainstorming and systematic-debugging are Superpowers' most common process skills, but the rule holds for any of them.

- "Let's build X" → superpowers:brainstorming first, then implementation skills.
- "Fix this bug" → superpowers:systematic-debugging first, then domain skills.

## Red Flags

These thoughts mean STOP—you're rationalizing:

| Thought | Reality |
|---------|---------|
| "This is just a simple question" | Questions are tasks. Check for skills. |
| "I need more context first" | Skill check comes BEFORE clarifying questions. |
| "Let me explore the codebase first" | Skills tell you HOW to explore. Check first. |
| "I can check git/files quickly" | Files lack conversation context. Check for skills. |
| "Let me gather information first" | Skills tell you HOW to gather information. |
| "This doesn't need a formal skill" | If a skill exists, use it. |
| "I remember this skill" | Skills evolve. Read current version. |
| "This doesn't count as a task" | Action = task. Check for skills. |
| "The skill is overkill" | Simple things become complex. Use it. |
| "I'll just do this one thing first" | Check BEFORE doing anything. |
| "This feels productive" | Undisciplined action wastes time. Skills prevent it. |
| "I know what that means" | Knowing the concept ≠ using the skill. Invoke it. |

## Platform Adaptation

If your harness appears here, read its reference file for special instructions:

- Freebuff: `references/freebuff-tools.md` (installed at `.agents/skills/using-superpowers/references/freebuff-tools.md`)
- Claude Code: `references/claude-code-tools.md`
- Codex: `references/codex-tools.md`
- Pi: `references/pi-tools.md`
- Antigravity: `references/antigravity-tools.md`
- Hermes Agent: `references/hermes-tools.md`
- Muse: `references/muse-tools.md`

## User Instructions

User instructions (CLAUDE.md, AGENTS.md, GEMINI.md, etc, direct requests) take precedence over skills, which in turn override default behavior. Only skip skill workflows or instructions when your human partner has explicitly told you to.

## Freebuff Tool Mapping

Skills speak in actions, not tool names. On Freebuff they resolve as follows:

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

Freebuff discovers project skills in `.agents/skills/*/SKILL.md` and lists each skill's name and description in the system prompt. Load one by name with the `skill` tool; reading a `SKILL.md` with `read_files` is only a fallback if the tool fails.

This CLI exposes no subagent or task-dispatch tool. Use `executing-plans` instead of `subagent-driven-development`, and do independent tasks sequentially instead of `dispatching-parallel-agents`. Never invent `Task`, `subagent`, or similar tool calls.
</EXTREMELY_IMPORTANT>
<!-- superpowers:freebuff:end -->

<!-- superpowers:kiro:start -->
<EXTREMELY_IMPORTANT>
> **Harness scope:** This section is the Kiro CLI integration. If you are running under Freebuff, OpenCode, Pi, Claude Code, or another harness that already injects Superpowers, keep following that integration and ignore the Kiro-specific tool mapping below.

You have superpowers.

**IMPORTANT: The using-superpowers skill content is included below. It is ALREADY LOADED — you are currently following it. Do NOT re-read `SKILL.md` for "using-superpowers" — that would be redundant.**

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, ignore this skill.
</SUBAGENT-STOP>

<EXTREMELY-IMPORTANT>
If you think there is even a 1% chance a skill might apply to what you are doing, you ABSOLUTELY MUST invoke the skill.

IF A SKILL APPLIES TO YOUR TASK, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT.

This is not negotiable. You cannot rationalize your way out of this.
</EXTREMELY-IMPORTANT>

## The Rule

**Invoke relevant or requested skills BEFORE any response or action** — including clarifying questions, exploring the codebase, or checking files. If it turns out wrong for the situation, you don't have to use it.

**Before entering plan mode:** if you haven't already brainstormed, invoke the brainstorming skill first.

Then announce "Using [skill] to [purpose]" and follow the skill exactly. If it has a checklist, create a todo per item.

## Skill Priority

When multiple skills apply, process skills come first — they set the approach, then implementation skills (frontend-design, etc.) carry it out. Brainstorming and systematic-debugging are Superpowers' most common process skills, but the rule holds for any of them.

- "Let's build X" → superpowers:brainstorming first, then implementation skills.
- "Fix this bug" → superpowers:systematic-debugging first, then domain skills.

## Red Flags

These thoughts mean STOP—you're rationalizing:

| Thought | Reality |
|---------|---------|
| "This is just a simple question" | Questions are tasks. Check for skills. |
| "I need more context first" | Skill check comes BEFORE clarifying questions. |
| "Let me explore the codebase first" | Skills tell you HOW to explore. Check first. |
| "I can check git/files quickly" | Files lack conversation context. Check for skills. |
| "Let me gather information first" | Skills tell you HOW to gather information. |
| "This doesn't need a formal skill" | If a skill exists, use it. |
| "I remember this skill" | Skills evolve. Read current version. |
| "This doesn't count as a task" | Action = task. Check for skills. |
| "The skill is overkill" | Simple things become complex. Use it. |
| "I'll just do this one thing first" | Check BEFORE doing anything. |
| "This feels productive" | Undisciplined action wastes time. Skills prevent it. |
| "I know what that means" | Knowing the concept ≠ using the skill. Invoke it. |

## Platform Adaptation

If your harness appears here, read its reference file for special instructions:

- Kiro: `.agents/skills/using-superpowers/references/kiro-tools.md`
- Freebuff: `.agents/skills/using-superpowers/references/freebuff-tools.md`
- Claude Code: `.agents/skills/using-superpowers/references/claude-code-tools.md`
- Codex: `.agents/skills/using-superpowers/references/codex-tools.md`
- Pi: `.agents/skills/using-superpowers/references/pi-tools.md`
- Antigravity: `.agents/skills/using-superpowers/references/antigravity-tools.md`
- Hermes Agent: `.agents/skills/using-superpowers/references/hermes-tools.md`
- Muse: `.agents/skills/using-superpowers/references/muse-tools.md`

## User Instructions

User instructions (CLAUDE.md, AGENTS.md, GEMINI.md, etc, direct requests) take precedence over skills, which in turn override default behavior. Only skip skill workflows or instructions when your human partner has explicitly told you to.

## Kiro Tool Mapping

Skills speak in actions, not tool names. On Kiro CLI they resolve as follows:

| Action skills request | Kiro CLI equivalent |
| --- | --- |
| Invoke or load a skill | Read the skill's `SKILL.md` with the `read` tool and follow its instructions directly |
| Create a todo / mark one complete | `todo_list` (create, add, complete, remove commands) |
| Read a file | `read` tool (Line or Directory mode) |
| Create or overwrite a file | `write` tool (create command) |
| Edit a file in place | `write` tool (strReplace command) |
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
| Persist progress across compaction | Write the ledger and briefs under `.superpowers/sdd/<plan-basename>/` (see `executing-plans`) |

Skills live in `.agents/skills/*/SKILL.md`. Kiro has no automatic skill-loading tool — read a `SKILL.md` with the `read` tool before following it.

For the full Kiro tool reference including subagent dispatch patterns and git worktree instructions, read `.agents/skills/using-superpowers/references/kiro-tools.md`.
</EXTREMELY_IMPORTANT>
<!-- superpowers:kiro:end -->

## Project Instructions

- Read `.agents/rules/agent_instructions.md` for the ODI domain guardrails, MCP conventions, testing strategy, and README maintenance rules.
- Keep `README.md` current in the same task whenever code, commands, dependencies, or capabilities change.
- Architecture and data-flow details live in `docs/architecture/`; update them when the package graph or runtime boundaries change.
- Superpowers artifacts belong under `docs/superpowers/`: designs in `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`, plans in `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`.
- Run `uv run pytest` from the root; see `.agents/workflows/test.md` and `docs/architecture/testing.md` for focused commands.

## Surface parity (learned the hard way)

- Every user-facing surface is a **thin adapter over one `ODIService` call**. A new outcome
  field must be threaded through *all* adapters in the same change — core renderer, MCP tool,
  CLI, Studio API, Studio card. A field added to the core model but omitted by an adapter is a
  silent defect (the CLI `brief export` once dropped the W1 value fields and always said "worth
  is unknown").
- After adding a field or section, exercise each surface end to end, not just the unit that owns
  it. The real CLI entry point is `agentic-odi` (`agentic_odi_cli.cli:app`); the Studio sidecar
  is `agentic-odi-studio-api` and reads `AGENTIC_ODI_DB` (default `~/.agentic-odi/odi.db`).
- "No fabricated numeral" tests must derive their allow-list **deterministically** from recorded
  inputs, computed scores, and structural positions. Pulling numerals out of a random UUID (as
  one pillar test did) makes the assertion pass by luck.
- A **second assembly path is a second place to forget a section**. `render_brief` gained a
  `strategy` field and `build_brief` supplied it, but the CLI's `brief export` builds its own
  `BriefInput` from `run_tool` records and dropped it — the section vanished from the exported
  file while the core brief still rendered it. When two callers assemble the same input, extract
  the *selection* rule into a pure function in the core module and have both call it; do not
  copy the rule.


## Merging `origin/main` into a long-lived feature branch

- Resolve by **union, not by picking a side**, when both branches added to the same region
  (entities, service methods, MCP tools, router handlers). Verify the union mechanically: parse
  each side and the merged file with `ast` and assert `ours - merged == []` and
  `theirs - merged == []` for top-level names, and scan for duplicate method names inside a class
  (a set-based check hides a duplicated method).
- A `git checkout -m -- <file>` or a partially-staged resolution makes a later `git merge-file`
  treat the *staged* content as "ours". If a resolution looks wrong, regenerate the three stages
  with `git show :1:/:2:/:3:<path>` and re-run `git merge-file` on the true stages.
- Splices leave duplicate imports and stray blank lines. After resolving, run
  `uv run ruff check . --fix && uv run ruff format .` before trusting the diff — `I001`/`F811`
  catch the leftover union imports.
- **Semantic merge bugs hide where both sides changed one function.** A function that main
  rewrote and the branch extended can silently lose one side's behavior. Re-read the merged body
  of any function both sides touched (`update_outcome` dropped main's signal emission this way);
  the full suite's behavior tests, not the import check, catch it.
- Raise a size/budget tripwire to the measured merged size, never to the larger of the two old
  constants, and say in the comment what grew. The website page budget is a build-from-source
  test, so the real byte count is what matters.
- CI (`npm run lint`) can fail on branch code that predates a plugin bump from main (the
  `react-hooks` immutability rule). Fix the branch code (precompute instead of mutating during
  render) rather than loosening the config.
