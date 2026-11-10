# Superpowers (Pi, OpenCode & Freebuff)

This project includes [Superpowers](https://github.com/obra/superpowers) as a
[Pi package](https://pi.dev/docs/packages). When using [Pi](https://pi.dev) with
this project, Superpowers skills and extensions are automatically loaded.

## Enable with Pi

1. Install Pi: `curl -fsSL https://pi.dev/install.sh | sh`
2. Trust the project (first time only): `pi config --local --approve`
3. Start Pi: `pi`

The `.pi/settings.json` declares the Superpowers package. Pi clones it and loads:

- **Extension**: `superpowers.ts` — injects the `using-superpowers` bootstrap at
  session startup and after compaction
- **Skills**: 12 Superpowers skills (TDD, subagent-driven-development,
  systematic-debugging, etc.)

> [!NOTE]
> Superpowers is also available for OpenCode via the plugin in `opencode.json`.
> The Pi package provides native Pi integration without needing the OpenCode
> compatibility layer.

## Freebuff

This project ships [Superpowers](https://github.com/obra/superpowers) for
[Freebuff](https://freebuff.com) as repo-local skills plus a session-start
bootstrap. No plugin or hook is required:

- **Skills**: `.agents/skills/` contains 15 Superpowers skills. Freebuff
  discovers them automatically; load one with the `skill` tool.
- **Bootstrap**: `AGENTS.md` injects the `using-superpowers` rules and the
  Freebuff tool mapping at session start.
- **Mapping**: `.agents/skills/using-superpowers/references/freebuff-tools.md`
  maps skill actions to Freebuff tools.

Start Freebuff in the repository and ask "What are your superpowers?" to verify.
See [docs/superpowers/freebuff-setup.md](superpowers/freebuff-setup.md) for
update and troubleshooting notes.
