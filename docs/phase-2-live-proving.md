# Phase 2 proved on the live site

The live-proving Manager's account, 2026-09-10, branch `phase-2-reading`,
worktree `D:/ReposFred/cc-linkedin.mission`.

**Read this as self-testimony.** It is written by the session that did the work,
about its own work. Section 7 is what is NOT proven and is the section worth
reading first.

Everything in `docs/inspection-fixes.md` had been built and tested offline and
**nothing had ever run against LinkedIn**. This pass ran it. It ends with three
consecutive clean runs, and it found four defects on the way that no offline
test could have found, one of which made a clean run arithmetically impossible
on any code.

**No third party's URL, name, headline or content id appears in this file.** The
identifiers live in the machine's own fixtures file, outside the repository -
see ruling R20 below.

---

## 1. The headline result

```
RESULT selftest passed=29 failed=0 rows=29/29      01:23
RESULT selftest passed=29 failed=0 rows=29/29      01:31
RESULT selftest passed=29 failed=0 rows=29/29      01:40
```

Three consecutive runs, every declared row reported, nothing left behind: zero
comments remaining on the post afterwards, no leftover Page post swept by any of
the three, and `P1-nothing-left` green in each.

Cost against the daily safety cap: **42 of 80**, plus 19 views of surfaces we
own. **The cap was not raised and was never close to being reached.** The
ruling that refused to raise it last night (`docs/ruling-view-cap-2026-09-09.md`)
cost nothing but a night's wait.

## 2. What was built before any run - because a run only certifies the code it ran

The Architect's ordering, and it is the reason the three runs above mean
anything: everything that changes behaviour lands first, then the runs.

| | |
|---|---|
| The `view` / `view_self` split | `docs/ruling-view-cap-2026-09-09.md`, implemented |
| R19 - the leak check learns organisation paths | new |
| R3.3 AMENDED - a failure to read is not a reading of failure | the ruling was wrong |
| R20 - fixtures live outside the repository | new |
| The INVENTORY row naming itself as never having run | found live |
| R1.2 RETIRED - redundant and false-premised | the ruling was wrong |

Two of those six are rulings that turned out to be wrong about the world. Both
were taken back to the Architect with evidence and amended by him; neither was
softened by the seat that hit them.

## 3. The four defects this pass found

### 3.1 The lock stole itself from a live holder, on Windows

`FileLock._holder()` asked one question - can I read it - and treated every no
as evidence the record was broken. A transient sharing violation therefore
produced `lock is BROKEN ... taking it over` and discarded a lock a LIVE holder
was still inside. R15's own forty-thread test lost an increment on it, and
`PermissionError` escaped `__enter__`, which caught only `FileExistsError`.

It printed on almost every run of that test, **passing runs included**, and it
reproduces at `HEAD` - nothing in this branch caused it. `BrowserLock` IS this
class, so the lock whose whole job is to stop two Playwright clients driving one
Chrome could take itself away from a healthy holder, on the machine that runs
the fleet.

R3.3's link-into-place argument earns the right to trust CONTENT: a file that
exists has complete bytes, so bytes that do not parse mean a broken record. It
earns nothing about an OPEN failure. The Architect amended the ruling
accordingly: broken means READ AND INVALID; any failure to open is retried and
then treated as HELD. Fail closed, never reclaim.

Evidence: `docs/evidence/lock-steals-itself-on-windows.txt` (the measurement)
and `docs/evidence/watched-failing-lock-amended.txt` (before and after, and what
thirty green runs do and do not prove).

### 3.2 The INVENTORY row named ITSELF as the row that never ran

R9's inventory is one of the declared rows AND the row that does the
reconciling, so at the moment it reconciled it had not reported yet. The first
live run printed, three lines apart:

```
INVENTORY FAILED: 29 rows declared, 28 reported; NEVER RAN: INVENTORY
RESULT selftest passed=26 failed=3 rows=29/29
```

The summary saying all 29 reported and the inventory row saying 28. **A clean
run was arithmetically impossible, on any code, with any fixture.** Every
offline test of `Rows` built its own list and reported every row before
reconciling; only a real run declares INVENTORY and then asks INVENTORY whether
everything reported.

### 3.3 A test wrote into the machine's own state directory

`kit/fixtures.py` bound `STATE_DIR` at import, so the tests' redirection could
not reach it and the first run of the new suite wrote three fabricated fixtures
into `%LOCALAPPDATA%/cc-linkedin/`. Removed; the directory is now resolved at
the moment of use; and the tests snapshot the real file in `setUp` and assert in
`tearDown` that they did not touch it. A test that can write to the machine's
state is a test that will eventually delete something.

### 3.4 The first revert-2 attempt reverted half the defect

Recorded because it nearly produced a proof of nothing. See section 5.

## 4. R1's survey, taken by running - and R1.2 retired

The census the code prints when it refuses to guess IS the survey R1.1 asked
for, and this is it. All three rows of the first live `--resolve`:

```
the page says it is urn:li:activity:<a> and the URL path says urn:li:share:<b>
- two different posts. Refusing to prefer one of them. The page carried: post
cards with a data-urn=1, canonical=none, og:url=none, any [data-urn] at all=1
```

(one row said `urn:li:ugcPost:<b>`; `<a>` and `<b>` are different numbers in
every row. The exact urns are third-party content ids and are in the machine's
fixtures file, not here.)

**R1.1's answer, measured:** a landed post page carries the post card's
`data-urn` and **nothing else**. No canonical link and no `og:url`, on any of
the three. R1.1's three-way preference order collapses to one item.

**R1.2 is RETIRED - as redundant and false-premised, never as relaxed.** The
distinction is the whole of it: a guard removed because a better one subsumes it
is engineering; a guard removed because it went red is how a suite ends up
certifying nothing.

*The premise was false.* R1.2 assumed the page and the path would name ONE id
under two kind labels. LinkedIn does not work that way - an activity urn WRAPS a
share or ugcPost and carries a DIFFERENT id from the thing it wraps. "The page
and the path must agree" was never a statement about LinkedIn; it was a
statement about what we assumed LinkedIn was.

*Proved by the server, not by us.* The Architect refused to amend a safety rule
on a plausible story and asked for both permalinks to be opened. Asking LinkedIn
for the SHARE permalink of one of those rows serves the page whose single post
card states the ACTIVITY urn, and the tool answered:

```
FAIL no post card for urn:li:share:<b> on .../feed/update/urn:li:share:<b>/.
The page holds 1 post card(s) and states its identity as urn:li:activity:<a>.
Refusing to act on whatever post is on the page instead of the one that was
asked for.
```

The activity permalink loads that post normally. One post, two names, answered
by LinkedIn's own routing.

*A shared numeric prefix was NOT counted as evidence*, on the Architect's
correction: LinkedIn ids carry a timestamp in their high bits, so two ids minted
seconds apart share a prefix whether or not they are related.

*It was redundant anyway.* The attack R1.2 existed to stop was a urn INFERRED
FROM A URL reaching a verb that comments, reacts or deletes. R1.1 ended that by
reading identity from the DOM. The path is no longer a source of identity, so
there was nothing left to cross-check.

*What guards it instead, untouched:* P2-6c compares the resolved post's AUTHOR
AND TEXT with the search row it came from, and R2.2's `may_use_any_card` refuses
a page whose stated identity is not the urn asked for.

**And the best thing in this pass: that refusal above is R2.2 meeting a REAL
mismatch on its first live outing.** The inspector found that the old code would
silently act on whatever post was on the page. Last night that was a
hypothetical. Tonight the server handed the guard exactly that situation, and it
named the urn it wanted and stopped.

After the retirement, `P2-6b` resolves **3 of 3** and `P2-6c` passes - the first
time the resolver has worked end to end.

## 5. The reverts - watched, not assumed

### Revert 2: the employer read - NOW WATCHED, and it took two attempts

**The first attempt reverted half the defect and must be recorded.** Only
`_current` was put back, and the result was `company=None` - which is neither
the old behaviour nor the new one. The fix of 2026-09-09 changed TWO things: the
Python that picked the employer AND the JS that decided which paragraphs it
picked from. A revert of half of a fix proves nothing about either half. The
faithful revert restores both: every `<p>` in the whole top card, then document
order.

With it in place, two profiles show two faces of ONE defect.

**The profile with no pronoun** gives the originally reported symptom exactly:

```
REVERT 2, the old lines in document order:
  ['<the headline>', '500+', 'connections', '<mutual connections sentence>']
  current.company : "500+"
```

A bare connections count in the employer field - the field a caller writes
straight into a CRM.

**The menu-profile fixture has a pronoun**, and there the same code shifts every
field by one:

```
REVERT 2, the old lines in document order:
  ['She/Her', '<the headline>', '500+', 'connections', 'Open to work', ...]
  current.company : "<the headline>"
```

The pronoun becomes the headline and the headline becomes the employer, with
the count sitting one place further back. **Position is not identification**, and
this is that sentence measured twice on two people.

**Say what this does NOT show.** The brief predicted `current.company` would
come back as a bare count on the menu profile, and on THIS fixture it does not -
the pronoun displaces it. So the guard that fires here is P2-10's `company=none`
correspondence:

```
- current.company: '<the headline>' wanted None
  P2-10 FAILED: menu profile, 36 checks
```

and the `current.company is not a count` invariant does NOT fire on this
profile. It is the second profile above that demonstrates the count form. Both
are the same defect; neither on its own shows all of it.

Full-suite run with the revert in place: **passed=26 failed=3**, the three being
P2-10 (the target) plus P2-6b/P2-6c, which were failing for the unrelated R1.2
reason and had not yet been retired. Every other row stayed green, including
P2-2 and P2-2b on profile B - the revert breaks only the profile whose shape
exposes it, which is exactly why that shape is specified so tightly.

Restored with `git checkout -- kit/people.py`; tree confirmed clean.

### Revert 1: the More-menu half - RE-OBSERVED, and this time the controls held

The 2026-09-09 run of this crossed the view cap half way through, so P2-5,
P2-6a, P2-6b, P2-6c and P2-9 failed on the cap rather than standing as green
controls. That half is now observed:

```
- can_connect: False
- connect_via: None
- the invite came from the menu, for this person: None
- can_connect: False wanted True
  P2-10 FAILED: menu profile, 35 checks
RESULT selftest passed=28 failed=1 rows=29/29
```

**One failure, and it is the reverted guard.** P2-5, P2-6a, P2-6b, P2-6c and
P2-9 were all green in the same run - P2-6b resolving 3 of 3. The reported
symptom is the right one: on a person the tool CAN invite, it reports that it
cannot, because it only looked where the invitation was not.

Restored; tree confirmed clean.

## 6. R20 - the fixtures now have a home

The rule that no third party's details may be committed is right and does not
move. But it was half a rule: it said where the values may NOT go and left them
nowhere else, so the two profiles the Phase 2 rows need were rediscovered by
hand by each new seat, out of the safety cap, and thrown away again. Three seats
paid; none kept the answer.

The repository documents the SHAPE; the machine holds the VALUES, beside
`pace.json`, outside every checkout. The flags still win when passed, and a
value in neither place still FAILS the run naming both routes.

**What the hunt cost this time: 8 capped views of the 80** - two people searches
and six profiles opened - to find one profile of shape B and one of shape D. It
should cost nobody anything again.

Recorded there now: profile B, the menu profile, a **pending-invitation**
profile (a state no other fixture reaches: `can_connect` false with a reason and
no invite URL), and `--post`, which was a fixture with no home either.

## 7. WHAT IS NOT PROVEN

Read this before trusting anything above.

**Three clean runs are three runs.** They are evidence that the suite passes on
this machine, with these fixtures, against LinkedIn as it was rendered tonight.
They are not evidence that it passes on another profile shape, in another
locale, or next week.

**The lock fix is proved by construction for the part that matters and by
repetition for the rest.** There is no longer any path from an open failure to
discarding the holder's lock - the only callers left require bytes that were
READ. That is construction. That the race no longer shows in thirty runs is
repetition, and a race that stops showing is not a race that cannot happen.

**R6.1's European measurement was still not made.** `1,2K` still fails by
design. Nothing tonight ran in another locale.

**P2-7 remains a smoke test and says so on every run.** The phase does not claim
`notifications` is proven.

**R5's menu scoping still has no offline test**, and the settle loop's timing is
still a judgement rather than a measurement. Unchanged from
`docs/inspection-fixes.md` section 4.

**Two profile views were taken outside the counter.** Reading the two fixture
top cards with my own eyes was done through browser-harness, which `Pace` does
not count, so the day's real profile-view total is the counter plus two. Small,
but the counter is a safety instrument and an uncounted view is exactly the
thing it must not have. **This is a gap worth a ruling:** either a survey/manual
read registers a view, or the counter's docstring stops implying it counts every
profile this machine opens.

**`notifications` and `stats` count NO view at all**, not even `view_self`. The
view-cap ruling's stated reason for counting self-views - a runaway loop should
be visible in `pace.json` - applies to them exactly, but the ruling names the
owner's profile and his Pages, so widening it was left to the Architect. Raised,
not taken.

**The expectations were read off screenshots by a person, but by the same person
who had already seen the verb's output.** That is much weaker than a reading
taken blind, and it is the honest description of what was done. It is not a copy
of the verb's output - which would have made P2-2 and P2-10 the verb agreeing
with itself - but it is not independent either.

**A pending invitation reports an uninformative reason.** On the pending
fixture, `can_connect` is correctly false, but the reason reads "no invite
control on the top card and none in the More menu" when the card plainly says
`Pending`. True, and less than the page knows. Not fixed - raised.

## 8. Where to look

* `docs/evidence/lock-steals-itself-on-windows.txt` - the lock, measured.
* `docs/evidence/watched-failing-lock-amended.txt` - before and after.
* `docs/evidence/watched-failing-view-split.txt` - the old counter spending the
  safety number on our own profile.
* `docs/evidence/watched-failing-company-id.txt` - R19, and what it adds over
  the redactor's own `--check`.
* `kit/identity.py` - the R1.2 retirement, and why the premise was false.
* `kit/fixtures.py` - R20, and what it must never become.
* `kit/browser.py` - the two counters and what each is for; `FileLock`'s four
  verdicts.
