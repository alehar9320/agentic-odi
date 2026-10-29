# The first minute in The Living Studio — design

**Date:** 2026-10-23
**Status:** approved for implementation (partner brief: remove the gate, guide in place)
**Scope:** `apps/studio` only. No sidecar, MCP, or API changes.

## Intent

We have a few seconds to show a new PM that this is worth their time. Today the
studio spends those seconds on a four-step modal that covers the product before
the person has touched it, and — behind it — an interview that replaces the
conversation before they have typed a word. Both are well made. Both are gates.

The first impression should be the opposite: the product, completely available,
with one clear invitation and a quiet voice that helps only when it is useful.

> The stage is the tutorial. The agent asks; the interface answers.

## What is wrong now

1. **The modal auto-opens on the first run.** `OnboardingProvider` opens the
   four-step tour whenever stored state is `pending` or `active`, so the first
   frame is a dialog over a dimmed product.
2. **The interview auto-opens too.** `StudioContext` initialises `setupOpen` to
   true when there is no brief, so even after skipping the tour the person lands
   in a four-question conversation instead of the studio.
3. **The first headline is "Good morning".** The hero's first candidate is the
   time of day. It is warm and says nothing about why the person is here.
4. **The empty-canvas third pill opens an empty landscape.** On a fresh install
   it is a dead end at exactly the wrong moment.
5. **Nothing teaches after the first exchange.** Once the hero is gone, the only
   guidance is `/help`.

## Goals

1. The first frame is the studio itself: headline, three starters, composer
   focused. No dialog, no interview, no required step.
2. One invitation, phrased in the PM's language, before any feature talk.
3. Teaching happens in place, one hint at a time, and only when it can change
   what the person does next.
4. The tour survives as a **tour**: explicit, resumable, replayable, never
   auto-opened.
5. Context capture moves to the moment it earns its keep — after the studio has
   given something back.

## Non-goals

- Redesigning the tour's four steps. Its UX is sound; only its entry changes.
- New agent capabilities, tools, or sidecar prompts.
- Transcript persistence, analytics, or a backend onboarding record.

## The experience

### First frame

```
LIVING STUDIO

What do you want to win?
One sentence is enough. I'll help you test whether it's worth chasing.

[Sharpen an opportunity] [Find the next one] [Pressure-test a bet]
                              Tell me what you're building · Show me around

[ Start with what's on your mind…                            ↑ ]
Enter to send · / for commands
```

- The hero opens on a **capability question**, not a greeting, and holds it
  still for the whole first run — the headline must not change while someone is
  deciding what to say. Once there is context or canvas data it becomes the
  quiet rotation returning users already know.
- Starters are sentences the PM would say out loud, not feature names.
- The third starter adapts to state. With a job on the canvas it is **Capture
  what you heard**; with outcomes it is **Pressure-test a bet**. It never opens
  an empty surface.
- **Show me around** is a quiet text action, not a button competing with the
  starters. It opens the existing tour at the stored step.
- The composer is focused on arrival.

### After the first exchange

A single hint line sits between the transcript and the composer. It is one
sentence, one action, and a permanent dismiss:

```
I don't know your product yet. Tell me and every reply gets sharper.  [Add context]  ×
```

Rules:

- **One at a time.** Priority: context (no brief), then evidence (outcomes
  exist, none carry evidence). When neither applies, nothing renders.
- **After the first exchange, never before.** The hero already carries the
  opening; two voices at once would be noise.
- **Dismissal is permanent** (`localStorage["studio.guidance"]`) and per hint.
- **Never blocks.** The composer stays focused and the hint never covers the
  thread.

### Context capture

`SetupConversation` is unchanged. It no longer auto-opens. It opens from:

- the **Tell me what you're building** starter,
- the **Add context** hint,
- `/start`,
- Settings → **Edit context**.

This is the only change to the interview: when it opens, it is because the person
asked for it.

### The tour

The four-step wizard is now a product tour.

- It never opens by itself. `OnboardingProvider` starts closed.
- It opens from **Show me around** on the home stage (resumes stored progress)
  and **Settings → Replay the tour** (starts from the top).
- Progress is still persisted, so closing mid-tour and reopening resumes.
- The final step still lands in a real destination. That is the point of a tour.

### The feature flag

`firstRunWizard` keeps its name (avoid a migration) but now means "the tour is
available". Off means: no tour entry on the home stage, no replay in Settings,
no state writes. It defaults on.

## Architecture

```
apps/studio/src/
├── lib/guidance.ts            ← pure hint selection + storage (new)
├── lib/guidance.test.ts       ← rules, priority, dismissal (new)
├── components/chat/
│   ├── Hero.tsx               ← invitation-first, tour entry, no dead-end pill
│   ├── GuidanceHint.tsx       ← one quiet line + action (new)
│   └── ChatStage.tsx          ← renders the hint between thread and dock
├── onboarding/
│   ├── OnboardingProvider.tsx ← never auto-opens; openTour + restart
│   ├── machine.ts             ← drop shouldAutoOpen
│   └── context.ts             ← openTour added
├── state/StudioContext.tsx    ← setupOpen starts false
└── lib/greeting.ts            ← capability line first
```

`guidance.ts` is pure and takes the state it needs, so the rules are unit-tested
without rendering. The component only reads `useStudio()` and calls existing
actions (`openSetup`, `openPanel`, `sendMessage`).

## Copy

- Headline: **What do you want to win?**
- Sub: **One sentence is enough. I'll help you test whether it's worth chasing.**
- Placeholder: **Start with what's on your mind…**
- Tour: **Show me around**
- Context hint: **I don't know your product yet. Tell me and every reply gets
  sharper.**
- Evidence hint: **A score is a guess until a customer says it. Capture what you
  heard.**

No exclamation marks, no "Welcome", no emoji, no feature inventory.

## Trade-offs

- **No auto-open means some people never see the tour.** Accepted. A tour that
  must interrupt is a tax on everyone to help a few; the stage and the hints
  carry the same information in the moment it is needed.
- **Context is not captured before use.** Accepted. An answer about a product
  the studio does not know is still useful, and the hint arrives after the first
  sign of value. It also removes the "form before value" smell.
- **Two guidance states only.** Deliberate. A hint system that keeps finding
  things to say becomes the modal we just removed.

## Acceptance criteria

- With no stored state and the flag on, the studio opens on the hero with the
  composer focused; no dialog and no setup conversation.
- The first hero line is a capability question, not a time-of-day greeting.
- **Show me around** opens the tour; finishing it still starts the chosen
  conversation; **Settings → Replay the tour** restarts it from step 1.
- On an empty canvas, no starter opens an empty lens.
- After the first exchange with no brief, the context hint appears once, can be
  dismissed permanently, and never covers the composer.
- With the flag off, no tour entry renders, and no onboarding state is written.
- `npm --prefix apps/studio run typecheck`, `run lint`, `test -- --run`, and
  `run build` pass; `uv run pytest` stays green.
