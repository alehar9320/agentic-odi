# Design: what this pass deliberately left

Companion to [DESIGN-AUDIT.md](DESIGN-AUDIT.md). Every audit item is either fixed on this
branch or recorded here with the reason it stayed. Verified against the built app in Chromium,
not by reading the diff.

| Item | Status | One-line reason |
| --- | --- | --- |
| A1 tokens & motion | fixed | One scale each for spacing, radius, type, weight, easing, duration. |
| A2 home hierarchy | fixed | Composer glow removed; hero aside demoted to quiet text links. |
| A3 customize | fixed | One shared sidecar error instead of three; stray "All" chip removed. |
| A4 banner stack | fixed | Offline notices merge into one calm banner with one primary CTA. |
| A5 intro conversation | fixed | Question binds to the composer; "Skip this question" demoted to text. |
| A6 first-run wizard | fixed | One skip affordance; readiness reads neutral until measured. |
| A7 settings | fixed | Duplicated status block replaced by one sentence per view. |
| A8 changelog modal | fixed | Quote removed; "Mark all read" only exists when something is unread. |
| A9 console errors | **left** | See below. |
| A10 shared grid | fixed | One `--measure` for every reading column, `--measure-wide` for the catalogue. |
| PR #61 micro-interaction block | **left** | See below. |
| Cold-visit connector prompt | **left** | See below. |
| Light theme | **not audited** | See below. |

## A9 — the 502 lines in the dev console

A cold journey through every screen logs 157 console lines, and all 157 are the browser's own
`Failed to load resource: 502 (Bad Gateway)` for `/api/*` health probes. There are zero
`pageerror`s: the app already answers an absent sidecar quietly, in the UI, which is what A4 and
A7 were about. The remaining noise is a `vite` dev-proxy artifact for a machine with no sidecar
running, and swallowing it in the proxy would hide a real absence from the next person debugging
one. Production has no proxy and no 502s.

## The PR #61 "micro-interactions" block in `theme.css`

Lines ~4130 onward predate this pass and carry a second set of easings, radii, and paddings that
duplicate the A1 scale, plus glassmorphism applied to five panels. I removed only the `.bar`
entry, because its `backdrop-filter` made the header a stacking context and the overflow menu
became unclickable — a behavior bug, not a taste call. Sweeping the rest means restyling every
panel at once, which is more than a single design batch should carry and would bury the
first-impression work in a diff nobody can review.

## The connector prompt that interrupts a first visit

A brand-new visitor gets a modal — "Give the studio something to read" — before they can see the
home screen, so the hero's one action is momentarily not the only action. Left because it is the
only route to a working copilot for someone with no connectors, and demoting it to a banner would
let a first-timer reach a silently broken model. The right fix is product work: decide whether the
studio should open with a working demo rather than a gate, then this modal goes away on its own.

## Light theme

The audit was walked in dark mode, which is the default and the only theme any screenshot here
was taken in. Light mode inherits the same tokens, so A1 carries over automatically, but the
contrast of the demoted elements (quiet text links, ghost buttons, the readiness panel's amber)
has not been re-checked by eye and should not be claimed.
