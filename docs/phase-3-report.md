# Phase 3, the remaining seven verbs: what was measured, what was built, and what nobody has proven

Written 2026-09-10 by the Manager seated for the rest of Phase 3, at the point
the mission was stopped. The owner is releasing what is on `main` as version 1.0
and everything unbuilt becomes a GitHub issue. **This document is the inventory
those issues come from, and its most important half is the second one.**

---

## 1. The state, in four sentences

* Four surfaces were **measured** and their dumps are committed:
  `docs/phase-3-survey-2.md`.
* Seven verbs were **built** on branch `phase-3-reach` - `connect`, `message`,
  `read-inbox`, `read-thread`, `invitations`, `follow`/`unfollow`,
  `invite-to-follow` - with 388 offline tests, every guard watched failing by
  reverting it.
* **NOT ONE OF THOSE SEVEN VERBS HAS EVER BEEN RUN AGAINST LINKEDIN.** Not
  submitted, not staged, not once. There have been **zero** live selftest runs
  of the Phase 3 block.
* Nothing reached a person. The only live contact was five read-only survey page
  loads; the invitation manager's own count read 39 before and 39 after, twice.

Nothing is on `main`. Nothing is half-finished or uncommitted: four commits are
pushed to `phase-3-reach` and the tree is clean.

---

## 2. What was MEASURED, and the six things the design was wrong about

Full detail in `docs/phase-3-survey-2.md`. The measurements are the part of this
work with no caveat on it - they are facts about the live pages, taken twice
where the budget allowed.

1. **Navigating to `/preload/custom-invite/?vanityName=<slug>` sends nothing.**
   Survey section 10.1 would not open it because nobody knew. Proved by count,
   not argument: the Sent tab's own `People (N)` pill read 39 before, 39 after
   the navigation, and 39 again after clicking **Add a note**.
2. **The note limit is 300, not the 200 the design remembered** - and the
   textarea carries **no `maxlength`**, so the browser enforces nothing. A tool
   must read the number off the page every run. The page also publishes a live
   `N/300` counter, which is a free second reading of what was typed.
3. **The landing dialog has no Send.** Its two actions are `Add a note` and
   `Send without a note`, and the second sends immediately with no confirmation
   at all.
4. **Two Phase 3 surfaces use two different dialog implementations.** The
   custom-invite modal is a `div[role="dialog"]`; the withdraw confirmation is a
   native `<dialog>` with an *implicit* role. `[role="dialog"]` finds nothing on
   one and `dialog[open]` finds nothing on the other, and either failure looks
   exactly like "the dialog did not open".
5. **`Open send options` is a `group` of two radios**, not a menu - "Press Enter
   to Send" / "Click Send". Which one the account has selected was **not read**;
   it costs a capped view and changes no line of code, because the rule is
   absolute either way.
6. **A bare `/messaging/compose/` renders the whole inbox list with no thread
   open** and no quick-reply row, and needs no `profileUrn`. That is the only
   route to the inbox this mission can prove does not mark somebody's
   conversation read.

A seventh, found while building: **the Page's invite dialog carried
`aria-label="Invite to follow"` on one pass and `aria-label=null` seven hours
later.** Same account, same Page. A selector written against the first reading
finds nothing on the second. This is the first time in Phase 3 that two passes
of one surface disagreed, and it is the argument for design section 1's "survey
twice" in one line.

---

## 3. THE FEED-HREF FORM HAS NEVER BEEN CLICKED LIVE - carried from the withdraw seat

Recorded here at the Architect's instruction, because it exists in no committed
file and is the kind of thing that is lost when a seat ends.

The Withdraw anchor on the invitation manager's Sent tab has **two href forms on
the same page**. The first ten rows are server-rendered and their anchors point
at **the feed**; the thirty rows that arrive by lazy-load point at **the Sent tab
itself**. Amendment A5 was written against the first form: an activation the
page's own handler does not swallow navigates away and withdraws nothing,
silently.

**That trap has never been observed firing on the live page.** The one real
withdrawal performed on 2026-09-10 was row forty - a lazy-loaded row, carrying
the sent-tab href - so the assertion covering the feed-href form has been watched
firing **offline only**. A5's original trap remains a hypothesis about the first
ten rows.

**If a second withdrawal is ever authorised, spend it on a row in the top ten.**
That is the only way to see the trap fire for real, and an old row cannot
substitute: the two forms are a property of *where the row is in the list*, not
of how old the invitation is.

---

## 4. What is built and NOT proven - the issue list

Every line here is a real gap, stated as what nobody has done rather than as a
risk that has been managed.

### 4.1 Every one of the seven verbs, against the live page

`connect`, `message`, `read-inbox`, `read-thread`, `invitations`,
`follow`/`unfollow`, `invite-to-follow` have run **only** against stub browsers.
They are argued for by 388 offline tests and by measurements taken from the real
pages, and neither of those is a run. Specifically unproven:

* that the selectors resolve on the live DOM at all - the offline tests supply
  the shapes the selectors are *supposed* to match;
* that `focus()` puts the keyboard in LinkedIn's composer;
* that `Ctrl+A` + `Delete` clears it, and that LinkedIn does not restore the
  draft afterwards;
* that the staged paths leave each surface as they found it, which is the whole
  of rule 0.1;
* that `follow` / `unfollow` flip anything - the control was *read* on the
  owner's own Page, all three signals agreeing, but never pressed.

### 4.2 The three rules the phase hangs on, and how far each got

| Rule | Proven | Not proven |
|---|---|---|
| 0.1 a staged action proves the pre-action state survived | the logic, offline, on both surfaces `connect` checks and on the thread re-read | that it holds on a live page |
| 0.2 never press Enter in the composer | that the typing path emits no bare Enter, that the bubble count fires when a fragment goes, and that it **stops at the first fragment rather than sending three** | that Shift+Enter does not submit LinkedIn's form. **That is a convention this code relies on and nobody has measured it.** It has never been typed into a live composer |
| 0.3 an irreversible act names its target twice | `--expect-name` required with `--submit`; the profile and the invitation dialog compared; the thread title bar's display name **and** its `/in/` slug compared | that the live surfaces state those names where the code looks for them |

### 4.3 The six acceptance rows that were always blocked

They need a person who consents to receiving a real invitation, a real message,
and a deliberately broken half-message. The selftest declares each by name,
counts them on a **BLOCKED** counter that is neither a pass nor a failure, and
exits non-zero because of them.

`P3-2` connect `--submit` · `P3-3` the withdraw of that invitation · `P3-6`
message `--submit` · `P3-8` the Enter guard broken on purpose · `P3-13b`
invite-to-follow `--submit`, which spends a real credit and puts an invitation in
front of a real person.

And one this seat added rather than quietly folding into a staged row:

`P3-7` **a multi-paragraph message, staged, LIVE.** A single-line draft uses
`Input.insertText` only, which fires no key events at all and cannot send
anything. A multi-paragraph one needs Shift+Enter - see 4.2. Proving it live
needs a thread where an accidental send harms nobody, and **no such thread has
been identified**.

### 4.4 Measurement gaps that survive

* **Whether `/messaging/` auto-selects a conversation** - survey 10.7's question,
  still open on purpose. The only experiment is somebody's real conversation.
* **Which send option the account has selected.**
* **The invitation row's `note` and `when`.** Design 4.6 asks for both; the one
  row this account had on 2026-09-10 stated neither, and had zero `<time>`
  elements. The parser looks for both and reports `null`. **A null note means
  the row did not say, NOT that the person sent no note**, and no caller should
  read it the other way.
* **What `Send without a note` and `Send invitation` actually do**, because
  pressing either sends to a real person.
* **A second pass** on the custom-invite page, the note dialog and the send
  options. Each was seen once; design section 1 asks for two - and the invite
  dialog's vanishing `aria-label` is what that rule is for.

---

## 5. Two things this seat got wrong, and one it nearly did

**A probe that leaked while measuring.** The text sweep that read
`Please limit personal note to 300 characters.` off the page also matched a block
of LinkedIn's own configuration JSON embedded in the document. Three lines of
probe output came to 150KB, and inside them was the signed-in member's own
numeric id - on no path, inside no urn, carrying no parameter name, and eight
digits long, so R17's fifteen-digit net sat above it by construction. Fixed at
the root: `tools/survey.py` gained `JSON_ID_FORMS` (a *shape* - a JSON key ending
in `id` holding a bare number - not another name to enumerate) and
`SAFE_LINE_LIMIT`, because **a dump nobody can read is a dump nobody DID read**
and reading it is the last guard the redaction rules rest on. Both were watched
failing on the artefact before the fix, and `tests/test_no_leak.py` loops over
both rather than restating them.

**A guard that was never covered, found only by performing the revert.** Taking
out `invite-to-follow`'s credit-drop assertion left the suite **green** - nothing
had ever driven its `--submit` path, while this file's own docstring said the
credit was the proof. That is proof covering the wrong thing, and reasoning about
the revert instead of running it would have missed it.

**A collision that would have wasted the first live run.** The selftest's
accounting helpers took `name` as a keyword and `invite-to-follow` has a `--name`
of its own, so that row could never have executed. It was found by a test that
drives the Phase 3 block offline with canned output; the live run costs about
twenty views of a cap of eighty and would have found it the expensive way.
`name` and `fn` are now positional-only, so it cannot come back under a different
spelling.

---

## 6. One question for the Architect, and it is a ruling, not a preference

**Amendment A2 uncapped the route that may mark somebody's conversation read, and
capped the one that cannot.**

A2 made `/messaging/` exactly - the list - `view_self`, on the reasoning that it
is the owner's own inbox, notifies nobody, and no volume of reading it resembles
scraping. That reasoning is right. But `/messaging/` is also the route this
mission has never dared load, because it is believed to select a conversation
into the reading pane and mark it read; and the route that *is* measured safe,
a bare `/messaging/compose/`, is not matched by A2 and stays on the safety cap.

`read-inbox` as built takes the capped view. That is the conservative direction
and it is deliberate: re-scoring a safety ruling to suit the run that benefits
from it is what `docs/ruling-view-cap-2026-09-09.md` forbids by name. But the
letter of A2 and its reason now point in opposite directions, and that is worth a
ruling rather than a workaround.

---

## 7. Pacing changed, and the change is on the branch

`connect` is capped at **20 a day AND 100 in any rolling seven days**, both
checked inside one atomic reservation. The retention change lands with it rather
than after it, and that coupling is the point: `pace.json` used to delete every
day key but today's, which makes a rolling sum identical to the daily count and a
weekly cap **unreachable forever** - a check whose pass condition is the absence
of data it had itself thrown away. `Pace.RETAIN_DAYS` is asserted against the
window by a test rather than left as two numbers that happen to agree.

`follow` was added to the outbound caps rather than filed as a read: following a
Page is visible to that Page.

**Not proven:** that 100 in seven days is LinkedIn's number. It is the published
safe range's lower end and a ceiling this tool imposes on itself; nobody has been
throttled to find out.
