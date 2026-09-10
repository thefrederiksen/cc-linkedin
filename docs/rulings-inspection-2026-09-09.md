# Rulings on the independent inspection

The Architect's, 2026-09-09 night, answering the findings in
`docs/inspection-slice-1-urn.md` and `docs/inspection-slice-3-verbs.md`. Rulings
on the two remaining passes are appended when they land.

These amend `docs/phase-2-design.md` and, where they touch it,
`docs/rulings-phase-2.md`. Where they disagree, THIS file wins.

Several findings are in code that is already on `main` (Phase 1). That is in
scope: Phase 2 is what makes them dangerous, and a fix and the thing that stops
it regressing are one unit.

---

## R1. The urn must be READ from the landed page, never inferred from its URL

**Finding:** `search-posts --resolve` proves only that some substring of
`page.url` matches an unanchored regex. A full urn in a query parameter beats
the real one in the path, because the full-urn pattern is searched first; and
the path pattern takes the FIRST `-kind-digits` motif anywhere in the string
rather than the terminal one. Ambiguity has no outcome: the first match becomes
a non-null permalink with a null `resolve_error`, counted as resolved, and no
caller can tell it from a good one.

**Ruling. Stop parsing the URL for identity. Read the post's own identity off
the page it landed on.** The landed post page states what post it is - in the
classic rendering as a `data-urn` on the post card, and in both renderings as
the canonical URL the page publishes for itself. That is a measurement. A
regular expression agreeing with a string it was pointed at is not.

Specifically:

1. After navigating, read the identity from the DOM. Prefer, in order: the post
   card's own `data-urn`; the page's canonical link or `og:url`; the post
   control menu's own "Copy link to post" value. **Survey which of these the
   landed page actually carries before writing the code** - Phase 2 learned that
   the content-search page carries none of them, and that is exactly why we are
   here.
2. **Cross-check, and require agreement.** If the URL path also yields a
   candidate, it must agree with what the page said. Disagreement is a FAIL for
   that row - never a preference for one of them.
3. **Exactly one candidate, or it is not resolved.** More than one distinct
   candidate anywhere is ambiguity, and ambiguity is `permalink: null` with a
   `resolve_error` naming both. First-match is banned.
4. Anchor the patterns and validate the host and path type. A final URL on
   another host, or on a `/company/` or `/school/` path, resolves to nothing.
5. `--resolve` uses `Browser.read`, not `Browser.goto`, so the signed-in
   assertion runs on it like everything else (see R3).

## R2. A permalink handed to a mutating verb must name the post it acts on

**Finding, which the inspector followed downstream without being asked:**
`kit/comments.py` `urn_of` is also an unanchored substring search, and
`Post.load()` falls back from the card for the requested urn to
`card_any` - **the first arbitrary post card on the page** - when the exact one
is not found. So a wrong-but-well-formed permalink reaches `comment`, `react`
and `delete-post`. The acceptance row cannot catch it: it asserts only that
`read-post` returns a non-empty author, and never compares that author to the
search row the permalink came from.

**Ruling. The fallback is the defect, not the parser.**

1. `urn_of` is anchored and requires exactly one match in the string it is
   given. Two different urns in one input is a FAIL.
2. **`Post.load()` may use `card_any` ONLY when it can prove the page holds
   exactly one post card AND the page's own stated identity matches the urn
   asked for.** Otherwise it fails, naming the urn it wanted. Today's fallback
   is silent and unconditional, and on a permalink page it is usually right,
   which is precisely why nobody noticed.
3. The `--expect` phrase guard stays, and stays optional, but it is not the
   answer to this: a phrase is not an identity, and `delete-comment` and
   `unreact` do not even accept it.
4. P2-6c is rewritten to compare the resolved post's AUTHOR AND TEXT with the
   search row it came from. Asserting a non-empty author proves the page loaded,
   which was never in doubt.

This is the highest-consequence item in the whole phase. Acting on a stranger's
post is not a degraded result, it is a different act.

## R3. The lock is released on every path, and a lock we cannot read is broken, not held

**Finding (CRITICAL):** the lock is taken before several fallible entry
operations and only the CDP-connect failure releases it, so a failure in
`sync_playwright().start()`, `contexts[0]`, the CDP session, or the
`createTarget` timeout leaves `__enter__` never returning and the lock file
behind - with no `__exit__` to run, because the `with` statement never began. On
the way out, `_pw.stop()` raising skips the release on the very next line. And a
half-written lock file parses as `{}`, has no pid, is never classified as dead,
and so is never reclaimed by anything.

A wedged lock stalls every other session on this machine, including the job that
posts the owner's video series each morning. This is the finding most likely to
hurt him in a way he cannot diagnose.

**Ruling:**

1. **Acquire the lock LAST**, after every fallible setup step that can be done
   without it; and wrap the whole of `__enter__` so that ANY exception -
   `BaseException`, so a KeyboardInterrupt counts - releases the lock before it
   propagates.
2. **Release in a `finally` that nothing can skip.** No fallible call may sit
   between the last statement and the release.
3. **Write the lock file ATOMICALLY** - write a temporary file, then rename it -
   so a half-written lock cannot exist. Once it cannot exist, a lock file that
   will not parse is a broken lock and is reclaimed with a log line saying so.
   Do NOT reclaim on a timer instead: a grace period would let a second run
   steal the lock from a healthy holder that was merely slow, which is worse
   than the bug being fixed.
4. `close_file_dialogs` and its `die` must not sit between the release and the
   end of `__exit__`.

## R4. An unreadable table is a failure, and stats must prove which Page it read

Both are the phase's own rule and neither needs argument: a table body that is
empty or unreadable is a FAIL, not a set of zeroes, and `stats` asserts that the
Page it landed on is the Page it was asked for before it reads a number.

Cleared, and worth recording as cleared: **the member-analytics widget cannot
reach a stats number.** The inspector confirmed the header assertion and the
cells come from the same local `table` object, so the 5-versus-48 mix-up the
ruling in `rulings-phase-2.md` was written against is genuinely gone.

## R5. `can_connect` fails rather than guesses, in both directions

A value that means "you can invite this person" must never be produced by a code
path that did not positively see an invite control, and "you cannot" must never
be produced by a path that merely failed to look properly. Where it cannot
decide, the field is null with a reason, and the reason names what it could not
read.

## R6. Numbers: reject the ambiguous, do not normalise it away

**Finding:** `to_int` strips every comma and every plus before deciding what the
number means, so the European `1,2K` becomes `12K` and returns **12000 instead
of 1200** - wrong by a factor of ten, silently. Global plus-stripping turns
`12+3` into `123`.

**Ruling. Stripping separators before parsing is the bug; the fix is a grammar,
not another replace.**

1. A comma is a thousands separator only when followed by exactly three digits,
   and only in a well-formed group. A comma followed by one or two digits is a
   decimal comma; accept it as a decimal point, or FAIL - the Manager decides
   which after measuring what LinkedIn actually renders in a European locale,
   and writes down what it saw. **What it must not do is silently pick one.**
2. A plus is stripped only when TRAILING. A plus anywhere else means the string
   is not a number and it fails.
3. Every ambiguous form fails loudly. "3 followers" is not the shape this has to
   get right; a Page with 1,2K followers in a European locale is.

## What does NOT change

`docs/phase-2-design.md` section 0 stands and is reinforced by every finding
above: a read that comes back empty is a failure, never a result, and every
assertion is a check for something PRESENT. Nothing here relaxes it.

---

## Rulings on the self-test pass

The self-test is the instrument every other claim in this phase is measured
with. An instrument that cannot read low is not a lenient instrument, it is a
broken one, and every "three clean runs" in this repository is worth exactly
what it is worth.

## R7. Delete `EXPECTED_VIEWS`. A test may not be its own oracle

**Finding:** the expected view count is a hand-set constant that P2-9 compares
the view counter against. Retuning it makes a view-count failure pass, and
nothing executable derives the number independently. The Phase 2 fix Manager
flagged this same constant unprompted as "the one constant in the suite a tired
Manager can quietly retune until a run goes green" - and it was right.

**Ruling. Remove the constant entirely.** Every operation that costs a view
registers itself as it is invoked, and P2-9 compares the pacing file's delta
against that registry. There is then no number to retune: a disagreement means
either the pacing is wrong or the registry is, and both deserve a red run.

Adjusting a constant until the suite agrees with the code is not a fix and must
never read as one. If the registry and the counter disagree, the run fails and
somebody finds out why.

P2-9 also gains the stray-tab assertion the design asked for and it never had.

## R8. An empty expectation is a FAIL, not a tautology

**Finding:** `headline=` is accepted as a supplied key, making the headline
comparison compare nothing to nothing and pass.

**Ruling:** a supplied key with an empty value fails the run, naming the key.
The whole point of the human-oracle rows is that a person looked at the screen
and wrote down what it said; an empty value means they did not, and the row must
say so rather than quietly agreeing with itself. Unknown keys already fail;
empty ones now fail the same way.

## R9. Nothing is skipped, and the run reconciles what it ran

**Finding:** a missing `--page` or `--page-name` silently skips the entire Page
publish-and-delete block, and no inventory is reconciled at the end.

**Ruling:** this is the skip-counted-as-a-pass that `phase-2-design.md` section
8 already forbade, so it is not a new rule, it is the existing one being
enforced. A missing fixture FAILS. And the run declares the rows it intends to
execute up front and reconciles that list against the rows that actually
reported: a row that never ran is a failed run, not an absent line. A count of
passes means nothing without the denominator it came from.

## R10. A row must assert something the verb does not already enforce

**Finding:** P2-7 repeats conditions `notifications` itself checks before
returning, so it can only go red if the verb crashes; it cannot tell a correct
notification from a wrong one.

**Ruling:** a row that re-checks the verb's own preconditions is not a test of
the verb, it is a test that Python still works. P2-7 asserts correspondence with
the page - a notification whose actor and target are checked against what is
actually on screen - or it is honestly labelled a smoke test and the phase stops
claiming `notifications` is proven.

Either is acceptable. Claiming the first while doing the second is not.

## R11. Vacuous truth is banned

**Finding:** P2-8's per-post assertion passes when zero posts were read, because
`all()` over an empty sequence is true. The same shape appears wherever the
suite checks "every row has X".

**Ruling:** every "all rows satisfy X" assertion is paired with an assertion
that there was at least one row, in the same check. This is the phase's
zero-rows rule applied to the test suite instead of to the verbs, and it is the
same defect: a condition that holds because nothing was examined.

## R12. Profile B's required shape is enforced

The design specifies a 1st- or 2nd-degree profile for the row that proves
`read-profile` works on somebody other than its owner. The row currently accepts
`3rd` and `3rd+` as well. Enforce what the design says, or amend the design
deliberately - not by accepting whatever turns up.

---

## Rulings on the claims-and-safety pass

## R13. The leak is fixed tonight, and the repository is treated as what it is

**Finding (HIGH, PROVED):** `docs/phase-2-fixes.md` states that no third party's
name, profile URL or headline appears in the code or the docs. That statement is
false in the same file that makes it: profile D's distinctive job-search
headline and connection count are written out in prose, outside the redactor
that the claim was reasoning about. Three exact `lnkd.in` short links are
handwritten into the `kit/search.py` docstring, and following one recovers the
post and its author. The survey dumps additionally carry organization slugs and
numeric ids, a job id, article paths, event urns and a precise postal-code map
URL.

The redactor only ever knew three things - `/in/` slugs, `ACoA` member ids, and
a fixed list of query parameters. Everything else was never covered, so
"redacted" was true of the three forms it knew and false of the artefact as a
whole.

**Ruling:**

1. **Redact all of it, tonight.** Third-party identifiers come out of
   `docs/phase-2-fixes.md`, out of the `kit/search.py` docstring, and out of the
   survey dumps. A measured fact can be stated without its subject: "a
   third-party profile whose top card states no employer" carries the whole
   engineering point, and the headline carries none of it.
2. **Teach the redactor what it did not know**: company paths and numeric ids,
   post/activity/ugcPost/share urns, event and job ids, article slugs, short
   links including ones nested inside a `url=` parameter, and map or address
   URLs. The dumps cannot be regenerated tonight - that needs a live page and
   the view cap is spent - so redact the committed ones in place with a script,
   and commit the script.
3. **The owner's own identifiers stay**, except the postal-code map URL, which
   is his home-adjacent location data and does not belong in a public
   repository. The Page id and his own profile are already public and already in
   the docs by intent.
4. **`--out` stops being described as "the safe public dump"** until the
   redactor covers the forms above. A name that overstates what a thing does is
   how the next person stops checking.

**What this ruling CANNOT do, stated plainly:** the branch is already pushed to
a public repository, so redacting now removes the data from the tip, not from
history. See R14.

## R14. How Phase 2 lands, given the leak is already pushed - FOR THE OWNER

Redaction fixes the tree. It does not fix the eight commits already on
`origin/phase-2-reading`, which anyone can read.

**The Architect's recommendation, NOT executed tonight:** land Phase 2 as a
SQUASH merge, so `main` carries one commit containing only the redacted tree and
never the intermediate ones, then delete the branch (already automatic on this
repository). The leaked commits then become unreachable.

**Why it was not done tonight:** a history rewrite and a force-push are
destructive and outward-facing on the owner's PUBLIC repository, and he is
asleep. Redaction is safe and strictly improves things, so it happens now; the
irreversible half waits for him. Squash-merging is a choice about how his
repository's history reads and it is his to make.

**Honest limit:** unreachable objects can still be fetched by anyone who knows
the commit hash until GitHub garbage-collects them, and that is not something
this repository can guarantee from here. If the exposure matters, the complete
remedy involves GitHub support, and the three `lnkd.in` links are the items most
worth caring about because they resolve to real people's posts.

## R15. `pace.json` must not claim a guarantee it cannot keep

**Finding:** `Pace` says its file makes caps hold "across sessions and agents".
It cannot: `before()` loads and checks, the action happens, and `after()`
separately reloads and increments, with no lock and no atomic update. Two
writers at 59 both pass a cap of 60, both act, and both save 60 - so 61 actions
happened and the file says 60. Different fields overwrite each other the same
way, so the spacing timestamps can be lost too. The browser lock is keyed by CDP
port and only incidentally serialises some of this.

**Ruling:** make the read-modify-write atomic and mutually excluded - a lock
file beside `pace.json`, taken for the whole check-act-account sequence where
the action is ours to bracket, and an atomic write as in R3. Where a true
reservation is not practical, **the docstring must stop promising one**. An
overstated guarantee in the one file that exists to keep the owner's account
safe is worse than an honest limitation, because it is the sentence someone will
rely on instead of checking.

## R16. A read-only verb may not overwrite the machine's state

**Finding:** `search-posts` clears and replaces the SYSTEM CLIPBOARD to read
each card's short link, and grants clipboard permission to the default browser
context without resetting it. A command documented as read-only silently
destroys whatever the owner had copied, and leaves a permission behind.

**Ruling:** save and restore the clipboard around the read, and revoke the
permission grant afterwards - or stop using the clipboard at all, which is
better, because R1 now requires reading the post's identity off the landed page
rather than from a copied link. If the clipboard route survives at all, its
side effect is documented in the verb's help text. "Read-only" is a promise
about the user's world, not only about LinkedIn.

---

## R3.3 AMENDED, 2026-09-10 - a failure to read is not a reading of failure

R3.3 as written said "a lock file that will not parse is a broken lock and is
reclaimed". The live-proving Manager stopped before spending a single view to
report that the implementation of it is **fail-open on Windows**, and it is
right, and the fault is in the ruling.

`_holder()` treats "the file could not be OPENED" identically to "the file was
read and its record does not parse". On Windows both a transient `Errno 13`
while a delete is pending and an `Errno 2` for a lock released a moment ago are
ordinary. So a run logs `lock is BROKEN ... taking it over` and discards a
LIVE holder's lock. R15's own forty-thread test loses an increment on almost
every run, and `PermissionError` escapes `__enter__`, which catches only
`FileExistsError`. It reproduces at HEAD, so it is not a consequence of tonight's
work.

**Where my reasoning went wrong.** The atomic write-then-rename earns the right
to trust CONTENT: a file that exists has complete bytes, so bytes that do not
parse mean a genuinely broken record. It earns NOTHING about a failure to open.
I carried the conclusion across from one to the other in a single sentence and
did not notice.

**Amended:**

1. **"Broken" means the file was opened AND read AND its content is not a valid
   record.** That, and only that, is reclaimable.
2. **A failure to OPEN is not evidence about the content.** Retry a bounded
   number of times with a short backoff. If it persists, treat the lock as HELD
   and wait. **Fail closed.**
3. Acquisition handles every `OSError`, not only `FileExistsError`.
4. The log line names which of the two cases it saw. Today it announces a
   healthy lock as broken, which is how somebody would come to distrust the
   correct message later.

**Why this outranks every verb in the phase**, and why it is fixed before any
run: the lock is what stops two Playwright clients driving one Chrome, and the
machine it can wedge is the one running the fleet and posting the owner's video
series each morning. A safety mechanism that can steal from a healthy holder is
worse than the collisions it was built to prevent.

**The pattern, named because it is now three in one night.** A redactor that
knew eight identifier forms and lost to the ninth. A leak test that could not
catch the leak it had itself reintroduced. And a lock that reads "I could not
look" as "there is nothing there". Each one converts an absence of evidence into
evidence of absence, and each one was invisible until something tried to make it
fail. This one was mine, written into a ruling while I was busy naming the same
defect in other people's code.

---

## R20. Fixtures live on the machine, not in the repository and not in nobody's hands

**The hole, and it is mine.** Phase 2's design says the fixture profiles must
never be committed, because this repository is public and the people are real.
That part is right and it stands. What it never said is where they should live
instead - so they lived in a Manager's head, and when that Manager was reaped
the values went with it. The third seat in a row then had to pay the discovery
cost again, out of the daily view cap, to find a profile of the same shape.

A rule that forbids the only recorded place without naming another one is not a
privacy rule, it is an amnesia generator.

**Ruling:**

1. Fixtures live in `%LOCALAPPDATA%/cc-linkedin/selftest-fixtures.json`, beside
   `pace.json`, on the machine and outside git. They are never committed and the
   path is never inside the repository, so there is nothing to gitignore wrongly
   and nothing to leak.
2. **The repository documents the SHAPE, the machine holds the VALUES.** The
   shape is the part that carries the engineering meaning and it belongs in the
   design document: "a profile whose invitation sits behind the More menu AND
   whose top card states no employer" is what the row is for. Who that is
   carries none of it.
3. The selftest reads the file when the flags are not passed, and **still fails
   rather than skips** when it has neither. R9 is untouched: nothing is skipped,
   ever.
4. Whoever discovers a fixture writes it there, with what was measured about it,
   so the discovery cost is paid once by the fleet rather than once per seat.

**A datum recorded for the next seat, deliberately without the URL:** the
profile the Architect used by hand on 2026-09-09 was a genuine D-shape and is
now PENDING, because a real connection request was sent to it at the owner's
instruction. It is therefore no longer usable for `can_connect: true`, and it is
now the only known fixture for a state nothing else reaches - a pending
invitation, where `can_connect` must be false with a reason and with no invite
URL. The URL is in the local fixtures file where it belongs.
