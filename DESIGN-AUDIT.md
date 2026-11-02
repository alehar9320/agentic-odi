# Design Audit — Living Studio

**Target identity: calm, precise, confident.**
Calm: one thing at a time, generous whitespace, no alarm theatre. Precise: one scale for
spacing/radius/type/motion, everything aligned, nothing approximate. Confident: a single
clear action per screen, stated plainly, without hedging or helper clutter.

Audited cold on `alehar9320/design-premium-pass` against the dev server (1440×900, fresh
profile, no sidecar — the true first-run path is the offline one).

---

## Screen 1 — Home (empty stage / Hero + composer)

- **Notices first:** the glowing indigo ring around the composer — decoration, not meaning.
- **Second:** "What do you want to win?" (correct — this should be first).
- **Third:** a scatter of underlined links, four starter chips, and an 8-control top bar.
- **5-second read:** "a chat thing about winning" — the ODI purpose never lands.
- **ONE intended action:** type a sentence in the composer.
- **Muddying it:** hero aside ("Start with you and your team" · "Show me around") reads as
  two more primary CTAs; starter chips sit between hero and composer as a third option set;
  top bar's Customize / What's New pills compete with each other; the composer ring is the
  loudest pixel on the screen.
- **Removal test:** the ring gradient, the "·" divider, the What's New pill (belongs in the
  overflow menu), the duplicate guidance chips row.

## Screen 2 — Intro conversation (first-run context questions)

- **Notices first:** a lone question floating at the top of a huge black void.
- **Second:** the pill "Skip this question" — the escape hatch is the most clickable thing.
- **Third:** the composer, far away at the bottom.
- **5-second read:** "it wants something from me but I can't tell what."
- **ONE intended action:** answer the question in the composer.
- **Muddying it:** question and input are vertically disjointed; "Skip this question" styled
  like a primary button; "Explore on my own" floats top-right as a second exit.
- **Removal test:** demote skip to a quiet text link; pull question block toward the composer.

## Screen 3 — Customize page

- **Notices first:** three identical red "The studio sidecar isn't reachable" boxes.
- **Second:** "Customize" title. Third: a stray "All" chip under the search box.
- **5-second read:** "this page is broken."
- **ONE intended action:** search the marketplace and connect something.
- **Muddying it:** the same error rendered once per section (Installed, Editor's Picks,
  Marketplace) — alarm theatre ×3; command-line instructions repeated verbatim in each.
- **Removal test:** collapse to one error notice; "All" chip is redundant with an empty filter.

## Screen 4 — Offline banner stack (after any launch, no sidecar)

- **Notices first:** a red-bordered banner shouting "The studio sidecar isn't running."
- **Second:** a second amber banner. Third: six buttons across two banners.
- **5-second read:** "errors everywhere" — contradicts the honest offline-by-design story.
- **ONE intended action:** keep working — the thread already responds.
- **Muddying it:** two stacked banners with equal weight and three CTAs each; the banners
  permanently eat ~140px above the bar.
- **Removal test:** one banner, one primary CTA, others demoted to text.

## Screen 5 — First-run wizard (4 steps)

- **Notices first:** the step title (correct). Second: the goal cards (correct on step 2).
- **Third:** the footer: "Skip the tour · Skip this step · Back · Continue" — four actions.
- **5-second read:** "a guided tour, fine." Read holds.
- **ONE intended action:** Continue (or the goal CTA).
- **Muddying it:** two adjacent skip links are indistinguishable; readiness step's three
  amber "Not reachable" rows read as failure rather than "nothing connected yet."
- **Removal test:** one skip affordance ("Skip tour"); neutral pending dots on readiness.

## Screen 6 — Settings panel

- **Notices first:** "Settings" header (correct). Second: "Set up context" card.
- **5-second read:** "a form of everything." Purpose lands but is noisy.
- **ONE intended action:** fix the model endpoint (or set context when unset).
- **Muddying it:** three status rows duplicate the top-bar health pill; section labels and
  status text sit at ~0.62–0.68rem — under legible.
- **Removal test:** the duplicate status block can go; keep one health readout per view.

## Screen 7 — What's New modal

- **Notices first:** the Jobs quote in the footer — decoration that isn't earning its place.
- **5-second read:** "release notes." Fine.
- **ONE intended action:** Done.
- **Muddying it:** "Mark all read" renders visually equal to "Done" on an empty list.
- **Removal test:** drop the quote; "Mark all read" only when there are unread entries.

---

## Consistency — measured, not vibes

Extracted from `styles/theme.css` + `onboarding/onboarding.css` (declarations counted):

| Axis | Today | Target scale (tokens) |
|---|---|---|
| Spacing | 20+ distinct px values (3,5,7,9,11,13,15,18,22,28,30…) | `--s-1:4 --s-2:8 --s-3:12 --s-4:16 --s-5:24` (page gutter 32 stays a layout constant) |
| Radius | 12 values incl. 999px **and** 9999px | `--r-sm:6 --r-md:10 --r-lg:14 --r-pill:999px` (50% for circles) |
| Font size | 20 distinct rem values (0.62…0.95) | `--t-xs:0.72 --t-sm:0.82 --t-md:0.92 --t-lg:1.1rem` per view max 4 steps + hero display |
| Font weight | 600,700,500,550,620,650,560,800 | `--w-regular:400 --w-strong:600 --w-display:700` (≤2 per view) |
| Motion | 0.14s/0.15s/0.16s/0.2s ease + 3 different cubic-beziers | `--ease-out:cubic-bezier(0.16,1,0.3,1) --dur-1:150ms --dur-2:250ms` app-wide |

Colors and shadows already have a clean token set (`--bg/--text/--accent/--line/--surface`)
— keep, don't invent a second palette.

## Layout — measured, not vibes

Every centred surface that holds a column of prose, grepped out of the two stylesheets:

| Surface | Before | Reads as |
|---|---|---|
| `.chat__welcome-inner`, `.chat__thread`, `.chat__dock > *` | 720 | the thread's column |
| `.setup__meta`, `.intro__summary`, `.intro__examples` | 720 | the thread's column |
| `.rail__list` | 720 | the thread's column |
| `.wizard-panel` | `min(720px, 100%)` | the thread's column, in a modal |
| `.changelog-modal` | **680** | the same column, 40px narrower for no reason |
| `.customize__head`, `.customize__body` | **900** | the catalogue grid |

So the app had one real column, drawn nine times at 720 and once at 680, plus a wider grid at
900. Two tokens, `--measure: 720px` and `--measure-wide: 900px`, now hold those; the changelog
modal moves onto the shared measure so its text edge lands where the thread's does.

Deliberately *not* columns, and left alone: `.lens` (`min(520px, 44vw)` — a drawer sized to the
shell), `.diagnostics-modal` (760 — a table, dev-only), popovers, tooltips and rail chips
(170–440 — component-sized). Widening the grid is not the same act as naming it.

## Audit items (ordered by impact on first impressions)

1. **A1 Tokens & motion** — define the five scales above as tokens; sweep the hero, composer,
   bar, wizard, and panels onto them; unify transition duration/easing.
2. **A2 Home hierarchy** — remove composer glow ring; demote hero aside links to one quiet
   text action; move "What's New" into the overflow menu; single dominant element = headline,
   single action = composer.
3. **A3 Customize** — one sidecar error, not three; remove stray "All" chip.
4. **A4 Banner stack** — merge offline banners into one calm notice with one primary CTA.
5. **A5 Intro conversation** — bind question to composer; demote "Skip this question" to text.
6. **A6 Wizard footer** — one skip affordance; neutral readiness pending state.
7. **A7 Settings** — remove duplicated status block; lift sub-legible sizes onto the type scale.
8. **A8 Changelog modal** — remove quote; demote "Mark all read".
9. **A9 Console errors** — dev-proxy 502s from health probes must not spam the console;
   fetch failures handled quietly.
10. **A10 Shared grid** — put every reading column on one `--measure`, the catalogue on
    `--measure-wide`, and stop the changelog modal from carrying a 680px width of its own.
    Ranked last by impact on first impressions on purpose: a visitor never sees a grid, only
    the places where two surfaces that should share an edge do not.
