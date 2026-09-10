# Phase 3 design: AMENDMENTS after the survey, 2026-09-10

`docs/phase-3-survey.md` measured the surfaces `docs/phase-3-design.md` was
written from reasoning about. It contradicts the design six times. Every one is
adopted below.

**Where an amendment and the design disagree, the amendment wins.** The design
was written before anything was measured, which was the correct order - a survey
exists to be run against a stated intent - but it means six parts of that
document are hypotheses that turned out to be wrong about the world.

## A1. The invite control is a LINK, and it is never found by the word "Connect"

Measured: the control is an `<a>`, its accessible name is
`Invite <Name> to connect`, and "Connect" is only its visible text.
`get_by_role("button", name="Connect")` finds NOTHING on this page. Design
sections 4.1 and 4.2 and rows P3-1 to P3-3 all specify the wrong thing.

**Amended: Phase 3 reuses Phase 2's identification, which already got this
right.** `kit/selectors.py` carries `INVITE_HREF = "custom-invite"` and
`INVITE_ARIA` matching that sentence, measured on five profiles, and
`read-profile` already resolves `can_connect`, `connect_via` and `connect_url`
from them. `connect` asks that resolver where the invitation is rather than
hunting a word. The href is the reliable marker, the accessible name is second,
and the visible text is not a marker at all: "Connect" appears all over a profile
page, the right-hand rail's suggestion cards being full of it.

The same governs the state check. `Pending`'s accessible name is a whole
sentence, so states are matched as patterns, never by equality against a word.

## A2. The messaging list and the invitation manager become `view_self`. A THREAD does not.

Measured: `/messaging/`, `/messaging/thread/<id>/` and
`/mynetwork/invitation-manager/` all count as capped `view`, because
`surface_kind` recognises only a profile on the owner's list, one of his Pages,
and `/notifications`.

**Amended, and the split is deliberate.** The cap exists against activity that
looks automated to LinkedIn *and* reaches other people
(`docs/ruling-view-cap-2026-09-09.md`).

* `/messaging/` (the list) and `/mynetwork/invitation-manager/` become
  **`view_self`**. They are the owner's own inbox and his own invitations, they
  notify nobody, and no volume of reading them resembles scraping.
* **A THREAD stays capped.** Not because it looks like scraping - it does not -
  but because opening one marks it read and can show the other participant a
  read receipt. It is the one messaging read with an outward, irreversible side
  effect, and keeping it on the safety number means a runaway loop meets a wall
  instead of quietly marking a hundred conversations read.

The surveyor obeyed the cap exactly as it stood and changed nothing, which was
right: this is a ruling, not a surveyor's call.

## A3. `read-inbox` cannot return `thread_url`. The field goes.

Measured: the list's rows are not links and carry no thread id in any attribute.
The id first exists in the address bar *after* a row is clicked, and clicking a
row is the thing design section 4.4 forbids because it marks the thread read.
**As specified, 4.4 asked for a field obtainable only by doing what 4.4
prohibits.**

**Amended:** `thread_url` is removed from `read-inbox`. It returns a
`thread_ref` - an opaque handle built from what the row actually carries: the
participant, the last message's time, and the row's position under a stated
filter. `read-thread` accepts either a thread URL or a `thread_ref`. Resolving a
`thread_ref` requires opening the thread, which marks it read, and `read-thread`
already carries `marked_read=true` on its RESULT line. The capability is
documented as what it is rather than promised as what it is not.

## A4. The invitation count is a per-filter pill

Measured: the page states `Focused (2)`, `Verified (2)` on Received and
`People (40)` on Sent. There is no "No pending invitations" sentence to fall back
on; it was searched for and is absent.

**Amended:** the zero-rows exception in design 4.6 survives, narrowed. The count
is read from the pill of THE SAME FILTER whose rows were parsed, and the two are
compared. If the pill cannot be read, **the exception does not apply and zero
rows is a FAIL**, like everywhere else in this toolkit. That exception was only
ever earned by the page publishing a number to check against; where it publishes
none, the general rule returns.

## A5. Withdraw is an anchor with a live href to the feed

Measured: on the Sent tab, Withdraw is an `<a>` whose `href` is
`https://www.linkedin.com/`. A click that the page's own handler does not swallow
navigates to the feed and withdraws nothing, **silently**.

**Amended:** `withdraw` asserts, after activating it, that the browser is still
on the invitation manager AND that the row is gone. Landing on the feed is a
`FAIL` naming exactly that.

This is the same defect class as everything else this week: an action whose
success was going to be inferred from the absence of an error.

## A6. Rule 0.2 was not paranoia, and the surface is worse than the design assumed

Measured: the composer's Send is `type=submit` inside a form, and a thread
carries **one-click quick-reply buttons that send canned text with no draft stage
at all**.

**Amended, strengthened:** rule 0.2 - never press Enter in the composer - stands
exactly as written and gains a companion. **Nothing inside a thread is clicked
except the composer and its Send button, each identified positively before it is
touched.** On this surface a coordinate click that misses by a few pixels does
not produce a typo. It sends a message to a real person.

## What the survey did NOT measure

Survey section 10 names it, and the design must not be read as covering any of
it: the custom-invite page itself, the Add-a-note dialog and its character limit,
the withdraw confirmation, the three-week re-invite restriction, and
`Open send options`. Six surfaces got a single pass rather than the two the
design asks for.

**These are measured before the verbs that touch them are built, not during.**
The Add-a-note limit in particular is stated on the page and must be read from
it rather than remembered - design 4.1's "measure it and enforce what the page
says, not what we remember" is unchanged, and now applies to a gap we know we
have.

---

# A5 CORRECTED, 2026-09-10 - the assertion I wrote passes on 30 of 40 rows while nothing happened

A5 said `withdraw` must assert, after activating, that the browser is still on
the invitation manager AND the row is gone. Measured while building it, that
first assertion is **fail-open on three quarters of the list**.

**Why.** The Withdraw anchor has TWO href forms on the same page. The first ten
rows are server-rendered and point at the feed, which is what the survey saw and
what A5 was written against. The thirty rows that lazy-load point at **the Sent
tab itself**. So on those thirty, a click the page's handler does not swallow
reloads this very page - and "am I still on the invitation manager?" answers yes,
while nothing was withdrawn.

I wrote an assertion whose pass condition was satisfied by the failure it was
meant to catch. That is the same shape as the redactor, the leak test, the lock
and the inventory row: **the fourth and fifth fail-open instruments in three
days**, and this one was mine.

**Corrected.** The proof is:

1. **The count.** The list's own People pill and the row count both drop by
   exactly one, and the specific row is gone.
2. **A window marker that a navigation destroys.** Set before activating and read
   after; if the page navigated - to the feed OR back to this same tab - the
   marker is gone and the run fails. That distinguishes "the handler ran" from
   "the browser went somewhere", which the URL cannot.

The URL check stays as a cheap first tripwire. It is no longer the proof.

# The confirmation is a native `<dialog>`, and `[role=dialog]` does not match it

Measured: the withdraw confirmation is a native `<dialog>` element. Native
`<dialog>` carries an IMPLICIT role, so it has no `role` attribute, so
`[role=dialog]` - the selector this toolkit uses everywhere - **finds nothing**.
The probe reported "no confirmation appeared" three times while the dialog sat
open, intercepting every click.

A selector that reports absence when the thing is present, blocking the page, is
the worst kind of instrument. `kit/selectors.py` carries this as a dated note so
nobody reaches for `[role=dialog]` on this surface again.

# Keyboard activation does nothing here, so this control is clicked

This toolkit prefers keyboard activation, because Phase 1 measured a click
falling through onto a Photo button and opening a native OS dialog. Measured on
this control: **keyboard activation does nothing at all** - no dialog, no
request, no change. So `withdraw` uses a hit-tested `locator.click()`, and the
reason is written at the call site rather than left as an unexplained exception
to a house rule.

This is the second control measured to need a click where the house rule says
keyboard - the invite dialog's Send was the first. The rule is not wrong; it is
scoped to the dialogs it was measured on, and each exception names its own
measurement.

# What the RESULT line says, and what it cannot

Measured, verbatim: **"If you withdraw now, you won't be able to resend to this
person for up to 3 weeks"**.

`up to` three weeks, not "about three weeks" as the design assumed - a weaker
claim than we were going to make on LinkedIn's behalf. And it is stated ONLY
inside the confirmation, so **no caller can read it before deciding**. That is
precisely why it belongs on the RESULT line: the tool is the only thing standing
where the sentence is visible.

# Still not proven

**The feed-href trap has never been seen firing live.** Only ten of forty rows
carry that href, no such row was ever clicked, and the assertion covering it has
been exercised offline only. The trap A5 was written for remains a hypothesis
about the first ten rows.
