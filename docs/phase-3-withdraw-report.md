# `withdraw`: what was built, what was measured, and what was wrong

The first slice of Phase 3, 2026-09-10, 06:45 to 07:15 local. Three things were
asked for and all three are done: the A2 ruling implemented, the withdraw flow
measured for the first time, and `withdraw` built against what was measured and
proven once on a live invitation.

**The scope changed mid-run and the record should say so.** The slice began
authorised to withdraw every pending invitation older than two months - the
owner's own housekeeping. The Architect cut that back to EXACTLY ONE, as the
proof for the verb, before anything had been withdrawn. So one invitation was
withdrawn and fifteen other qualifying rows were left alone. The mission is the
library, not the owner's inbox.

Third-party names appear nowhere here: this repository is public. The one
withdrawal is recorded by name in
`%LOCALAPPDATA%/cc-linkedin/withdrawn-2026-09-10.json`, which is outside any
repository, and the age and the counts are below.

---

## 1. The answer a caller needs: what a withdrawal costs

**"If you withdraw now, you won't be able to resend to this person for up to 3
weeks."**

That sentence is quoted from the confirmation dialog on the live page. It is the
thing design 4.2 required the RESULT line to carry, and until this run it was
UNMEASURED - survey section 10.5 says so plainly, and says it could not be
measured without withdrawing a real invitation.

Two details worth keeping:

* The page says **"up to 3 weeks"**. The design said "about three weeks". The
  page's own words are both weaker and vaguer, and the RESULT line carries the
  page's, never the design's memory.
* It is stated ONLY in the confirmation dialog, which appears only after the
  withdraw control is activated. There is nowhere a caller can read it in
  advance, which is precisely why the verb puts it on the line they do read.

The RESULT line from the real run:

```
RESULT withdrawn person=/in/<slug> age='Sent 6 months ago' months_at_least=6
       outstanding=39 reinvite="stated-on-screen: you won't be able to resend to
       this person for up to 3 weeks"
```

---

## 2. What was withdrawn

| | |
|---|---|
| Displayed age | `Sent 6 months ago` |
| What that proves | at least six whole months (LinkedIn rounds down) |
| Outstanding invitations before | 40, and the page's own `People (40)` pill agreed |
| Outstanding invitations after | 39, and the pill agreed |
| Rows that left the list | exactly one, and it was the one asked for |

It was the OLDEST of the forty - the most conservative row available, and
unambiguously past the two-month line.

**Fifteen other rows qualify and were left alone:** six at `3 months ago`, four
at `4 months ago`, five at `5 months ago`. Nothing was pressed on any of them.
The list also holds twenty-four rows newer than that (one month or less), which
were never in scope. Those numbers are as of 07:14 on 2026-09-10, after the
withdrawal.

---

## 3. The design was wrong about the withdraw flow in three ways

Each of these was measured, not reasoned about, and each has a wrong answer that
looks exactly like a right one.

### 3.1 A5's href has TWO forms, and A5's own assertion cannot catch the second

A5 says the withdraw control is an anchor with `href="https://www.linkedin.com/"`
- the feed - so an activation the page does not swallow navigates away and
withdraws nothing, silently. That is true of **ten** of the forty rows. It is not
true of the other thirty.

Measured across all forty:

| Rows | `href` on the withdraw anchor |
|---|---|
| 1-10, the server-rendered page | `https://www.linkedin.com/` |
| 11-40, everything that arrives by lazy-load | `.../mynetwork/invitation-manager/sent/` |

So on thirty rows out of forty, a fall-through navigation **reloads the Sent tab
and leaves the address bar exactly where it was**. A5's assertion - "afterwards
the browser is still on the invitation manager" - passes, and nothing was
withdrawn.

The assertion is kept, because it is right about the ten. Two things cover the
thirty:

* the count proof in 3.3, which no navigation can satisfy; and
* a marker set on `window` before the activation and read after it. A navigation
  destroys it. That is how "the page swallowed the activation" is told apart
  from "the browser followed the link" when both end on the same URL.

### 3.2 The confirmation is a NATIVE `<dialog>`, and that cost four attempts

Design 4.2 says "confirm by keyboard" and survey section 10.4 records that
whether there is a confirmation at all was unmeasured. There is one:

```
<dialog open data-testid="dialog" aria-labelledby="dialog-header">
  heading  "Withdraw invitation"
  text     "If you withdraw now, you won't be able to resend to this person
            for up to 3 weeks."
  buttons  Dismiss | Cancel | "Withdraw invitation sent to <Full Name>"
```

**A native `<dialog>` has an IMPLICIT role, so it carries no `role` attribute and
`[role="dialog"]` does not match it.** The first probe looked for exactly that,
found nothing, and reported *no confirmation appeared* - three times - while the
confirmation was open on screen intercepting every pointer event. The verb then
went to its assertions, correctly found the row still present, and correctly
failed.

This is the checks-that-fail-open shape again, and it is the fourth instrument in
three days that could not fail: the probe's pass condition was an ABSENCE, and
the absence was the probe being blind. It was found only because Playwright's
click actionability check named the intercepting element in a timeout message.

A missing confirmation is now a FAILURE, not a shortcut, for that reason
specifically: the last time this verb said there was no dialog, there was one.

### 3.3 "The row is gone" proves nothing on its own

A broken selector, a half-loaded list and a page that failed to render all
produce a missing row for free. So the proof is a NUMBER, in four parts, all of
which must hold:

1. the list, loaded to exhaustion, is exactly one row shorter;
2. the page's own `People (N)` pill fell by exactly one;
3. the row asked for is absent; and
4. the rows that left are exactly that one row - no other row moved.

This is what actually caught the three failed attempts, and it is what covers the
thirty rows A5's URL assertion cannot.

### 3.4 A fourth thing, about reading the list at all

`window.scrollTo(0, document.body.scrollHeight)` and twelve mouse-wheel events
both left the list at ten rows of forty. **The window is not the scroller;
`<main>` is.** A tool that scrolls the wrong thing sees ten rows and reports that
somebody's invitation is not in the list. That is a half-read list, not a shorter
one - the same shape as the short table row in `stats`.

The forty rows also arrive ten at a time, so the verb scrolls until the count
stops growing for three consecutive passes, then checks the parse against the
page's own pill. A pill that cannot be read is a broken instrument and fails,
rather than licensing the parse.

---

## 4. Keyboard activation does not work on this control

Every other verb in this toolkit presses with focus + Enter, and the reason is
written in `cc_linkedin.py`: a click delivered after a dialog has closed falls
through to whatever is underneath it, and a keystroke cannot.

That reason does not reach this control, and the keystroke does not work on it.
Focus + Enter produced NOTHING: no confirmation, no network request, no change to
the list, the page's own count unmoved at forty. What works is a trusted mouse
click on the element, and `locator.click()` also hit-tests - it refuses if the
element at that point is not the one asked for - so the thing the keyboard was
protecting against is checked by the click rather than avoided by not clicking.

The choice is written at the call site with what was measured, so the next reader
does not "fix" it back to a keystroke.

---

## 5. The target is named three times

Design rule 0.3 asks for two namings on an irreversible act. This surface offers
three, and the verb takes all of them:

1. the `/in/` slug in the URL the caller passed, matched against the row's own
   profile link - and two rows for one person is ambiguity, which has no outcome;
2. `--expect-name`, required with `--submit`, compared with the name read off the
   withdraw control that is about to be clicked; and
3. the confirmation dialog's confirm button, which carries **the same sentence
   again** - so the last control pressed is identified by the person it acts on.

The third one matters more than it looks. The confirm button's visible text is
"Withdraw", and so is part of the dialog's heading: matching the bare word would
have three candidates on screen, one of them a heading.

---

## 6. Pacing

A withdrawal is OUTBOUND, not a read. It changes something on another person's
side, and twenty in a burst is what an automated account looks like from the
outside. So `withdraw` takes the 45-90 second gap like every other outbound
action and a daily cap of twenty - the same number `connect` carries, so that an
account cannot withdraw its way past the rate it is allowed to invite at.

The failed attempts each reserved a slot and were never given back. That is the
conservative direction on purpose: the slot is taken immediately before the act,
so an act that then fails is still counted, because a request that errored may
still have reached LinkedIn.

---

## 7. A2, and one thing to be honest about

`/messaging/` and `/mynetwork/invitation-manager/...` are now `view_self`:
counted, uncapped. A messaging THREAD is deliberately still capped, because
opening one marks it read and can show the other participant a read receipt - the
one messaging read with an outward, irreversible side effect. Twenty-one offline
tests, eight of them watched failing first, and the ones that matter are the
thread and compose rows: a classifier that got the two easy cases right by
writing the messaging pattern as a prefix would satisfy the letter of A2 and
destroy its reason.

The two new patterns match the URL's PARSED PATH rather than the whole URL
string, which is stricter than the three that were already there - a whole-string
search can be satisfied by our own path sitting in somebody else's query
parameter. The older three were left alone; narrowing them is not what A2 ruled
on, and the difference is written down where it is made.

**The thing to be honest about.** This slice opened the Sent tab about fifteen
times, and under the rule as it stood this morning every one of those would have
been a capped view against a day that had six left. A2 is what made the slice
possible. It was ruled before this task existed and it was implemented first, on
its own merits, but the run that benefits from a rule is not the run that should
be trusted to say the rule was neutral. The daily cap was not raised, no capped
view was spent, and the counter is where it was.

---

## 8. What is NOT proven

* **The three-week restriction is quoted, not verified.** The page says it;
  nobody has waited three weeks and tried. The RESULT line reports it as
  `stated-on-screen`, which is what it is.
* **One row, one rendering, one account, one morning.** Everything here was
  measured on the signed-in account on 2026-09-10, on whatever A/B bucket it is
  in. The two href forms in particular are a property of how this page happened
  to render forty rows today.
* **Nothing proves the verb is right about a row in the first ten.** The one real
  withdrawal was row forty, a lazy-loaded row, so the anchor it clicked carried
  the sent-tab href. The feed-href form has never been clicked, and A5's original
  trap has therefore never been observed firing on the live page - only its
  assertion, in the offline tests.
* **Nothing else in Phase 3 is built.** `connect`, `message`, `read-inbox`,
  `read-thread`, `invitations`, `follow`/`unfollow` and `invite-to-follow` are
  untouched, and the acceptance rows that need a consenting person are still
  blocked.
