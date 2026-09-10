# Phase 2 follow-up: four known items, carried deliberately

> **STATUS: DONE, 2026-09-10, on branch `phase-2-follow-up`.** All four
> rulings below are built or, for F4, confirmed. What was done, what was
> measured, and what is NOT proven: `docs/phase-2-follow-up-report.md`.
> This file is left as it was written - it is the mandate, not the account.

Phase 2 lands with these open. They are recorded here rather than fixed first
because the three clean runs certify the code at `a88a32f` exactly, and changing
that code would mean the runs certify a build we did not ship. None of them
produces a confident wrong answer that leads a caller to act - which is the line
this phase draws.

The Architect's rulings on each are below. They are the first work of the next
seat, before any new verb.

## F1. The view counter has an uncounted path, and the docstring oversells it

**Found by the live-proving Manager, about its own work, unprompted.** It read
two fixture top cards by eye through `browser-harness` to write down what a
person sees. `Pace` does not count those, so two real profile views were taken
against the owner's account and against LinkedIn's tolerance without appearing
anywhere in `pace.json`.

**The Architect did the same thing** the night before, reading a profile by hand
through the same tool while the counter sat at 80. Neither of us noticed. An
uncounted path is exactly what a safety counter must not have.

**Ruling, both halves required:**

1. `tools/survey.py` drives `kit/browser.Browser`, so it is ours and it
   registers a view like everything else. No exemption for "just looking".
2. **The docstring stops claiming what it cannot deliver.** `Pace` cannot count
   a profile opened by an agent hand-driving a browser, because that path never
   enters this code. The honest scope is "views taken through this toolkit", and
   it must say so. A guarantee that overstates itself is the sentence someone
   relies on instead of checking - the same defect as `pace.json` promising
   cross-process caps it could not keep (R15).
3. The skill and README tell any agent that hand-driving profiles spends the
   same real-world budget while being invisible to the counter.

## F2. `notifications` and `stats` count no view at all

Not even `view_self`. They are our own surfaces so they are correctly outside
the safety cap, but the point of the `view_self` track is that `pace.json` shows
everything this toolkit opened. A surface that appears nowhere cannot be
reconciled against anything.

**Ruling:** both register `view_self`.

## F3. A pending invitation is reported as "no invite control"

On a profile with an invitation already outstanding, the card plainly reads
**Pending** and `read-profile` answers `can_connect: false` with the reason "no
invite control". The answer is right and the reason is wrong, and a wrong reason
is how the next reader spends an hour looking in the wrong place.

**Ruling:** detect the pending state explicitly. `can_connect: false` with a
reason naming it, plus an `invitation_pending: true` field, because Phase 3's
`withdraw` needs exactly that and will otherwise re-derive it badly. R5 already
says a field must name what it saw rather than what it failed to find; this is
that rule applied to a state we can now reach, because the fixtures file holds a
pending profile - the one the owner sent a real invitation to.

## F4. R6.1's European measurement was never made

`1,2K` fails rather than resolving to 1200 or 12. That is R6.3's default and the
only safe direction: accepting it means guessing between two answers a factor of
ten apart, with the wrong guess silent.

**Ruling: leave it failing.** It is not a defect, it is an honest refusal, and
it stays until somebody can measure what LinkedIn actually renders in a European
locale. **Do not resolve this by reasoning about what LinkedIn probably does.**
Every expensive hour of this phase came from a premise about LinkedIn that
nobody had measured, and the last one - R1.2 - was the Architect's.
