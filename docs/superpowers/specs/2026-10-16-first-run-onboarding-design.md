# First-Run Onboarding (PM Baseline) Design

**Date:** 2026-10-16
**Status:** Approved
**Scope:** CLI first-launch experience + persistent PM baseline profile

## Intent & Why

Agentic ODI ships 69 PM skills (vendored from Paweł Huryn's pm-skills) and an ODI/JTBD agent, but nothing establishes *who the user is* — domain, audience, business model, current goal. Every skill run starts cold, asking generic questions or guessing. The fix: one designed first-run moment that captures (mostly auto-detects) a minimal product/domain baseline, persists it, and lets the agent and skills consume it forever after.

Jobsian bar: the PM should never fill out a form. They give **one input — a product URL or company name** — the CLI fetches and infers, prints a small confirmation card, and one keypress completes setup. Typed questions exist only as fallback when the fetch fails or inference is unclear. Total happy-path effort: ~30 seconds, one keystroke.

## Goals

- First `agentic-odi` invocation (interactive TTY) triggers a short, designed onboarding moment instead of a bare help screen.
- Happy path: **URL → fetch → infer → confirm card → done**.
- Fallback path (fetch fails / non-obvious site / user prefers typing): **3 typed questions with suggested defaults**.
- Baseline persisted to `~/.config/agentic-odi/baseline.json` (XDG-overridable); never re-prompts once the file exists.
- `odi setup` re-runs onboarding; `odi profile` shows the current baseline.
- PM skills / agent can later read the baseline file as standing context; follow-ups happen only when a specific task needs missing fields (out of scope to implement here beyond exposing the file and a `profile` command).

## Non-Goals / Anti-Goals

- No long diagnostic questionnaire (the 15-question PM audit is explicitly rejected).
- No LLM call during onboarding (no API key exists yet at first run; inference must be deterministic, offline-capable keyword mapping).
- No storage of secrets (API keys stay in env, as today).
- No GUI/Streamlit changes (CLI only; GUI can adopt the file later).
- No dependency on the unfinished bundled-distribution work (`paths.py`, auto-update). If that plan lands first, its `paths.config_dir()` should replace the local helper (see Open Questions).

## User Flow

### 1. Trigger

- Hook in the root Typer callback (`cli/src/cli/cli.py` `main()`).
- Runs only when: baseline file absent **AND** stdin/stdout are TTYs **AND** command is not `--version`/`version` and not `setup`/`profile` (those manage it explicitly).
- Non-interactive first run (pipes, CI): print one hint line — `Run 'odi setup' to create your PM baseline.` — and continue; never block.

### 2. Opening (the designed moment)

```
Agentic ODI — your ODI/JTBD + PM-skills workspace.

Let's set up your context so every skill starts smart.
First: what product are you working on?
Paste a product URL or company name:
```

### 3. Happy path — URL auto-detect

1. Accept URL or bare name (normalize `acme.com` → `https://acme.com`).
2. Fetch with httpx (httpx already a workspace dep): homepage, ~8s timeout, no retries, follow ≤3 redirects, conservative UA header. Optionally try `/pricing` and `/about` if homepage text is thin (<200 words).
3. Extract signals: `<title>`, meta description, og tags, H1/H2 text, nav labels, pricing hints ("per seat", "free tier", "usage-based").
4. **Inference engine** (pure-Python heuristic, `onboard/infer.py`): keyword dictionaries map extracted text → domain archetype (DevTools, FinTech, HealthTech, MarTech, Marketplace, B2B SaaS, B2C, etc.), business model hints (PLG/freemium vs sales-led), and candidate primary user. Deterministic and unit-testable; low-confidence results fall back to the typed path with the inferred values pre-filled as suggestions.
5. Show the confirmation card:

```
Based on sentry.io — does this look right?

  Domain      Developer Tools / Observability
  Users       Software engineers, DevOps teams
  Business    B2B SaaS · Product-led (freemium → team plans)
  Solves      Real-time error tracking & debugging

  [Enter] confirm   [e] edit a line   [r] retry URL   [q] quit
```

6. `e` asks only for the lines the user picks, with current value as the default. `r` returns to URL prompt. Confirm writes `baseline.json` and prints a one-line success (`Saved to ~/.config/agentic-odi/baseline.json — you're set. Try: odi outcomes list`).

### 4. Fallback — typed path (3 questions)

Entered on fetch failure, low inference confidence, or if the user types `skip` at the URL prompt. Each question offers suggestions (from partial inference when available):

1. **Domain** — free text with hint list (B2B SaaS, DevTools, FinTech, HealthTech, Marketplace, …).
2. **Who uses it** — primary user/job ("e.g., Staff engineers reducing CI friction").
3. **What matters most right now** — launch / activation / retention / scaling / discovery (single select from menu via arrow keys — Typer+readchar or plain numbered menu; numbered menu chosen for zero extra deps).

Then the same confirmation card and save.

### 5. After onboarding

- Baseline file presence suppresses the hook forever.
- `odi setup` — full re-run, overwrites file (keeps a timestamped backup).
- `odi profile` — print the current card from the file. (`setup`/`profile` confirmed: plain language, matches the reserved `odi` alias.)
- All user-facing copy (hints, "Try: …" lines) uses the invoked program name (`sys.argv[0]` basename) so it is valid on any install, `odi` or `agentic-odi`.
- Skills/agent consumption (future): the file path is stable and documented; `odi profile --json` dumps machine-readable baseline.

## Data Model

`~/.config/agentic-odi/baseline.json` (dir per XDG_CONFIG_HOME, Windows %APPDATA%):

```json
{
  "schema_version": 1,
  "created_at": "2026-10-16T12:00:00Z",
  "source": "url" | "typed",
  "product": {"name": "Sentry", "url": "https://sentry.io"},
  "domain": "Developer Tools / Observability",
  "primary_user": "Software engineers & DevOps teams",
  "business_model": "B2B SaaS · Product-led growth",
  "core_problem": "Real-time application error tracking & code-level debugging",
  "current_focus": null | "launch" | "activation" | "retention" | "scaling" | "discovery",
  "confidence": "high" | "low"
}
```

Missing/optional fields are `null`, not guessed — later skills ask just-in-time for what they need. The typed path stays at 3 questions; `product.name` may be empty, `business_model`/`core_problem`/`current_focus` may be null, and the confirmation card renders only the lines we actually know.

## Code Layout (new)

```
cli/src/cli/onboard.py      # flow orchestration (prompt, fetch, confirm, save)
cli/src/cli/profile.py      # load/save baseline, `profile` + `setup` commands
cli/src/cli/infer.py        # heuristic domain/model inference from page text
cli/tests/test_onboard.py
cli/tests/test_infer.py
cli/tests/test_profile.py
```

- `paths` helper lives in `profile.py` for now (config dir resolution only: `XDG_CONFIG_HOME` → `~/.config`, Windows `%APPDATA%`), deliberately minimal to avoid coupling to the distribution plan.
- httpx used for fetch; inference has no network/LLM deps.

## Copy & Polish Rules (the Jobsian part)

- Total onboarding text on screen at once: one card, no scrolling paragraph.
- Voice: warm, direct, second person; no jargon dumps; no emoji.
- Every prompt has a sensible default or suggestion; Enter almost always works.
- Failure is silent-and-graceful: fetch errors fall to typed path without a scary traceback; one soft line (`Couldn't read that site — two quick questions instead.`).
- `--no-onboard` global flag to bypass (for scripting/tests); env `AGENTIC_ODI_NO_ONBOARD=1` equivalent.

## Constraints

- Python 3.10+, Typer, pytest — already in the workspace. `httpx` is **added** as a declared dependency of the `cli` package (builder check correction: it was not one; it is the fetch client of choice, and its `MockTransport` powers the fetch tests). Tests must not touch the real home dir (tmp_path + env overrides).
- Fetch tests use mocked transport (`httpx.MockTransport`), never live network.

## Review Focus (likely to bite)

1. Fetch hang/timeout on weird sites — hard 8s timeout, errors → typed path.
2. TTY detection wrong in some terminals — conservative check; hint-line behavior in non-TTY.
3. Inference confidently wrong — confirmation card always shown; nothing saved without confirm.
4. Concurrent first runs — file written atomically (temp file + replace).
5. `--version` and help must never trigger onboarding.

## Resolved Questions

1. Command naming: **`odi setup` / `odi profile`** (plain language; matches reserved `odi` alias). Copy uses the invoked program name.
2. `current_focus`: **just-in-time only** — not asked on the happy path; asked as the 3rd typed question in the fallback path.

## Builder Calls (made during review)

1. Typed-path fields: schema fields other than `schema_version` are nullable; card renders only non-null lines.
2. `httpx` added as an explicit `cli` package dependency (spec previously, incorrectly, claimed it already was).
