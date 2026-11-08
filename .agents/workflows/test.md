---
description: how to run the test suite
---

# Testing Tiers

There are three tiers. They are not three ways to run "the whole suite" — each
one is a different amount of the product, and the bar for opening a pull
request is the middle one.

| Tier | What it runs | Who runs it |
|---|---|---|
| **Fast** | pytest on the changed packages, ruff on the changed files | anyone who wants a quick answer |
| **Default** | the fast tier, plus type checking, plus the studio units | **the bar for opening a PR** |
| **Full** | the default tier, plus the studio build, plus the browser e2e suite | CI |

`--full` is CI's responsibility. It budgets 5–20 minutes per job
(`.github/workflows/ci.yml`), so nobody is asked to run it locally before
opening a pull request.

The fast tier is the focused gate described in issue #754, which has not
landed yet. Until it does, the fast tier is that gate run by hand — pytest on
the packages the diff touches, lint on the changed files:

## 1. Fast tier

```bash
uv run pytest packages/<changed>     # pytest on the packages the diff touches
uv run ruff check .                  # lint (the fast tier stops at lint, not format)
```

This is the answer to "did I break the thing I just edit". It is not a
statement that the suite passes — it is a statement about the changed slice.

## 2. Default tier — the bar for opening a PR

```bash
uv run pytest                # all Python tests
uv run --directory website pytest tests/
npm --prefix apps/studio test -- --run          # studio units (jsdom)
npm --prefix apps/studio run lint               # ESLint
npm --prefix apps/studio run typecheck          # tsc --noEmit
```

Run this before you open a pull request. If it does not pass, the PR is not
ready for review.

The browser-level end-to-end suite and the production build are **not** part
of this tier. They live in the full tier on purpose: they need a browser
download and a running sidecar, and they are CI's job.

## 3. Full tier — CI's job

```bash
npm --prefix apps/studio run build
npm --prefix apps/studio run test:e2e
```

CI runs this in the `e2e` job against the real Studio, the real sidecar, and
the real MCP server. It is deliberately non-blocking: set the repository
variable `AGENTIC_ODI_E2E` to `false` to skip it, and `continue-on-error`
keeps a failure from turning CI red.

## Honest PR bodies

A pull request names the tiers it ran and the tiers it did not run. In the
"Diff summary" section of the PR template, say which tier was the highest one
the author executed — and say plainly which tiers were skipped and why.

This is the repo's no-silent-fabrication rule applied to verification: a PR
that ran only the fast tier must not read as if it ran the default tier, and
a PR that ran nothing must say so instead of leaving the checkboxes blank.

## Where the tests live

Tests live next to the package they cover (`packages/*/tests`,
`apps/*/tests`, `website/tests`). Every file is named `test_*.py`.

- **pytest + pytest-asyncio in STRICT mode** — `@pytest.mark.asyncio` is
  required on every async test.
- **In-memory by default** — tests use `InMemoryRepository` and
  `AGENTIC_ODI_DB=:memory:`; no running server is required.
- **The `reset_db` fixture** clears in-memory state before every test — do
  not skip it.
- **End-to-end specs** live in `apps/studio/e2e/` and are named `*.spec.ts`.
  They bind to roles, labels, and visible text — never to a `data-testid`, of
  which the application has none.
- **Browser mode** needs Chromium locally: `npx --prefix apps/studio playwright
  install chromium`. The unit suite deliberately ignores `*.visual.test.tsx`;
  those run under Chromatic on every branch push.