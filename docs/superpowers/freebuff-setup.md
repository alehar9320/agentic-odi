# Superpowers for Freebuff

Freebuff uses the same [Superpowers](https://github.com/obra/superpowers) methodology as the OpenCode and Pi integrations, delivered through the two surfaces Freebuff loads automatically:

1. **Skills** — `.agents/skills/` contains the 15 Superpowers skills. Freebuff scans `.agents/skills/*/SKILL.md`, validates each frontmatter block, and lists every skill's name and description in the system prompt. The `skill` tool loads one by name.
2. **Bootstrap** — `AGENTS.md` at the repository root carries the `using-superpowers` bootstrap, the Freebuff tool mapping, and a pointer to the project guardrails. Freebuff loads project `AGENTS.md` at session start, so the methodology is active without a plugin or hook. The section is explicitly scoped to Freebuff so OpenCode and Pi keep using their own integrations.
3. **Reference mapping** — `.agents/skills/using-superpowers/references/freebuff-tools.md` is the detailed action-to-tool translation. `AGENTS.md` inlines the same mapping so it is present even before a skill is loaded.

## Layout

```text
AGENTS.md                                        # session-start bootstrap + Freebuff mapping
.agents/skills/<skill>/SKILL.md                  # 15 vendored Superpowers skills
.agents/skills/using-superpowers/references/
  freebuff-tools.md                              # detailed Freebuff tool mapping
skills-lock.json                                 # source + hash for `npx skills update`
```

## First run

Freebuff may ask whether to trust a repository's `.agents` directory the first time it sees one. Approve it interactively, or pass `--trust-agents` (intended for CI) when starting Freebuff.

## Verify

Start a fresh Freebuff session in this repository and ask:

```text
What are your superpowers?
```

The agent should know it has Superpowers and list the installed skills. The real acceptance check is:

```text
Let's make a react todo list
```

`brainstorming` must trigger before any code is written.

## Updating

The skill tree is committed, so a fresh clone needs no install step. To pull the latest Superpowers skills:

```bash
npx skills update -y
```

To reinstall from upstream:

```bash
npx skills add obra/superpowers --agent universal --skill '*' --copy -y
```

The `universal` target installs to `.agents/skills/`, which is the directory Freebuff scans. After an update, confirm `.agents/skills/using-superpowers/references/freebuff-tools.md` still exists; the `AGENTS.md` bootstrap is independent of the skill tree and survives skill updates.

## Freebuff limitations

- **No subagent tool.** Use `executing-plans` instead of `subagent-driven-development`, and run independent tasks sequentially instead of `dispatching-parallel-agents`.
- **No plan mode.** Designs and plans are written to `docs/superpowers/specs/` and `docs/superpowers/plans/` with `write_file`.
- **No session hooks.** `AGENTS.md` is the session-start surface; there is no plugin to install and no per-session opt-in.
- **Compaction.** `write_todos` is a live view. Keep the durable ledger from `executing-plans` under `.superpowers/sdd/<plan-basename>/progress.md`.
